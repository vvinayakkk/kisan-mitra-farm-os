"""Canonical reviewed evidence and explicitly synthetic scenario contracts."""

import json
import os

import pytest

from skyview.assistant import reference_tools
from skyview.data.v3 import db
from skyview.data.v3.ingestion import import_reviewed


@pytest.fixture
def pg(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated integration database required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)


def test_scenario_keeps_exact_series_and_reports_actual_coverage(pg):
    result = reference_tools.price_scenarios("Rice", "Andhra Pradesh")
    assert (
        result["available"]
        and result["kind"] == "scenario"
        and result["not_observed_prices"]
    )
    assert result["provenance"]["origin"] == "scenario"
    assert 300 <= len(result["chart"]["points"]) <= 365
    assert result["coverage_days"] == len(result["chart"]["points"])
    assert len(result["records"]) == 10 and result["chart"]["unit"] == "INR/quintal"
    assert (
        result["series"]["market"]
        and result["series"]["variety"]
        and result["series"]["grade"]
    )
    assert len(json.dumps(result)) < 30000
    assert not reference_tools.price_scenarios("Missing crop")["available"]


def test_only_reviewed_curated_evidence_is_searched(pg):
    payload = {
        "source_url": "https://icar.gov.in/",
        "title": "Integration fixture: reviewed crop guidance",
        "language": "en",
        "review_status": "reviewed",
        "reviewed_by": "isolated integration fixture",
        "evidence_text": "Public integration fixture: inspect crop leaves carefully; this is a fixture, not actual published agronomic guidance.",
    }
    with db.connection(write=True, ingest=True) as conn:
        import_reviewed(conn, payload, "demo")
    result = reference_tools.knowledge_search("fixture")
    assert result["available"]
    assert all(
        r["review_status"] == "reviewed"
        and r["origin"] == "curated"
        and r["source_url"].startswith("https://")
        for r in result["references"]
    )
    assert not reference_tools.knowledge_search("zz_no_matching_evidence_982398")[
        "available"
    ]
    assert not reference_tools.knowledge_search("fixture", language="zz")["available"]


def test_no_reference_or_scenario_fabricated_in_legacy(monkeypatch):
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "legacy")
    assert not reference_tools.knowledge_search("Rice")["available"]
    assert not reference_tools.price_scenarios("Rice")["available"]
