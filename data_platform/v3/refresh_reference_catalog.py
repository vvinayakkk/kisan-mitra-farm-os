"""Idempotent local import of reviewed public references; no private farmer payloads."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    document = json.loads((ROOT / "data_platform/v3/catalog/reviewed_sources.json").read_text())
    if not args.apply:
        print(
            json.dumps(
                {
                    "bundles": len(document["bundles"]),
                    "schemes": sum(
                        len(b.get("schemes", [])) for b in document["bundles"]
                    ),
                    "coverage": document["coverage_note"],
                    "applied": False,
                }
            )
        )
        return
    for key, value in dotenv_values(ROOT / ".v3-data/runtime.env").items():
        if value is not None:
            os.environ[key] = value
    from skyview.data.v3 import db
    from skyview.data.v3.ingestion import execute, import_reviewed

    if db.mode() != "v3_demo":
        raise SystemExit("This local refresh targets the practice database only.")
    with db.connection(ingest=True) as conn:
        for bundle in document["bundles"]:
            for guide in bundle.get("crop_guides", []):
                code = guide.pop("crop_code", None)
                if code:
                    crop_id = execute(
                        conn,
                        "SELECT id FROM sv3.crops WHERE lower(code)=lower(:code) OR lower(name)=lower(:code) LIMIT 1",
                        code=code,
                    ).scalar()
                    if crop_id:
                        guide["crop_id"] = str(crop_id)
            bundle["crop_guides"] = [
                g for g in bundle.get("crop_guides", []) if g.get("crop_id")
            ]
            import_reviewed(conn, bundle, "demo")
        counts = (
            execute(
                conn,
                "SELECT (SELECT count(*) FROM sv3.scheme_versions) AS schemes,(SELECT count(*) FROM sv3.documents) AS documents,(SELECT count(*) FROM sv3.document_chunks) AS chunks",
            )
            .mappings()
            .one()
        )
        print(json.dumps({**dict(counts), "applied": True}))


if __name__ == "__main__":
    main()
