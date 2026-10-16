"""Explicit, repeat-safe import of existing local capability workspaces into DEMO.

Never reads plaintext tokens; source SQLite and source file bytes remain untouched.
Run: python -m skyview.assistant.v3_import --env .v3-data/runtime.env
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import uuid
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text

from skyview.data.v3 import db as database


def safe_copy(source, destination, relative):
    name = Path(relative).name
    if name != relative or not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", name):
        raise ValueError("Unsafe legacy file name")
    src = source / name
    if src.is_symlink() or not src.is_file():
        raise ValueError("Legacy file is missing or is a symbolic link")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name
    if not target.exists():
        shutil.copy2(src, target)
    return target


def migrate(source, destination):
    if database.mode() != "v3_demo":
        raise ValueError("Legacy anonymous workspace import is allowed only in v3_demo")
    from . import store, v3_store

    store.ROOT = destination.resolve()
    if not (source / "assistant.db").is_file():
        return {"sessions": 0, "records": 0, "archives": 0}
    with database.connection() as db:
        fid = db.execute(
            text("SELECT sv3.assistant_demo_farmer(:profile)"),
            {"profile": os.getenv("V3_DEMO_FARMER_KEY", "DEMO-F0001")},
        ).scalar_one()
    counts = {"sessions": 0, "records": 0, "archives": 0}
    with sqlite3.connect(f"file:{source / 'assistant.db'}?mode=ro", uri=True) as legacy:
        legacy.row_factory = sqlite3.Row
        for old in legacy.execute("SELECT * FROM sessions"):
            if not re.fullmatch(r"[a-f0-9]{32}", old["id"]) or not re.fullmatch(
                r"[a-f0-9]{64}", old["token_hash"] or ""
            ):
                continue
            sid = old["id"]
            state = json.loads(old["state"])
            cid = uuid.UUID(
                state.get("conversation_id")
                or uuid.uuid5(uuid.UUID(sid), "active-conversation").hex
            )
            with database.connection(str(fid), write=True) as db:
                existing = (
                    db.execute(
                        text(
                            "SELECT legacy_imported_at FROM sv3.assistant_sessions WHERE id=:sid"
                        ),
                        {"sid": sid},
                    )
                    .mappings()
                    .first()
                )
                if existing and existing["legacy_imported_at"] is not None:
                    # Older imports may have durable records but no canonical file rows.
                    # Never replay session state over newer conversations during repair.
                    from .v3_reconcile import reconcile_files

                    report = reconcile_files(
                        source, destination, apply=True, farmer_id=fid, session_id=sid
                    )
                    if report["failed"]:
                        raise ValueError(
                            "Imported file reconciliation failed; run v3_reconcile for details"
                        )
                    continue
                if not existing:
                    db.execute(
                        text(
                            "INSERT INTO sv3.conversations(id,farmer_id,title) VALUES(:id,:f,'Imported workspace') ON CONFLICT(id) DO NOTHING"
                        ),
                        {"id": cid, "f": fid},
                    )
                    db.execute(
                        text(
                            "INSERT INTO sv3.assistant_sessions(id,farmer_id,token_hash,conversation_id) VALUES(:sid,:f,:hash,:cid)"
                        ),
                        {"sid": sid, "f": fid, "hash": old["token_hash"], "cid": cid},
                    )
            for archive in legacy.execute(
                "SELECT * FROM conversations WHERE session_id=?", (sid,)
            ):
                saved = json.loads(archive["state"])
                saved["conversation_id"] = archive["id"]
                v3_store.save(sid, saved)
                with database.connection(str(fid), write=True) as db:
                    db.execute(
                        text(
                            "INSERT INTO sv3.assistant_archives(id,farmer_id,session_id,title,state) VALUES(:id,:f,:sid,:title,CAST(:state AS jsonb)) ON CONFLICT(id) DO NOTHING"
                        ),
                        {
                            "id": uuid.UUID(archive["id"]),
                            "f": fid,
                            "sid": sid,
                            "title": archive["title"],
                            "state": v3_store.dump(saved),
                        },
                    )
                counts["archives"] += 1
            state["conversation_id"] = cid.hex
            v3_store.save(sid, state)
            for record in legacy.execute(
                "SELECT * FROM records WHERE session_id=?", (sid,)
            ):
                data = json.loads(record["data"])
                rid = uuid.UUID(record["id"])
                kind = record["kind"]
                with database.connection(str(fid)) as db:
                    current = db.execute(
                        text("SELECT data FROM sv3.assistant_records WHERE id=:id"),
                        {"id": rid},
                    ).scalar_one_or_none()
                if (
                    data.get("retired") in (True, "true")
                    or current
                    and current.get("retired") in (True, "true")
                ):
                    continue
                if kind == "artifact":
                    safe_copy(
                        source / "files",
                        destination / "files",
                        f"{data['file_id']}.{data['format']}",
                    )
                elif kind == "attachment":
                    if data.get("filename"):
                        safe_copy(
                            source / "photos", destination / "photos", data["filename"]
                        )
                    else:
                        # Old uploads kept only extracted text, so never invent original PDF/Office bytes.
                        filename = rid.hex + ".txt"
                        folder = destination / "uploads"
                        folder.mkdir(parents=True, exist_ok=True)
                        payload = (
                            data.get("text") or "[No legacy extracted text]"
                        ).encode("utf-8")
                        (folder / filename).write_bytes(payload)
                        data.update(
                            filename=filename,
                            mime="text/plain",
                            size=len(payload),
                            legacy_original_bytes_unavailable=True,
                        )
                with database.connection(str(fid), write=True) as db:
                    exists = db.execute(
                        text("SELECT id FROM sv3.assistant_records WHERE id=:id"),
                        {"id": rid},
                    ).scalar_one_or_none()
                    if exists:
                        continue
                    db.execute(
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
                    v3_store.canonical_record(
                        db, str(fid), rid, kind, data, "legacy:" + rid.hex
                    )
                if kind == "task" and data.get("deleted"):
                    v3_store.edit_task(sid, rid.hex, {"deleted": True})
                counts["records"] += 1
            # Interrupted old imports can also leave existing record IDs without
            # canonical file rows before the session's imported marker is set.
            from .v3_reconcile import reconcile_files

            report = reconcile_files(
                source, destination, apply=True, farmer_id=fid, session_id=sid
            )
            if report["failed"]:
                raise ValueError(
                    "Imported file reconciliation failed; run v3_reconcile for details"
                )
            with database.connection(str(fid), write=True) as db:
                db.execute(
                    text(
                        "UPDATE sv3.assistant_sessions SET legacy_imported_at=now() WHERE id=:sid"
                    ),
                    {"sid": sid},
                )
            counts["sessions"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=Path(".assistant-data"))
    parser.add_argument("--destination", type=Path, default=Path(".v3-data/assistant"))
    args = parser.parse_args()
    for key, value in dotenv_values(args.env).items():
        if value is not None:
            os.environ[key] = value
    print(json.dumps(migrate(args.source.resolve(), args.destination.resolve())))


if __name__ == "__main__":
    main()
