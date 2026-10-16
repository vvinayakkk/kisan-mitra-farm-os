"""Owner isolation and compare-and-swap persistence for preparation checklists."""

import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_support_folder_routes import router
from skyview.assistant import store
from skyview.data.v3 import db


@pytest.fixture
def folder(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL integration database")
    assert url.rsplit("/", 1)[-1].split("?", 1)[0] == "skyview_v3_test"
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    sessions = []
    for key in ("DEMO-F0091", "DEMO-F0092"):
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        sessions.append(store.create_session())

    scheme = "53000000-0000-0000-0000-000000000001"
    document = "53000000-0000-0000-0000-000000000002"
    with db.connection(write=True, ingest=True) as conn:
        dataset = conn.execute(
            text("SELECT id FROM sv3.datasets ORDER BY id LIMIT 1")
        ).scalar_one()
        conn.execute(
            text("""INSERT INTO sv3.documents(id,dataset_id,source_url,title,language,checksum,retrieved_at,review_status)
            VALUES(:id,:dataset,'https://www.pib.gov.in/','Support checklist test reference','en','support-checklist-test',now(),'reviewed') ON CONFLICT DO NOTHING"""),
            {"id": document, "dataset": dataset},
        )
        conn.execute(
            text("""INSERT INTO sv3.scheme_versions(id,document_id,scheme_code,version,name,requirements,benefits,application_url)
            VALUES(:id,:document,'SUPPORT-CHECKLIST-TEST','test','Checklist test programme','{}','{}','https://www.pib.gov.in/') ON CONFLICT DO NOTHING"""),
            {"id": scheme, "document": document},
        )
    app = FastAPI()
    app.include_router(router)
    headers = [
        {
            "Authorization": "Bearer " + session["token"],
            "X-Assistant-Session": session["id"],
        }
        for session in sessions
    ]
    with TestClient(app) as client:
        yield client, headers, f"/api/support-folder/{scheme}"


def body(version, reviewed=True):
    return {
        "row_version": version,
        "eligibility_reviewed": reviewed,
        "documents_reviewed": False,
        "application_reviewed": False,
    }


def test_owner_and_versioned_persistence(folder):
    client, headers, path = folder
    assert client.get(path).status_code == 401
    before = client.get(path, headers=headers[0]).json()
    other = client.get(path, headers=headers[1]).json()
    saved = client.put(path, headers=headers[0], json=body(before["row_version"]))
    assert saved.status_code == 200
    current = saved.json()
    assert current["row_version"] == before["row_version"] + 1
    assert current["eligibility_reviewed"] is True
    assert (
        client.get(path, headers=headers[0]).json()["row_version"]
        == current["row_version"]
    )
    assert client.get(path, headers=headers[1]).json() == other
    assert (
        client.put(
            path, headers=headers[0], json=body(before["row_version"], False)
        ).status_code
        == 409
    )
    assert (
        client.put(
            path,
            headers=headers[0],
            json={**body(current["row_version"]), "farmer_id": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    assert (
        client.put(
            path,
            headers=headers[0],
            json={**body(current["row_version"]), "eligibility_reviewed": "yes"},
        ).status_code
        == 422
    )
    assert (
        client.put(
            path, headers=headers[0], json=body(current["row_version"], False)
        ).status_code
        == 200
    )


def test_unknown_programme_cannot_create_or_read_flags(folder):
    client, headers, _ = folder
    path = f"/api/support-folder/{uuid.uuid4()}"
    assert client.get(path, headers=headers[0]).status_code == 404
    assert client.put(path, headers=headers[0], json=body(0)).status_code == 404
