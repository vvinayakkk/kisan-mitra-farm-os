"""Shared bounded data access for both the station UI and agent tools."""

import asyncio
import math
import os
from datetime import UTC, datetime

import httpx


async def upstream(client, station_id, path, params=None):
    base = os.getenv("ASSISTANT_DATA_URL", "").rstrip("/")
    if not base:

        def local_read():
            from skyview.data.queries import get_latest_weather, get_weather_history

            query = params or {}
            if path.startswith("/api/sensors/latest/"):
                return get_latest_weather(station_id) or {"available": False}
            if path.startswith("/api/sensors/history/"):
                return {
                    "data": get_weather_history(
                        station_id,
                        query.get("hours", 24),
                        query.get("limit", 100),
                    )
                }
            if path == "/api/schemes":
                from skyview.api.profile_routes import get_schemes_catalog

                return get_schemes_catalog(
                    state=query.get("state") or None,
                    q=query.get("q") or None,
                    limit=query.get("limit", 8),
                )
            if path == "/api/mandi/history":
                from skyview.api.mandi_routes import mandi_history

                return mandi_history(
                    commodity=query.get("commodity"),
                    state=query.get("state") or None,
                    market=None,
                    year=None,
                    month=None,
                    week=None,
                    limit=100,
                )
            raise ValueError("Unknown data source")

        return await asyncio.to_thread(local_read)
    response = await client.get(base + path, params=params, timeout=8)
    response.raise_for_status()
    return response.json()


async def station_snapshot(client, station_id, reader=None):
    try:
        data = (
            await reader(f"/api/sensors/latest/{station_id}")
            if reader
            else await upstream(client, station_id, f"/api/sensors/latest/{station_id}")
        )
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            "available": False,
            "message": "Station measurements are unavailable. Try again shortly.",
        }
    if (
        not isinstance(data, dict)
        or data.get("_source") in ("mock", "fallback", "demo")
        or data.get("available") is False
    ):
        return {
            "available": False,
            "message": "No measured station readings are available.",
        }
    stamp = data.get("timestamp")
    try:
        received = datetime.fromisoformat(str(stamp))
        if received.tzinfo is None:
            received = received.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - received).total_seconds()
        if age < -300:
            raise ValueError("Future measurement")
    except (ValueError, TypeError):
        return {
            "available": False,
            "message": "The station supplied an invalid measurement time.",
        }
    # Never promote non-finite values or booleans into measured telemetry.
    clean = {
        key: (
            None
            if isinstance(value, bool)
            or (isinstance(value, float) and not math.isfinite(value))
            else value
        )
        for key, value in data.items()
    }
    clean["timestamp"] = received.astimezone(UTC).isoformat()
    return {
        "available": True,
        "stale": age > 60,
        "age_seconds": round(max(0, age)),
        "source": "station measurements",
        "station_id": station_id,
        "data": clean,
    }
