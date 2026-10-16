"""Install the v3 schema on an explicitly selected PostgreSQL database.

Designed for an empty database created by an administrator. Repeated runs only
apply additive runtime SQL; they never reseed or drop existing farm records.
"""

import argparse
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
from layout import RUNTIME_MIGRATIONS, SQL
from psycopg2 import sql

DATABASES = {"skyview_v3_demo", "skyview_v3_live", "skyview_v3_test"}
APP_ROLE = "skyview_v3_api"


def _apply(conn, path: Path):
    with conn.cursor() as cursor:
        cursor.execute(path.read_text())


def _apply_seed(path: Path):
    # The generator emits psql COPY FROM STDIN blocks. Keep its transaction and
    # integrity checks intact rather than splitting CSV and SQL in Python.
    result = subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Demo seed failed; database credentials and payload suppressed"
        )


def bootstrap(*, seed_demo: bool = False):
    if not os.getenv("PGPASSWORD") or not os.getenv("V3_APP_PASSWORD"):
        raise RuntimeError("PGPASSWORD and V3_APP_PASSWORD must be set")
    with psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"),
        dbname=os.getenv("PGDATABASE", ""),
        connect_timeout=5,
    ) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), to_regclass('sv3.farmers') IS NOT NULL"
            )
            database, installed = cursor.fetchone()
            if database not in DATABASES:
                raise RuntimeError("Refusing to install v3 into an unknown database")
            if seed_demo and database != "skyview_v3_demo":
                raise RuntimeError("Demo seed is restricted to skyview_v3_demo")
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (APP_ROLE,))
            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}"
                    ).format(
                        sql.Identifier(APP_ROLE),
                        sql.Literal(os.environ["V3_APP_PASSWORD"]),
                    )
                )
        if not installed:
            _apply(conn, SQL / "schema.sql")
            if seed_demo:
                from seed_demo import generate

                with tempfile.TemporaryDirectory(prefix="kisan-v3-seed-") as directory:
                    output = Path(directory)
                    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
                    generate(output, today, 20261014)
                    _apply_seed(output / "seed.sql")
        for filename in RUNTIME_MIGRATIONS:
            _apply(conn, SQL / filename)
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT sv3_app,sv3_writer,sv3_ingest TO {}").format(
                    sql.Identifier(APP_ROLE)
                )
            )
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    print(f"v3 schema ready in {database}; existing farmer records preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-demo", action="store_true")
    args = parser.parse_args()
    bootstrap(seed_demo=args.seed_demo)
