"""The active DB catalog describes actual deployed schemas/files and audit references."""

import hashlib
import os
import time
import uuid

import pytest
from sqlalchemy import text

from skyview.assistant import catalog, store, v3_store
from skyview.assistant.tools import SKILLS, SKILLS_DIR, TOOLS
from skyview.data.v3 import db


@pytest.fixture
def session(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated V3_TEST_DATABASE_URL")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0080")
    return store.create_session()


def test_catalog_is_actual_complete_versioned_and_repeat_safe(session):
    result = catalog.sync_runtime_catalog()
    assert result["tools"] == len(TOOLS) and result["skills"] == len(SKILLS)
    assert not catalog.sync_runtime_catalog()["changed"]
    with db.connection() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT code,arguments_schema,effect,requires_approval FROM sv3.tool_versions WHERE active"
                )
            )
            .mappings()
            .all()
        )
        assert {row["code"] for row in rows} == set(TOOLS)
        for row in rows:
            assert (
                row["arguments_schema"]
                == TOOLS[row["code"]].arguments.model_json_schema()
            )
            assert row["requires_approval"] == TOOLS[row["code"]].approval
        skills = (
            conn.execute(
                text(
                    "SELECT code,workflow_hash,workflow FROM sv3.skill_versions WHERE active"
                )
            )
            .mappings()
            .all()
        )
        assert {row["code"] for row in skills} == set(SKILLS)
        for row in skills:
            exact = (SKILLS_DIR / f"{row['code']}.md").read_text()
            assert (
                row["workflow"] == exact
                and row["workflow_hash"] == hashlib.sha256(exact.encode()).hexdigest()
            )


def test_real_tool_and_skill_audits_link_active_runtime_version(session):
    sid = session["id"]
    rid = uuid.uuid4().hex
    v3_store.append_event(
        sid, {"type": "run_started", "run_id": rid, "at": time.time()}
    )
    v3_store.append_event(
        sid,
        {
            "type": "tool_started",
            "run_id": rid,
            "at": time.time(),
            "call_id": "skill-fixture",
            "tool": "load_skill",
            "arguments": {"skill": "documents"},
        },
    )
    pending = {
        "id": uuid.uuid4().hex,
        "run_id": rid,
        "kind": "approval",
        "tool": "save_task",
        "call_id": "write-fixture",
        "arguments": {"title": "Versioned audit fixture", "due_date": "2026-10-20"},
    }
    v3_store.append_event(
        sid, {"type": "approval", "run_id": rid, "at": time.time(), "pending": pending}
    )
    with db.connection(store.farmer_id(sid)) as conn:
        calls = (
            conn.execute(
                text(
                    "SELECT c.tool_name,c.tool_version_id,c.skill_version_id,t.code,t.active,s.code AS skill FROM sv3.tool_calls c JOIN sv3.tool_versions t ON t.id=c.tool_version_id LEFT JOIN sv3.skill_versions s ON s.id=c.skill_version_id WHERE c.run_id=:run"
                ),
                {"run": rid},
            )
            .mappings()
            .all()
        )
        assert len(calls) == 2 and all(
            c["tool_version_id"] and c["active"] for c in calls
        )
        skill = next(c for c in calls if c["tool_name"] == "load_skill")
        assert skill["skill_version_id"] and skill["skill"] == "documents"


def test_call_pins_its_own_version_during_another_active_deployment(session):
    catalog.sync_runtime_catalog()
    expected = catalog.runtime_version_bindings()["tools"]["list_tasks"]
    with db.connection(write=True, ingest=True) as conn:
        conn.execute(
            text("UPDATE sv3.tool_versions SET active=false WHERE code='list_tasks'")
        )
        conn.execute(
            text(
                "INSERT INTO sv3.tool_versions(code,version,title,arguments_schema,output_schema,effect,requires_approval,active) VALUES('list_tasks','fixture-other-deployment','Other deployment',CAST(:schema AS jsonb),CAST(:schema AS jsonb),'read',false,true) ON CONFLICT(code,version) DO UPDATE SET active=true"
            ),
            {"schema": '{"type":"object"}'},
        )
    try:
        rid = uuid.uuid4().hex
        v3_store.append_event(
            session["id"], {"type": "run_started", "run_id": rid, "at": time.time()}
        )
        v3_store.append_event(
            session["id"],
            {
                "type": "tool_started",
                "run_id": rid,
                "at": time.time(),
                "tool": "list_tasks",
                "call_id": "own-runtime",
                "arguments": {},
            },
        )
        with db.connection(store.farmer_id(session["id"])) as conn:
            assert (
                conn.execute(
                    text(
                        "SELECT v.version FROM sv3.tool_calls c JOIN sv3.tool_versions v ON v.id=c.tool_version_id WHERE c.run_id=:run"
                    ),
                    {"run": rid},
                ).scalar_one()
                == expected
            )
    finally:
        with db.connection(write=True, ingest=True) as conn:
            conn.execute(
                text(
                    "UPDATE sv3.tool_versions SET active=false WHERE code='list_tasks'"
                )
            )
            conn.execute(
                text(
                    "UPDATE sv3.tool_versions SET active=true WHERE code='list_tasks' AND version=:version"
                ),
                {"version": expected},
            )
