"""Owned live onboarding and physical enrollment contracts against isolated v3."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from skyview.api.v3_onboarding_routes import PlotInput, router
from skyview.api.v3_routes import router as domain_router
from skyview.assistant import auth, store
from skyview.data.v3 import db


@pytest.fixture
def live(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set isolated V3_TEST_DATABASE_URL with seeded demo and matching empty live DB"
        )
    liveurl = os.getenv("V3_TEST_LIVE_DATABASE_URL") or make_url(url).set(
        database="skyview_v3_test"
    ).render_as_string(hide_password=False)
    monkeypatch.setenv("V3_DATABASE_URL", liveurl)
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_live")
    subject = "oidc:" + uuid.uuid4().hex + uuid.uuid4().hex
    monkeypatch.setattr(
        auth,
        "verify_identity",
        lambda token: {
            "auth_subject": subject,
            "issuer": "https://identity.example.invalid/",
        },
    )
    session = auth.create_live_session("verified-fixture")
    app = FastAPI()
    app.include_router(router)
    app.include_router(domain_router)
    return (
        TestClient(app),
        session,
        {
            "Authorization": "Bearer " + session["token"],
            "X-Assistant-Session": session["id"],
        },
    )


def complete(client, headers):
    options = client.get("/api/onboarding/options")
    assert options.status_code == 200
    regions = options.json()["regions"]
    assert len(regions) == 36 and all(
        r["code_system"] == "skyview-curated-state-name" for r in regions
    )
    region = next(r["id"] for r in regions if r["name"] == "Maharashtra")
    response = client.post(
        "/api/onboarding",
        headers=headers,
        json={
            "display_name": "Verified test farmer",
            "region_id": region,
            "preferred_language": "mr",
            "consent_to_store_profile": True,
        },
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["status"] == "active"
        and not response.json()["contact_verified"]
    )
    return region


def farm_and_plot(client, headers, region):
    farm = {
        "name": "Owned test field",
        "region_id": region,
        "ownership_type": "owned",
        "irrigation_method": "rainfed",
    }
    response = client.post("/api/farms", headers=headers, json=farm)
    assert response.status_code == 200, response.text
    fid = response.json()["id"]
    plot = {
        "farm_id": fid,
        "area_ha": "0.8000",
        "latitude": "19.250000",
        "longitude": "73.130000",
        "soil_texture": "loam",
    }
    response = client.post("/api/plots", headers=headers, json=plot)
    assert response.status_code == 200, response.text
    return fid, response.json()["id"], farm, plot


def test_owned_live_account_completes_without_fake_contact_and_crud(live):
    client, session, headers = live
    assert client.get("/api/farms").status_code == 401
    options = client.get("/api/onboarding/options").json()
    region = options["regions"][0]["id"]
    blocked = client.post(
        "/api/farms",
        headers=headers,
        json={
            "name": "Before onboarding",
            "region_id": region,
            "ownership_type": "owned",
            "irrigation_method": "rainfed",
        },
    )
    assert blocked.status_code == 409
    region = complete(client, headers)
    fid, pid, farm, plot = farm_and_plot(client, headers, region)
    assert (
        client.put(
            "/api/farms/" + fid, headers=headers, json={**farm, "name": "Renamed field"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/plots/" + pid, headers=headers, json={**plot, "area_ha": "0.9000"}
        ).status_code
        == 200
    )

    crops = options["crops"]
    if crops:
        crop = crops[0]["id"]
        cycle = {
            "plot_id": pid,
            "crop_id": crop,
            "season": "Rabi",
            "sowing_date": datetime.now(UTC).date().isoformat(),
            "status": "growing",
        }
        result = client.post("/api/crop-cycles", headers=headers, json=cycle)
        assert result.status_code == 200, result.text
        assert client.delete("/api/plots/" + pid, headers=headers).status_code == 409
        assert (
            client.delete(
                "/api/crop-cycles/" + result.json()["id"], headers=headers
            ).status_code
            == 200
        )
    assert client.delete("/api/plots/" + pid, headers=headers).status_code == 200
    assert client.delete("/api/farms/" + fid, headers=headers).status_code == 200
    with db.connection(store.farmer_id(session["id"])) as conn:
        farmer = (
            conn.execute(
                text(
                    "SELECT status,contact_phone,contact_verified_at,region_id FROM sv3.farmers"
                )
            )
            .mappings()
            .one()
        )
        assert (
            farmer["status"] == "active"
            and farmer["contact_phone"] is None
            and farmer["contact_verified_at"] is None
        )
        assert farmer["region_id"] is not None


def test_cross_farmer_links_and_forged_geo_rejected(live, monkeypatch):
    client, _session, headers = live
    region = complete(client, headers)
    fid, pid, farm, plot = farm_and_plot(client, headers, region)
    subject = "oidc:" + uuid.uuid4().hex + uuid.uuid4().hex
    monkeypatch.setattr(
        auth,
        "verify_identity",
        lambda token: {
            "auth_subject": subject,
            "issuer": "https://identity.example.invalid/",
        },
    )
    other = auth.create_live_session("another-verified-fixture")
    otherheaders = {
        "Authorization": "Bearer " + other["token"],
        "X-Assistant-Session": other["id"],
    }
    complete(client, otherheaders)
    assert (
        client.put("/api/farms/" + fid, headers=otherheaders, json=farm).status_code
        == 404
    )
    assert client.post("/api/plots", headers=otherheaders, json=plot).status_code == 404
    assert client.delete("/api/plots/" + pid, headers=otherheaders).status_code == 404
    assert (
        client.post(
            "/api/stations/enroll",
            headers=otherheaders,
            json={
                "plot_id": pid,
                "device_label": "Not my device",
                "physical_device": True,
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/plots", headers=headers, json={**plot, "latitude": 91}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/plots", headers=headers, json={**plot, "area_ha": 0}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/onboarding",
            headers=headers,
            json={
                "display_name": "Another",
                "region_id": str(uuid.uuid4()),
                "preferred_language": "mr",
                "consent_to_store_profile": True,
            },
        ).status_code
        == 422
    )


def test_enrollment_issues_only_hashed_once_and_actual_device_ingest(live):
    client, session, headers = live
    region = complete(client, headers)
    _fid, pid, _farm, _plot = farm_and_plot(client, headers, region)
    invalid = client.post(
        "/api/stations/enroll",
        headers=headers,
        json={
            "plot_id": pid,
            "device_label": "Device fixture",
            "physical_device": False,
        },
    )
    assert invalid.status_code == 422
    result = client.post(
        "/api/stations/enroll",
        headers=headers,
        json={
            "plot_id": pid,
            "device_label": "Physical device fixture",
            "physical_device": True,
        },
    )
    assert result.status_code == 200, result.text
    enrolled = result.json()
    owner = store.farmer_id(session["id"])
    with db.connection(owner) as conn:
        lineage_before = (
            conn.execute(
                text(
                    "SELECT d.id,d.provider_id,d.release_key,d.lane,d.origin,d.as_of_date,d.source_url FROM sv3.datasets d JOIN sv3.stations s ON s.dataset_id=d.id WHERE s.id=:id"
                ),
                {"id": enrolled["id"]},
            )
            .mappings()
            .one()
        )
    second = client.post(
        "/api/stations/enroll",
        headers=headers,
        json={
            "plot_id": pid,
            "device_label": "Second physical device fixture",
            "physical_device": True,
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] != enrolled["id"]
    assert second.json()["device_key"] != enrolled["device_key"]
    with db.connection(owner) as conn:
        lineage_after = (
            conn.execute(
                text(
                    "SELECT d.id,d.provider_id,d.release_key,d.lane,d.origin,d.as_of_date,d.source_url FROM sv3.datasets d JOIN sv3.stations s ON s.dataset_id=d.id WHERE s.id=:id AND s.farmer_id=:owner"
                ),
                {"id": second.json()["id"], "owner": owner},
            )
            .mappings()
            .one()
        )
    assert dict(lineage_after) == dict(lineage_before)
    assert (
        lineage_after["lane"] == "live" and lineage_after["origin"] == "user_reported"
    )
    assert (
        not enrolled["connection_verified"]
        and enrolled["calibration_status"] == "uncalibrated"
    )
    with db.connection(store.farmer_id(session["id"]), write=True) as conn:
        secret = conn.execute(
            text("SELECT key_hash FROM sv3.device_credentials WHERE station_id=:id"),
            {"id": enrolled["id"]},
        ).scalar_one()
        assert len(secret) == 64 and secret != enrolled["device_key"]
        assert (
            conn.execute(
                text("SELECT last_received_at FROM sv3.stations WHERE id=:id"),
                {"id": enrolled["id"]},
            ).scalar_one()
            is None
        )
    payload = {
        "station_id": enrolled["station_id"],
        "boot_id": str(uuid.uuid4()),
        "sequence": 1,
        "observed_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "measurements": {"temperature_c": 27.5, "humidity_pct": 61},
    }
    actual = client.post(
        "/api/sensors/ingest",
        headers={"Authorization": "Device " + enrolled["device_key"]},
        json=payload,
    )
    assert actual.status_code == 200, actual.text
    assert actual.json()["accepted"]
    duplicate = client.post(
        "/api/sensors/ingest",
        headers={"Authorization": "Device " + enrolled["device_key"]},
        json=payload,
    )
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"]
    assert (
        client.post(
            "/api/stations/" + enrolled["id"] + "/revoke", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/sensors/ingest",
            headers={"Authorization": "Device " + enrolled["device_key"]},
            json=payload,
        ).status_code
        == 401
    )


def test_geojson_invalid_shape_fails_before_database():
    pytest.importorskip("shapely")
    payload = {
        "farm_id": str(uuid.uuid4()),
        "area_ha": "0.8",
        "latitude": "19.25",
        "longitude": "73.13",
    }
    with pytest.raises(ValueError):
        PlotInput(
            **payload,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [
                        [73.12, 19.24],
                        [73.14, 19.26],
                        [73.12, 19.26],
                        [73.14, 19.24],
                        [73.12, 19.24],
                    ]
                ],
            },
        )


def test_confirmed_soil_transcription_keeps_basis_owner_and_no_lab_claim(
    live, monkeypatch, tmp_path
):
    from skyview.assistant.attachments import extract

    client, session, headers = live
    region = complete(client, headers)
    _fid, pid, _farm, _plot = farm_and_plot(client, headers, region)
    monkeypatch.setattr(store, "ROOT", tmp_path)
    report = extract(
        session["id"],
        "soil-report.txt",
        b"Farmer-provided report transcription. pH 6.7 and available nitrogen 160 kg/ha.",
    )
    payload = {
        "request_key": str(uuid.uuid4()),
        "plot_id": pid,
        "attachment_id": report["id"],
        "sampled_on": datetime.now(UTC).date().isoformat(),
        "values_confirmed_by_farmer": True,
        "values": [
            {
                "property": "ph",
                "value": "6.7",
                "unit_code": "ph",
                "reported_basis": "hydrogen activity",
                "depth_top_cm": "0",
                "depth_bottom_cm": "15",
            },
            {
                "property": "nitrogen",
                "value": "160",
                "unit_code": "kg_ha",
                "reported_basis": "available N",
                "depth_top_cm": "0",
                "depth_bottom_cm": "15",
            },
        ],
    }
    saved = client.post("/api/soil-reports", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert (
        saved.json()["evidence_type"] == "farmer_report"
        and not saved.json()["lab_verified"]
    )
    assert client.post("/api/soil-reports", headers=headers, json=payload).json()[
        "duplicate"
    ]
    changed = {**payload, "values": [{**payload["values"][0], "value": "7.0"}]}
    assert (
        client.post("/api/soil-reports", headers=headers, json=changed).status_code
        == 409
    )
    units = {
        **payload,
        "request_key": str(uuid.uuid4()),
        "values": [{**payload["values"][0], "unit_code": "kg_ha"}],
    }
    assert (
        client.post("/api/soil-reports", headers=headers, json=units).status_code == 422
    )
    basis = {
        **payload,
        "request_key": str(uuid.uuid4()),
        "values": [{**payload["values"][1], "reported_basis": "total nitrogen"}],
    }
    assert (
        client.post("/api/soil-reports", headers=headers, json=basis).status_code == 422
    )
    assert len(client.get("/api/soil-report/options").json()["parameters"]) == 12
    values = client.get("/api/soil-reports", headers=headers).json()["values"]
    assert len(values) == 2 and all(
        v["evidence_type"] == "farmer_report" for v in values
    )
    other_subject = "oidc:" + uuid.uuid4().hex + uuid.uuid4().hex
    monkeypatch.setattr(
        auth,
        "verify_identity",
        lambda token: {
            "auth_subject": other_subject,
            "issuer": "https://identity.example.invalid/",
        },
    )
    other = auth.create_live_session("other-verified-fixture")
    otherheaders = {
        "Authorization": "Bearer " + other["token"],
        "X-Assistant-Session": other["id"],
    }
    assert client.get("/api/soil-reports", headers=otherheaders).json()["values"] == []


def test_coarse_weather_link_requires_explicit_owner_consent_and_revokes(
    live, monkeypatch
):
    from skyview.data.v3 import worker

    client, session, headers = live
    region = complete(client, headers)
    fid, pid, _farm, _plot = farm_and_plot(client, headers, region)
    notifications = []
    monkeypatch.setattr(
        worker, "notify_weather_link", lambda: notifications.append(True)
    )
    endpoint = "/api/farms/" + fid + "/weather-link"
    assert (
        client.post(
            endpoint,
            headers=headers,
            json={"plot_id": pid, "consent_to_share_coarse_grid": False},
        ).status_code
        == 422
    )
    fake = {**headers, "X-Assistant-Session": "0" * 32}
    assert (
        client.post(
            endpoint,
            headers=fake,
            json={"plot_id": pid, "consent_to_share_coarse_grid": True},
        ).status_code
        == 401
    )
    assert (
        client.post(
            endpoint,
            headers=headers,
            json={"plot_id": str(uuid.uuid4()), "consent_to_share_coarse_grid": True},
        ).status_code
        == 404
    )
    linked = client.post(
        endpoint,
        headers=headers,
        json={"plot_id": pid, "consent_to_share_coarse_grid": True},
    )
    assert linked.status_code == 200, linked.text
    response = linked.json()
    location = response["location_id"]
    assert notifications == [True] and response["lookup_requested"]
    assert response["coarse_grid"]["resolution_m"] >= 25000
    for axis in ("latitude", "longitude"):
        assert response["coarse_grid"][axis] * 4 == int(
            response["coarse_grid"][axis] * 4
        )
    with db.connection(write=True, ingest=True) as conn:
        eligible = (
            conn.execute(text("SELECT id FROM sv3.consented_weather_locations()"))
            .scalars()
            .all()
        )
        assert uuid.UUID(location) in eligible
    with db.connection(store.farmer_id(session["id"])) as conn:
        row = conn.execute(
            text("SELECT location_id FROM sv3.farms WHERE id=:id"), {"id": fid}
        ).scalar_one()
        assert str(row) == location
        exact = (
            conn.execute(
                text("SELECT latitude,longitude FROM sv3.plots WHERE id=:id"),
                {"id": pid},
            )
            .mappings()
            .one()
        )
        assert float(exact["longitude"]) == 73.13
    revoked = client.delete(endpoint, headers=headers)
    assert (
        revoked.status_code == 200
        and revoked.json()["future_account_grid_lookups_disabled"]
    )
    with db.connection(store.farmer_id(session["id"])) as conn:
        assert (
            conn.execute(
                text("SELECT location_id FROM sv3.farms WHERE id=:id"), {"id": fid}
            ).scalar_one()
            is None
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM sv3.consents WHERE purpose='weather_grid_lookup' AND revoked_at IS NULL"
                )
            ).scalar_one()
            == 0
        )
    with db.connection(write=True, ingest=True) as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM sv3.farms WHERE id=:id AND location_id IS NOT NULL"
                ),
                {"id": fid},
            ).scalar_one()
            == 0
        )


def test_app_profile_and_starter_plans_are_shared_with_second_device(live, monkeypatch):
    client, app_session, app_headers = live
    region = complete(client, app_headers)
    fid, pid, _, _ = farm_and_plot(client, app_headers, region)
    result = client.post('/api/profile/save', headers=app_headers,
                         json={'crops': ['Groundnut'], 'land_size_acres': 4})
    assert result.status_code == 200
    assert not result.json()['profile']['onboarding_required']
    first = client.post('/api/onboarding/starter-plans', headers=app_headers, json={'approved': True})
    assert first.status_code == 200
    # Another verified sign-in for the same identity gets a distinct capability,
    # while the database profile, farms and deterministic routine IDs are shared.
    laptop = auth.create_live_session('same-verified-identity-on-laptop')
    assert laptop['id'] != app_session['id']
    headers = {'Authorization': 'Bearer ' + laptop['token'], 'X-Assistant-Session': laptop['id']}
    profile = client.get('/api/profile', headers=headers).json()['profile']
    assert profile['id'] == result.json()['profile']['id']
    assert profile['crops'] == ['Groundnut'] and profile['land_size_acres'] == 4
    assert not profile['onboarding_required']
    assert any(f['id'] == fid for f in client.get('/api/farms', headers=headers).json()['farms'])
    assert any(p['id'] == pid for p in client.get('/api/plots', headers=headers).json()['plots'])
    routines = client.get('/api/onboarding/starter-plans', headers=headers).json()['plans']
    assert len(routines) == 3 and all(p['saved'] for p in routines)
    repeated = client.post('/api/onboarding/starter-plans', headers=headers, json={'approved': True})
    assert repeated.json()['mission_ids'] == first.json()['mission_ids']
    assert client.get('/api/onboarding/starter-plans').status_code == 401
    assert client.post('/api/profile/save', headers=headers, json={'crops': ['Maize']}).status_code == 200
    assert client.get('/api/profile', headers=app_headers).json()['profile']['crops'] == ['Maize']

    monkeypatch.setattr(auth, 'verify_identity', lambda token: {
        'auth_subject': 'oidc:' + uuid.uuid4().hex + uuid.uuid4().hex,
        'issuer': 'https://identity.example.invalid/'})
    other = auth.create_live_session('another-farmer')
    other_headers = {'Authorization': 'Bearer ' + other['token'], 'X-Assistant-Session': other['id']}
    other_profile = client.get('/api/profile', headers=other_headers).json()['profile']
    assert other_profile['id'] != profile['id'] and other_profile['onboarding_required']
    assert not any(p['saved'] for p in client.get('/api/onboarding/starter-plans', headers=other_headers).json()['plans'])
    assert client.get('/api/farms', headers=other_headers).json()['farms'] == []
