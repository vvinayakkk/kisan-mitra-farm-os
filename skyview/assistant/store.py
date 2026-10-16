"""Capability-scoped local storage; no writes to the farm telemetry database."""

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / ".assistant-data"
ROOT = (
    Path(os.getenv("ASSISTANT_STORAGE_DIR", str(DEFAULT_ROOT))).expanduser().resolve()
)


@contextmanager
def connection():
    ROOT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ROOT / "assistant.db", timeout=5) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
          CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, token_hash TEXT,
            state TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, session_id TEXT,
            kind TEXT, data TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE IF NOT EXISTS runs (session_id TEXT PRIMARY KEY, token TEXT, expires_at REAL);
          CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, session_id TEXT,
            title TEXT, state TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS records_scope ON records(session_id,kind,created_at)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS conversations_scope ON conversations(session_id,created_at)"
        )
        yield db


def create_session():
    sid, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
    with connection() as db:
        db.execute(
            "INSERT INTO sessions(id,token_hash,state) VALUES (?,?,?)",
            (
                sid,
                hashlib.sha256(token.encode()).hexdigest(),
                json.dumps({"messages": [], "pending": None, "events": []}),
            ),
        )
    return {"id": sid, "token": token}


def authenticate(sid, token):
    with connection() as db:
        row = db.execute(
            "SELECT token_hash FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    return bool(
        row
        and secrets.compare_digest(
            row["token_hash"], hashlib.sha256(token.encode()).hexdigest()
        )
    )


def load(sid):
    with connection() as db:
        row = db.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()
    return json.loads(row["state"]) if row else None


def save(sid, state):
    with connection() as db:
        db.execute(
            "UPDATE sessions SET state=? WHERE id=?",
            (json.dumps(state, ensure_ascii=False, default=str), sid),
        )


def add_record(sid, kind, data, execution_id=None):
    rid = (
        hashlib.sha256(f"{sid}:{kind}:{execution_id}".encode()).hexdigest()[:32]
        if execution_id
        else uuid.uuid4().hex
    )
    with connection() as db:
        db.execute(
            "INSERT OR IGNORE INTO records(id,session_id,kind,data) VALUES (?,?,?,?)",
            (rid, sid, kind, json.dumps(data, default=str)),
        )
        stored = db.execute("SELECT data FROM records WHERE id=?", (rid,)).fetchone()
    return {"id": rid, **json.loads(stored["data"])}


def records(sid, kind, *, include_deleted=False):
    with connection() as db:
        rows = db.execute(
            "SELECT id,data FROM records WHERE session_id=? AND kind=?"
            + (
                ""
                if include_deleted
                else " AND COALESCE(json_extract(data, '$.deleted'),0)=0"
            )
            + " ORDER BY created_at DESC,rowid DESC LIMIT 100",
            (sid, kind),
        ).fetchall()
    items = [{"id": r["id"], **json.loads(r["data"])} for r in rows]
    return (
        items
        if include_deleted
        else [item for item in items if not item.get("deleted")]
    )


def complete_task(sid, task_id):
    with connection() as db:
        row = db.execute(
            "SELECT data FROM records WHERE id=? AND session_id=? AND kind='task'",
            (task_id, sid),
        ).fetchone()
        if not row:
            raise ValueError("Task not found in this conversation")
        if json.loads(row["data"]).get("deleted"):
            raise ValueError("This task was deleted")
        data = {**json.loads(row["data"]), "completed": True}
        db.execute(
            "UPDATE records SET data=? WHERE id=? AND session_id=?",
            (json.dumps(data), task_id, sid),
        )
    return {"id": task_id, **data}


def claim_run(sid):
    token = uuid.uuid4().hex
    now = time.time()
    with connection() as db:
        cursor = db.execute(
            """INSERT INTO runs(session_id,token,expires_at) VALUES(?,?,?)
          ON CONFLICT(session_id) DO UPDATE SET token=excluded.token,expires_at=excluded.expires_at
          WHERE runs.expires_at<=?""",
            (sid, token, now + 240, now),
        )
        return token if cursor.rowcount else None


def release_run(sid, token):
    with connection() as db:
        db.execute("DELETE FROM runs WHERE session_id=? AND token=?", (sid, token))


def is_running(sid):
    with connection() as db:
        return (
            db.execute(
                "SELECT 1 FROM runs WHERE session_id=? AND expires_at>?",
                (sid, time.time()),
            ).fetchone()
            is not None
        )


def archive_conversation(sid):
    state = load(sid)
    if not state["messages"]:
        return
    title = next(
        (m["content"] for m in state["messages"] if m["role"] == "user"), "Conversation"
    )[:80]
    with connection() as db:
        db.execute(
            "INSERT INTO conversations(id,session_id,title,state) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,state=excluded.state",
            (
                state.setdefault("conversation_id", uuid.uuid4().hex),
                sid,
                title,
                json.dumps(state, ensure_ascii=False, default=str),
            ),
        )


def conversations(sid):
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,title,created_at FROM conversations WHERE session_id=? ORDER BY created_at DESC LIMIT 50",
                (sid,),
            ).fetchall()
        ]


def conversation(sid, cid):
    with connection() as db:
        row = db.execute(
            "SELECT state FROM conversations WHERE session_id=? AND id=?", (sid, cid)
        ).fetchone()
    return json.loads(row["state"]) if row else None


def edit_task(sid, task_id, patch):
    with connection() as db:
        row = db.execute(
            "SELECT data FROM records WHERE id=? AND session_id=? AND kind='task'",
            (task_id, sid),
        ).fetchone()
        if not row:
            raise ValueError("Task not found in this workspace")
        original = json.loads(row["data"])
        if original.get("deleted") and "deleted" not in patch:
            raise ValueError("This task was deleted. Restore it first.")
        data = {**original, **patch}
        db.execute(
            "UPDATE records SET data=? WHERE id=? AND session_id=?",
            (json.dumps(data), task_id, sid),
        )
    return {"id": task_id, **data}


def find_record(sid, kind, identifier, *, file_id=False):
    """Owned direct lookup independent of the display list's 100-record limit."""
    with connection() as db:
        clause = "json_extract(data, '$.file_id')=?" if file_id else "id=?"
        row = db.execute(
            "SELECT id,data FROM records WHERE session_id=? AND kind=? AND " + clause,
            (sid, kind, identifier),
        ).fetchone()
    return {"id": row["id"], **json.loads(row["data"])} if row else None


def farmer_id(sid):
    """Trusted session binding; v3 callers authenticate the capability first."""
    from skyview.data.v3.db import enabled

    if not enabled():
        return None
    from . import v3_store

    return v3_store.farmer_id(sid)


def append_event(sid, event):
    from skyview.data.v3.db import enabled

    if enabled():
        from . import v3_store

        v3_store.append_event(sid, event)


def answer_question(sid, pending, answers, cancelled=False):
    from skyview.data.v3.db import enabled

    if enabled():
        from . import v3_store

        v3_store.answer_question(sid, pending, answers, cancelled)


def _dispatch(name, legacy):
    def delegated(*args, **kwargs):
        from skyview.data.v3.db import enabled

        if enabled():
            from . import v3_store

            return getattr(v3_store, name)(*args, **kwargs)
        return legacy(*args, **kwargs)

    delegated.__name__ = name
    return delegated


for _name in (
    "create_session",
    "authenticate",
    "load",
    "save",
    "add_record",
    "records",
    "complete_task",
    "claim_run",
    "release_run",
    "is_running",
    "archive_conversation",
    "conversations",
    "conversation",
    "edit_task",
    "find_record",
):
    globals()[_name] = _dispatch(_name, globals()[_name])


def decide_approval(sid, pending, approved):
    from skyview.data.v3.db import enabled

    if enabled():
        from . import v3_store

        v3_store.decide_approval(sid, pending, approved)
