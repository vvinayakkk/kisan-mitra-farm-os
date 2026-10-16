"""Provision persistent local v3 databases. Never resets or targets legacy storage."""

import argparse
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

from layout import RUNTIME_MIGRATIONS, SQL

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
STATE = ROOT / ".v3-data"
CONTAINER = "skyview_v3_backend_db"
DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"


def call(args, input=None):
    result = subprocess.run(
        args, input=input, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(
            "Local v3 provisioning command failed (credentials suppressed). Check container availability and port 15433."
        )
    return result.stdout.strip()


def sql(body, database="postgres"):
    return call(
        [
            DOCKER,
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            database,
        ],
        body,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-dir", type=Path, required=True)
    args = parser.parse_args()
    STATE.mkdir(exist_ok=True)
    os.chmod(STATE, 0o700)
    config = STATE / "runtime.env"
    if config.exists():
        print(
            "Persistent v3 configuration already exists; preserving databases and credentials."
        )
        return
    admin = secrets.token_hex(24)
    app = secrets.token_hex(24)
    docker_env = STATE / "postgres.env"
    docker_env.write_text("POSTGRES_PASSWORD=" + admin + "\n")
    os.chmod(docker_env, 0o600)
    exists = (
        subprocess.run(
            [DOCKER, "inspect", CONTAINER], check=False, capture_output=True
        ).returncode
        == 0
    )
    if exists:
        raise RuntimeError(
            "Existing container without this runtime configuration: inspect before reusing; no reset performed."
        )
    call(
        [
            DOCKER,
            "run",
            "-d",
            "--name",
            CONTAINER,
            "--restart",
            "unless-stopped",
            "--env-file",
            str(docker_env),
            "-p",
            "127.0.0.1:15433:5432",
            "-v",
            "skyview_v3_backend_data:/var/lib/postgresql/data",
            "postgres:16-alpine",
        ]
    )
    for attempt in range(30):
        ready = subprocess.run(
            [DOCKER, "exec", CONTAINER, "pg_isready", "-U", "postgres"],
            check=False,
            capture_output=True,
        )
        if ready.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Local v3 database did not become ready")
    sql(
        f"CREATE ROLE skyview_v3_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD '{app}';"
    )
    for name in ("skyview_v3_demo", "skyview_v3_live"):
        sql(f"CREATE DATABASE {name};")
        sql((SQL / "schema.sql").read_text(), name)
        if name.endswith("demo"):
            sql((args.seed_dir / "seed.sql").read_text(), name)
        for migration in RUNTIME_MIGRATIONS:
            sql((SQL / migration).read_text(), name)
        sql("GRANT sv3_app,sv3_writer,sv3_ingest TO skyview_v3_api;", name)
        sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC;", name)
    config.write_text(
        f"SKYVIEW_DATA_MODE=v3_demo\nV3_DATABASE_URL=postgresql+psycopg2://skyview_v3_api:{app}@127.0.0.1:15433/skyview_v3_demo\nV3_DEMO_FARMER_KEY=DEMO-F0001\nV3_RAW_STORAGE_DIR={STATE}/raw\nASSISTANT_STORAGE_DIR={STATE}/assistant\nENABLE_MQTT=False\nASSISTANT_DATA_URL=\n"
    )
    os.chmod(config, 0o600)
    (STATE / "provisioned.json").write_text(
        json.dumps(
            {
                "container": CONTAINER,
                "port": 15433,
                "databases": ["skyview_v3_demo", "skyview_v3_live"],
                "demo_manifest": json.loads(
                    (args.seed_dir / "manifest.json").read_text()
                ),
                "existing_legacy_database_touched": False,
            },
            indent=2,
        )
    )
    print(
        "Persistent v3 demo and separate empty live databases provisioned on localhost:15433; credentials stored in ignored owner-only runtime.env."
    )


if __name__ == "__main__":
    main()
