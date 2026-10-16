"""Opt-in real PostgreSQL contract tests, using an isolated v3 demo/test DB."""

import os
import time
import uuid

import pytest
from sqlalchemy import text

from skyview.assistant import attachments, models, store, v3_store
from skyview.data.v3 import db as database


@pytest.fixture
def pg(monkeypatch, tmp_path):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set V3_TEST_DATABASE_URL to an isolated seeded v3 database")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0080")
    monkeypatch.setattr(store, "ROOT", tmp_path)
    return store.create_session()


@pytest.fixture
def file_pg(pg):
    """File-repair fixtures must not leak into this farmer's later chat manifests."""
    yield pg
    with database.connection(store.farmer_id(pg["id"]), write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.assistant_records SET data=data || jsonb_build_object('retired',true,'retirement_reason','integration_fixture_complete') WHERE session_id=:sid AND kind IN ('artifact','attachment') AND coalesce(data->>'retired','false') <> 'true'"
            ),
            {"sid": pg["id"]},
        )


def test_pg_capability_and_farmer_isolation(pg, monkeypatch):
    assert store.authenticate(pg["id"], pg["token"])
    assert not store.authenticate(pg["id"], "incorrect")
    task = store.add_record(
        pg["id"],
        "task",
        {
            "title": "Private PostgreSQL task",
            "due_date": "2026-10-20",
            "notes": "Only owner",
        },
        "test:" + uuid.uuid4().hex,
    )
    assert any(row["id"] == task["id"] for row in store.records(pg["id"], "task"))
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0079")
    other = store.create_session()
    assert not any(
        row["id"] == task["id"] for row in store.records(other["id"], "task")
    )
    with pytest.raises(ValueError, match="not found"):
        store.edit_task(other["id"], task["id"], {"title": "Cross-owner edit"})
    changed = store.edit_task(pg["id"], task["id"], {"completed": True})
    assert changed["completed"] and changed["row_version"] == 2
    store.edit_task(pg["id"], task["id"], {"deleted": True})
    with pytest.raises(ValueError, match="deleted"):
        store.complete_task(pg["id"], task["id"])


def test_pg_records_transcript_memory_reset_and_idempotency(pg):
    sid = pg["id"]
    key = "test:" + uuid.uuid4().hex
    expense = {"description": "Demo seeds", "amount": 310.25, "date": "2026-10-14"}
    first = store.add_record(sid, "expense", expense, key)
    assert store.add_record(sid, "expense", expense, key) == first
    assert any(row["id"] == first["id"] for row in store.records(sid, "expense"))
    state = store.load(sid)
    state["messages"] = [
        {"role": "user", "content": "I grow lavender on the north plot"},
        {"role": "assistant", "content": "Recorded your statement."},
    ]
    state.update(
        memory_cursor=1, memory_summary="Farmer reports lavender; needs verification."
    )
    store.save(sid, state)
    store.save(sid, state)
    assert v3_store.recall_memory(sid, "lavender")["memories"]
    with database.connection(store.farmer_id(sid)) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.messages WHERE conversation_id=:cid"),
                {"cid": state["conversation_id"]},
            ).scalar_one()
            == 2
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM sv3.context_compactions WHERE conversation_id=:cid"
                ),
                {"cid": state["conversation_id"]},
            ).scalar_one()
            == 1
        )
    old_cid = state["conversation_id"]
    store.archive_conversation(sid)
    store.save(sid, {"messages": [], "pending": None, "events": []})
    assert store.load(sid)["conversation_id"] != old_cid
    assert store.conversation(sid, old_cid)["messages"] == state["messages"]


def test_pg_questions_progress_and_exact_approval(pg):
    sid = pg["id"]
    run = uuid.uuid4().hex
    v3_store.append_event(
        sid, {"type": "run_started", "run_id": run, "at": time.time()}
    )
    pending = {
        "id": uuid.uuid4().hex,
        "run_id": run,
        "kind": "question",
        "call_id": "question-1",
        "tool": "ask_farmer",
        "arguments": {
            "question": "Which crop?",
            "fields": [{"name": "crop", "label": "Crop", "type": "text"}],
        },
    }
    v3_store.append_event(
        sid, {"type": "question", "run_id": run, "at": time.time(), "pending": pending}
    )
    store.answer_question(sid, pending, {"crop": "Wheat"})
    approval = {
        "id": uuid.uuid4().hex,
        "run_id": run,
        "kind": "approval",
        "call_id": "write-1",
        "tool": "save_task",
        "arguments": {"title": "Scout wheat", "due_date": "2026-10-20"},
    }
    v3_store.append_event(
        sid, {"type": "approval", "run_id": run, "at": time.time(), "pending": approval}
    )
    altered = {
        **approval,
        "arguments": {**approval["arguments"], "title": "Changed operation"},
    }
    with pytest.raises(ValueError, match="changed"):
        store.decide_approval(sid, altered, True)
    store.decide_approval(sid, approval, True)
    with pytest.raises(ValueError, match="already decided"):
        store.decide_approval(sid, approval, True)
    assert len(store.load(sid)["events"]) == 3
    with database.connection(store.farmer_id(sid)) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.question_answers WHERE question_id=:id"),
                {"id": pending["id"]},
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("format", ["docx", "pdf", "xlsx", "csv", "pptx"])
def test_pg_files_have_canonical_metadata_and_upload_bytes(pg, format):
    from skyview.assistant.artifacts import create_file

    result = create_file(
        pg["id"],
        models.FileArgs(
            format=format,
            title="Database contract",
            sections=[{"heading": "Evidence", "text": "Synthetic test file"}],
            columns=["Item", "Amount"],
            rows=[["Seed", 10]],
        ),
    )
    with database.connection(store.farmer_id(pg["id"])) as conn:
        row = (
            conn.execute(
                text("SELECT * FROM sv3.artifacts WHERE id=:id"), {"id": result["id"]}
            )
            .mappings()
            .one()
        )
        assert row["bytes"] > 0 and len(row["checksum"]) == 64
        assert row["preview"]
    uploaded = attachments.extract(
        pg["id"], "farm-note.txt", b"Farmer-provided test text"
    )
    with database.connection(store.farmer_id(pg["id"])) as conn:
        row = (
            conn.execute(
                text("SELECT * FROM sv3.attachments WHERE id=:id"),
                {"id": uploaded["id"]},
            )
            .mappings()
            .one()
        )
        assert (
            row["bytes"] == 25 and row["extracted_text"] == "Farmer-provided test text"
        )


def test_pg_readonly_legacy_import_preserves_capabilities_and_is_repeat_safe(
    pg, tmp_path
):
    import hashlib
    import json
    import sqlite3

    from skyview.assistant.v3_import import migrate

    source = tmp_path / "legacy"
    destination = tmp_path / "destination"
    source.mkdir()
    sid = uuid.uuid4().hex
    token = "test-only-private-capability"
    recordid = uuid.uuid4().hex
    legacy_path = source / "assistant.db"
    state = {
        "messages": [{"role": "user", "content": "Legacy farmer evidence"}],
        "pending": None,
        "events": [],
    }
    with sqlite3.connect(legacy_path) as legacy:
        legacy.executescript(
            "CREATE TABLE sessions(id TEXT PRIMARY KEY,token_hash TEXT,state TEXT); CREATE TABLE records(id TEXT PRIMARY KEY,session_id TEXT,kind TEXT,data TEXT); CREATE TABLE conversations(id TEXT PRIMARY KEY,session_id TEXT,title TEXT,state TEXT);"
        )
        legacy.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (sid, hashlib.sha256(token.encode()).hexdigest(), json.dumps(state)),
        )
        legacy.execute(
            "INSERT INTO records VALUES(?,?,?,?)",
            (
                recordid,
                sid,
                "attachment",
                json.dumps(
                    {
                        "name": "earlier.pdf",
                        "format": "pdf",
                        "text": "Extracted legacy evidence",
                        "characters": 25,
                    }
                ),
            ),
        )
    source_hash = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
    assert migrate(source, destination) == {"sessions": 1, "records": 1, "archives": 0}
    assert store.authenticate(sid, token)
    assert store.load(sid)["messages"] == state["messages"]
    attachment = store.find_record(sid, "attachment", recordid)
    assert attachment["legacy_original_bytes_unavailable"]
    assert (
        destination / "uploads" / attachment["filename"]
    ).read_text() == "Extracted legacy evidence"
    assert migrate(source, destination) == {"sessions": 0, "records": 0, "archives": 0}
    assert hashlib.sha256(legacy_path.read_bytes()).hexdigest() == source_hash


def test_pg_verified_live_bootstrap_creates_only_own_pending_account(pg, monkeypatch):
    from sqlalchemy.engine import make_url

    from skyview.assistant import auth

    liveurl = (
        make_url(os.environ["V3_DATABASE_URL"])
        .set(database="skyview_v3_test")
        .render_as_string(hide_password=False)
    )
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_live")
    monkeypatch.setenv("V3_DATABASE_URL", liveurl)
    subject = "oidc:" + uuid.uuid4().hex + uuid.uuid4().hex
    monkeypatch.setattr(
        auth,
        "verify_identity",
        lambda token: {
            "auth_subject": subject,
            "issuer": "https://identity.example.invalid/",
        },
    )
    first = auth.create_live_session("verified-test-token")
    second = auth.create_live_session("verified-test-token")
    assert store.farmer_id(first["id"]) == store.farmer_id(second["id"])
    with database.connection(store.farmer_id(first["id"])) as conn:
        row = (
            conn.execute(text("SELECT status,region_id,contact_phone FROM sv3.farmers"))
            .mappings()
            .one()
        )
        assert (
            row["status"] == "onboarding"
            and row["region_id"] is None
            and row["contact_phone"] is None
        )
    with pytest.raises(ValueError, match="onboarding"):
        store.create_session()


@pytest.mark.asyncio
async def test_pg_chat_market_trend_contains_full_exact_series(pg):
    import httpx

    from skyview.assistant.tools import Executor

    async with httpx.AsyncClient() as client:
        result = await Executor(pg["id"], "WS01", client).run(
            "market_trend", {"commodity": "Wheat", "observed_only": False}
        )
    assert result["available"]
    assert len(result["chart"]["points"]) == 365
    assert result["provenance"]["origin"] == "synthetic"
    assert (
        len(
            {
                (
                    row["market"],
                    row["variety"],
                    row["grade"],
                    row["unit"],
                    row["series_id"],
                )
                for row in result["records"]
            }
        )
        == 1
    )


def test_pg_calendar_conflict_status_and_authenticated_station(pg, monkeypatch):
    from fastapi.testclient import TestClient

    from skyview.main import app

    task = store.add_record(
        pg["id"],
        "task",
        {"title": "Versioned API task", "due_date": "2026-10-25"},
        "test:" + uuid.uuid4().hex,
    )
    headers = {"Authorization": "Bearer " + pg["token"]}
    client = TestClient(app)
    path = f"/api/assistant/sessions/{pg['id']}/tasks/{task['id']}"
    response = client.patch(
        path,
        headers=headers,
        json={"title": "Edited", "due_date": "2026-10-25", "row_version": 1},
    )
    assert response.status_code == 200
    assert response.json()["row_version"] == 2
    assert (
        client.delete(path, headers={**headers, "If-Match": '"1"'}).status_code == 409
    )
    assert client.get("/api/assistant/station/WS01").status_code == 401
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0001")
    station_session = store.create_session()
    response = client.get(
        "/api/assistant/station/WS01",
        headers={
            "Authorization": "Bearer " + station_session["token"],
            "X-Assistant-Session": station_session["id"],
        },
    )
    assert response.status_code == 200 and response.json()["available"]


def test_capability_revocation_and_expiry_keep_farmer_records(pg):
    from fastapi.testclient import TestClient

    from skyview.main import app

    fid = store.farmer_id(pg["id"])
    expense = store.add_record(
        pg["id"],
        "expense",
        {"description": "Expiry-preserved fixture", "amount": 25, "date": "2026-10-14"},
        "test:" + uuid.uuid4().hex,
    )
    client = TestClient(app)
    response = client.post(
        f"/api/assistant/sessions/{pg['id']}/revoke",
        headers={"Authorization": "Bearer " + pg["token"]},
    )
    assert response.status_code == 200 and response.json()["history_preserved"]
    assert not store.authenticate(pg["id"], pg["token"])
    fresh = store.create_session()
    assert store.farmer_id(fresh["id"]) == fid
    assert any(r["id"] == expense["id"] for r in store.records(fresh["id"], "expense"))
    with database.connection(fid, write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.assistant_sessions SET expires_at=now()-interval '1 second' WHERE id=:sid"
            ),
            {"sid": fresh["id"]},
        )
    assert not store.authenticate(fresh["id"], fresh["token"])
    assert (
        client.get(
            f"/api/assistant/sessions/{fresh['id']}",
            headers={"Authorization": "Bearer " + fresh["token"]},
        ).status_code
        == 401
    )


@pytest.mark.asyncio
async def test_live_chart_snapshot_and_old_snapshot_recovery_preserve_demo_labels(
    pg, monkeypatch
):
    import json

    from fastapi.testclient import TestClient

    from skyview.assistant import engine, provider
    from skyview.main import app

    sid = pg["id"]
    turns = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "restart-market-regression",
                    "type": "function",
                    "function": {
                        "name": "market_trend",
                        "arguments": json.dumps(
                            {"commodity": "Wheat", "observed_only": False}
                        ),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "This is synthetic demo price history, not actual sale offers.",
        },
    ]

    async def stream(*args, **kwargs):
        message = turns.pop(0)
        if message.get("content"):
            yield {"type": "delta", "text": message["content"]}
        yield {"type": "turn", "message": message}

    monkeypatch.setattr(provider, "stream_turn", stream)
    events = [
        event
        async for event in engine.run(
            sid,
            models.RunRequest(message="Show the full Wheat price trend"),
            store.load(sid),
        )
    ]
    completed = next(
        event
        for event in events
        if event["type"] == "tool_completed" and event.get("tool") == "market_trend"
    )
    assert completed["result"]["provenance"]["origin"] == "synthetic"
    assert len(completed["result"]["chart"]["points"]) == 365
    loaded = store.load(sid)
    message = next(
        m for m in loaded["display_history"] if m["id"] == completed["run_id"]
    )
    result = next(
        a["result"]
        for a in message["activities"]
        if a["call_id"] == "restart-market-regression"
    )
    assert result["provenance"] == completed["result"]["provenance"]
    assert result["note"] == completed["result"]["note"]
    assert len(result["chart"]["points"]) == 365

    result.pop("provenance")
    result.pop("note")
    result["chart"]["points"] = []
    store.save(sid, loaded)
    fid = store.farmer_id(sid)
    with database.connection(fid, write=True) as conn:
        seq = conn.execute(
            text("SELECT max(sequence) FROM sv3.run_events WHERE run_id=:rid"),
            {"rid": completed["run_id"]},
        ).scalar_one()
        for i in range(205):
            conn.execute(
                text(
                    "INSERT INTO sv3.run_events(farmer_id,run_id,sequence,event_type,payload,occurred_at) VALUES(:f,:rid,:seq,'text_delta',CAST(:event AS jsonb),now())"
                ),
                {
                    "f": fid,
                    "rid": completed["run_id"],
                    "seq": seq + i + 1,
                    "event": json.dumps(
                        {
                            "type": "delta",
                            "run_id": completed["run_id"],
                            "call_id": "unrelated",
                            "text": "fixture",
                        }
                    ),
                },
            )
    database.dispose()
    response = TestClient(app).get(
        f"/api/assistant/sessions/{sid}",
        headers={"Authorization": "Bearer " + pg["token"]},
    )
    assert response.status_code == 200
    restored = next(
        m for m in response.json()["messages"] if m["id"] == completed["run_id"]
    )
    result = next(
        a["result"]
        for a in restored["activities"]
        if a["call_id"] == "restart-market-regression"
    )
    assert (
        result["provenance"]["origin"] == "synthetic"
        and result["provenance"]["lane"] == "demo"
    )
    assert result["provenance"] == completed["result"]["provenance"]
    assert result["source"] == completed["result"]["source"]
    assert len(result["chart"]["points"]) == 365
    assert result["chart"]["points"] == completed["result"]["chart"]["points"]


def test_pg_memory_only_explicit_facts_and_corrections(pg):
    sid = pg["id"]
    state = store.load(sid)
    state["messages"] = [
        {"role": "user", "content": "Show the price chart"},
        {"role": "user", "content": "I want to plant onions in January"},
        {
            "role": "user",
            "content": "Public synthetic integration test: I have 4 acres",
        },
        {"role": "user", "content": "My soil is clay"},
        {"role": "user", "content": "Actually my soil is sandy loam"},
    ]
    store.save(sid, state)
    store.save(sid, state)
    with database.connection(store.farmer_id(sid)) as conn:
        memories = (
            conn.execute(
                text(
                    "SELECT m.value,m.confidence,m.valid_to,m.supersedes_id FROM sv3.memories m JOIN sv3.messages t ON t.id=m.evidence_message_id WHERE t.conversation_id=:cid ORDER BY m.valid_from"
                ),
                {"cid": state["conversation_id"]},
            )
            .mappings()
            .all()
        )
        assert len(memories) == 2
        assert memories[0]["valid_to"] and memories[1]["supersedes_id"]
        assert memories[1]["valid_to"] is None
        assert all(float(m["confidence"]) < 1 for m in memories)
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.messages WHERE conversation_id=:cid"),
                {"cid": state["conversation_id"]},
            ).scalar_one()
            == 5
        )
    assert any(
        "sandy loam" in m["excerpt"]
        for m in v3_store.recall_memory(sid, "soil")["memories"]
    )


def test_pg_memory_correction_survives_repeated_full_state_saves(pg, monkeypatch):
    sid = pg["id"]
    state = store.load(sid)
    state["messages"] = [{"role": "user", "content": "My soil is sandy"}]
    store.save(sid, state)
    state["messages"].append(
        {"role": "user", "content": "Actually my soil is heavy clay"}
    )
    store.save(sid, state)
    for _ in range(3):
        store.save(sid, state)

    from contextlib import contextmanager
    from types import SimpleNamespace

    original_connection = database.connection

    @contextmanager
    def replay_connection(*args, **kwargs):
        with original_connection(*args, **kwargs) as underlying:

            class Replay:
                def execute(self, statement, *parameters, **options):
                    if "coalesce(max(sequence),0)" in str(statement):
                        return SimpleNamespace(scalar_one=lambda: 0)
                    return underlying.execute(statement, *parameters, **options)

            yield Replay()

    with monkeypatch.context() as patch:
        patch.setattr(database, "connection", replay_connection)
        store.save(sid, state)
    with database.connection(store.farmer_id(sid)) as conn:
        versions = (
            conn.execute(
                text(
                    "SELECT m.value,m.valid_to FROM sv3.memories m JOIN sv3.messages t ON t.id=m.evidence_message_id WHERE t.conversation_id=:cid ORDER BY m.valid_from"
                ),
                {"cid": state["conversation_id"]},
            )
            .mappings()
            .all()
        )
        assert len(versions) == 2
        active = [v for v in versions if v["valid_to"] is None]
        assert len(active) == 1
        assert active[0]["value"]["statement"] == "my soil is heavy clay"


def test_reconcile_missing_file_metadata_preserves_ids_bytes_and_is_repeat_safe(
    file_pg, tmp_path
):
    pg = file_pg
    import hashlib

    from skyview.assistant.v3_reconcile import reconcile_files

    source, destination = tmp_path / "legacy-files", tmp_path / "current-files"
    (source / "files").mkdir(parents=True)
    fid, sid = store.farmer_id(pg["id"]), pg["id"]
    artifact_id, file_id, attachment_id = uuid.uuid4(), uuid.uuid4().hex, uuid.uuid4()
    payload = b"Original generated document bytes"
    (source / "files" / (file_id + ".docx")).write_bytes(payload)
    artifact = {
        "title": "Saved farm report",
        "filename": "saved-farm-report.docx",
        "file_id": file_id,
        "format": "docx",
        "preview": {"title": "Saved farm report"},
    }
    attachment = {
        "name": "old.pdf",
        "format": "pdf",
        "text": "Previously extracted words",
    }
    with database.connection(fid, write=True) as conn:
        for rid, kind, data in [
            (artifact_id, "artifact", artifact),
            (attachment_id, "attachment", attachment),
        ]:
            conn.execute(
                text(
                    "INSERT INTO sv3.assistant_records(id,farmer_id,session_id,kind,data) VALUES(:id,:f,:sid,:kind,CAST(:data AS jsonb))"
                ),
                {
                    "id": rid,
                    "f": fid,
                    "sid": sid,
                    "kind": kind,
                    "data": v3_store.dump(data),
                },
            )
    preview = reconcile_files(source, destination, session_id=sid)
    assert preview["ready"] == 2 and not preview["repaired"] and not preview["failed"]
    assert not destination.exists()
    root_before = store.ROOT
    applied = reconcile_files(source, destination, apply=True, session_id=sid)
    assert applied["repaired"] == 2 and not applied["failed"]
    assert store.ROOT == root_before
    with database.connection(fid) as conn:
        row = (
            conn.execute(
                text(
                    "SELECT id,object_uri,checksum,bytes FROM sv3.artifacts WHERE id=:id"
                ),
                {"id": artifact_id},
            )
            .mappings()
            .one()
        )
        assert (
            row["id"] == artifact_id
            and row["checksum"] == hashlib.sha256(payload).hexdigest()
        )
        assert row["object_uri"] == str(destination / "files" / (file_id + ".docx"))
        assert row["bytes"] == len(payload)
        row = (
            conn.execute(
                text(
                    "SELECT id,object_uri,mime_type,metadata FROM sv3.attachments WHERE id=:id"
                ),
                {"id": attachment_id},
            )
            .mappings()
            .one()
        )
        assert row["id"] == attachment_id and row["mime_type"] == "text/plain"
        assert row["metadata"]["legacy_original_bytes_unavailable"]
        assert (
            destination / "uploads" / (attachment_id.hex + ".txt")
        ).read_text() == attachment["text"]
    repeated = reconcile_files(source, destination, apply=True, session_id=sid)
    assert (
        repeated["repaired"] == 0
        and repeated["existing"] == 2
        and not repeated["failed"]
    )
    assert (source / "files" / (file_id + ".docx")).read_bytes() == payload


def test_reconcile_failure_rolls_back_metadata_and_only_removes_new_copy(
    file_pg, tmp_path, monkeypatch
):
    pg = file_pg
    from skyview.assistant.v3_reconcile import reconcile_files

    source, destination = tmp_path / "legacy", tmp_path / "current"
    (source / "files").mkdir(parents=True)
    fid, sid, rid, file_id = (
        store.farmer_id(pg["id"]),
        pg["id"],
        uuid.uuid4(),
        uuid.uuid4().hex,
    )
    (source / "files" / (file_id + ".pdf")).write_bytes(b"original")
    with database.connection(fid, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.assistant_records(id,farmer_id,session_id,kind,data) VALUES(:id,:f,:sid,'artifact',CAST(:data AS jsonb))"
            ),
            {
                "id": rid,
                "f": fid,
                "sid": sid,
                "data": v3_store.dump(
                    {
                        "title": "Rollback report",
                        "filename": "rollback-report.pdf",
                        "file_id": file_id,
                        "format": "pdf",
                    }
                ),
            },
        )
    original = v3_store.canonical_record

    def fail_after_insert(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("simulated interruption")

    monkeypatch.setattr(v3_store, "canonical_record", fail_after_insert)
    result = reconcile_files(source, destination, apply=True, session_id=sid)
    assert (
        result["failed"] == 1
        and not (destination / "files" / (file_id + ".pdf")).exists()
    )
    with database.connection(fid) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.artifacts WHERE id=:id"), {"id": rid}
            ).scalar_one()
            == 0
        )
    (destination / "files" / (file_id + ".pdf")).write_bytes(b"existing file")
    result = reconcile_files(source, destination, apply=True, session_id=sid)
    assert result["failed"] == 1
    assert (destination / "files" / (file_id + ".pdf")).read_bytes() == b"existing file"


def test_retired_files_remain_hidden_and_are_never_recreated_by_reconciliation(
    file_pg, tmp_path
):
    pg = file_pg
    from skyview.assistant.v3_reconcile import reconcile_files

    fid, sid, rid, file_id = (
        store.farmer_id(pg["id"]),
        pg["id"],
        uuid.uuid4(),
        uuid.uuid4().hex,
    )
    source, destination = tmp_path / "retired-legacy", tmp_path / "retired-current"
    (source / "files").mkdir(parents=True)
    (source / "files" / (file_id + ".pdf")).write_bytes(b"Retired review fixture")
    data = {
        "title": "Retired fixture",
        "format": "pdf",
        "file_id": file_id,
        "retired": True,
        "retirement_reason": "local_review_fixture",
    }
    with database.connection(fid, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.assistant_records(id,farmer_id,session_id,kind,data) VALUES(:id,:f,:sid,'artifact',CAST(:data AS jsonb))"
            ),
            {"id": rid, "f": fid, "sid": sid, "data": v3_store.dump(data)},
        )
        v3_store.canonical_record(
            conn, fid, rid, "artifact", data, "retired:" + rid.hex
        )
    assert not any(row["id"] == rid.hex for row in store.records(sid, "artifact"))
    assert store.find_record(sid, "artifact", rid.hex) is None
    assert store.find_record(sid, "artifact", file_id, file_id=True) is None
    result = reconcile_files(source, destination, apply=True, session_id=sid)
    assert (
        result["retired"] == 1
        and result["ready"] == result["repaired"] == result["failed"] == 0
    )
    assert not destination.exists()
    with database.connection(fid) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.artifacts WHERE id=:id"), {"id": rid}
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT data->>'retirement_reason' FROM sv3.assistant_records WHERE id=:id"
                ),
                {"id": rid},
            ).scalar_one()
            == "local_review_fixture"
        )
