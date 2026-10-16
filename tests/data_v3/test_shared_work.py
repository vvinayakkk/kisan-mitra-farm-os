"""Shared group roles never broaden access to private farmer records."""

import os
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_farm_workflow_routes import router as private_router
from skyview.api.v3_shared_work_routes import router
from skyview.assistant import store
from skyview.data.v3 import db


@pytest.fixture
def accounts(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL integration opt-in required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    sessions = []
    for key in ["DEMO-F0085", "DEMO-F0086", "DEMO-F0087"]:
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        sessions.append(store.create_session())
    app = FastAPI()
    app.include_router(router)
    app.include_router(private_router)
    client = TestClient(app)
    headers = [
        {"Authorization": "Bearer " + s["token"], "X-Assistant-Session": s["id"]}
        for s in sessions
    ]
    return client, headers, sessions


def test_service_records_are_private_versioned_and_never_external_booking(accounts):
    client, (owner, other, _), _ = accounts
    url = "/api/farm-workspace/service-requests"
    assert client.get(url).status_code == 401
    response = client.post(
        url,
        headers=owner,
        json={"title": "Test tractor work", "service_type": "machinery"},
    )
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "planned" and item["quote_inr"] is None
    assert not any(
        r["id"] == item["id"] for r in client.get(url, headers=other).json()["items"]
    )
    patch = {
        k: item[k]
        for k in [
            "title",
            "service_type",
            "supplier",
            "quote_inr",
            "scheduled_on",
            "status",
            "notes",
            "row_version",
        ]
    }
    assert (
        client.patch(url + "/" + item["id"], headers=other, json=patch).status_code
        == 404
    )
    quote = {
        **patch,
        "status": "quote_recorded",
        "supplier": "Farmer-reported test supplier",
        "quote_inr": "1200.25",
    }
    assert (
        client.patch(url + "/" + item["id"], headers=owner, json=quote).json()[
            "row_version"
        ]
        == 2
    )
    assert (
        client.patch(url + "/" + item["id"], headers=owner, json=quote).status_code
        == 409
    )
    assert (
        client.patch(
            url + "/" + item["id"],
            headers=owner,
            json={
                **quote,
                "row_version": 2,
                "status": "farmer_completed",
                "scheduled_on": str(date.today() + timedelta(days=1)),
            },
        ).status_code
        == 422
    )
    assert "No supplier was contacted" in client.get(url, headers=owner).json()["note"]


def test_single_use_invite_reader_role_and_private_scope(accounts):
    client, (owner, reader, other), sessions = accounts
    base = "/api/farm-workspace/groups"
    g = client.post(base, headers=owner, json={"name": "Test household"}).json()
    gid = g["id"]
    task = client.post(
        f"{base}/{gid}/tasks",
        headers=owner,
        json={"title": "Shared seed checklist", "notes": "Visible only to group"},
    ).json()
    assert client.get(f"{base}/{gid}/tasks", headers=other).status_code == 404
    invite = client.post(
        f"{base}/{gid}/invites",
        headers=owner,
        json={"role": "reader", "consent_to_share_group_plans": True},
    ).json()
    assert len(invite["code"]) >= 32
    assert (
        client.post(
            base + "/join",
            headers=reader,
            json={"code": invite["code"], "consent_to_share_display_name": True},
        ).json()["role"]
        == "reader"
    )
    assert (
        client.post(
            base + "/join",
            headers=other,
            json={"code": invite["code"], "consent_to_share_display_name": True},
        ).status_code
        == 422
    )
    assert (
        client.get(f"{base}/{gid}/tasks", headers=reader).json()["items"][0]["id"]
        == task["id"]
    )
    assert (
        client.post(
            f"{base}/{gid}/tasks", headers=reader, json={"title": "Forbidden task"}
        ).status_code
        == 403
    )
    assert client.get(f"{base}/{gid}/invites", headers=reader).status_code == 403
    listing = client.get(f"{base}/{gid}/invites", headers=owner).json()["items"]
    assert not any("token_hash" in r or "code" in r for r in listing)
    # Private records stay behind the original farmer RLS; group access is isolated.
    item = client.post(
        "/api/farm-workspace/ledger",
        headers=owner,
        json={
            "description": "Private household cost",
            "category": "seed",
            "kind": "expense",
            "basis": "actual",
            "amount_inr": 100,
            "occurred_on": str(date.today()),
        },
    ).json()
    assert item["id"] not in [
        r["id"]
        for r in client.get("/api/farm-workspace/ledger", headers=reader).json()[
            "items"
        ]
    ]
    person = store.farmer_id(sessions[1]["id"])
    assert client.delete(f"{base}/{gid}/members/{person}", headers=owner).json()[
        "revoked"
    ]
    assert client.get(f"{base}/{gid}/tasks", headers=reader).status_code == 404


def test_contributor_task_versions_and_revoked_expired_invites(accounts):
    client, (owner, member, other), sessions = accounts
    base = "/api/farm-workspace/groups"
    gid = client.post(base, headers=owner, json={"name": "Test FPO work"}).json()["id"]
    invite = client.post(
        f"{base}/{gid}/invites",
        headers=owner,
        json={"role": "contributor", "consent_to_share_group_plans": True},
    ).json()
    assert (
        client.post(
            base + "/join",
            headers=member,
            json={"code": invite["code"], "consent_to_share_display_name": True},
        ).status_code
        == 200
    )
    task = client.post(
        f"{base}/{gid}/tasks",
        headers=member,
        json={"title": "Coordinate machinery", "notes": "Test only"},
    ).json()
    patch = {
        k: task[k] for k in ["title", "notes", "due_on", "completed", "row_version"]
    }
    patch["completed"] = True
    assert client.patch(
        f"{base}/{gid}/tasks/{task['id']}", headers=member, json=patch
    ).json()["completed"]
    assert (
        client.patch(
            f"{base}/{gid}/tasks/{task['id']}", headers=member, json=patch
        ).status_code
        == 409
    )
    revoked = client.post(
        f"{base}/{gid}/invites",
        headers=owner,
        json={"role": "reader", "consent_to_share_group_plans": True},
    ).json()
    assert (
        client.delete(
            f"{base}/{gid}/invites/{revoked['id']}", headers=owner
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + "/join",
            headers=other,
            json={"code": revoked["code"], "consent_to_share_display_name": True},
        ).status_code
        == 422
    )
    expired = client.post(
        f"{base}/{gid}/invites",
        headers=owner,
        json={"role": "reader", "consent_to_share_group_plans": True},
    ).json()
    with db.connection(store.farmer_id(sessions[0]["id"]), write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.group_invites SET expires_at=now()-interval '1 second' WHERE id=:id"
            ),
            {"id": expired["id"]},
        )
    assert (
        client.post(
            base + "/join",
            headers=other,
            json={"code": expired["code"], "consent_to_share_display_name": True},
        ).status_code
        == 422
    )
    db.dispose()
    assert any(r["id"] == gid for r in client.get(base, headers=member).json()["items"])


@pytest.mark.asyncio
async def test_service_and_group_tools_require_review_and_replay_atomically(accounts):
    import uuid

    from skyview.assistant.tools import TOOLS, Executor

    client, (owner, _, _), sessions = accounts
    executor = Executor(sessions[0]["id"], "WS01", None)
    for name in ["record_service", "create_farm_group", "create_shared_task"]:
        assert TOOLS[name].approval
    created = {}
    for name, args in [
        (
            "record_service",
            {"title": "Tool planned machinery", "service_type": "machinery"},
        ),
        ("create_farm_group", {"name": "Tool isolated shared checklist"}),
    ]:
        call_id = uuid.uuid4().hex
        first = await executor.run(name, args, call_id)
        db.dispose()
        assert (
            await Executor(sessions[0]["id"], "WS01", None).run(name, args, call_id)
            == first
        )
        created[name] = first["saved"]
    args = {
        "group_id": created["create_farm_group"]["id"],
        "title": "Shared tool checklist",
    }
    call_id = uuid.uuid4().hex
    task = await executor.run("create_shared_task", args, call_id)
    assert (
        await Executor(sessions[0]["id"], "WS01", None).run(
            "create_shared_task", args, call_id
        )
        == task
    )
    rows = client.get(
        "/api/farm-workspace/groups/" + args["group_id"] + "/tasks", headers=owner
    ).json()["items"]
    assert len(rows) == 1 and rows[0]["completed"] is False
