"""Domain examples preserve provenance, dates, ownership and real market identity."""

import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "data_platform/v3"))
    spec = importlib.util.spec_from_file_location(
        "domain_expansion_test", ROOT / "data_platform/v3/expand_domain_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expansion_has_separate_historical_and_scenario_contract(monkeypatch):
    m = load(monkeypatch)
    body = m.build(date(2026, 10, 15))
    assert "current_database()<>'skyview_v3_demo'" in body
    assert len(m.CROP_CODES) == 150 and len(set(m.CROP_CODES)) == 150
    assert "generate_series('2026-10-15'::date-730,'2026-10-15'::date,'1 day')" in body
    assert "generate_series(1,365)" in body and "'scenario_only'" in body
    assert "INSERT INTO sv3.price_projections" in body
    assert (
        "NOT EXISTS(SELECT 1 FROM sv3.price_observations old WHERE old.series_id=s.id AND old.observed_on=d::date)"
        in body
    )
    assert "DELETE " not in body and "TRUNCATE " not in body
    assert "UPDATE sv3.farmers" not in body
    assert "m.code_system='SAMPLE-DOMAIN'" in body
    assert "synthetic_example" in body and "'image_available',false" in body
    assert "f.profile_key LIKE 'DEMO-F%'" in body
    assert body == m.build(date(2026, 10, 15))


def test_official_directory_names_never_get_fictional_prices(monkeypatch):
    m = load(monkeypatch)
    body = m.reference_sql(date(2026, 10, 15))
    directory = json.loads(
        (ROOT / "data_platform/v3/catalog/enam_market_reference.json").read_text()
    )
    assert len(directory["markets"]) == 158
    assert directory["source_url"] == "https://enam.gov.in/aspirational-districts"
    assert "price_observations" not in body and "price_projections" not in body
    assert "contact_phone" not in body and "latitude" not in body
    assert "'ENAM-REFERENCE'" in body and "'curated'" in body
    assert "r.code_system='DEMO'" in body


def test_common_crops_get_three_stable_comparison_series(monkeypatch):
    m = load(monkeypatch)
    body = m.build(date(2026, 10, 15), m.COMPARISON_CROPS, (1, 2))
    assert len(m.COMPARISON_CROPS) == 10
    assert "generate_series(1,2)off" in body
    assert "'tomato'" in body and "'papaya'" in body
    assert "(.85+get_byte(decode(md5(s.id::text),'hex'),0)::numeric/255*.35)" in body
    assert "'domain-v2-regional'" in body
    assert "old.valid_on='2026-10-15'::date+n" in body


def test_daily_maintenance_only_fills_missing_tail(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "data_platform/v3"))
    from domain_roll import statements

    body = statements(date(2026, 10, 15))
    assert "greatest(s.history_day+1" in body
    assert "greatest(s.projection_day+1" in body
    assert "'domain-v2-regional'" in body
    assert "DELETE " not in body and "UPDATE " not in body
    assert "s.id AND old.valid_on=day::date" in body
    assert "ON COMMIT DROP" in body


def test_regional_correction_uses_audit_marker_and_immutable_lineage(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "data_platform/v3"))
    from regionalize_domain_demo import statements

    body = statements()
    assert "UPDATE sv3.datasets" not in body
    assert "job_key='domain-regional-v2:'||d.id AND i.state='done'" in body
    assert "INSERT INTO sv3.ingest_runs" in body
    assert (
        "p.code='domain-sample-v1' AND d.origin='synthetic' AND d.lane='demo'" in body
    )
    assert "m.external_code=r.code||'-SAMPLE-'||((dc.value::integer%30)+1)" in body
