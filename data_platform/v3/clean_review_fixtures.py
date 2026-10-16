"""Remove identified local review fixtures; preserve seeded farming data and user history."""

import argparse
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from data_platform.v3.provision import sql

DATABASE = "skyview_v3_demo"
ROOT = Path(__file__).resolve().parents[2]
OWNER = "(SELECT id FROM sv3.farmers WHERE profile_key='DEMO-F0001')"
TARGETS = {
    "attachments": f"farmer_id={OWNER} AND original_name IN ('integration-test.docx','integration-test.txt','public-vision-test.png','synthetic-leaf.png','synthetic-receipt.png')",
    "artifacts": f"farmer_id={OWNER} AND title IN ('Public Sample','Public Test','Software integration test','Sample field checklist','Farm Budget')",
    "tasks": f"farmer_id={OWNER} AND title IN ('Public calendar test','Inspect wheat field')",
    "ledger_entries": "description='Visual QA · estimated seed cost'",
    "exchange_listings": "title IN ('Demo sprayer swap · UI acceptance test','Demo labour offer · UI test')",
    "memories": f"farmer_id={OWNER} AND (search_text ~* '(public (synthetic |commodity |calendar |test)|integration test|lavender on the north plot|Seeds,2,100|seeds quantity 2 at Rs 100|save a task to inspect my wheat field|How can you help me edit this calendar|Briefly explain how to edit my calendar|What can I edit here)' OR search_text='Help me create an Excel farm budget from my actual costs.')",
    "assistant_archives": f"farmer_id={OWNER} AND (title ~* '(public |lavender on the north plot)' OR title='Help me create an Excel farm budget from my actual costs.')",
}


def ids_clause(ids):

    return "(" + ",".join("'" + str(uuid.UUID(str(i))) + "'::uuid" for i in ids) + ")"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    records = {}
    for table, condition in TARGETS.items():
        records[table] = json.loads(
            sql(
                f"SELECT coalesce(json_agg(t),'[]'::json) FROM sv3.{table} t WHERE {condition}",
                DATABASE,
            )
        )

    retired_ids = {
        row["id"]
        for table in ("artifacts", "attachments", "tasks")
        for row in records[table]
    }
    for previous in (ROOT / ".v3-data").glob("review-fixture-backup-*.json"):
        archived = json.loads(previous.read_text())
        for table in ("artifacts", "attachments", "tasks", "assistant_records"):
            retired_ids.update(row["id"] for row in archived.get(table, []))
    records["assistant_records"] = (
        json.loads(
            sql(
                f"SELECT coalesce(json_agg(t),'[]'::json) FROM sv3.assistant_records t WHERE farmer_id={OWNER} AND id IN {ids_clause(retired_ids)} AND coalesce(data->>'retired','false')<>'true'",
                DATABASE,
            )
        )
        if retired_ids
        else []
    )
    print(
        json.dumps(
            {
                "database": DATABASE,
                "identified": {t: len(rows) for t, rows in records.items()},
                "applied": False,
            }
        )
    )
    if not args.apply:
        return
    backup = (
        ROOT
        / ".v3-data"
        / (
            "review-fixture-backup-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            + ".json"
        )
    )
    backup.write_text(json.dumps(records, ensure_ascii=False))
    os.chmod(backup, 0o600)
    statements = ["BEGIN;"]
    if records["assistant_records"]:
        selected = ids_clause([row["id"] for row in records["assistant_records"]])
        statements.append(
            f"UPDATE sv3.assistant_records SET data=data || jsonb_build_object('retired',true,'retired_reason','local_review_fixture','retired_at',now()) WHERE id IN {selected};"
        )
    listings = [r["id"] for r in records["exchange_listings"]]
    if listings:
        selected = ids_clause(listings)
        conversations = (
            f"SELECT id FROM sv3.exchange_conversations WHERE listing_id IN {selected}"
        )
        statements += [
            f"DELETE FROM sv3.exchange_events WHERE conversation_id IN ({conversations});",
            f"DELETE FROM sv3.exchange_messages WHERE conversation_id IN ({conversations});",
            f"DELETE FROM sv3.exchange_conversations WHERE listing_id IN {selected};",
        ]
    tasks = [r["id"] for r in records["tasks"]]
    if tasks:
        selected = ids_clause(tasks)
        statements += [
            f"DELETE FROM sv3.notifications WHERE task_id IN {selected};",
            f"DELETE FROM sv3.task_events WHERE task_id IN {selected};",
        ]
    memories = [r["id"] for r in records["memories"]]
    if memories:
        statements.append(
            f"UPDATE sv3.memories SET supersedes_id=NULL WHERE supersedes_id IN {ids_clause(memories)};"
        )
    attachments = [r["id"] for r in records["attachments"]]
    if attachments:
        selected = ids_clause(attachments)
        statements += [
            f"UPDATE sv3.field_observations SET attachment_id=NULL WHERE attachment_id IN {selected};",
            f"UPDATE sv3.disease_cases SET attachment_id=NULL WHERE attachment_id IN {selected};",
        ]
    for table, rows in records.items():
        if rows and table != "assistant_records":
            statements.append(
                f"DELETE FROM sv3.{table} WHERE id IN {ids_clause([r['id'] for r in rows])};"
            )
    statements.append("COMMIT;")
    sql("\n".join(statements), DATABASE)
    files_root = (ROOT / ".v3-data/assistant/files").resolve()
    retired = ROOT / ".v3-data/review-fixture-files"
    retired.mkdir(mode=0o700, exist_ok=True)
    for record in records["artifacts"] + records["attachments"]:
        path = Path(record["object_uri"])
        uploads_root = (ROOT / ".v3-data/assistant/uploads").resolve()
        if (
            path.exists()
            and not path.is_symlink()
            and path.resolve().parent in (files_root, uploads_root)
        ):
            shutil.move(str(path), str(retired / path.name))
    print(
        json.dumps(
            {
                "applied": True,
                "backup": backup.name,
                "removed": {
                    t: len(rows)
                    for t, rows in records.items()
                    if t != "assistant_records"
                },
                "retired_chat_records": len(records["assistant_records"]),
            }
        )
    )


if __name__ == "__main__":
    main()
