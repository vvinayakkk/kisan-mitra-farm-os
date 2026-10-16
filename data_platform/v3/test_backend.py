"""Run backend contracts only against dedicated local integration storage."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
config = dotenv_values(ROOT / ".v3-data/runtime.env")
url = (
    make_url(config["V3_DATABASE_URL"])
    .set(database="skyview_v3_test")
    .render_as_string(hide_password=False)
)
os.environ.update(
    V3_TEST_DATABASE_URL=url,
    V3_TEST_LIVE_DATABASE_URL=url,
    V3_DATABASE_URL=url,
    SKYVIEW_V3_INGEST_TESTS="1",
    SKYVIEW_DATA_MODE="legacy",
)
raise SystemExit(
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/assistant",
            "tests/data_v3",
            "tests/test_disease_screening.py",
            "tests/test_v3_voice.py",
            "-q",
            "--disable-warnings",
            "--tb=short",
        ],
        cwd=ROOT,
        check=False,
    ).returncode
)
