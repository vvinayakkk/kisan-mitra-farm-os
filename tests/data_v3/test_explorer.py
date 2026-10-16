"""Safe owned classic data explorer against isolated PostgreSQL only."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api.v3_explorer_routes import TABLES, router
from skyview.api.v3_routes import identity
from skyview.data.v3 import db


@pytest.fixture
def explorer(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated V3_TEST_DATABASE_URL required")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    with db.connection(ingest=True) as conn:
        owners = (
            conn.execute(
                text(
                    "SELECT id FROM sv3.farmers WHERE profile_key LIKE 'DEMO-%' ORDER BY profile_key LIMIT 2"
                )
            )
            .scalars()
            .all()
        )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), app, [str(owner) for owner in owners]


def authenticate(app, owner):
    app.dependency_overrides[identity] = lambda: owner


def test_explorer_requires_auth(explorer):
    client, _, _ = explorer
    assert client.get("/admin/tables").status_code == 401
    assert client.get("/admin/tables/tasks").status_code == 401


def test_only_allowlisted_owned_tables_and_real_metadata(explorer):
    client, app, owners = explorer
    authenticate(app, owners[0])
    response = client.get("/admin/tables")
    assert response.status_code == 200, response.text
    data = response.json()
    assert {table["name"] for table in data["tables"]} == set(TABLES)
    tasks = next(table for table in data["tables"] if table["name"] == "tasks")
    assert tasks["row_count"] > 0
    assert any(
        column["name"] == "id" and column["primary_key"] for column in tasks["columns"]
    )
    assert all(
        {"name", "type", "nullable", "default", "primary_key"} <= column.keys()
        for column in tasks["columns"]
    )
    for forbidden in [
        "farmers",
        "messages",
        "raw_objects",
        "sessions",
        "packet_receipts",
        "sensor_packets",
        "sensor_packets_202610",
        "quality_issues",
        "providers",
    ]:
        assert client.get("/admin/tables/" + forbidden).status_code == 404


def test_explorer_owner_isolation(explorer):
    client, app, owners = explorer
    authenticate(app, owners[0])
    first = client.get("/admin/tables/expenses", params={"page_size": 200}).json()
    assert first["records"] and all(
        row["farmer_id"] == owners[0] for row in first["records"]
    )
    authenticate(app, owners[1])
    second = client.get("/admin/tables/expenses", params={"page_size": 200}).json()
    assert second["records"] and all(
        row["farmer_id"] == owners[1] for row in second["records"]
    )
    assert not {row["id"] for row in first["records"]} & {
        row["id"] for row in second["records"]
    }
    stolen = client.get(
        "/admin/tables/expenses",
        params={"filter_column": "farmer_id", "filter_value": owners[0]},
    ).json()
    assert stolen["records"] == [] and stolen["pagination"]["total_rows"] == 0


def test_explorer_sort_filter_search_and_pagination(explorer):
    client, app, owners = explorer
    authenticate(app, owners[0])
    params = {"page_size": 3, "order_by": "amount_inr", "desc": True}
    first = client.get("/admin/tables/expenses", params=params)
    assert first.status_code == 200, first.text
    data = first.json()
    amounts = [record["amount_inr"] for record in data["records"]]
    assert amounts == sorted(amounts, reverse=True)
    second = client.get("/admin/tables/expenses", params={**params, "page": 2}).json()
    assert not {row["id"] for row in data["records"]} & {
        row["id"] for row in second["records"]
    }
    assert (
        data["pagination"]["total_rows"] >= 6 and data["pagination"]["total_pages"] >= 2
    )
    row = data["records"][0]
    filtered = client.get(
        "/admin/tables/expenses",
        params={"filter_column": "id", "filter_value": row["id"]},
    ).json()
    assert len(filtered["records"]) == 1 and filtered["records"][0]["id"] == row["id"]
    search = client.get(
        "/admin/tables/expenses", params={"search": row["description"]}
    ).json()
    assert search["records"]
    literal = client.get("/admin/tables/expenses", params={"search": "%_%"}).json()
    assert literal["records"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"order_by": "id DESC; DROP TABLE sv3.tasks;--"},
        {"filter_column": "id) OR true --", "filter_value": "anything"},
        {"filter_column": "nonexistent", "filter_value": "x"},
        {"filter_column": "id"},
        {"filter_value": "x"},
    ],
)
def test_explorer_rejects_identifier_injection(explorer, params):
    client, app, owners = explorer
    authenticate(app, owners[0])
    assert client.get("/admin/tables/tasks", params=params).status_code == 400


def test_explorer_binds_filter_values_and_bounds_pages(explorer):
    client, app, owners = explorer
    authenticate(app, owners[0])
    response = client.get(
        "/admin/tables/tasks",
        params={"filter_column": "id", "filter_value": "' OR true --"},
    )
    assert response.status_code == 200 and response.json()["records"] == []
    assert (
        client.get("/admin/tables/tasks", params={"page_size": 201}).status_code == 422
    )
    assert client.get("/admin/tables/tasks", params={"page": 0}).status_code == 422
