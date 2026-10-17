"""Load the Cloud Run secret bundle before importing application settings."""

import json
import os


def load_secret_environment():
    raw = os.getenv("APP_SECRET_ENV", "")
    if not raw:
        return
    values = json.loads(raw)
    if not isinstance(values, dict):
        raise RuntimeError("APP_SECRET_ENV must contain a JSON object")
    for key, value in values.items():
        if not isinstance(key, str) or not key.isidentifier() or not isinstance(value, str):
            raise RuntimeError("APP_SECRET_ENV contains an invalid entry")
        os.environ[key] = value
    os.environ.pop("APP_SECRET_ENV", None)


load_secret_environment()

from skyview.main import app
