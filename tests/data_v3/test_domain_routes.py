"""HTTP and canonical-query contracts against an explicitly isolated database."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.api.v3_routes import router
from skyview.assistant import store
from skyview.data.v3.repository import provenance


@pytest.fixture
def client(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL integration opt-in required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0081")
    session = store.create_session()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), {
        "Authorization": "Bearer " + session["token"],
        "X-Assistant-Session": session["id"],
    }


def test_auth_scope_and_saved_profile_roundtrip(client):
    http, headers = client
    assert http.get("/api/profile").status_code == 401
    original = http.get("/api/profile", headers=headers).json()["profile"]
    assert (
        http.get("/api/profile?phone=another-owner", headers=headers).json()["profile"][
            "id"
        ]
        == original["id"]
    )
    try:
        changed = {
            "crops": ["Lavender"],
            "land_size_acres": 3.25,
            "excess_resources": ["Trailer"],
            "preferred_language": "or",
        }
        response = http.post("/api/profile/save", json=changed, headers=headers)
        assert response.status_code == 200
        current = http.get("/api/profile", headers=headers).json()["profile"]
        assert all(current[key] == value for key, value in changed.items())
        assert current["mapped_plot_area_acres"] == original["mapped_plot_area_acres"]
        from skyview.api.assistant_routes import session

        assert (
            session(headers["X-Assistant-Session"], headers["Authorization"])[
                "preferred_language"
            ]
            == "or"
        )
        assert (
            http.post(
                "/api/profile/save",
                json={"preferred_language": "invalid"},
                headers=headers,
            ).status_code
            == 422
        )
    finally:
        http.post(
            "/api/profile/save", json={k: original[k] for k in changed}, headers=headers
        )
    assert not http.get("/api/sensors/latest/DEMO-ST0001", headers=headers).json()[
        "available"
    ]


def test_public_prices_directory_and_capabilities(client):
    http, headers = client
    records = http.get(
        "/api/mandi/history?commodity=Rice&state=Andhra%20Pradesh&limit=3000"
    ).json()["records"]
    assert records and all(r["data_origin"] == "synthetic" for r in records)
    assert all(
        r["unit"] == "INR/quintal" and r["provenance"]["observed_at"] for r in records
    )
    directory = http.get("/api/marketplace/directory", headers=headers).json()[
        "farmers"
    ]

    assert directory == []
    assert all(
        not r.get("sharing_contact_available") and not r.get("whatsapp_number")
        for r in directory
    )
    assert http.get("/api/data/status").json()["legacy_database_used"] is False
    assert (
        http.get("/api/fpga/status", headers=headers).json()[
            "physical_hardware_confirmed"
        ]
        is False
    )
    for path in (
        "/api/system-health",
        "/api/recent-alerts",
        "/api/trends/history",
        "/api/weather/forecast",
    ):
        assert http.get(path, headers=headers).status_code == 200


def test_price_observation_freshness_is_not_fetch_freshness():
    now = datetime.now(UTC)
    result = provenance(
        {
            "arrival_date": (now - timedelta(days=5)).date().isoformat(),
            "fetched_at": now.isoformat(),
        }
    )
    assert result["stale"] and result["age_seconds"] < 2
    assert result["observation_age_seconds"] > 4 * 86400


def test_lane_validation_runs_before_pool_cache(monkeypatch):
    from skyview.data.v3 import db

    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_live")
    monkeypatch.setenv("V3_DATABASE_URL", "postgresql://localhost/skyview_v3_demo")
    monkeypatch.setattr(db, "_engine", lambda url: "cached-demo-pool")
    with pytest.raises(RuntimeError, match="selected v3 database"):
        db.engine()


@pytest.mark.parametrize(
    "origin,expected",
    [
        ("http://127.0.0.1:5173", 200),
        ("http://localhost:5173", 200),
        ("http://attacker.example", 400),
    ],
)
def test_unified_api_loopback_cors(monkeypatch, origin, expected):
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    from skyview.main import app

    http = TestClient(app)
    response = http.options(
        "/api/profile",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,X-Assistant-Session",
        },
    )
    assert response.status_code == expected
    if expected == 200:
        assert response.headers["access-control-allow-origin"] == origin
