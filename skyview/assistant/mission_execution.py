"""Link reviewed missions to actual assistant runs, without claiming field execution."""

import json
import uuid

from sqlalchemy import text

from skyview.data.v3 import db, repository

from . import store


def context(sid: str, identifier: str):
    if not db.enabled():
        raise ValueError("Mission work requires the unified farm workspace.")
    owner = store.farmer_id(sid)
    with db.connection(owner) as conn:
        row = (
            conn.execute(
                text(
                    "SELECT id,title,objective,status,steps FROM sv3.farm_missions WHERE id=:id"
                ),
                {"id": identifier},
            )
            .mappings()
            .first()
        )
    if not row:
        raise ValueError("This farm plan is unavailable in your workspace.")
    if row["status"] in {"paused", "cancelled", "completed"}:
        raise ValueError(
            "Resume this plan or create a new one before asking Mitra to work on it."
        )
    return repository.clean(dict(row))


def record_run(sid: str, identifier: str, run_id: str, status: str, activities):
    owner = store.farmer_id(sid)
    material = {
        "run_id": run_id,
        "status": status,
        "steps": [
            {
                "tool": a["tool"],
                "status": a["status"],
                **(
                    {
                        "file_title": a["result"]["artifact"]["title"],
                        "file_id": a["result"]["artifact"]["file_id"],
                    }
                    if a.get("result", {}).get("artifact")
                    else {}
                ),
            }
            for a in activities
        ],
        "note": "Assistant workspace actions only. Checklist completion, physical work, payments and external deliveries are not inferred.",
    }
    receipt_id = uuid.uuid5(
        uuid.UUID(owner), "mission-run:" + identifier + ":" + run_id
    )
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.mission_receipts(id,farmer_id,mission_id,action,detail) VALUES(:id,:owner,:mission,'assistant_run',:detail) ON CONFLICT(id) DO NOTHING"
            ),
            {
                "id": str(receipt_id),
                "owner": owner,
                "mission": identifier,
                "detail": json.dumps(material),
            },
        )
