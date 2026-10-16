"""Read-only local readiness report. No seed/reset, credentials, or farmer content in output."""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
for key, value in dotenv_values(ROOT / ".v3-data/runtime.env").items():
    if value is not None:
        os.environ[key] = value

from skyview.data.v3 import db, repository


def main():
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "mode": db.mode(),
        "reads": [],
    }
    with db.connection() as conn:
        owner = conn.execute(
            text("SELECT sv3.assistant_demo_farmer(:key)"),
            {"key": os.getenv("V3_DEMO_FARMER_KEY", "DEMO-F0001")},
        ).scalar()
        report["database_bytes"] = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar()
        report["crops"] = conn.execute(text("SELECT count(*) FROM sv3.crops")).scalar()
        report["markets"] = conn.execute(
            text("SELECT count(*) FROM sv3.markets")
        ).scalar()
        report["history"] = repository.rows(
            conn,
            "SELECT count(*) AS rows,min(observed_on) AS first_day,max(observed_on) AS last_day,count(*) FILTER(WHERE observed_on>(now() AT TIME ZONE 'Asia/Kolkata')::date) AS future_rows FROM sv3.price_observations",
        )[0]
        report["future_planning_rows"] = conn.execute(
            text("SELECT count(*) FROM sv3.price_projections")
        ).scalar()
        report["worker_last_sweep"] = repository.clean(
            conn.execute(
                text(
                    "SELECT last_sweep_at FROM sv3.companion_worker_state WHERE singleton"
                )
            ).scalar()
        )
        report["source_health"] = repository.rows(
            conn,
            "SELECT DISTINCT ON(p.code) p.code,h.status,h.checked_at,h.last_success_at FROM sv3.source_health h JOIN sv3.providers p ON p.id=h.provider_id WHERE h.scope_key<>'demo-outage-fixture' ORDER BY p.code,h.checked_at DESC LIMIT 12",
        )
    for crop, state in [
        ("Tomato", "Karnataka"),
        ("Rice", "Tamil Nadu"),
        ("Cotton", "Gujarat"),
        ("Onion", "Maharashtra"),
        ("Banana", "Kerala"),
        ("Arhar", "Uttar Pradesh"),
        ("Bhindi", "Bihar"),
        ("Wheat", "Punjab"),
    ]:
        start = time.perf_counter()
        rates = repository.market_rates(crop, state, limit=20)["records"]
        history = repository.market_history(crop, state, limit=90)["records"]
        report["reads"].append(
            {
                "crop": crop,
                "state": state,
                "markets": len(rates),
                "history_points": len(history),
                "milliseconds": round((time.perf_counter() - start) * 1000),
            }
        )
    report["support_searches"] = [
        {
            "query": q,
            "state": state,
            "matches": len(repository.schemes(state=state, q=q)["schemes"]),
        }
        for q, state in [
            ("insurance", "Maharashtra"),
            ("solar", "Rajasthan"),
            ("credit", "Punjab"),
            ("soil", "Tamil Nadu"),
        ]
    ]
    failures = []
    unavailable_seed_references = 0
    storage = Path(os.environ["ASSISTANT_STORAGE_DIR"]).resolve()
    with db.connection(owner) as conn:
        artifacts = repository.rows(
            conn,
            "SELECT id,object_uri,bytes,checksum FROM sv3.artifacts UNION ALL SELECT id,object_uri,bytes,checksum FROM sv3.attachments",
        )
        for item in artifacts:
            if str(item["object_uri"]).startswith("demo://unavailable/"):
                unavailable_seed_references += 1
                continue
            path = Path(item["object_uri"]).resolve()
            if not path.is_relative_to(storage) or not path.is_file():
                failures.append(
                    {"id": item["id"], "reason": "missing_or_outside_storage"}
                )
            elif (
                path.stat().st_size != item["bytes"]
                or hashlib.sha256(path.read_bytes()).hexdigest() != item["checksum"]
            ):
                failures.append({"id": item["id"], "reason": "checksum_mismatch"})
    report["files"] = {
        "checked": len(artifacts) - unavailable_seed_references,
        "unavailable_seed_references": unavailable_seed_references,
        "failures": failures,
    }
    swept_at = report["worker_last_sweep"]
    report["worker_healthy"] = (
        bool(swept_at)
        and (datetime.now(UTC) - datetime.fromisoformat(str(swept_at))).total_seconds()
        < 180
    )
    report["external_sources_healthy"] = all(
        source["status"] == "healthy" for source in report["source_health"]
    )
    report["passed"] = (
        not failures
        and report["worker_healthy"]
        and report["history"]["future_rows"] == 0
        and all(r["markets"] and r["history_points"] for r in report["reads"])
        and all(s["matches"] for s in report["support_searches"])
    )
    path = ROOT / ".v3-data/local-verification.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
