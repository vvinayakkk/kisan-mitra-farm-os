"""Run the existing local database, API/worker and UI with one command; never reseed."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from dotenv import dotenv_values
from layout import RUNTIME_MIGRATIONS, SQL

ROOT = Path(__file__).resolve().parents[2]


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def run():
    if not (ROOT / ".v3-data/runtime.env").exists():
        raise SystemExit(
            "Local database settings are missing. Provision the database first; nothing was reset."
        )
    if not (ROOT / "frontend/node_modules").exists():
        raise SystemExit("Install frontend dependencies with npm ci in frontend first.")
    config = dotenv_values(ROOT / ".v3-data/runtime.env")
    target = urlsplit(config.get("V3_DATABASE_URL") or "")
    if (
        config.get("SKYVIEW_DATA_MODE") != "v3_demo"
        or target.hostname not in {"127.0.0.1", "localhost"}
        or target.port != 15433
        or target.path != "/skyview_v3_demo"
    ):
        raise SystemExit(
            "This launcher only manages the existing local database on port 15433. Nothing was changed."
        )
    subprocess.run(
        ["docker", "start", "skyview_v3_backend_db"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    for _ in range(40):
        if listening(15433):
            break
        time.sleep(0.25)
    else:
        raise SystemExit("PostgreSQL did not start on port 15433.")

    for filename in RUNTIME_MIGRATIONS:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "skyview_v3_backend_db",
                "psql",
                "-X",
                "-q",
                "-U",
                "postgres",
                "-d",
                "skyview_v3_demo",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=(SQL / filename).read_bytes(),
            check=True,
            stdout=subprocess.DEVNULL,
        )
    children = []
    try:
        if not listening(8001):
            children.append(
                subprocess.Popen(
                    [sys.executable, str(ROOT / "data_platform/v3/run_backend.py")],
                    cwd=ROOT,
                    start_new_session=True,
                )
            )
        if not listening(5173):
            children.append(
                subprocess.Popen(
                    ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--strictPort"],
                    cwd=ROOT / "frontend",
                    start_new_session=True,
                )
            )
        for _ in range(80):
            if any(child.poll() is not None for child in children):
                raise RuntimeError(
                    "A local service stopped. Review the startup output above."
                )
            try:
                with urlopen("http://127.0.0.1:8001/health", timeout=1) as response:
                    healthy = b"healthy" in response.read()
                if healthy and listening(5173):
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("The API did not become healthy within 40 seconds.")
        print(
            "\nLocal workspace: http://127.0.0.1:5173/workspace\nAPI and background workers: http://127.0.0.1:8001/health\nPostgreSQL data is retained. Ctrl+C stops only services started by this command.",
            flush=True,
        )
        if not children:
            print("Both servers are already running.")
            return
        while all(child.poll() is None for child in children):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == "__main__":
    run()
