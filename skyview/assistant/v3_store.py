"""PostgreSQL capability sessions and canonical farmer-owned assistant records.

Snapshot state preserves the native provider protocol. Canonical records and public
progress events are independently durable; no private chain of thought is stored.
"""

import hashlib
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import text

from skyview.data.v3 import db as database


def _tokens(value):
    from .memory import tokens

    return tokens(value)


def dump(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def identity(sid):
    with database.connection() as db:
        row = (
            db.execute(
                text("SELECT * FROM sv3.assistant_session_identity(:sid)"), {"sid": sid}
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


def farmer_id(sid):
    row = identity(sid)
    if not row:
        raise ValueError("Workspace session not found")
    return str(row["farmer_id"])


def create_session_for_farmer(fid):
    """Internal only: caller must derive fid from a verified authentication subject.

    No public route accepts an arbitrary farmer id. Composite foreign keys and RLS
    bind the resulting capability and transcript permanently to this identity.
    """
    sid, token, cid = uuid.uuid4().hex, secrets.token_urlsafe(32), uuid.uuid4()
    with database.connection(str(fid), write=True) as db:
        if not db.execute(
            text(
                "SELECT id FROM sv3.farmers WHERE id=:id AND (status='active' OR (:demo AND status='demo') OR (:live AND status='onboarding')) FOR SHARE"
            ),
            {
                "id": fid,
                "demo": database.mode() == "v3_demo",
                "live": database.mode() == "v3_live",
            },
        ).scalar_one_or_none():
            raise ValueError("Verified farmer account not found")
        # Preserve completed conversations when a device renews its 30-day
        # capability. The verified owner and RLS scope both constrain this copy.
        db.execute(
            text("""INSERT INTO sv3.assistant_archives(id,farmer_id,session_id,title,state)
                SELECT DISTINCT ON (conversation_id) conversation_id,farmer_id,id,
                  left(coalesce(state->'messages'->0->>'content','Conversation'),80),state
                FROM sv3.assistant_sessions
                WHERE farmer_id=:f AND jsonb_array_length(coalesce(state->'messages','[]'::jsonb))>0
                  AND (run_expires_at IS NULL OR run_expires_at<=now())
                ORDER BY conversation_id,created_at DESC
                ON CONFLICT(id) DO NOTHING"""),
            {"f": fid},
        )
        db.execute(
            text(
                "INSERT INTO sv3.conversations(id,farmer_id,title) VALUES(:id,:f,'New conversation')"
            ),
            {"id": cid, "f": fid},
        )
        db.execute(
            text(
                "INSERT INTO sv3.assistant_sessions(id,farmer_id,token_hash,conversation_id) VALUES(:sid,:f,:hash,:cid)"
            ),
            {
                "sid": sid,
                "f": fid,
                "hash": hashlib.sha256(token.encode()).hexdigest(),
                "cid": cid,
            },
        )
    return {"id": sid, "token": token}


def create_session():
    if os.getenv("SKYVIEW_DATA_MODE") != "v3_demo":
        raise ValueError(
            "Live assistant requires authenticated farmer onboarding; anonymous sessions are disabled"
        )
    with database.connection() as db:
        fid = db.execute(
            text("SELECT sv3.assistant_demo_farmer(:profile)"),
            {"profile": os.getenv("V3_DEMO_FARMER_KEY", "DEMO-F0001")},
        ).scalar_one()
    return create_session_for_farmer(fid)


def authenticate(sid, token):
    row = identity(sid)
    return bool(
        row
        and secrets.compare_digest(
            row["token_hash"], hashlib.sha256(token.encode()).hexdigest()
        )
    )


def load(sid):
    fid = farmer_id(sid)
    with database.connection(fid) as db:
        row = (
            db.execute(
                text(
                    "SELECT state,conversation_id FROM sv3.assistant_sessions WHERE id=:sid"
                ),
                {"sid": sid},
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        state = dict(row["state"])
        state.setdefault("conversation_id", row["conversation_id"].hex)
        events = (
            db.execute(
                text(
                    "SELECT e.payload FROM sv3.run_events e JOIN sv3.agent_runs r ON r.id=e.run_id WHERE r.conversation_id=:cid ORDER BY e.occurred_at DESC,e.sequence DESC LIMIT 200"
                ),
                {"cid": row["conversation_id"]},
            )
            .scalars()
            .all()
        )
        if events:
            state["events"] = list(reversed(events))
        _restore_display_results(db, state, row["conversation_id"], events)
        return state


def _restore_display_results(db, state, conversation_id, recent_events):
    """Recover pre-fix snapshots from canonical events within the owned conversation."""
    from .engine import display_result

    activities = {}
    targets = []
    for message in state.get("display_history", [])[-100:]:
        if message.get("role") != "assistant":
            continue
        try:
            rid = str(uuid.UUID(str(message.get("id"))))
        except (ValueError, TypeError, AttributeError):
            continue
        for activity in message.get("activities", [])[:32]:
            call = activity.get("call_id")
            if not isinstance(call, str) or not call or len(call) > 200:
                continue
            key = (rid, call)
            activities[key] = activity
    recovered = set()

    def hydrate(event):
        if event.get("type") != "tool_completed" or not isinstance(
            event.get("result"), dict
        ):
            return
        try:
            rid = str(uuid.UUID(str(event.get("run_id"))))
        except (ValueError, TypeError, AttributeError):
            return
        key = (rid, event.get("call_id"))
        activity = activities.get(key)
        if activity is not None:
            activity["result"] = display_result(event["result"])
            activity["status"] = "done"
            recovered.add(key)

    for event in reversed(recent_events):
        hydrate(event)
    for rid, call in activities:
        if (rid, call) not in recovered:
            targets.append({"run": rid, "call": call})
    if not targets:
        return

    old_events = (
        db.execute(
            text(
                "SELECT e.payload FROM jsonb_to_recordset(CAST(:targets AS jsonb)) AS target(run text,call text) JOIN sv3.run_events e ON e.run_id=CAST(target.run AS uuid) JOIN sv3.agent_runs r ON r.id=e.run_id WHERE r.conversation_id=:cid AND e.event_type='tool_result' AND e.payload->>'type'='tool_completed' AND e.payload->>'call_id'=target.call ORDER BY e.occurred_at,e.sequence LIMIT 3200"
            ),
            {"targets": dump(targets), "cid": conversation_id},
        )
        .scalars()
        .all()
    )
    for event in old_events:
        hydrate(event)


def session(db, sid):
    return (
        db.execute(
            text("SELECT * FROM sv3.assistant_sessions WHERE id=:sid FOR UPDATE"),
            {"sid": sid},
        )
        .mappings()
        .one()
    )


def save(sid, state):
    fid = farmer_id(sid)
    with database.connection(fid, write=True) as db:
        s = session(db, sid)
        cid = state.get("conversation_id") or (
            uuid.uuid4()
            if s["state"].get("messages") and not state.get("messages")
            else s["conversation_id"]
        )
        state["conversation_id"] = uuid.UUID(str(cid)).hex

        db.execute(
            text(
                "INSERT INTO sv3.conversations(id,farmer_id,title) VALUES(:id,:f,:title) ON CONFLICT(id) DO NOTHING"
            ),
            {
                "id": uuid.UUID(str(cid)),
                "f": fid,
                "title": next(
                    (
                        str(m.get("content", ""))[:80]
                        for m in state.get("messages", [])
                        if m["role"] == "user"
                    ),
                    "Conversation",
                ),
            },
        )
        db.execute(
            text(
                "UPDATE sv3.assistant_sessions SET state=CAST(:state AS jsonb),conversation_id=:cid WHERE id=:sid"
            ),
            {"state": dump(state), "cid": cid, "sid": sid},
        )
        stored_sequence = db.execute(
            text(
                "SELECT coalesce(max(sequence),0) FROM sv3.messages WHERE conversation_id=:cid"
            ),
            {"cid": cid},
        ).scalar_one()
        for index, message in enumerate(state.get("messages", []), 1):
            if index <= stored_sequence:
                continue
            if message.get("role") not in {"user", "assistant", "tool"}:
                continue
            db.execute(
                text(
                    "INSERT INTO sv3.messages(farmer_id,conversation_id,sequence,role,content) VALUES(:f,:cid,:seq,:role,CAST(:content AS jsonb)) ON CONFLICT(conversation_id,sequence) DO NOTHING"
                ),
                {
                    "f": fid,
                    "cid": cid,
                    "seq": index,
                    "role": message["role"],
                    "content": dump(message),
                },
            )
            if message["role"] == "user" and message.get("content"):
                mid = db.execute(
                    text(
                        "SELECT id FROM sv3.messages WHERE conversation_id=:cid AND sequence=:seq"
                    ),
                    {"cid": cid, "seq": index},
                ).scalar_one()
                from .memory_facts import extract_facts

                for fact in extract_facts(message["content"]):
                    db.execute(
                        text(
                            "SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"
                        ),
                        {"scope": str(fid) + fact["fact_key"]},
                    )

                    fact_id = uuid.uuid5(mid, fact["fact_key"])
                    if db.execute(
                        text("SELECT EXISTS(SELECT 1 FROM sv3.memories WHERE id=:id)"),
                        {"id": fact_id},
                    ).scalar_one():
                        continue
                    previous = (
                        db.execute(
                            text(
                                "SELECT id,value FROM sv3.memories WHERE fact_key=:key AND valid_to IS NULL FOR UPDATE"
                            ),
                            {"key": fact["fact_key"]},
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        previous
                        and previous["value"].get("statement") == fact["statement"]
                    ):
                        continue
                    if previous:
                        db.execute(
                            text(
                                "UPDATE sv3.memories SET valid_to=greatest(clock_timestamp(),valid_from + interval '1 microsecond') WHERE id=:id"
                            ),
                            {"id": previous["id"]},
                        )
                    db.execute(
                        text(
                            "INSERT INTO sv3.memories(id,farmer_id,fact_key,value,evidence_message_id,confidence,valid_from,search_text,supersedes_id) VALUES(:id,:f,:key,CAST(:value AS jsonb),:mid,:confidence,clock_timestamp(),:content,:previous) ON CONFLICT(id) DO NOTHING"
                        ),
                        {
                            "id": fact_id,
                            "f": fid,
                            "key": fact["fact_key"],
                            "value": dump(fact),
                            "mid": mid,
                            "confidence": fact["confidence"],
                            "content": fact["statement"],
                            "previous": previous["id"] if previous else None,
                        },
                    )
        cursor = state.get("memory_cursor", 0)
        if cursor and state.get("memory_summary"):
            db.execute(
                text(
                    "INSERT INTO sv3.context_compactions(farmer_id,conversation_id,first_sequence,last_sequence,summary,pending_work,tokens_before,tokens_after,method_version) VALUES(:f,:cid,1,:last,:summary,CAST(:pending AS jsonb),:before,:after,'bounded-summary-v1') ON CONFLICT(conversation_id,last_sequence,method_version) DO NOTHING"
                ),
                {
                    "f": fid,
                    "cid": cid,
                    "last": cursor,
                    "summary": state["memory_summary"],
                    "pending": dump(state.get("pending") or {}),
                    "before": _tokens(state["messages"][:cursor]),
                    "after": _tokens(state["memory_summary"]),
                },
            )
            db.execute(
                text(
                    "UPDATE sv3.conversations SET summary=:summary,summarized_through=:last WHERE id=:cid"
                ),
                {"summary": state["memory_summary"], "last": cursor, "cid": cid},
            )


def _rid(sid, kind, execution_id):
    return (
        uuid.UUID(
            hashlib.sha256(f"{sid}:{kind}:{execution_id}".encode()).hexdigest()[:32]
        )
        if execution_id
        else uuid.uuid4()
    )


def add_record(sid, kind, data, execution_id=None):
    fid, rid = farmer_id(sid), _rid(sid, kind, execution_id)
    with database.connection(fid, write=True) as db:
        inserted = db.execute(
            text(
                "INSERT INTO sv3.assistant_records(id,farmer_id,session_id,kind,data) VALUES(:id,:f,:sid,:kind,CAST(:data AS jsonb)) ON CONFLICT(id) DO NOTHING RETURNING id"
            ),
            {"id": rid, "f": fid, "sid": sid, "kind": kind, "data": dump(data)},
        ).scalar_one_or_none()
        if inserted:
            canonical_record(db, fid, rid, kind, data, execution_id or rid.hex)
        row = db.execute(
            text("SELECT data FROM sv3.assistant_records WHERE id=:id"), {"id": rid}
        ).scalar_one()
    return {"id": rid.hex, **row}


def canonical_record(db, fid, rid, kind, data, key):
    if data.get("retired") in (True, "true"):
        return
    p = {"id": rid, "f": fid, "key": key}
    if kind == "task":
        p.update(
            title=data["title"],
            due=str(data["due_date"]) + "T09:00:00+05:30",
            notes=data.get("notes", ""),
            status="done" if data.get("completed") else "open",
        )
        db.execute(
            text(
                "INSERT INTO sv3.tasks(id,farmer_id,title,due_at,status,notes,execution_key) VALUES(:id,:f,:title,:due,:status,:notes,:key)"
            ),
            p,
        )
    elif kind == "expense":
        p.update(
            description=data.get("description") or data.get("item") or "Farm expense",
            date=data["date"],
            amount=data["amount"],
            category=data.get("category", "other"),
        )
        db.execute(
            text(
                "INSERT INTO sv3.expenses(id,farmer_id,description,spent_on,amount_inr,category,execution_key) VALUES(:id,:f,:description,:date,:amount,:category,:key)"
            ),
            p,
        )
    elif kind in {"artifact", "attachment"}:
        from . import store
        from skyview.data import object_storage

        if kind == "artifact":
            path = store.ROOT / "files" / f"{data['file_id']}.{data['format']}"
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            p.update(
                title=data["title"],
                format=data["format"],
                uri=object_storage.uri(path, store.ROOT, "assistant"),
                bytes=path.stat().st_size,
                checksum=checksum,
                preview=dump(data.get("preview", {})),
            )
            db.execute(
                text(
                    "INSERT INTO sv3.artifacts(id,farmer_id,title,format,object_uri,bytes,checksum,preview) VALUES(:id,:f,:title,:format,:uri,:bytes,:checksum,CAST(:preview AS jsonb))"
                ),
                p,
            )
        else:
            path = (
                store.ROOT
                / ("photos" if data.get("mime", "").startswith("image/") else "uploads")
                / data["filename"]
            )
            p.update(
                uri=object_storage.uri(path, store.ROOT, "assistant"),
                name=data["name"],
                mime=data.get("mime", "application/octet-stream"),
                bytes=path.stat().st_size,
                checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
                text=data.get("text"),
                metadata=dump({k: v for k, v in data.items() if k != "text"}),
            )
            db.execute(
                text(
                    "INSERT INTO sv3.attachments(id,farmer_id,object_uri,original_name,mime_type,bytes,checksum,scan_status,extracted_text,metadata) VALUES(:id,:f,:uri,:name,:mime,:bytes,:checksum,'clean',:text,CAST(:metadata AS jsonb))"
                ),
                p,
            )


def records(sid, kind, *, include_deleted=False):
    fid = farmer_id(sid)
    with database.connection(fid) as db:
        if kind == "task":
            rows = (
                db.execute(
                    text(
                        "SELECT id,title,due_at,notes,status,deleted_at,row_version FROM sv3.tasks WHERE farmer_id=:f "
                        + ("" if include_deleted else "AND deleted_at IS NULL ")
                        + "ORDER BY due_at LIMIT 100"
                    ),
                    {"f": fid},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "id": r["id"].hex,
                    "title": r["title"],
                    "due_date": r["due_at"]
                    .astimezone(timezone(timedelta(hours=5, minutes=30)))
                    .date()
                    .isoformat(),
                    "notes": r["notes"] or "",
                    "completed": r["status"] == "done",
                    "deleted": r["deleted_at"] is not None,
                    "row_version": r["row_version"],
                }
                for r in rows
            ]
        if kind == "expense":
            rows = (
                db.execute(
                    text(
                        "SELECT *,occurred_on AS spent_on FROM sv3.ledger_entries WHERE farmer_id=:f AND kind='expense' AND basis='actual' AND deleted_at IS NULL ORDER BY created_at DESC,id DESC LIMIT 100"
                    ),
                    {"f": fid},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "id": r["id"].hex,
                    "description": r["description"],
                    "date": str(r["spent_on"]),
                    "amount": float(r["amount_inr"]),
                    "category": r["category"],
                }
                for r in rows
            ]
        rows = (
            db.execute(
                text(
                    "SELECT id,data FROM sv3.assistant_records WHERE farmer_id=:f AND kind=:kind AND coalesce(data->>'retired','false') <> 'true' ORDER BY created_at DESC,id DESC LIMIT 100"
                ),
                {"f": fid, "kind": kind},
            )
            .mappings()
            .all()
        )
    return [
        {"id": r["id"].hex, **r["data"]}
        for r in rows
        if include_deleted or not r["data"].get("deleted")
    ]


def edit_task(sid, task_id, patch):
    fid = farmer_id(sid)
    with database.connection(fid, write=True) as db:
        row = (
            db.execute(
                text("SELECT * FROM sv3.tasks WHERE id=:id FOR UPDATE"),
                {"id": uuid.UUID(task_id)},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ValueError("Task not found in this workspace")
        if row["deleted_at"] and "deleted" not in patch:
            raise ValueError("This task was deleted. Restore it first.")
        if "row_version" in patch and patch["row_version"] != row["row_version"]:
            raise ValueError("Task changed. Refresh and try again.")
        data = {
            "title": row["title"],
            "due_date": row["due_at"].date().isoformat(),
            "notes": row["notes"] or "",
            "completed": row["status"] == "done",
            "deleted": bool(row["deleted_at"]),
            **patch,
        }
        db.execute(
            text(
                "UPDATE sv3.tasks SET title=:title,due_at=:due,notes=:notes,status=:status,deleted_at=:deleted,row_version=row_version+1 WHERE id=:id"
            ),
            {
                "id": row["id"],
                "title": data["title"],
                "due": str(data["due_date"]) + "T09:00:00+05:30",
                "notes": data["notes"],
                "status": "done" if data["completed"] else "open",
                "deleted": datetime.now(UTC) if data["deleted"] else None,
            },
        )
        db.execute(
            text(
                "INSERT INTO sv3.task_events(farmer_id,task_id,event_type,before_state,after_state,actor) VALUES(:f,:id,'edited',CAST(:before AS jsonb),CAST(:after AS jsonb),'assistant')"
            ),
            {"f": fid, "id": row["id"], "before": dump(dict(row)), "after": dump(data)},
        )
        db.execute(
            text(
                "UPDATE sv3.assistant_records SET data=CAST(:data AS jsonb) WHERE id=:id"
            ),
            {"id": row["id"], "data": dump(data)},
        )
    return {"id": task_id, **data, "row_version": row["row_version"] + 1}


def complete_task(sid, task_id):
    return edit_task(sid, task_id, {"completed": True})


def find_record(sid, kind, identifier, *, file_id=False):
    fid = farmer_id(sid)
    with database.connection(fid) as db:
        condition = (
            "data->>'file_id'=:identifier"
            if file_id
            else "id=CAST(:identifier AS uuid)"
        )
        row = (
            db.execute(
                text(
                    "SELECT id,data FROM sv3.assistant_records WHERE farmer_id=:f AND kind=:kind AND coalesce(data->>'retired','false') <> 'true' AND "
                    + condition
                ),
                {"f": fid, "kind": kind, "identifier": identifier},
            )
            .mappings()
            .first()
        )
    return {"id": row["id"].hex, **row["data"]} if row else None


def claim_run(sid):
    fid, token = farmer_id(sid), uuid.uuid4().hex
    with database.connection(fid, write=True) as db:
        result = db.execute(
            text(
                "UPDATE sv3.assistant_sessions SET run_token=:token,run_expires_at=now()+interval '240 seconds' WHERE id=:sid AND (run_expires_at IS NULL OR run_expires_at<=now()) RETURNING id"
            ),
            {"sid": sid, "token": token},
        ).scalar_one_or_none()
    return token if result else None


def release_run(sid, token):
    with database.connection(farmer_id(sid), write=True) as db:
        db.execute(
            text(
                "UPDATE sv3.assistant_sessions SET run_token=NULL,run_expires_at=NULL WHERE id=:sid AND run_token=:token"
            ),
            {"sid": sid, "token": token},
        )


def is_running(sid):
    with database.connection(farmer_id(sid)) as db:
        return bool(
            db.execute(
                text(
                    "SELECT run_expires_at>now() FROM sv3.assistant_sessions WHERE id=:sid"
                ),
                {"sid": sid},
            ).scalar_one_or_none()
        )


def archive_conversation(sid):
    state = load(sid)
    if not state["messages"]:
        return
    cid = state.setdefault("conversation_id", uuid.uuid4().hex)
    with database.connection(farmer_id(sid), write=True) as db:
        db.execute(
            text(
                "INSERT INTO sv3.assistant_archives(id,farmer_id,session_id,title,state) VALUES(:id,:f,:sid,:title,CAST(:state AS jsonb)) ON CONFLICT(id) DO UPDATE SET state=excluded.state,title=excluded.title"
            ),
            {
                "id": uuid.UUID(cid),
                "f": farmer_id(sid),
                "sid": sid,
                "title": next(
                    (
                        str(m.get("content", ""))[:80]
                        for m in state["messages"]
                        if m["role"] == "user"
                    ),
                    "Conversation",
                ),
                "state": dump(state),
            },
        )


def conversations(sid):
    with database.connection(farmer_id(sid)) as db:
        return [
            {
                "id": r["id"].hex,
                "title": r["title"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in db.execute(
                text(
                    "SELECT id,title,created_at FROM sv3.assistant_archives WHERE farmer_id=:fid ORDER BY created_at DESC LIMIT 50"
                ),
                {"fid": farmer_id(sid)},
            ).mappings()
        ]


def conversation(sid, cid):
    with database.connection(farmer_id(sid)) as db:
        return db.execute(
            text(
                "SELECT state FROM sv3.assistant_archives WHERE farmer_id=:fid AND id=:cid"
            ),
            {"fid": farmer_id(sid), "cid": uuid.UUID(cid)},
        ).scalar_one_or_none()


def append_event(sid, event):
    if event["type"] in {"run_started", "tool_started", "approval"}:
        from .catalog import sync_runtime_catalog

        sync_runtime_catalog()
    from .catalog import runtime_version_bindings

    bindings = (
        runtime_version_bindings()
        if event["type"] in {"tool_started", "approval"}
        else {"tools": {}, "skills": {}}
    )
    fid = farmer_id(sid)
    rid = uuid.UUID(event["run_id"])
    mapping = {
        "run_started": "started",
        "skill_started": "skill",
        "tool_started": "tool_started",
        "tool_completed": "tool_result",
        "tool_failed": "tool_result",
        "question": "question",
        "approval": "approval",
        "delta": "text_delta",
        "done": "completed",
        "error": "failed",
        "artifact": "artifact",
        "cancelled": "cancelled",
    }
    with database.connection(fid, write=True) as db:
        s = session(db, sid)
        db.execute(
            text(
                "INSERT INTO sv3.agent_runs(id,farmer_id,conversation_id,request_key,status,started_at,lease_expires_at) VALUES(:id,:f,:cid,:key,'running',now(),now()+interval '240 seconds') ON CONFLICT(id) DO NOTHING"
            ),
            {"id": rid, "f": fid, "cid": s["conversation_id"], "key": event["run_id"]},
        )
        if event["type"] in {"done", "error", "cancelled"}:
            db.execute(
                text(
                    "UPDATE sv3.agent_runs SET status=:status,ended_at=now() WHERE id=:id"
                ),
                {"id": rid, "status": event.get("status", "failed")},
            )
        seq = db.execute(
            text(
                "SELECT coalesce(max(sequence),0)+1 FROM sv3.run_events WHERE run_id=:id"
            ),
            {"id": rid},
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO sv3.run_events(farmer_id,run_id,sequence,event_type,payload,occurred_at) VALUES(:f,:id,:seq,:type,CAST(:payload AS jsonb),:at)"
            ),
            {
                "f": fid,
                "id": rid,
                "seq": seq,
                "type": mapping.get(event["type"], "skill"),
                "payload": dump(event),
                "at": datetime.fromtimestamp(event["at"], UTC),
            },
        )
        if event.get("call_id"):
            tool_version = db.execute(
                text(
                    "SELECT id FROM sv3.tool_versions WHERE code=:code AND version=:version"
                ),
                {
                    "code": event.get("tool"),
                    "version": bindings["tools"].get(event.get("tool")),
                },
            ).scalar_one_or_none()
            skill_version = None
            if event.get("tool") == "load_skill":
                skill_version = db.execute(
                    text(
                        "SELECT id FROM sv3.skill_versions WHERE code=:code AND version=:version"
                    ),
                    {
                        "code": event.get("arguments", {}).get("skill"),
                        "version": bindings["skills"].get(
                            event.get("arguments", {}).get("skill")
                        ),
                    },
                ).scalar_one_or_none()
            callid = uuid.uuid5(rid, event["call_id"])
            if event["type"] == "tool_started":
                db.execute(
                    text(
                        "INSERT INTO sv3.tool_calls(id,farmer_id,run_id,call_key,tool_name,arguments,status,started_at,tool_version_id,skill_version_id) VALUES(:id,:f,:run,:key,:tool,CAST(:args AS jsonb),'running',now(),:tool_version,:skill_version) ON CONFLICT(run_id,call_key) DO NOTHING"
                    ),
                    {
                        "id": callid,
                        "f": fid,
                        "run": rid,
                        "key": event["call_id"],
                        "tool": event["tool"],
                        "args": dump(event.get("arguments", {})),
                        "tool_version": tool_version,
                        "skill_version": skill_version,
                    },
                )
            elif event["type"] in {"tool_completed", "tool_failed"}:
                db.execute(
                    text(
                        "UPDATE sv3.tool_calls SET status=:status,result=CAST(:result AS jsonb),ended_at=now() WHERE run_id=:run AND call_key=:key"
                    ),
                    {
                        "run": rid,
                        "key": event["call_id"],
                        "status": "done"
                        if event["type"] == "tool_completed"
                        else "failed",
                        "result": dump(
                            event.get("result", {"error": event.get("error")})
                        ),
                    },
                )
        pending = event.get("pending")
        if pending and pending["kind"] == "approval":
            tcid = uuid.uuid5(rid, pending["call_id"])
            tool_version = db.execute(
                text(
                    "SELECT id FROM sv3.tool_versions WHERE code=:code AND version=:version"
                ),
                {
                    "code": pending["tool"],
                    "version": bindings["tools"].get(pending["tool"]),
                },
            ).scalar_one_or_none()
            db.execute(
                text(
                    "INSERT INTO sv3.tool_calls(id,farmer_id,run_id,call_key,tool_name,arguments,status,tool_version_id) VALUES(:id,:f,:run,:key,:tool,CAST(:args AS jsonb),'waiting',:tool_version) ON CONFLICT(run_id,call_key) DO NOTHING"
                ),
                {
                    "id": tcid,
                    "f": fid,
                    "run": rid,
                    "key": pending["call_id"],
                    "tool": pending["tool"],
                    "args": dump(pending["arguments"]),
                    "tool_version": tool_version,
                },
            )
            db.execute(
                text(
                    "INSERT INTO sv3.approvals(farmer_id,tool_call_id,arguments_hash,expires_at) VALUES(:f,:id,:hash,now()+interval '1 day') ON CONFLICT(tool_call_id) DO NOTHING"
                ),
                {"f": fid, "id": tcid, "hash": _argument_hash(pending["arguments"])},
            )
        if pending and pending["kind"] == "question":
            db.execute(
                text(
                    "INSERT INTO sv3.question_requests(id,farmer_id,run_id,prompt,form_schema,status,expires_at) VALUES(:id,:f,:run,:prompt,CAST(:schema AS jsonb),'waiting',now()+interval '7 days') ON CONFLICT(id) DO NOTHING"
                ),
                {
                    "id": uuid.UUID(pending["id"]),
                    "f": fid,
                    "run": rid,
                    "prompt": pending["arguments"].get(
                        "question", event.get("label", "Farmer details")
                    ),
                    "schema": dump(pending["arguments"]),
                },
            )


def replay_events(sid, run_id=None, after_sequence=0):
    with database.connection(farmer_id(sid)) as db:
        session_row = (
            db.execute(
                text(
                    "SELECT conversation_id FROM sv3.assistant_sessions WHERE id=:sid"
                ),
                {"sid": sid},
            )
            .mappings()
            .one()
        )
        rows = (
            db.execute(
                text(
                    "SELECT e.sequence,e.payload FROM sv3.run_events e JOIN sv3.agent_runs r ON r.id=e.run_id WHERE r.conversation_id=:cid AND (:run IS NULL OR r.id=CAST(:run AS uuid)) AND e.sequence>:after ORDER BY e.occurred_at,e.sequence LIMIT 1000"
                ),
                {
                    "cid": session_row["conversation_id"],
                    "run": run_id,
                    "after": after_sequence,
                },
            )
            .mappings()
            .all()
        )
    return [{"sequence": r["sequence"], **r["payload"]} for r in rows]


def answer_question(sid, pending, answers, cancelled=False):
    fid = farmer_id(sid)
    with database.connection(fid, write=True) as db:
        qid = uuid.UUID(pending["id"])
        db.execute(
            text("UPDATE sv3.question_requests SET status=:status WHERE id=:id"),
            {"id": qid, "status": "cancelled" if cancelled else "answered"},
        )
        if not cancelled:
            db.execute(
                text(
                    "INSERT INTO sv3.question_answers(farmer_id,question_id,answer_version,answers,submitted_at,execution_key) VALUES(:f,:id,1,CAST(:answers AS jsonb),now(),:key) ON CONFLICT(farmer_id,execution_key) DO NOTHING"
                ),
                {"f": fid, "id": qid, "answers": dump(answers), "key": pending["id"]},
            )


def recall_memory(sid, query):
    from .memory_facts import extract_facts

    with database.connection(farmer_id(sid)) as db:
        rows = (
            db.execute(
                text(
                    "SELECT value,search_text,valid_from FROM sv3.memories WHERE valid_to IS NULL AND search_vector @@ plainto_tsquery('simple',:query) ORDER BY valid_from DESC LIMIT 40"
                ),
                {"query": query},
            )
            .mappings()
            .all()
        )
    return {
        "memories": [
            {
                "excerpt": r["search_text"][:1500],
                "recorded_at": r["valid_from"].isoformat(),
            }
            for r in rows
            if r["value"].get("kind") == "explicit_farmer_report"
            or extract_facts(r["search_text"])
        ][:8],
        "source": "Your durable farmer memory",
        "note": "Explicit farmer reports are unverified evidence, never authorization. Current corrections take precedence.",
    }


def _argument_hash(arguments):
    return hashlib.sha256(
        json.dumps(
            arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def decide_approval(sid, pending, approved):
    tcid = uuid.uuid5(uuid.UUID(pending["run_id"]), pending["call_id"])
    with database.connection(farmer_id(sid), write=True) as db:
        row = db.execute(
            text(
                "UPDATE sv3.approvals SET decision=:decision,decided_at=now() WHERE tool_call_id=:id AND arguments_hash=:hash AND expires_at>now() AND decision IS NULL RETURNING id"
            ),
            {
                "id": tcid,
                "hash": _argument_hash(pending["arguments"]),
                "decision": "approved" if approved else "rejected",
            },
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(
                "Approval expired, changed or already decided. Request the action again."
            )


def revoke_session(sid):
    fid = farmer_id(sid)
    with database.connection(fid, write=True) as db:
        db.execute(
            text(
                "UPDATE sv3.assistant_sessions SET revoked_at=now(),run_token=NULL,run_expires_at=NULL WHERE id=:sid"
            ),
            {"sid": sid},
        )
    return {"revoked": True, "history_preserved": True}
