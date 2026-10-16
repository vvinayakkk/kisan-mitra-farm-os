"""Durable suggestions are owner-scoped and approval has exactly one saved effect."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from skyview.assistant import companion_plans as plans
from skyview.data.v3 import db


def insert_draft(owner, area="records"):
    identifier = str(uuid.uuid4())
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.companion_proposals(id,farmer_id,area,dedupe_key,title,summary,steps) VALUES(:id,:owner,:area,:key,'Review my records','Saved field context',CAST(:steps AS jsonb))"
            ),
            {
                "id": identifier,
                "owner": owner,
                "area": area,
                "key": "test:" + identifier,
                "steps": json.dumps(
                    [{"title": "Record a field observation", "done": False}]
                ),
            },
        )
    return identifier


def test_edit_approve_replay_and_other_owner(companion):
    client, headers, owners = companion
    older_identifier = insert_draft(owners[0])
    identifier = insert_draft(owners[0])
    assert older_identifier not in [
        row["id"]
        for row in client.get("/api/companion", headers=headers[0]).json()["prepared"]
    ]
    assert identifier in [
        row["id"]
        for row in client.get("/api/companion", headers=headers[0]).json()["prepared"]
    ]
    assert identifier not in [
        row["id"]
        for row in client.get("/api/companion", headers=headers[1]).json()["prepared"]
    ]
    path = f"/api/companion/proposals/{identifier}/review"
    payload = {"row_version": 1, "action": "approve"}
    assert client.post(path, headers=headers[1], json=payload).status_code == 404
    edited = client.post(
        path,
        headers=headers[0],
        json={
            "row_version": 1,
            "action": "edit",
            "title": "My field plan",
            "steps": ["Inspect the north field"],
        },
    )
    assert edited.status_code == 200
    assert client.post(path, headers=headers[0], json=payload).status_code == 409
    payload["row_version"] = 2
    first = client.post(path, headers=headers[0], json=payload)
    assert first.status_code == 200
    second = client.post(path, headers=headers[0], json=payload)
    assert first.json()["mission_id"] == second.json()["mission_id"]
    with db.connection(owners[0]) as conn:
        mission = (
            conn.execute(
                text("SELECT title,steps FROM sv3.farm_missions WHERE id=:id"),
                {"id": first.json()["mission_id"]},
            )
            .mappings()
            .one()
        )
        assert (
            mission["title"] == "My field plan"
            and mission["steps"][0]["title"] == "Inspect the north field"
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.mission_receipts WHERE mission_id=:id"),
                {"id": first.json()["mission_id"]},
            ).scalar()
            == 1
        )
    summary = client.get("/api/companion", headers=headers[0]).json()
    saved = next(row for row in summary["prepared"] if row["id"] == identifier)
    assert (
        saved["status"] == "approved"
        and saved["steps"][0]["title"] == "Inspect the north field"
    )
    assert saved["summary"] == "Saved field context"
    receipts = [
        row for row in summary["activity"] if row.get("proposal_id") == identifier
    ]
    assert len(receipts) == 1
    assert receipts[0]["mission_id"] == first.json()["mission_id"]
    assert "tab=missions" in receipts[0]["href"]
    assert not any(
        row.get("proposal_id") == identifier
        for row in client.get("/api/companion", headers=headers[1]).json()["activity"]
    )
    visible = client.get(
        "/api/companion/proposals?area=records", headers=headers[1]
    ).json()
    assert identifier not in [row["id"] for row in visible["proposals"]]


def test_dismiss_and_validation(companion):
    client, headers, owners = companion
    identifier = insert_draft(owners[0])
    path = f"/api/companion/proposals/{identifier}/review"
    assert (
        client.post(
            path,
            headers=headers[0],
            json={"row_version": 1, "action": "edit", "steps": [" "]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, headers=headers[0], json={"row_version": 1, "action": "dismiss"}
        ).json()["proposal"]["status"]
        == "dismissed"
    )
    assert (
        client.post(
            path, headers=headers[0], json={"row_version": 2, "action": "approve"}
        ).status_code
        == 409
    )
    assert (
        client.post("/api/companion/prepare", json={"area": "records"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/companion/prepare", headers=headers[0], json={"area": "arbitrary"}
        ).status_code
        == 422
    )


def test_prepare_coalesces_and_complete_checks_lease(companion):
    client, headers, owners = companion
    first = client.post(
        "/api/companion/prepare", headers=headers[0], json={"area": "records"}
    ).json()
    second = client.post(
        "/api/companion/prepare", headers=headers[0], json={"area": "records"}
    ).json()
    assert first["id"] == second["id"]
    token = str(uuid.uuid4())
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.companion_jobs SET state='running',lease_token=:token,lease_until=now()+interval '2 minutes' WHERE id=:id"
            ),
            {"id": first["id"], "token": token},
        )
    job = {
        "id": first["id"],
        "farmer_id": owners[0],
        "lease_token": token,
        "area": "records",
    }
    result = plans.draft("records", plans.snapshot(owners[0]))
    assert not plans.complete({**job, "lease_token": str(uuid.uuid4())}, result, None)
    assert plans.complete(job, result, None)
    assert not plans.complete(job, result, None)
    data = client.get(
        "/api/companion/proposals?area=records", headers=headers[0]
    ).json()
    assert data["job"]["state"] == "done" and data["proposals"]


def test_context_shapes_and_all_feature_drafts(companion):
    _, _, owners = companion
    context = plans.snapshot(owners[0])
    assert context["state"] and "preferred_language" in context
    assert "contact_phone" not in context
    for area in plans.AREAS:
        result = plans.draft(area, context)
        assert result["title"] and result["summary"] and 1 <= len(result["steps"]) <= 8
        assert all(step["done"] is False for step in result["steps"])


def test_retry_remains_bounded_and_stale_worker_cannot_finish(companion):
    _, _, owners = companion
    identifier = str(uuid.uuid4())
    token = str(uuid.uuid4())
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.companion_jobs SET state='failed' WHERE area='today' AND state IN ('queued','running')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO sv3.companion_jobs(id,farmer_id,area,state,attempts,lease_token,lease_until) VALUES(:id,:owner,'today','running',3,:token,:expired)"
            ),
            {
                "id": identifier,
                "owner": owners[0],
                "token": token,
                "expired": datetime.now(UTC) - timedelta(seconds=1),
            },
        )
    job = {
        "id": identifier,
        "farmer_id": owners[0],
        "area": "today",
        "lease_token": token,
    }
    assert not plans.complete(
        job, plans.draft("today", plans.snapshot(owners[0])), None
    )
    plans.fail(job)
    with db.connection(owners[0]) as conn:
        assert (
            conn.execute(
                text("SELECT state FROM sv3.companion_jobs WHERE id=:id"),
                {"id": identifier},
            ).scalar()
            == "failed"
        )


def test_research_refresh_retains_changed_sources_without_timestamp_duplicates(
    companion,
):
    _, _, owners = companion
    owner = owners[0]
    title = "Research refresh fixture " + uuid.uuid4().hex
    result = {
        "title": title,
        "summary": "Check dated official conditions",
        "steps": [{"title": "Check conditions", "done": False}],
        "evidence": [],
        "research_query": "official conditions",
        "requested_language": "hi",
        "language": "en",
        "translation_status": "unavailable",
    }
    first = {
        "available": True,
        "answer": "Conditions one",
        "sources": [{"url": "https://india.gov.in/one"}],
        "retrieved_at": "2026-10-15T00:00:00Z",
    }
    second = {
        **first,
        "answer": "Conditions two",
        "sources": [{"url": "https://india.gov.in/two"}],
    }
    for research in [first, second, {**second, "retrieved_at": "2026-10-15T00:10:00Z"}]:
        identifier, token = str(uuid.uuid4()), str(uuid.uuid4())
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "UPDATE sv3.companion_jobs SET state='failed' WHERE area='schemes' AND state IN ('queued','running')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO sv3.companion_jobs(id,farmer_id,area,state,lease_token,lease_until) VALUES(:id,:owner,'schemes','running',:token,now()+interval '2 minutes')"
                ),
                {"id": identifier, "owner": owner, "token": token},
            )
        assert plans.complete(
            {
                "id": identifier,
                "farmer_id": owner,
                "area": "schemes",
                "lease_token": token,
            },
            result,
            research,
        )
    with db.connection(owner) as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT research FROM sv3.companion_proposals WHERE farmer_id=:owner AND title=:title"
                ),
                {"owner": owner, "title": title},
            )
            .scalars()
            .all()
        )
    assert len(rows) == 2
    assert {row["answer"] for row in rows} == {"Conditions one", "Conditions two"}
    assert all(
        row["preparation"]
        == {
            "requested_language": "hi",
            "language": "en",
            "translation_status": "unavailable",
        }
        for row in rows
    )


def test_research_requested_during_local_preparation_is_not_lost(companion):
    client, headers, owners = companion
    first = client.post(
        "/api/companion/prepare", headers=headers[0], json={"area": "markets"}
    ).json()
    token = str(uuid.uuid4())
    with db.connection(owners[0], write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.companion_jobs SET state='running',lease_token=:token,lease_until=now()+interval '2 minutes' WHERE id=:id"
            ),
            {"token": token, "id": first["id"]},
        )
    upgraded = client.post(
        "/api/companion/prepare",
        headers=headers[0],
        json={"area": "markets", "research": True},
    ).json()
    assert upgraded["id"] == first["id"]
    job = {
        "id": first["id"],
        "farmer_id": owners[0],
        "lease_token": token,
        "area": "markets",
        "research": False,
    }
    assert plans.complete(job, plans.draft("markets", plans.snapshot(owners[0])), None)
    with db.connection(owners[0]) as conn:
        row = (
            conn.execute(
                text(
                    "SELECT state,research,attempts,lease_token FROM sv3.companion_jobs WHERE id=:id"
                ),
                {"id": first["id"]},
            )
            .mappings()
            .one()
        )
        assert row["state"] == "queued" and row["research"] is True
        assert row["attempts"] == 0 and row["lease_token"] is None
