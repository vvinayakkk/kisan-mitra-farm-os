"""Short-lived, owner-scoped weather display data for a linked farm.

The canonical stored forecast remains the fallback. Extra current/hourly values
are fetched only for the farm's already consented coarse weather grid.
"""

from __future__ import annotations

import threading
import time
import math
from datetime import UTC, datetime

import httpx

from skyview.assistant.weather_tools import forecast
from skyview.data.v3 import db, repository

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_CACHE_SECONDS = 900
_city_cache: dict[str, tuple[float, object]] = {}


def _geocoding(path: str, params: dict) -> dict:
    key = f"{path}:{sorted(params.items())}"
    with _cache_lock:
        cached = _city_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
    with httpx.Client(timeout=6, follow_redirects=False) as client:
        response = client.get(
            f"https://geocoding-api.open-meteo.com/v1/{path}", params=params
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("City lookup is unavailable")
    with _cache_lock:
        if len(_city_cache) >= 128:
            _city_cache.pop(next(iter(_city_cache)))
        _city_cache[key] = (time.monotonic() + 86400, payload)
    return payload


def _city(item: dict) -> dict:
    latitude, longitude = float(item["latitude"]), float(item["longitude"])
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
    ):
        raise ValueError("Invalid city coordinates")
    return {
        "id": int(item["id"]),
        "name": str(item["name"]),
        "admin1": str(item.get("admin1") or ""),
        "country": str(item.get("country") or ""),
        "latitude": latitude,
        "longitude": longitude,
    }


def search_cities(query: str, count: int = 6) -> list[dict]:
    query = query.strip()
    if len(query) < 2 or len(query) > 100:
        return []
    payload = _geocoding(
        "search", {"name": query, "count": min(count, 10), "language": "en"}
    )
    return [
        _city(item) for item in payload.get("results", []) if isinstance(item, dict)
    ]


def city_dashboard(city_id: int) -> dict:
    if city_id <= 0:
        raise ValueError("Choose a city from search results")
    city = _city(_geocoding("get", {"id": city_id, "language": "en"}))
    live = _public_weather(city["latitude"], city["longitude"])
    daily = live["daily"]
    return {
        "available": True,
        "city": {key: city[key] for key in ("id", "name", "admin1", "country")},
        "live": live,
        "forecast": {
            "farm": city["name"],
            "farm_key": "",
            "records": [
                {
                    "valid_on": date,
                    "temperature_max_c": daily["temperature_2m_max"][index],
                    "temperature_min_c": daily["temperature_2m_min"][index],
                    "rainfall_mm": daily["precipitation_sum"][index],
                }
                for index, date in enumerate(daily["time"])
            ],
            "provenance": {"source": live["source"], "issued_at": live["captured_at"]},
            "note": "Regional model forecast for this city, not a farm measurement.",
        },
    }


def location_dashboard(latitude: float, longitude: float) -> dict:
    live = _public_weather(round(latitude, 2), round(longitude, 2))
    return {
        "available": True,
        "location_kind": "device_area",
        "live": live,
        "forecast": {
            "farm": "Near you",
            "records": [],
            "provenance": {"source": live["source"], "issued_at": live["captured_at"]},
            "note": "Regional weather near your device; not a farm sensor measurement.",
        },
    }


def city_weather(query: str, days: int = 7) -> dict:
    matches = search_cities(query, count=6)
    if not matches:
        return {
            "available": False,
            "message": "No matching city found. Ask for city and state or country.",
        }
    exact = [
        item for item in matches if item["name"].casefold() == query.strip().casefold()
    ]
    if len(exact) > 1:
        return {
            "available": False,
            "requires_city_selection": True,
            "city_choices": [
                {key: item[key] for key in ("name", "admin1", "country")}
                for item in exact
            ],
        }
    result = city_dashboard((exact or matches)[0]["id"])
    live = result["live"]
    current = live["current"]
    daily = live["daily"]
    return {
        "available": True,
        "city": result["city"],
        "source": live["source"],
        "captured_at": live["captured_at"],
        "timezone": live["timezone"],
        "current": {
            key: current.get(key)
            for key in (
                "time",
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "is_day",
            )
        },
        "forecast": [
            {
                "date": date,
                "high_c": daily["temperature_2m_max"][index],
                "low_c": daily["temperature_2m_min"][index],
                "rain_mm": daily["precipitation_sum"][index],
                "rain_chance_percent": daily.get(
                    "precipitation_probability_max", [None] * len(daily["time"])
                )[index],
            }
            for index, date in enumerate(daily["time"][:days])
        ],
        "note": "Regional model estimate; confirm field conditions before irrigation or spraying.",
    }


def _public_weather(latitude: float, longitude: float) -> dict:
    key = f"{latitude:.2f}:{longitude:.2f}"
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

    with httpx.Client(timeout=8, follow_redirects=False) as client:
        weather = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "auto",
                "forecast_days": 10,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure",
                "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,sunrise,sunset,uv_index_max",
            },
        )
        weather.raise_for_status()
        payload = weather.json()
        daily = payload.get("daily", {})
        required = (
            "time",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        )
        if (
            payload.get("error")
            or not daily.get("time")
            or any(
                not isinstance(daily.get(key), list)
                or len(daily[key]) != len(daily["time"])
                for key in required
            )
        ):
            raise ValueError("Weather provider returned no forecast")

        air = None
        air_grid = []
        try:
            neighbors = [
                (round(latitude + delta_lat, 2), round(longitude + delta_lon, 2))
                for delta_lat in (0.35, 0, -0.35)
                for delta_lon in (-0.35, 0, 0.35)
            ]
            response = client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": ",".join(str(point[0]) for point in neighbors),
                    "longitude": ",".join(str(point[1]) for point in neighbors),
                    "timezone": "Asia/Kolkata",
                    "current": "us_aqi,pm2_5,pm10,uv_index",
                },
            )
            response.raise_for_status()
            air_payload = response.json()
            if isinstance(air_payload, list) and len(air_payload) == 9:
                air = air_payload[4].get("current")
                air_grid = [
                    item.get("current", {}).get("us_aqi") for item in air_payload
                ]
            elif isinstance(air_payload, dict):
                air = air_payload.get("current")
        except (httpx.HTTPError, ValueError):
            pass

    result = {
        "current": payload.get("current", {}),
        "hourly": payload.get("hourly", {}),
        "daily": payload["daily"],
        "air": air,
        "air_grid": air_grid,
        "captured_at": datetime.now(UTC).isoformat(),
        "source": "Open-Meteo",
        "air_source": "Open-Meteo / CAMS" if air else None,
        "timezone": payload.get("timezone", "Asia/Kolkata"),
        "kind": "regional_grid_model",
    }
    with _cache_lock:
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic() + _CACHE_SECONDS, result)
    return result


def dashboard(owner: str, farm_key: str = "") -> dict:
    stored = forecast(owner, days=10, farm_key=farm_key)
    if stored.get("requires_farm_selection"):
        return stored
    with db.connection(owner) as conn:
        rows = repository.rows(
            conn,
            """SELECT f.farm_key,f.name,l.latitude,l.longitude FROM sv3.farms f
               JOIN sv3.locations l ON l.id=f.location_id
               WHERE f.farmer_id=:owner AND (:farm_key='' OR f.farm_key=:farm_key)
               ORDER BY f.farm_key LIMIT 1""",
            {"owner": owner, "farm_key": farm_key or stored.get("farm_key", "")},
        )
    result = {
        "available": bool(stored.get("available")),
        "forecast": stored if stored.get("available") else None,
        "live": None,
    }
    if not rows or rows[0]["latitude"] is None or rows[0]["longitude"] is None:
        return result if result["available"] else stored
    try:
        live = _public_weather(float(rows[0]["latitude"]), float(rows[0]["longitude"]))
        result["live"] = live
        if not result["available"]:
            daily = live["daily"]
            result["forecast"] = {
                "farm": rows[0]["name"],
                "farm_key": rows[0]["farm_key"],
                "records": [
                    {
                        "valid_on": date,
                        "temperature_max_c": daily["temperature_2m_max"][index],
                        "temperature_min_c": daily["temperature_2m_min"][index],
                        "rainfall_mm": daily["precipitation_sum"][index],
                    }
                    for index, date in enumerate(daily["time"])
                ],
                "provenance": {
                    "source": live["source"],
                    "issued_at": live["captured_at"],
                },
                "note": "Captured regional weather model forecast, not an on-farm measurement.",
            }
            result["available"] = True
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        result["live_error"] = (
            f"Live weather details are unavailable ({type(exc).__name__}). The dated forecast below is still available."
        )
    return result if result["available"] else stored
