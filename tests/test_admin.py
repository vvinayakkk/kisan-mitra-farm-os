"""Admin boundary tests; optional PostgreSQL tests use one rollback-only local transaction."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from skyview.admin import admin_routes as admin


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "ADMIN_IDENTITIES",
        json.dumps(
            {
                "verified-owner": "owner",
                "verified-editor": "editor",
                "verified-viewer": "viewer",
            }
        ),
    )

    def verify(token, *, check_revoked=False):
        assert check_revoked
        if token == "invalid":
            raise ValueError("invalid")
        return {"auth_subject": "verified-" + token}

    monkeypatch.setattr(admin, "verify_identity", verify)
    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app)


def headers(role="owner"):
    return {"Authorization": "Bearer " + role}


@pytest.mark.parametrize("path", ["/me", "/resources", "/resources/farmers", "/audit"])
def test_all_reads_require_verified_admin(client, path):
    assert client.get("/admin" + path).status_code == 401
    assert client.get("/admin" + path, headers=headers("invalid")).status_code == 401
    assert client.get("/admin" + path, headers=headers("outsider")).status_code == 403


def test_identity_and_no_cache(client):
    r = client.get("/admin/me", headers=headers("viewer"))
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    assert r.headers["cache-control"] == "no-store"


def test_writes_cannot_use_farmer_session_or_missing_auth(client):
    assert (
        client.post(
            "/admin/resources/crops/preview",
            json={
                "reason": "testing",
                "operations": [{"action": "create", "values": {"name": "x"}}],
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/admin/previews/" + str(uuid4()) + "/commit",
            json={"confirmation": "APPLY 1"},
            headers=headers("outsider"),
        ).status_code
        == 403
    )


def test_legacy_password_login_removed(client):
    assert (
        client.post(
            "/admin/login", json={"username": "admin", "password": "anything"}
        ).status_code
        == 404
    )
    assert client.get("/admin/users", headers=headers()).status_code == 404


def test_database_configuration_fails_closed(client, monkeypatch):
    monkeypatch.delenv("ADMIN_DATABASE_URL", raising=False)
    assert client.get("/admin/resources", headers=headers()).status_code == 503


def test_scrubs_secrets_recursively():
    assert admin.clean(
        {
            "name": "A",
            "auth_subject": "s",
            "nested": {"api_key": "secret", "access_token": "s", "field": "ok"},
        }
    ) == {"name": "A", "nested": {"field": "ok"}}


def test_oversized_batch_rejected(client):
    body = {
        "reason": "testing",
        "operations": [
            {"action": "delete", "key": {"id": str(uuid4())}, "version": "x"}
        ]
        * 101,
    }
    assert (
        client.post(
            "/admin/resources/crops/preview", headers=headers(), json=body
        ).status_code
        == 422
    )


@pytest.fixture
def database(monkeypatch):
    url = os.getenv("ADMIN_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ADMIN_TEST_DATABASE_URL to the local isolated test database")
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    assert parsed.database == "skyview_v3_test" and parsed.host in (
        "localhost",
        "127.0.0.1",
    )
    engine = create_engine(url)
    db = engine.connect()
    transaction = db.begin()
    migration = (
        Path("data_platform/v3/sql/admin-runtime.sql")
        .read_text()
        .replace("\nBEGIN;", "\n")
        .replace("\nCOMMIT;", "\n")
    )
    db.execute(text(migration))

    # All records, role/policy changes and migration DDL are rolled back at teardown.
    class IsolatedEngine:
        @contextmanager
        def begin(self):
            with db.begin_nested():
                yield db

    monkeypatch.setenv("ADMIN_DATABASE_URL", url)
    monkeypatch.setattr(admin, "_engine", lambda _: IsolatedEngine())
    yield db
    db.execute(text("RESET ROLE"))
    transaction.rollback()
    db.close()
    engine.dispose()


def create(client, values):
    return client.post(
        "/admin/resources/crops/preview",
        headers=headers(),
        json={
            "reason": "Integration test record",
            "operations": [{"action": "create", "values": values}],
        },
    )


def sample():
    return {
        "code": "ADMIN-TEST-" + str(uuid4()),
        "name": "Admin test crop",
        "category": "cereal",
        "perennial": False,
    }


def fetch(client, code):
    r = client.get("/admin/resources/crops", params={"search": code}, headers=headers())
    assert r.status_code == 200, r.text
    return r.json()["records"]


def commit(client, preview, role="owner", confirmation="APPLY 1"):
    return client.post(
        "/admin/previews/" + preview["id"] + "/commit",
        headers=headers(role),
        json={"confirmation": confirmation},
    )


def test_preview_commit_replay_and_audit(client, database):
    values = sample()
    p = create(client, values)
    assert p.status_code == 200, p.text
    assert fetch(client, values["code"]) == []
    assert commit(client, p.json(), confirmation="wrong").status_code == 422
    assert commit(client, p.json()).status_code == 200
    rows = fetch(client, values["code"])
    assert len(rows) == 1
    assert commit(client, p.json()).json()["status"] == "already_applied"
    audit = client.get("/admin/audit", headers=headers()).json()["records"][0]
    assert audit["resource"] == "crops" and "before_hash" in audit["changes"][0]
    assert "before" not in audit["changes"][0]


def test_roles_protected_fields_and_stale_updates(client, database):
    values = sample()
    p = create(client, values)
    assert commit(client, p.json()).status_code == 200
    row = fetch(client, values["code"])[0]

    def update(changes, role="owner"):
        return client.post(
            "/admin/resources/crops/preview",
            headers=headers(role),
            json={
                "reason": "Update for tests",
                "operations": [
                    {
                        "action": "update",
                        "key": {"id": row["id"]},
                        "version": row["_version"],
                        "values": changes,
                    }
                ],
            },
        )

    assert update({"name": "Changed"}, "viewer").status_code == 403
    assert update({"id": str(uuid4())}).status_code == 422
    p1 = update({"name": "First"})
    p2 = update({"name": "Second"})
    assert p1.status_code == 200 and p2.status_code == 200
    assert commit(client, p1.json(), "editor").status_code == 404
    assert commit(client, p1.json()).status_code == 200
    assert commit(client, p2.json()).status_code == 409
    assert fetch(client, values["code"])[0]["name"] == "First"


def test_atomic_failed_batch_and_expiry(client, database):
    a = sample()
    b = sample()
    b["code"] = a["code"]
    r = client.post(
        "/admin/resources/crops/preview",
        headers=headers(),
        json={
            "reason": "Test rollback",
            "operations": [
                {"action": "create", "values": a},
                {"action": "create", "values": b},
            ],
        },
    )
    assert r.status_code == 409 and fetch(client, a["code"]) == []
    p = create(client, a).json()
    database.execute(
        text(
            "UPDATE sv3.admin_previews SET expires_at=now()-interval '1 minute' WHERE id=:id"
        ),
        {"id": p["id"]},
    )
    assert commit(client, p).status_code == 409


def test_delete_permission_and_linked_records(client, database):
    values = sample()
    p = create(client, values)
    commit(client, p.json())
    row = fetch(client, values["code"])[0]
    body = {
        "reason": "Delete test record",
        "operations": [
            {"action": "delete", "key": {"id": row["id"]}, "version": row["_version"]}
        ],
    }
    assert (
        client.post(
            "/admin/resources/crops/preview", headers=headers("editor"), json=body
        ).status_code
        == 403
    )
    p = client.post("/admin/resources/crops/preview", headers=headers(), json=body)
    assert p.status_code == 200, p.text
    assert commit(client, p.json()).status_code == 200
    assert fetch(client, values["code"]) == []


def test_metadata_and_identity_not_editable(client, database):
    r = client.get("/admin/resources", headers=headers("viewer"))
    assert r.status_code == 200, r.text
    assert all(not x["writable"] for x in r.json()["resources"])
    farmers = next(x for x in r.json()["resources"] if x["name"] == "farmers")
    assert "auth_subject" not in [x["name"] for x in farmers["columns"]]
    assert (
        client.get("/admin/resources/assistant_sessions", headers=headers()).status_code
        == 404
    )
    assert (
        client.get(
            "/admin/resources/farmers",
            params={"farmer_id": "injection"},
            headers=headers(),
        ).status_code
        == 422
    )


def test_suspension_revokes_existing_sessions(client, database):
    # Pick only an existing local test account. Its profile and sessions roll back.
    database.execute(text("RESET ROLE"))
    row = (
        database.execute(
            text("SELECT * FROM sv3.farmers WHERE status IN ('demo','active') LIMIT 1")
        )
        .mappings()
        .first()
    )
    assert row is not None
    sid = uuid4().hex
    cid = uuid4()
    database.execute(
        text(
            "INSERT INTO sv3.conversations(id,farmer_id,title) VALUES(:id,:f,'Admin suspension test')"
        ),
        {"id": cid, "f": row["id"]},
    )
    database.execute(
        text(
            "INSERT INTO sv3.assistant_sessions(id,farmer_id,token_hash,conversation_id) VALUES(:id,:f,:hash,:c)"
        ),
        {"id": sid, "f": row["id"], "hash": "test", "c": cid},
    )
    p = client.post(
        "/admin/resources/farmers/preview",
        headers=headers(),
        json={
            "reason": "Suspension integration test",
            "operations": [
                {
                    "action": "update",
                    "key": {"id": str(row["id"])},
                    "version": admin.digest(row),
                    "values": {"status": "suspended"},
                }
            ],
        },
    )
    assert p.status_code == 200, p.text
    assert commit(client, p.json()).status_code == 200
    database.execute(text("RESET ROLE"))
    assert database.execute(
        text("SELECT revoked_at IS NOT NULL FROM sv3.assistant_sessions WHERE id=:id"),
        {"id": sid},
    ).scalar_one()


def test_linked_delete_and_atomic_commit_race(client, database):
    values = sample()
    p = create(client, values).json()
    assert commit(client, p).status_code == 200
    row = fetch(client, values["code"])[0]
    database.execute(text("RESET ROLE"))
    database.execute(
        text(
            "INSERT INTO sv3.crop_varieties(crop_id,code,name) VALUES(:id,:code,'Linked variety')"
        ),
        {"id": row["id"], "code": str(uuid4())},
    )
    deletion = client.post(
        "/admin/resources/crops/preview",
        headers=headers(),
        json={
            "reason": "Check linked record protection",
            "operations": [
                {
                    "action": "delete",
                    "key": {"id": row["id"]},
                    "version": row["_version"],
                }
            ],
        },
    )
    assert deletion.status_code == 409
    a, b = sample(), sample()
    batch = client.post(
        "/admin/resources/crops/preview",
        headers=headers(),
        json={
            "reason": "Atomic commit race test",
            "operations": [
                {"action": "create", "values": a},
                {"action": "create", "values": b},
            ],
        },
    ).json()
    competing = create(client, b).json()
    assert commit(client, competing).status_code == 200
    assert commit(client, batch, confirmation="APPLY 2").status_code == 409
    assert fetch(client, a["code"]) == []


def test_readonly_activity_and_protected_identity(client, database):
    r = client.post(
        "/admin/resources/agent_runs/preview",
        headers=headers(),
        json={
            "reason": "Try rewriting activity",
            "operations": [{"action": "create", "values": {"status": "done"}}],
        },
    )
    assert r.status_code == 403
    r = client.post(
        "/admin/resources/farmers/preview",
        headers=headers(),
        json={
            "reason": "Try replacing identity",
            "operations": [
                {
                    "action": "update",
                    "key": {"id": str(uuid4())},
                    "version": "v",
                    "values": {"auth_subject": "new"},
                }
            ],
        },
    )
    assert r.status_code == 422


def test_normal_app_role_cannot_read_admin_records(client, database):
    from sqlalchemy.exc import DBAPIError

    for table in ("admin_audit", "admin_previews"):
        with database.begin_nested() as sp:
            database.execute(text("SET LOCAL ROLE sv3_app"))
            with pytest.raises(DBAPIError):
                database.execute(text(f"SELECT * FROM sv3.{table}"))
            sp.rollback()
