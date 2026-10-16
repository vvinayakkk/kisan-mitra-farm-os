"""Start the unified local API using ignored v3 settings, never echoing credentials."""

import os
import sys
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
config = ROOT / ".v3-data/runtime.env"
if not config.exists():
    raise SystemExit("Provision v3 first with data_platform/v3/provision.py")
for key, value in dotenv_values(config).items():
    if value is not None:
        os.environ[key] = value
uvicorn.run("skyview.main:app", host="127.0.0.1", port=8001, log_level="warning")
