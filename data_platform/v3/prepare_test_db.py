"""Prepare isolated acceptance storage without resetting demo or live databases."""

import argparse
from pathlib import Path

from layout import RUNTIME_MIGRATIONS, SQL
from provision import STATE, sql

parser = argparse.ArgumentParser()
parser.add_argument("--seed-dir", type=Path, required=True)
args = parser.parse_args()
if not (STATE / "runtime.env").exists():
    raise SystemExit("Provision the persistent local v3 runtime first.")
name = "skyview_v3_test"
exists = sql("SELECT count(*) FROM pg_database WHERE datname='skyview_v3_test'") == "1"
if not exists:
    seed = (args.seed_dir / "seed.sql").read_text()
    sql("CREATE DATABASE skyview_v3_test;")
    sql((SQL / "schema.sql").read_text(), name)
    sql(seed, name)
for migration in RUNTIME_MIGRATIONS:
    sql((SQL / migration).read_text(), name)
sql("GRANT sv3_app,sv3_writer,sv3_ingest TO skyview_v3_api;")
print(
    "Isolated test storage ready; existing demo/live data and test records preserved."
)
