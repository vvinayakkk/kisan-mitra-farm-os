from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from skyview.assistant import models, weather_tools
from skyview.assistant.tools import Executor, public_catalog, schemas


@pytest.mark.parametrize("days", [0, 17, 365])
def test_forecast_does_not_promise_a_year_of_known_weather(days):
    with pytest.raises(ValidationError):
        models.WeatherForecastArgs(days=days)


def test_archive_schema_and_catalog_explain_grid_vs_station():
    assert models.WeatherArchiveArgs(days=365).days == 365
    catalog = public_catalog()
    tools = {item["id"]: item for item in catalog["tools"]}
    assert tools["weather_forecast"]["approval"] is False
    assert "not station" in tools["weather_archive"]["description"].lower()
    skill = next(item for item in catalog["skills"] if item["id"] == "weather-outlook")
    assert "1–16" in skill["workflow"] and "Reanalysis" in skill["workflow"]
    assert {"weather_forecast", "weather_archive"} <= {
        tool["function"]["name"] for tool in schemas()
    }
    assert "city_weather" in {tool["function"]["name"] for tool in schemas(["weather-outlook"])}


@pytest.mark.asyncio
async def test_city_weather_tool_uses_named_location(monkeypatch):
    from skyview.api import weather_dashboard

    monkeypatch.setattr(weather_dashboard, "city_weather", lambda city, days: {"available": True, "city": city, "days": days})
    async with httpx.AsyncClient() as client:
        executor = Executor("trusted-session", "WS01", client)
        result = await executor.run("city_weather", {"city": "Mumbai, Maharashtra", "days": 3})
    assert result == {"available": True, "city": "Mumbai, Maharashtra", "days": 3}
    with pytest.raises(ValidationError):
        models.CityWeatherArgs(city="M", days=3)


def test_selects_one_issued_forecast_and_never_substitutes_demo_scenarios():
    now = datetime(2026, 10, 14, 10, tzinfo=UTC)
    older = now - timedelta(hours=20)
    current = now - timedelta(hours=1)
    records = [
        {
            "series_id": "old",
            "issued_at": older.isoformat(),
            "valid_on": "2026-10-15",
            "kind": "forecast",
            "data_origin": "modeled",
            "rainfall_mm": 20,
        },
        {
            "series_id": "current",
            "issued_at": current.isoformat(),
            "valid_on": "2026-10-15",
            "kind": "forecast",
            "data_origin": "modeled",
            "rainfall_mm": 2,
        },
        {
            "series_id": "current",
            "issued_at": current.isoformat(),
            "valid_on": "2026-10-16",
            "kind": "forecast",
            "data_origin": "modeled",
            "rainfall_mm": 3,
        },
        {
            "series_id": "demo",
            "issued_at": now.isoformat(),
            "valid_on": "2026-10-15",
            "kind": "scenario",
            "data_origin": "synthetic",
            "rainfall_mm": 99,
        },
    ]
    assert [
        item["rainfall_mm"] for item in weather_tools.select_forecast(records, now)
    ] == [2, 3]


def test_select_forecast_rejects_future_issued_and_expired_runs():
    now = datetime(2026, 10, 14, 10, tzinfo=UTC)
    records = [
        {
            "series_id": "bad",
            "issued_at": (now + timedelta(hours=1)).isoformat(),
            "valid_on": "2026-10-15",
            "kind": "forecast",
            "data_origin": "modeled",
        },
        {
            "series_id": "old",
            "issued_at": (now - timedelta(hours=49)).isoformat(),
            "valid_on": "2026-10-15",
            "kind": "forecast",
            "data_origin": "modeled",
        },
    ]
    assert weather_tools.select_forecast(records, now) == []


def test_canonical_forecast_has_no_legacy_fallback(monkeypatch):
    monkeypatch.setattr(weather_tools.db, "enabled", lambda: False)
    result = weather_tools.forecast(None)
    assert result["available"] is False and result["records"] == []
    assert "No forecast was invented" in result["message"]


def test_multiple_owned_farm_locations_require_selection(monkeypatch):
    monkeypatch.setattr(
        weather_tools.repository,
        "rows",
        lambda *args, **kwargs: [
            {"farm_key": "farm1", "name": "North field", "location_id": "loc1"},
            {"farm_key": "farm2", "name": "South field", "location_id": "loc2"},
        ],
    )
    farm, result = weather_tools._farm(None, "verified-owner", "")
    assert farm is None and result["requires_farm_selection"] is True
    assert result["farm_choices"] == [
        {"farm_key": "farm1", "name": "North field"},
        {"farm_key": "farm2", "name": "South field"},
    ]


@pytest.mark.asyncio
async def test_executor_uses_server_bound_farmer_never_arbitrary_location(monkeypatch):
    from skyview.assistant import store

    calls = []
    monkeypatch.setattr(store, "farmer_id", lambda sid: "trusted-owner")
    monkeypatch.setattr(
        weather_tools,
        "forecast",
        lambda owner, days, key: (
            calls.append((owner, days, key)) or {"available": False, "records": []}
        ),
    )
    async with httpx.AsyncClient() as client:
        executor = Executor("trusted-session", "WS01", client)
        result = await executor.run("weather_forecast", {"days": 7})
        assert result["available"] is False
        assert calls == [("trusted-owner", 7, "")]
        with pytest.raises(ValidationError):
            await executor.run("weather_forecast", {"farmer_id": "other-owner"})


def test_rainfall_chart_preserves_zero_and_never_fills_missing_days():
    chart = weather_tools.rain_chart(
        [
            {"day": "2026-10-10", "rainfall_mm": 0},
            {"day": "2026-10-11", "rainfall_mm": None},
            {"day": "2026-10-12", "rainfall_mm": 2},
        ],
        "weather_history",
        "Demo field",
    )
    assert chart["kind"] == "weather_history"
    assert chart["points"] == [
        {"date": "2026-10-10", "value": 0},
        {"date": "2026-10-12", "value": 2},
    ]
    assert chart["value_name"] == "Grid rainfall"


def test_monthly_rainfall_total_reports_actual_coverage():
    result = weather_tools.monthly_summary(
        [
            {"day": "2026-10-10", "rainfall_mm": 0},
            {"day": "2026-10-11", "rainfall_mm": None},
            {"day": "2026-10-12", "rainfall_mm": 2},
        ]
    )
    assert result == [
        {
            "month": "2026-10",
            "days_recorded": 3,
            "rainfall_days_available": 2,
            "rainfall_total_mm": 2,
        }
    ]


@pytest.mark.asyncio
async def test_market_chart_retains_year_but_evidence_stays_bounded(monkeypatch):
    import json

    from skyview.data.v3 import db

    monkeypatch.setattr(db, "enabled", lambda: False)
    start = datetime(2025, 10, 15, tzinfo=UTC)
    records = [
        {
            "market": "One market",
            "variety": "Standard",
            "unit": "INR/quintal",
            "grade": "FAQ",
            "series_id": "one-series",
            "arrival_date": (start + timedelta(days=i)).date().isoformat(),
            "modal_price": 2000 + i,
            "provenance": {"origin": "synthetic"},
        }
        for i in range(365)
    ]
    async with httpx.AsyncClient() as client:
        executor = Executor("fixture-session", "WS01", client)

        async def upstream(*args, **kwargs):
            return {"records": records, "source": "Synthetic integration fixture"}

        monkeypatch.setattr(executor, "upstream", upstream)
        result = await executor.run("market_trend", {"commodity": "Wheat"})
    assert len(result["chart"]["points"]) == 365
    assert result["total_observations"] == 365
    assert len(result["records"]) == 10
    assert result["series_scope"]["unit"] == "INR/quintal"
    assert len(json.dumps(result)) < 30000
