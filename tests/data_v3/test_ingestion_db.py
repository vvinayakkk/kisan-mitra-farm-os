"""Opt-in rollback-only connector integration tests against a provisioned v3 database."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from skyview.data.v3.db import connection
from skyview.data.v3.ingestion import (
    Ingestor,
    execute,
    ingest_mock_packet,
    ingest_sensor_envelope,
)

pytestmark = pytest.mark.skipif(
    os.getenv("SKYVIEW_V3_INGEST_TESTS") != "1",
    reason="explicit v3 integration opt-in required",
)


@pytest.fixture(autouse=True)
def isolated_mode(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated V3_TEST_DATABASE_URL required")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")


class Rollback(Exception):
    pass


def test_mock_retry_and_owner_sensor_replay():
    with pytest.raises(Rollback):
        with connection(write=True, ingest=True) as db:
            station = (
                execute(
                    db,
                    "SELECT s.id,s.farmer_id FROM sv3.stations s JOIN sv3.datasets d ON d.id=s.dataset_id WHERE d.origin='synthetic' ORDER BY s.id LIMIT 1",
                )
                .mappings()
                .one()
            )
            now = datetime.now(UTC).replace(microsecond=0)
            execute(
                db,
                "SELECT sv3.ensure_month_partitions('sensor_packets',:day,:day)",
                day=now.date().replace(day=1),
            )
            assert ingest_mock_packet(db, station, now) is True
            assert ingest_mock_packet(db, station, now) is False
            envelope = {
                "observed_at": now.isoformat(),
                "boot_id": str(uuid4()),
                "sequence": 1,
                "measurements": {"temperature_c": 25, "humidity_pct": 60},
            }
            assert ingest_sensor_envelope(
                db, station["farmer_id"], station["id"], envelope, lane="demo", now=now
            )["accepted"]
            assert ingest_sensor_envelope(
                db, station["farmer_id"], station["id"], envelope, lane="demo", now=now
            )["duplicate"]
            with pytest.raises(ValueError, match="bound"):
                ingest_sensor_envelope(
                    db, str(uuid4()), station["id"], envelope, lane="demo", now=now
                )
            raise Rollback()


def test_market_snapshot_retry_and_quarantine():
    with pytest.raises(Rollback):
        with connection(write=True, ingest=True) as db:
            now = datetime.now(UTC)
            execute(
                db,
                "SELECT sv3.ensure_month_partitions('price_observations',:day,:day)",
                day=now.date().replace(day=1),
            )
            record = {
                "state": "Punjab",
                "market": "Integration fixture market",
                "commodity": "Wheat",
                "arrival_date": now.strftime("%d/%m/%Y"),
                "min_price": "1000",
                "modal_price": "1100",
                "max_price": "1200",
            }
            payload = {
                "records": [
                    record,
                    {**record, "unit": "Rs/100Nuts"},
                    {**record, "commodity": "Unmapped demo fixture"},
                ]
            }
            importer = Ingestor(db)
            result = importer.mandi(payload, now)
            assert result == {"accepted": 1, "quarantined": 2}
            count = execute(
                db,
                "SELECT count(*) FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id JOIN sv3.providers s ON s.id=d.provider_id WHERE s.code='ogd_agmarknet'",
            ).scalar_one()
            importer.mandi(payload, now)
            assert (
                execute(
                    db,
                    "SELECT count(*) FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id JOIN sv3.providers s ON s.id=d.provider_id WHERE s.code='ogd_agmarknet'",
                ).scalar_one()
                == count
            )
            raise Rollback()
