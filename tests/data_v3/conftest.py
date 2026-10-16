import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_companion_routes import router
from skyview.assistant import store
from skyview.data.v3 import db


@pytest.fixture
def companion(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL integration database")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    sessions = []
    for key in ("DEMO-F0087", "DEMO-F0088"):
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        sessions.append(store.create_session())
    app = FastAPI()
    app.include_router(router)
    headers = [
        {"Authorization": "Bearer " + s["token"], "X-Assistant-Session": s["id"]}
        for s in sessions
    ]
    owners = [store.farmer_id(s["id"]) for s in sessions]
    with TestClient(app) as client:
        for owner in owners:
            with db.connection(owner, write=True) as conn:
                conn.execute(
                    text(
                        "INSERT INTO sv3.companion_preferences(farmer_id) VALUES(:id) ON CONFLICT DO NOTHING"
                    ),
                    {"id": owner},
                )
                conn.execute(
                    text(
                        "UPDATE sv3.companion_preferences SET enabled=false WHERE farmer_id=:id"
                    ),
                    {"id": owner},
                )
        yield client, headers, owners
    for owner in owners:
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "DELETE FROM sv3.notifications WHERE payload->>'source'='companion'"
                )
            )
            conn.execute(
                text(
                    "DELETE FROM sv3.tasks WHERE execution_key LIKE 'companion-test:%'"
                )
            )
            conn.execute(
                text(
                    "UPDATE sv3.companion_preferences SET enabled=false WHERE farmer_id=:id"
                ),
                {"id": owner},
            )
