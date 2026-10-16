"""Opt-in follow-ups are bounded, owned and deduplicated, never fake external sends."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_companion_routes import router
from skyview.assistant import store
from skyview.data.v3 import db, worker


@pytest.fixture
def companion(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL integration database")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    sessions = []
    for key in ("DEMO-F0087", "DEMO-F0088"):
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        sessions.append(store.create_session())
    app = FastAPI()
    app.include_router(router)
    headers = [
        {"Authorization": "Bearer " + s["token"], "X-Assistant-Session": s["id"]}
        for s in sessions
    ]
    owners = [store.farmer_id(s["id"]) for s in sessions]
    with TestClient(app) as client:
        for owner in owners:
            with db.connection(owner, write=True) as conn:
                conn.execute(
                    text(
                        "INSERT INTO sv3.companion_preferences(farmer_id) VALUES(:id) ON CONFLICT DO NOTHING"
                    ),
                    {"id": owner},
                )
                conn.execute(
                    text(
                        "UPDATE sv3.companion_preferences SET enabled=false WHERE farmer_id=:id"
                    ),
                    {"id": owner},
                )
        yield client, headers, owners
    for owner in owners:
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "DELETE FROM sv3.notifications WHERE payload->>'source'='companion'"
                )
            )
            conn.execute(
                text(
                    "DELETE FROM sv3.tasks WHERE execution_key LIKE 'companion-test:%'"
                )
            )
            conn.execute(
                text(
                    "UPDATE sv3.companion_preferences SET enabled=false WHERE farmer_id=:id"
                ),
                {"id": owner},
            )


def test_requires_owner_and_preferences_conflict(companion):
    client, headers, _ = companion
    assert client.get("/api/companion").status_code == 401
    initial = client.get("/api/companion", headers=headers[0]).json()
    assert (
        initial["status"] == "paused"
        and initial["channels"]["whatsapp"]["connected"] is False
    )
    body = {
        key: initial["settings"][key]
        for key in (
            "name",
            "enabled",
            "frequency_hours",
            "quiet_start",
            "quiet_end",
            "timezone",
            "row_version",
        )
    }
    body.update(name="My Saathi", enabled=True, quiet_start=0, quiet_end=0)
    assert (
        client.patch(
            "/api/companion/preferences", headers=headers[0], json=body
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/companion/preferences", headers=headers[0], json=body
        ).status_code
        == 409
    )
    assert (
        client.get("/api/companion", headers=headers[1]).json()["name"] != "My Saathi"
    )
    body["timezone"] = "Unknown/Fake"
    assert (
        client.patch(
            "/api/companion/preferences", headers=headers[0], json=body
        ).status_code
        == 422
    )


def test_due_followup_is_real_deduplicated_and_private(companion):
    client, headers, owners = companion
    identifier = str(uuid.uuid4())
    now = datetime.now(UTC)
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.tasks(id,farmer_id,title,due_at,status,execution_key) VALUES(:id,:owner,'Inspect irrigation today',:due,'open',:key)"
            ),
            {
                "id": identifier,
                "owner": owners[0],
                "due": now + timedelta(hours=2),
                "key": "companion-test:" + identifier,
            },
        )
    # Paused is a real boundary: having a due task does not imply opt-in.
    worker._companion_sweep()
    assert not client.get("/api/companion", headers=headers[0]).json()["activity"]
    initial = client.get("/api/companion", headers=headers[0]).json()["settings"]
    body = {
        key: initial[key]
        for key in (
            "name",
            "enabled",
            "frequency_hours",
            "quiet_start",
            "quiet_end",
            "timezone",
            "row_version",
        )
    }
    body.update(enabled=True, quiet_start=0, quiet_end=0)
    client.patch(
        "/api/companion/preferences", headers=headers[0], json=body
    ).raise_for_status()
    worker._companion_sweep()
    data = client.get("/api/companion", headers=headers[0]).json()
    matching = [
        r for r in data["activity"] if r["evidence"].get("task_id") == identifier
    ]
    assert len(matching) == 1 and matching[0]["detail"] == "Inspect irrigation today"
    assert data["status"] == "watching"
    assert not client.get("/api/companion", headers=headers[1]).json()["activity"]
    receipt = matching[0]["id"]
    assert (
        client.post(
            "/api/companion/activity/" + receipt + "/read", headers=headers[1]
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/companion/activity/" + receipt + "/read", headers=headers[0]
        ).status_code
        == 200
    )
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.companion_preferences SET next_check_at=now() WHERE farmer_id=:id"
            ),
            {"id": owners[0]},
        )
    worker._companion_sweep()
    assert (
        len(
            [
                r
                for r in client.get("/api/companion", headers=headers[0]).json()[
                    "activity"
                ]
                if r["evidence"].get("task_id") == identifier
            ]
        )
        == 1
    )
    with db.connection(owners[0]) as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM sv3.notifications WHERE payload->>'source'='companion' AND channel<>'in_app'"
                )
            ).scalar()
            == 0
        )


def test_quiet_hours_defer_without_fabricating_activity(companion):
    client, headers, owners = companion
    hour = datetime.now(ZoneInfo("Asia/Kolkata")).hour
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.companion_preferences SET enabled=true,quiet_start=:start,quiet_end=:end,next_check_at=now() WHERE farmer_id=:id"
            ),
            {"start": hour, "end": (hour + 1) % 24, "id": owners[0]},
        )
    worker._companion_sweep()
    data = client.get("/api/companion", headers=headers[0]).json()
    assert data["status"] == "quiet_hours" and not data["activity"]
