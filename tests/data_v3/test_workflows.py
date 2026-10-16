"""Owned persistence, accounting bases, conflict recovery and truthful missions."""

import os
import uuid
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_farm_workflow_routes import router
from skyview.assistant import store
from skyview.data.v3 import db


@pytest.fixture
def workspace(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL integration opt-in required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0081")
    session = store.create_session()
    app = FastAPI()
    app.include_router(router)
    headers = {
        "Authorization": "Bearer " + session["token"],
        "X-Assistant-Session": session["id"],
    }
    return TestClient(app), headers, session


def test_ledger_bases_versions_and_owner(workspace, monkeypatch):
    client, headers, _session = workspace
    base = "/api/farm-workspace"
    assert client.get(base + "/ledger").status_code == 401
    before = client.get(base + "/ledger", headers=headers).json()["summary"]
    entry = {
        "description": "Test actual expense",
        "category": "seed",
        "kind": "expense",
        "basis": "actual",
        "amount_inr": 100.25,
        "occurred_on": str(date.today()),
    }
    response = client.post(base + "/ledger", headers=headers, json=entry)
    assert response.status_code == 200, response.text
    record = response.json()
    updated = {**entry, "amount_inr": 105, "row_version": record["row_version"]}
    assert (
        client.patch(
            base + "/ledger/" + record["id"], headers=headers, json=updated
        ).json()["row_version"]
        == 2
    )
    assert (
        client.patch(
            base + "/ledger/" + record["id"], headers=headers, json=updated
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/ledger", headers=headers, json={**entry, "basis": "receivable"}
        ).status_code
        == 422
    )
    receivable = client.post(
        base + "/ledger",
        headers=headers,
        json={**entry, "kind": "income", "basis": "receivable", "amount_inr": 400},
    ).json()
    estimated = client.post(
        base + "/ledger",
        headers=headers,
        json={**entry, "basis": "estimated", "amount_inr": 500},
    ).json()
    totals = client.get(base + "/ledger", headers=headers).json()["summary"]
    assert totals["actual_expense"] == before["actual_expense"] + 105
    assert totals["receivable"] == before["receivable"] + 400
    assert totals["recorded_balance"] == before["recorded_balance"] - 105
    assert totals["estimated_expense"] == before["estimated_expense"] + 500
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0082")
    other = store.create_session()
    other_headers = {
        "Authorization": "Bearer " + other["token"],
        "X-Assistant-Session": other["id"],
    }
    assert record["id"] not in [
        r["id"]
        for r in client.get(base + "/ledger", headers=other_headers).json()["items"]
    ]
    assert (
        client.patch(
            base + "/ledger/" + record["id"],
            headers=other_headers,
            json={**updated, "row_version": 2},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            base + "/ledger/" + record["id"] + "?row_version=1", headers=headers
        ).status_code
        == 409
    )
    for item, version in ((record, 2), (receivable, 1), (estimated, 1)):
        assert (
            client.delete(
                base + "/ledger/" + item["id"] + f"?row_version={version}",
                headers=headers,
            ).status_code
            == 200
        )
    db.dispose()
    assert all(
        item["id"] != record["id"]
        for item in client.get(base + "/ledger", headers=headers).json()["items"]
    )


def test_mission_transitions_and_persistent_receipts(workspace):
    client, headers, _ = workspace
    base = "/api/farm-workspace/missions"
    content = {
        "title": "Scout field before irrigation",
        "objective": "Observe leaf changes",
        "steps": [{"title": "Walk field", "done": False}],
    }
    result = client.post(base, headers=headers, json=content)
    assert result.status_code == 200, result.text
    record = result.json()
    path = base + "/" + record["id"]
    assert (
        client.patch(
            path,
            headers=headers,
            json={**content, "status": "completed", "row_version": 1},
        ).status_code
        == 409
    )
    for status, version in (("active", 1), ("paused", 2), ("active", 3)):
        result = client.patch(
            path,
            headers=headers,
            json={**content, "status": status, "row_version": version},
        )
        assert result.status_code == 200, result.text
    assert (
        client.patch(
            path,
            headers=headers,
            json={**content, "status": "completed", "row_version": 4},
        ).status_code
        == 422
    )
    completed = {
        **content,
        "steps": [{"title": "Walk field", "done": True}],
        "status": "completed",
        "row_version": 4,
    }
    assert client.patch(path, headers=headers, json=completed).status_code == 200
    db.dispose()
    receipts = client.get(path + "/receipts", headers=headers).json()["items"]
    assert len(receipts) == 5
    assert "self-reported" in receipts[0]["detail"]
    assert (
        client.patch(
            path,
            headers=headers,
            json={**completed, "status": "active", "row_version": 5},
        ).status_code
        == 409
    )


def test_crop_cases_notes_and_future_observation(workspace):
    client, headers, _ = workspace
    base = "/api/farm-workspace/cases"
    result = client.post(
        base,
        headers=headers,
        json={"title": "Leaf colour changed", "note": "Farmer observed yellow patches"},
    )
    assert result.status_code == 200, result.text
    case = result.json()
    listing = client.get(base, headers=headers).json()["items"]
    row = next(item for item in listing if item["id"] == case["id"])
    assert (
        row["assessment"] is None
        and row["model_version"] is None
        and not row["has_image"]
    )
    path = base + "/" + case["id"]
    assert (
        client.post(
            path + "/notes",
            headers=headers,
            json={
                "note": "Retake photo tomorrow",
                "observed_on": str(date.today() + timedelta(days=1)),
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/notes",
            headers=headers,
            json={"note": "Spread has slowed", "observed_on": str(date.today())},
        ).status_code
        == 200
    )
    assert len(client.get(path + "/notes", headers=headers).json()["items"]) == 2
    assert (
        client.patch(
            path,
            headers=headers,
            json={
                "title": "Leaf change follow-up",
                "status": "monitoring",
                "row_version": 1,
            },
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path,
            headers=headers,
            json={
                "title": "Leaf change follow-up",
                "status": "resolved",
                "row_version": 2,
            },
        ).status_code
        == 200
    )


def test_memory_correction_and_forget_scope(workspace):
    client, headers, session = workspace
    owner = store.farmer_id(session["id"])
    key, identifier = "test_fact:" + uuid.uuid4().hex, str(uuid.uuid4())
    with db.connection(owner, write=True) as connection:
        connection.execute(
            text(
                "INSERT INTO sv3.memories(id,farmer_id,fact_key,value,confidence,valid_from,search_text) VALUES(:id,:owner,:key,'{\"content\":\"old fact\"}',1,now(),'old fact')"
            ),
            {"id": identifier, "owner": owner, "key": key},
        )
    base = "/api/farm-workspace/memories"
    result = client.patch(
        base + "/" + identifier,
        headers=headers,
        json={"value": "Farmer corrected field size"},
    )
    assert result.status_code == 200, result.text
    corrected = result.json()
    assert corrected["id"] != identifier
    items = client.get(base, headers=headers).json()["items"]
    assert not any(item["id"] == identifier for item in items)
    assert any(item["id"] == corrected["id"] for item in items)
    assert (
        client.patch(
            base + "/" + identifier, headers=headers, json={"value": "stale"}
        ).status_code
        == 404
    )
    assert (
        client.delete(base + "/" + corrected["id"], headers=headers).status_code == 200
    )
    assert not any(
        item["id"] == corrected["id"]
        for item in client.get(base, headers=headers).json()["items"]
    )


def test_assistant_expenses_share_the_ledger(workspace):
    client, headers, session = workspace
    key = "workflow-" + uuid.uuid4().hex
    saved = store.add_record(
        session["id"],
        "expense",
        {
            "description": "Shared ledger entry",
            "amount": 81.75,
            "date": str(date.today()),
            "category": "labour",
        },
        key,
    )
    items = client.get("/api/farm-workspace/ledger", headers=headers).json()["items"]
    item = next(row for row in items if row["id"].replace("-", "") == saved["id"])
    assert item["amount_inr"] == 81.75
    assert (
        client.delete(
            "/api/farm-workspace/ledger/" + item["id"] + "?row_version=1",
            headers=headers,
        ).status_code
        == 200
    )
    assert not any(
        row["id"] == saved["id"] for row in store.records(session["id"], "expense")
    )
    assert client.get("/api/farm-workspace/today", headers=headers).status_code == 200
    assert (
        client.get("/api/farm-workspace/timeline", headers=headers).status_code == 200
    )


def test_approved_write_replay_is_atomic_and_rejects_changed_arguments(workspace):
    from fastapi import HTTPException

    from skyview.api.v3_farm_workflow_routes import execute_tool

    _client, _headers, session = workspace
    owner = store.farmer_id(session["id"])
    key = uuid.uuid4().hex
    args = {
        "title": "Replay-safe scouting mission",
        "steps": [{"title": "Walk field", "done": False}],
    }
    first = execute_tool("create_mission", args, owner, key)
    db.dispose()
    again = execute_tool("create_mission", args, owner, key)
    assert again == first
    with db.connection(owner) as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM sv3.mission_receipts WHERE mission_id=:id"),
                {"id": first["id"]},
            ).scalar()
            == 1
        )
    with pytest.raises(HTTPException) as changed:
        execute_tool(
            "create_mission", {**args, "title": "Changed after approval"}, owner, key
        )
    assert changed.value.status_code == 409
    with pytest.raises(HTTPException):
        execute_tool(
            "add_crop_note",
            {
                "case_id": str(uuid.uuid4()),
                "note": "Invalid case",
                "observed_on": str(date.today()),
            },
            owner,
            "invalid-" + key,
        )
    with db.connection(owner) as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM sv3.workflow_tool_executions WHERE id=:id"),
                {
                    "id": str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL, f"{owner}:add_crop_note:invalid-{key}"
                        )
                    )
                },
            ).scalar()
            == 0
        )


@pytest.mark.asyncio
async def test_executor_approved_writes_replay_and_owner_isolation(
    workspace, monkeypatch
):
    import json

    from fastapi import HTTPException

    from skyview.assistant.tools import Executor

    _client, _headers, session = workspace
    executor = Executor(session["id"], "WS01", None)
    ledger_args = {
        "description": "Executor integration entry",
        "category": "seed",
        "kind": "expense",
        "basis": "actual",
        "amount_inr": "73.25",
        "occurred_on": str(date.today()),
    }
    created = {}
    for name, args in (
        ("record_ledger", ledger_args),
        (
            "create_crop_case",
            {"title": "Executor observed leaf patches", "note": "Needs a dated photo"},
        ),
        (
            "create_mission",
            {
                "title": "Executor replay-safe mission",
                "steps": [{"title": "Observe field", "done": False}],
            },
        ),
    ):
        call_id = uuid.uuid4().hex
        first = await executor.run(name, args, call_id)
        db.dispose()
        replay = await Executor(session["id"], "WS01", None).run(name, args, call_id)
        assert replay == first
        json.dumps(first)
        created[name] = first["saved"]
    args = {
        "case_id": created["create_crop_case"]["id"],
        "note": "Follow-up after scouting",
        "observed_on": str(date.today()),
    }
    note_id = uuid.uuid4().hex
    note = await executor.run("record_crop_note", args, note_id)
    db.dispose()
    assert (
        await Executor(session["id"], "WS01", None).run(
            "record_crop_note", args, note_id
        )
        == note
    )
    with db.connection(store.farmer_id(session["id"])) as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM sv3.crop_case_notes WHERE case_id=:id"),
                {"id": args["case_id"]},
            ).scalar()
            == 2
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM sv3.mission_receipts WHERE mission_id=:id"),
                {"id": created["create_mission"]["id"]},
            ).scalar()
            == 1
        )
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0082")
    other = store.create_session()
    other_executor = Executor(other["id"], "WS01", None)
    for name, record in (
        ("farm_ledger", created["record_ledger"]),
        ("crop_cases", created["create_crop_case"]),
        ("farm_missions", created["create_mission"]),
    ):
        result = await other_executor.run(name, {})
        assert not any(item["id"] == record["id"] for item in result["items"])
    with pytest.raises(HTTPException) as forbidden:
        await other_executor.run("record_crop_note", args, uuid.uuid4().hex)
    assert forbidden.value.status_code == 404


@pytest.mark.asyncio
async def test_executor_field_and_soil_records_are_jsonsafe_and_owned(
    workspace, monkeypatch
):
    import json

    from skyview.assistant.tools import Executor

    _client, _headers, session = workspace
    own = Executor(session["id"], "WS01", None)
    fields = await own.run("field_context", {})
    soil = await own.run("soil_reports", {})
    assert fields["farms"] and fields["plots"] and fields["crop_cycles"]
    assert soil["samples"] and soil["values"]
    json.dumps(fields, allow_nan=False)
    json.dumps(soil, allow_nan=False)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0082")
    other = store.create_session()
    other_executor = Executor(other["id"], "WS01", None)
    other_fields = await other_executor.run("field_context", {})
    other_soil = await other_executor.run("soil_reports", {})
    for kind in ("farms", "plots", "crop_cycles"):
        assert not (
            {item["id"] for item in fields[kind]}
            & {item["id"] for item in other_fields[kind]}
        )
    for kind in ("samples", "values"):
        assert not (
            {item["id"] for item in soil[kind]}
            & {item["id"] for item in other_soil[kind]}
        )


@pytest.mark.asyncio
async def test_ledger_api_and_tool_reject_invalid_accounting(workspace):
    from pydantic import ValidationError

    from skyview.assistant.tools import Executor

    client, headers, session = workspace
    executor = Executor(session["id"], "WS01", None)
    base = {
        "description": "Invalid accounting test",
        "category": "seed",
        "kind": "expense",
        "basis": "actual",
        "amount_inr": 10,
        "occurred_on": str(date.today()),
    }
    for change in (
        {"amount_inr": 0},
        {"amount_inr": -1},
        {"amount_inr": 2.345},
        {"basis": "receivable"},
        {"occurred_on": str(date.today() + timedelta(days=1))},
        {"amount_inr": 100000001},
    ):
        args = {**base, **change}
        assert (
            client.post(
                "/api/farm-workspace/ledger", headers=headers, json=args
            ).status_code
            == 422
        )
        with pytest.raises(ValidationError):
            await executor.run("record_ledger", args, uuid.uuid4().hex)


def test_future_plans_do_not_hide_history_or_today_urgency(workspace):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    client, headers, session = workspace
    day = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    future = store.add_record(
        session["id"],
        "task",
        {
            "title": "Far future task test",
            "due_date": str(day + timedelta(days=365)),
            "notes": "Planned, not performed",
        },
        "future-" + uuid.uuid4().hex,
    )
    overdue = store.add_record(
        session["id"],
        "task",
        {
            "title": "Overdue task test",
            "due_date": str(day - timedelta(days=3650)),
            "notes": "Farmer saved task",
        },
        "overdue-" + uuid.uuid4().hex,
    )
    timeline = client.get("/api/farm-workspace/timeline", headers=headers).json()
    assert not any(
        row["id"].replace("-", "") == future["id"] for row in timeline["items"]
    )
    with db.connection(store.farmer_id(session["id"])) as connection:
        database_now = connection.execute(text("SELECT now()")).scalar()

    assert all(
        datetime.fromisoformat(row["occurred_at"]) <= database_now
        for row in timeline["items"]
    )
    today = client.get("/api/farm-workspace/today", headers=headers).json()
    assert any(row["id"].replace("-", "") == overdue["id"] for row in today["actions"])
    assert not any(
        row["id"].replace("-", "") == future["id"] for row in today["actions"]
    )
    store.edit_task(session["id"], future["id"], {"deleted": True})
    store.edit_task(session["id"], overdue["id"], {"deleted": True})


def test_forgetting_fact_does_not_rewrite_transcript_or_archive(workspace):
    from skyview.assistant import v3_store

    client, headers, session = workspace
    sid = session["id"]
    statement = "I grow memorymarker " + uuid.uuid4().hex
    state = store.load(sid)
    state["messages"] = [{"role": "user", "content": statement}]
    store.save(sid, state)
    store.archive_conversation(sid)
    owner = store.farmer_id(sid)
    with db.connection(owner) as connection:
        identifier = str(
            connection.execute(
                text(
                    "SELECT id FROM sv3.memories WHERE search_text=:statement AND valid_to IS NULL"
                ),
                {"statement": statement},
            ).scalar_one()
        )
    assert v3_store.recall_memory(sid, statement)["memories"]
    result = client.delete(
        "/api/farm-workspace/memories/" + identifier, headers=headers
    )
    assert (
        result.status_code == 200 and "Original conversation" in result.json()["note"]
    )
    assert not v3_store.recall_memory(sid, statement)["memories"]
    store.save(sid, state)
    assert not v3_store.recall_memory(sid, statement)["memories"]
    assert store.load(sid)["messages"][0]["content"] == statement
    archives = store.conversations(sid)
    assert any(
        store.conversation(sid, item["id"])["messages"][0]["content"] == statement
        for item in archives
    )


def test_http_mission_runs_keep_owned_receipts_and_resume_questions(
    workspace, monkeypatch
):
    import json

    from skyview.api.assistant_routes import router as assistant_router
    from skyview.assistant import provider

    _client, headers, session = workspace
    app = FastAPI()
    app.include_router(router)
    app.include_router(assistant_router)
    client = TestClient(app)
    mission = client.post(
        "/api/farm-workspace/missions",
        headers=headers,
        json={
            "title": "Owned assistant mission",
            "steps": [{"title": "Gather farmer context", "done": False}],
        },
    ).json()
    turns = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "mission-question-" + uuid.uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": "ask_farmer",
                        "arguments": json.dumps(
                            {
                                "question": "Which plot should I use?",
                                "fields": [
                                    {"id": "plot", "label": "Plot name", "type": "text"}
                                ],
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "Prepared the next steps for your named plot. No field work was performed.",
        },
    ]

    async def scripted(*_args):
        turn = turns.pop(0)
        if turn.get("content"):
            yield {"type": "delta", "text": turn["content"]}
        yield {"type": "turn", "message": turn}

    monkeypatch.setattr(provider, "stream_turn", scripted)
    url = f"/api/assistant/sessions/{session['id']}/run"
    result = client.post(
        url,
        headers=headers,
        json={"message": "Help me work on this plan", "mission_id": mission["id"]},
    )
    assert result.status_code == 200, result.text
    events = [json.loads(line) for line in result.text.splitlines() if line]
    assert events[-1]["status"] == "waiting"
    state = store.load(session["id"])
    assert state["mission_context"]["id"] == mission["id"]
    pending = state["pending"]
    different = str(uuid.uuid4())
    assert (
        client.post(
            url,
            headers=headers,
            json={
                "pending_id": pending["id"],
                "answers": {"plot": "North plot"},
                "mission_id": different,
            },
        ).status_code
        == 422
    )
    db.dispose()
    result = client.post(
        url,
        headers=headers,
        json={"pending_id": pending["id"], "answers": {"plot": "North plot"}},
    )
    assert result.status_code == 200, result.text
    events = [json.loads(line) for line in result.text.splitlines() if line]
    assert events[-1]["status"] == "completed"
    assert not store.load(session["id"]).get("mission_context")
    saved = next(
        item
        for item in client.get("/api/farm-workspace/missions", headers=headers).json()[
            "items"
        ]
        if item["id"] == mission["id"]
    )
    assert saved["status"] == "draft" and saved["steps"][0]["done"] is False
    receipts = client.get(
        f"/api/farm-workspace/missions/{mission['id']}/receipts", headers=headers
    ).json()["items"]
    run_receipts = [
        json.loads(item["detail"])
        for item in receipts
        if item["action"] == "assistant_run"
    ]
    assert len(run_receipts) == 2 and {item["status"] for item in run_receipts} == {
        "waiting",
        "completed",
    }
    assert any(item["steps"] for item in run_receipts)
    assert all("physical work" in item["note"] for item in run_receipts)
    assert (
        client.post(
            url,
            headers=headers,
            json={"message": "Unknown mission", "mission_id": different},
        ).status_code
        == 422
    )
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0082")
    other = store.create_session()
    other_headers = {
        "Authorization": "Bearer " + other["token"],
        "X-Assistant-Session": other["id"],
    }
    assert (
        client.post(
            f"/api/assistant/sessions/{other['id']}/run",
            headers=other_headers,
            json={"message": "Other owner plan", "mission_id": mission["id"]},
        ).status_code
        == 422
    )

    for status, version in (("active", 1), ("paused", 2), ("cancelled", 3)):
        changed = client.patch(
            f"/api/farm-workspace/missions/{mission['id']}",
            headers=headers,
            json={
                "title": mission["title"],
                "objective": "",
                "steps": mission["steps"],
                "status": status,
                "row_version": version,
            },
        )
        assert changed.status_code == 200, changed.text
        if status in {"paused", "cancelled"}:
            assert (
                client.post(
                    url,
                    headers=headers,
                    json={
                        "message": "Work on paused or cancelled plan",
                        "mission_id": mission["id"],
                    },
                ).status_code
                == 422
            )


def test_selected_uploads_reach_the_model_and_reject_foreign_or_local_ids(
    workspace, monkeypatch, tmp_path
):
    import io

    from PIL import Image

    from skyview.api.assistant_routes import router as assistant_router
    from skyview.assistant import attachments, provider

    _client, headers, session = workspace
    monkeypatch.setattr(store, "ROOT", tmp_path)
    data = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(data, format="PNG")
    upload = attachments.extract(session["id"], "selected receipt.png", data.getvalue())
    captured = []

    async def reply(_client, messages, _tools):
        captured.append(messages)
        yield {
            "type": "turn",
            "message": {
                "role": "assistant",
                "content": "Selected document is available for review.",
            },
        }

    monkeypatch.setattr(provider, "stream_turn", reply)
    app = FastAPI()
    app.include_router(assistant_router)
    client = TestClient(app)
    url = f"/api/assistant/sessions/{session['id']}/run"
    assert (
        client.post(
            url,
            headers=headers,
            json={"message": "Read selected file", "attachment_ids": [upload["id"]]},
        ).status_code
        == 200
    )
    assert upload["id"] in captured[0][0]["content"]
    latest_user = next(
        message for message in reversed(captured[0]) if message["role"] == "user"
    )
    assert (
        upload["id"] in latest_user["content"]
        and "selected receipt.png" in latest_user["content"]
    )
    assert (
        client.post(
            url,
            headers=headers,
            json={
                "message": "Read local draft",
                "attachment_ids": ["local-" + str(uuid.uuid4())],
            },
        ).status_code
        == 422
    )
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0082")
    other = store.create_session()
    foreign = attachments.extract(other["id"], "private receipt.png", data.getvalue())
    assert (
        client.post(
            url,
            headers=headers,
            json={"message": "Read other file", "attachment_ids": [foreign["id"]]},
        ).status_code
        == 422
    )
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_soil_tool_stores_only_reviewed_owned_transcription_and_replays(
    workspace, monkeypatch, tmp_path
):
    from skyview.assistant import attachments
    from skyview.assistant.tools import TOOLS, Executor

    _client, _headers, session = workspace
    monkeypatch.setattr(store, "ROOT", tmp_path)
    report = attachments.extract(
        session["id"],
        "confirmed-soil.txt",
        b"Farmer supplied sample. pH 6.7 at 0-15 cm.",
    )
    executor = Executor(session["id"], "WS01", None)
    fields = await executor.run("field_context", {})
    args = {
        "plot_id": fields["plots"][0]["id"],
        "attachment_id": report["id"],
        "sampled_on": str(date.today()),
        "values": [
            {
                "property": "ph",
                "value": "6.7",
                "unit_code": "ph",
                "reported_basis": "hydrogen activity",
                "depth_top_cm": "0",
                "depth_bottom_cm": "15",
            }
        ],
    }
    assert TOOLS["save_soil_report"].approval
    labels = await executor.approval_labels(args)
    assert labels["attachment_id"] == "confirmed-soil.txt" and labels["plot_id"]
    call_id = uuid.uuid4().hex
    first = await executor.run("save_soil_report", args, call_id)
    assert (
        first["saved"]
        and first["evidence_type"] == "farmer_report"
        and not first["lab_verified"]
    )
    db.dispose()
    duplicate = await Executor(session["id"], "WS01", None).run(
        "save_soil_report", args, call_id
    )
    assert duplicate["id"] == first["id"] and duplicate["duplicate"]
    changed = {**args, "values": [{**args["values"][0], "value": "7"}]}
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as conflict:
        await executor.run("save_soil_report", changed, call_id)
    assert conflict.value.status_code == 409
