"""The farmer weather view may use only owned grids and sourced values."""

from contextlib import nullcontext

import httpx

from skyview.api import weather_dashboard


def test_dashboard_uses_owned_grid_and_live_forecast_if_worker_is_pending(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        weather_dashboard,
        "forecast",
        lambda owner, **kwargs: {"available": False, "message": "Not imported yet"},
    )
    monkeypatch.setattr(weather_dashboard.db, "connection", lambda owner: nullcontext())

    def owned_rows(_conn, _sql, params):
        seen.update(params)
        return [
            {
                "farm_key": "farm-a",
                "name": "North farm",
                "latitude": 18.25,
                "longitude": 73.5,
            }
        ]

    monkeypatch.setattr(weather_dashboard.repository, "rows", owned_rows)
    monkeypatch.setattr(
        weather_dashboard,
        "_public_weather",
        lambda lat, lon: {
            "source": "Open-Meteo",
            "captured_at": "2026-10-16T01:00:00+00:00",
            "daily": {
                "time": ["2026-10-16"],
                "temperature_2m_max": [31],
                "temperature_2m_min": [21],
                "precipitation_sum": [4],
            },
        },
    )
    result = weather_dashboard.dashboard("owner-a", "farm-a")
    assert seen == {"owner": "owner-a", "farm_key": "farm-a"}
    assert result["available"] is True
    assert result["forecast"]["records"] == [
        {
            "valid_on": "2026-10-16",
            "temperature_max_c": 31,
            "temperature_min_c": 21,
            "rainfall_mm": 4,
        }
    ]


def test_dashboard_keeps_stored_forecast_when_provider_fails(monkeypatch):
    stored = {
        "available": True,
        "farm_key": "farm-a",
        "records": [{"valid_on": "2026-10-16", "rainfall_mm": 2}],
    }
    monkeypatch.setattr(weather_dashboard, "forecast", lambda owner, **kwargs: stored)
    monkeypatch.setattr(weather_dashboard.db, "connection", lambda owner: nullcontext())
    monkeypatch.setattr(
        weather_dashboard.repository,
        "rows",
        lambda *_args, **_kwargs: [
            {
                "farm_key": "farm-a",
                "name": "North farm",
                "latitude": 18.25,
                "longitude": 73.5,
            }
        ],
    )

    def unavailable(*_args):
        raise httpx.ConnectError("source unavailable")

    monkeypatch.setattr(weather_dashboard, "_public_weather", unavailable)
    result = weather_dashboard.dashboard("owner-a", "farm-a")
    assert result["forecast"] is stored
    assert result["live"] is None
    assert "unavailable" in result["live_error"]


def test_city_search_and_dashboard_use_provider_location(monkeypatch):
    city = {
        "id": 1275339,
        "name": "Mumbai",
        "admin1": "Maharashtra",
        "country": "India",
        "latitude": 19.07,
        "longitude": 72.88,
    }
    monkeypatch.setattr(
        weather_dashboard,
        "_geocoding",
        lambda path, params: {"results": [city]} if path == "search" else city,
    )
    seen = []

    def public_weather(latitude, longitude):
        seen.append((latitude, longitude))
        return {
            "source": "Open-Meteo",
            "timezone": "Asia/Kolkata",
            "captured_at": "2026-10-16T01:00:00+00:00",
            "current": {"temperature_2m": 28, "weather_code": 61, "is_day": 1},
            "daily": {
                "time": ["2026-10-16"],
                "temperature_2m_max": [31],
                "temperature_2m_min": [24],
                "precipitation_sum": [6],
                "precipitation_probability_max": [80],
            },
        }

    monkeypatch.setattr(weather_dashboard, "_public_weather", public_weather)
    assert weather_dashboard.search_cities("Mumbai")[0]["id"] == city["id"]
    assert (
        weather_dashboard.city_dashboard(city["id"])["forecast"]["records"][0][
            "rainfall_mm"
        ]
        == 6
    )
    assert weather_dashboard.city_weather("Mumbai")["current"]["weather_code"] == 61
    assert seen == [(19.07, 72.88), (19.07, 72.88)]


def test_city_weather_asks_when_exact_name_is_ambiguous(monkeypatch):
    monkeypatch.setattr(
        weather_dashboard,
        "search_cities",
        lambda query, count=6: [
            {
                "id": 1,
                "name": "Springfield",
                "admin1": "Illinois",
                "country": "United States",
            },
            {
                "id": 2,
                "name": "Springfield",
                "admin1": "Massachusetts",
                "country": "United States",
            },
        ],
    )
    result = weather_dashboard.city_weather("Springfield")
    assert result["requires_city_selection"] is True
    assert len(result["city_choices"]) == 2
