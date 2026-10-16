"""Repair missing canonical file metadata from owned assistant records.

Dry-run by default. Original file bytes are read only from the explicit legacy root.
Existing destination files and existing canonical rows are never overwritten.
"""

import argparse
import json
import mimetypes
import os
import re
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from skyview.data.v3 import db as database


def _file(root, folder, name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", name):
        raise ValueError("Unsafe file name")
    path = root / folder / name
    if (root / folder).is_symlink() or path.is_symlink():
        raise ValueError("Symbolic links are not accepted")
    return path


def _plan(row, source, destination):
    data = dict(row["data"])
    if row["kind"] == "artifact":
        name = f"{data['file_id']}.{data['format']}"
        folder = "files"
    else:
        name = data.get("filename")
        if not name:
            if not isinstance(data.get("text"), str):
                raise ValueError(
                    "Neither original file nor extracted text is available"
                )
            name = row["id"].hex + ".txt"
            data.update(
                filename=name, mime="text/plain", legacy_original_bytes_unavailable=True
            )
        mime = (
            data.get("mime")
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream"
        )
        data["mime"] = mime
        folder = "photos" if mime.startswith("image/") else "uploads"
    target = _file(destination, folder, name)
    legacy_paths = [_file(root, folder, name) for root in source]
    legacy = next((path for path in legacy_paths if path.is_file()), None)
    payload = None
    origin = "existing"
    if target.exists():
        if not target.is_file():
            raise ValueError("Destination is not a regular file")
    elif legacy is not None:
        payload = legacy.read_bytes()
        origin = "legacy"
    elif (
        row["kind"] == "attachment"
        and data.get("legacy_original_bytes_unavailable")
        and isinstance(data.get("text"), str)
    ):
        payload = data["text"].encode("utf-8")
        origin = "extracted_text"
    else:
        raise ValueError("Original file is missing from both storage roots")
    if row["kind"] == "attachment":
        data["size"] = target.stat().st_size if payload is None else len(payload)
    return target, payload, data, origin


def reconcile_files(
    source: Path | list[Path],
    destination: Path,
    *,
    apply=False,
    farmer_id=None,
    session_id=None,
):
    """Insert only absent canonical rows; one transaction/file with rollback cleanup."""
    if database.mode() != "v3_demo":
        raise ValueError("Local file reconciliation requires v3_demo mode")
    source = [
        root.resolve() for root in (source if isinstance(source, list) else [source])
    ]
    destination = destination.resolve()
    if session_id and not farmer_id:
        from . import v3_store

        farmer_id = v3_store.farmer_id(session_id)
    if farmer_id:
        owners = [str(farmer_id)]
    else:
        with database.connection(ingest=True) as db:
            owners = (
                db.execute(text("SELECT id FROM sv3.farmers ORDER BY id"))
                .scalars()
                .all()
            )
    rows = []
    for owner in owners:
        with database.connection(str(owner)) as db:
            rows.extend(
                db.execute(
                    text("""
                SELECT r.id,r.farmer_id,r.session_id,r.kind,r.data,
                       CASE WHEN r.kind='artifact' THEN a.id ELSE u.id END AS canonical_id
                FROM sv3.assistant_records r
                LEFT JOIN sv3.artifacts a ON a.id=r.id AND a.farmer_id=r.farmer_id
                LEFT JOIN sv3.attachments u ON u.id=r.id AND u.farmer_id=r.farmer_id
                WHERE r.kind IN ('artifact','attachment') AND r.farmer_id=CAST(:farmer AS uuid)
                  AND (CAST(:session AS text) IS NULL OR r.session_id=:session)
                ORDER BY r.id
            """),
                    {"farmer": str(owner), "session": session_id},
                )
                .mappings()
                .all()
            )
    report = {
        "apply": apply,
        "existing": 0,
        "retired": 0,
        "ready": 0,
        "repaired": 0,
        "failed": 0,
        "files": [],
    }
    for record in rows:
        if record["data"].get("retired") in (True, "true"):
            report["retired"] += 1
            continue
        if record["canonical_id"]:
            report["existing"] += 1
            continue
        detail = {"id": record["id"].hex, "kind": record["kind"]}
        created = None
        try:
            target, payload, data, origin = _plan(record, source, destination)
            detail.update(path=str(target), recovery=origin)
            report["ready"] += 1
            if apply:
                from . import store, v3_store

                original_root = store.ROOT
                try:
                    with database.connection(
                        str(record["farmer_id"]), write=True
                    ) as db:
                        current = db.execute(
                            text(
                                "SELECT data FROM sv3.assistant_records WHERE id=:id AND farmer_id=:f FOR UPDATE"
                            ),
                            {"id": record["id"], "f": record["farmer_id"]},
                        ).scalar_one()
                        if current.get("retired") in (True, "true"):
                            detail["status"] = "retired"
                            report["retired"] += 1
                            report["files"].append(detail)
                            continue
                        table = (
                            "artifacts"
                            if record["kind"] == "artifact"
                            else "attachments"
                        )
                        if db.execute(
                            text(f"SELECT id FROM sv3.{table} WHERE id=:id"),
                            {"id": record["id"]},
                        ).scalar_one_or_none():
                            detail["status"] = "already_repaired"
                            report["files"].append(detail)
                            continue
                        target, payload, data, origin = _plan(
                            {**record, "data": current}, source, destination
                        )
                        if payload is not None:
                            target.parent.mkdir(parents=True, exist_ok=True)

                            with target.open("xb") as handle:
                                created = target
                                handle.write(payload)
                        store.ROOT = destination
                        v3_store.canonical_record(
                            db,
                            str(record["farmer_id"]),
                            record["id"],
                            record["kind"],
                            data,
                            "legacy:" + record["id"].hex,
                        )
                        if data != current:
                            db.execute(
                                text(
                                    "UPDATE sv3.assistant_records SET data=CAST(:data AS jsonb) WHERE id=:id"
                                ),
                                {"id": record["id"], "data": v3_store.dump(data)},
                            )
                    report["repaired"] += 1
                finally:
                    store.ROOT = original_root
            detail["status"] = "repaired" if apply else "ready"
        except (OSError, ValueError, KeyError, TypeError, SQLAlchemyError) as error:
            if created is not None:
                created.unlink(missing_ok=True)
            report["failed"] += 1
            detail.update(status="failed", error=str(error))
        report["files"].append(detail)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        required=True,
        help="Explicit legacy root; repeat for multiple original storage roots",
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for key, value in dotenv_values(args.env).items():
        if value is not None:
            os.environ[key] = value
    report = reconcile_files(args.source, args.destination, apply=args.apply)
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
