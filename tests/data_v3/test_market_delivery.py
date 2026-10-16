"""Real canonical query regressions, isolated PostgreSQL only."""

import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from skyview.data.v3 import db, repository


@pytest.fixture
def canonical(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL integration database")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    return repository


def test_rates_current_and_history_never_return_future(canonical):
    today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    rates = canonical.market_rates(limit=200)["rates"]
    assert rates
    assert all(row["arrival_date"] <= today for row in rates)
    assert len({row["series_id"] for row in rates}) == len(rates)
    future = canonical.market_history(year=int(today[:4]) + 10)
    assert not future["records"]


def test_catalogue_round_trip_crop_state_and_market(canonical):
    catalogue = canonical.market_catalogue()
    assert len(catalogue["states"]) == 36
    assert "Wheat" in catalogue["commodities"]
    wheat = canonical.market_catalogue("Wheat", "Punjab")
    assert wheat["markets"]
    market = wheat["markets"][0]
    rates = canonical.market_rates("Wheat", "Punjab", market=market["id"])["rates"]
    assert rates and all(
        row["market"] == market["name"]
        and row["commodity"] == "Wheat"
        and row["state"] == "Punjab"
        for row in rates
    )


def test_scheme_search_before_limit_and_national_inclusion(canonical, monkeypatch):
    import uuid
    from contextlib import contextmanager

    from sqlalchemy import text

    with db.connection(write=True, ingest=True) as conn:
        savepoint = conn.begin_nested()
        doc = str(uuid.uuid4())
        dataset = conn.execute(text("SELECT id FROM sv3.datasets LIMIT 1")).scalar_one()
        conn.execute(
            text("""INSERT INTO sv3.documents(id,dataset_id,source_url,title,language,checksum,retrieved_at,review_status)
         VALUES(:id,:dataset,'https://www.pib.gov.in/','Isolated regression source','en',:id,now(),'reviewed')"""),
            {"id": doc, "dataset": dataset},
        )
        for name in ("A income reference", "Z crop insurance reference"):
            conn.execute(
                text("""INSERT INTO sv3.scheme_versions(document_id,scheme_code,version,name,requirements,benefits,application_url)
             VALUES(:doc,:code,'test',:name,'{}','{}','https://www.pib.gov.in/')"""),
                {"doc": doc, "code": str(uuid.uuid4()), "name": name},
            )

        @contextmanager
        def same_connection():
            yield conn

        monkeypatch.setattr(canonical, "connection", same_connection)
        data = canonical.schemes("Punjab", limit=1, q="insurance")
        assert data["schemes"][0]["scheme_name"] == "Z crop insurance reference"
        assert data["schemes"][0]["state"] == "India"
        assert canonical.schemes(q="no matching programme")["available"] is False
        savepoint.rollback()


def test_market_aliases_match_the_same_canonical_series(canonical):
    rice = canonical.market_rates("Rice", limit=200)["rates"]
    paddy = canonical.market_rates("Paddy", limit=200)["rates"]
    assert {row["series_id"] for row in rice} == {row["series_id"] for row in paddy}
    assert set(canonical._crop_aliases("Arhar")) >= {"arhar", "pigeonpea", "tur"}


def test_market_worker_cursor_is_committed_with_each_page(
    canonical, monkeypatch, tmp_path
):
    from contextlib import contextmanager

    from sqlalchemy import text

    from skyview.data.v3 import worker

    offsets = []

    def page(**kwargs):
        offsets.append(kwargs["offset"])
        return {
            "records": [],
            "next_offset": 3000 if len(offsets) == 1 else 0,
            "complete": len(offsets) > 1,
            "bounded_pages": 3,
        }

    monkeypatch.setattr(worker, "fetch_mandi", page)
    monkeypatch.setenv("V3_RAW_STORAGE_DIR", str(tmp_path))
    with db.connection(write=True, ingest=True) as conn:
        savepoint = conn.begin_nested()
        conn.execute(
            text(
                "UPDATE sv3.ingest_runs SET cursor=jsonb_build_object('offset',0) WHERE job_key='ogd-agmarknet:page-cursor'"
            )
        )

        @contextmanager
        def same_connection(**kwargs):
            yield conn

        monkeypatch.setattr(worker, "connection", same_connection)
        worker._mandi()
        assert not worker._mandi_due()
        cursor = conn.execute(
            text(
                "SELECT cursor FROM sv3.ingest_runs WHERE job_key='ogd-agmarknet:page-cursor'"
            )
        ).scalar_one()
        assert cursor["offset"] == 3000
        worker._mandi()
        assert offsets == [0, 3000]
        cursor = conn.execute(
            text(
                "SELECT cursor FROM sv3.ingest_runs WHERE job_key='ogd-agmarknet:page-cursor'"
            )
        ).scalar_one()
        assert cursor["offset"] == 0
        savepoint.rollback()


def test_ogd_indian_midnight_is_not_rejected_as_future(
    canonical, monkeypatch, tmp_path
):
    from sqlalchemy import text

    from skyview.data.v3.ingestion import Ingestor

    monkeypatch.setenv("V3_RAW_STORAGE_DIR", str(tmp_path))

    now = datetime(2026, 10, 14, 20, tzinfo=UTC)
    payload = {
        "records": [
            {
                "state": "Punjab",
                "district": "Isolated fixture",
                "market": "Isolated midnight fixture",
                "commodity": "Wheat",
                "arrival_date": "15/10/2026",
                "min_price": "1000",
                "modal_price": "1100",
                "max_price": "1200",
            }
        ]
    }
    with db.connection(write=True, ingest=True) as conn:
        savepoint = conn.begin_nested()
        result = Ingestor(conn, "demo").mandi(payload, now)
        assert result["accepted"] == 1 and result["quarantined"] == 0
        row = conn.execute(
            text(
                "SELECT p.observed_on,d.as_of_date FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id WHERE d.release_key LIKE 'ogd_agmarknet:daily:2026-10-15:%' ORDER BY p.fetched_at DESC LIMIT 1"
            )
        ).one()
        assert (
            row.observed_on.isoformat() == "2026-10-15"
            and row.as_of_date == row.observed_on
        )
        savepoint.rollback()


def test_observed_market_mode_never_falls_back_to_synthetic(canonical):
    """A missing real feed must not silently turn generated fixtures into quotes."""
    for result in (
        canonical.market_rates(limit=200, observed_only=True),
        canonical.market_history(limit=3000, observed_only=True),
    ):
        assert result["observed_only"] is True
        assert all(row["data_origin"] == "observed" for row in result["records"])
    catalogue = canonical.market_catalogue(observed_only=True)
    assert all(
        row["data_origin"] in {"curated", "observed"} for row in catalogue["markets"]
    )

    assert any(
        row["data_origin"] == "synthetic"
        for row in canonical.market_rates(limit=200)["records"]
    )


def test_reported_quote_filters_end_to_end(canonical, monkeypatch, tmp_path):
    """Rollback-only artificial source response verifies the observed query path."""
    from contextlib import contextmanager

    from skyview.data.v3.ingestion import Ingestor

    now = datetime.now(UTC)
    monkeypatch.setenv("V3_RAW_STORAGE_DIR", str(tmp_path))
    with db.connection(write=True, ingest=True) as conn:
        savepoint = conn.begin_nested()
        payload = {
            "records": [
                {
                    "state": "Punjab",
                    "district": "Isolated integration fixture",
                    "market": "Rollback-only official adapter fixture",
                    "commodity": "Wheat",
                    "arrival_date": now.astimezone(ZoneInfo("Asia/Kolkata")).strftime(
                        "%d/%m/%Y"
                    ),
                    "min_price": "1000",
                    "modal_price": "1100",
                    "max_price": "1200",
                }
            ]
        }
        result = Ingestor(conn, "demo").mandi(payload, now)
        assert result == {"accepted": 1, "quarantined": 0}

        @contextmanager
        def same_connection():
            yield conn

        monkeypatch.setattr(canonical, "connection", same_connection)
        rates = canonical.market_rates("Wheat", "Punjab", observed_only=True)["records"]
        target = next(
            row for row in rates if row["market"] == payload["records"][0]["market"]
        )
        assert target["data_origin"] == "observed"
        assert float(target["modal_price"]) == 1100
        assert "data.gov.in" in target["source_url"]
        history = canonical.market_history(
            "Wheat", "Punjab", market=target["market"], observed_only=True
        )["records"]
        assert len(history) == 1 and history[0]["series_id"] == target["series_id"]
        assert (
            canonical.market_rates(
                "Wheat", "Punjab", market="No reported market", observed_only=True
            )["available"]
            is False
        )
        savepoint.rollback()


def test_market_route_passes_observed_only(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from skyview.api import v3_routes

    captured = []
    for name in ("market_rates", "market_history", "market_catalogue"):
        monkeypatch.setattr(
            v3_routes.repo, name, lambda *args: captured.append(args) or {"records": []}
        )
    app = FastAPI()
    app.include_router(v3_routes.router)
    with TestClient(app) as client:
        for path in ("rates", "history", "catalog", "catalogue"):
            assert (
                client.get(f"/api/mandi/{path}?observed_only=true").status_code == 200
            )
            assert captured[-1][-1] is True
        assert client.get("/api/mandi/rates?observed_only=invalid").status_code == 422


@pytest.mark.asyncio
async def test_agent_market_tools_keep_reported_filter(monkeypatch):
    import httpx

    from skyview.assistant.tools import Executor

    monkeypatch.setattr(db, "enabled", lambda: True)
    calls = []

    def reported(*args, **kwargs):
        calls.append(kwargs)
        return {"records": [], "available": False}

    monkeypatch.setattr(repository, "market_rates", reported)
    monkeypatch.setattr(repository, "market_history", reported)
    async with httpx.AsyncClient() as client:
        executor = Executor("isolated-filter-fixture", "WS01", client)
        for name in ("market_prices", "market_trend"):
            result = await executor.run(name, {"commodity": "Wheat"})
            assert result["available"] is False
    assert len(calls) >= 3
    assert all(call["observed_only"] is True for call in calls)
