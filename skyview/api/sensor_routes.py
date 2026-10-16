"""
Sensor Data Routes
POST /api/sensors/data            — hardware ingestion (LoRa/ESP32 nested JSON)
POST /api/sensors/ingest          — flat JSON ingestion (test_all_routes compatible)
GET  /api/sensors/latest/{station_id}
GET  /api/sensors/history/{station_id}
GET  /api/sensors/stations
POST /api/sensors/trends/store    — store a trends snapshot from the frontend
"""

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skyview.data.db import execute_update
from skyview.data.queries import (
    get_active_installations,
    get_latest_weather,
    get_weather_history,
)
from skyview.utils.logger import get_logger

router = APIRouter(prefix="/api/sensors", tags=["Sensors"])
logger = get_logger(__name__)

# ── Models ────────────────────────────────────────────────────────────────────


class FlatSensorPayload(BaseModel):
    """Flat sensor payload used by test_all_routes and direct HTTP callers."""

    model_config = ConfigDict(allow_inf_nan=False)
    station_id: str = Field(default="WS01", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    wind_speed: float | None = None
    wind_direction: str | None = None
    rainfall: float | None = None
    soil_temperature: float | None = None
    soil_moisture: float | None = None
    pm25: float | None = None
    pm10: float | None = None
    uv_index: float | None = None
    lux: float | None = None
    battery_voltage: float | None = None
    solar_voltage: float | None = None


class TrendsStoreReq(BaseModel):
    station_id: str = "WS01"
    period: str = "24h"
    data: list | None = None  # raw chart data to persist if needed


# ── Helpers ───────────────────────────────────────────────────────────────────


def _insert_weather(params: dict) -> bool:
    from sqlalchemy import text

    return execute_update(
        text("""
            INSERT INTO weather_data (
                station_id, timestamp,
                temperature, humidity, pressure,
                wind_speed, wind_direction, rainfall,
                soil_temperature, soil_moisture,
                pm25, pm10, uv_index, lux,
                battery_voltage, solar_voltage
            ) VALUES (
                :sid, :ts, :temp, :hum, :pres,
                :ws, :wd, :rain,
                :st, :sm, :pm25, :pm10, :uv, :lux, :bat, :sol
            )
        """),
        params,
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/stations")
def list_stations():
    return {"stations": get_active_installations()}


@router.get("/latest/{station_id}")
def latest_reading(station_id: str = "WS01"):
    data = get_latest_weather(station_id)
    if not data:
        return {
            "available": False,
            "station_id": station_id,
            "_source": "unavailable",
            "message": "No measured station readings are available.",
        }
    return data


@router.get("/history/{station_id}")
def history(
    station_id: str = "WS01",
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """
    Returns historical readings.
    Response shape: { station_id, data: [...], totalRecords, returnedRecords }
    The `data` key is what the frontend (weatherData.ts) expects.
    """
    rows = get_weather_history(station_id, hours, limit)
    return {
        "station_id": station_id,
        "data": rows,
        "totalRecords": len(rows),
        "returnedRecords": len(rows),
    }


@router.post("/data")
async def ingest_sensor_data_nested(request: Request):
    """
    Hardware ingestion endpoint for ESP32/LoRa nested JSON format:
    { id, ts, env:{t,h,p}, wind:{s,d}, rain, soil:{t,m}, air:{pm25,pm10},
      rad:{uv,lux}, pwr:{bat,sol} }
    Also accepts the flat format for backwards compatibility.
    """
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise TypeError("Expected a JSON object")
        if "station_id" in data:
            payload = FlatSensorPayload.model_validate(data)
            ts = datetime.now(UTC)
        else:
            if not all(
                key in data
                for key in ("id", "ts", "env", "wind", "soil", "air", "rad", "pwr")
            ):
                raise ValueError("Missing hardware packet fields")
            if not all(
                isinstance(data[key], dict)
                for key in ("env", "wind", "soil", "air", "rad", "pwr")
            ):
                raise ValueError("Hardware groups must be objects")
            if isinstance(data["ts"], bool) or not isinstance(data["ts"], (int, float)):
                raise ValueError("Timestamp must be Unix seconds")
            ts = datetime.fromtimestamp(data["ts"], UTC)
            if abs((datetime.now(UTC) - ts).total_seconds()) > 86400 * 30:
                raise ValueError(
                    "Hardware timestamp is outside the 30-day ingestion window"
                )
            payload = FlatSensorPayload.model_validate(
                {
                    "station_id": data["id"],
                    "temperature": data["env"].get("t"),
                    "humidity": data["env"].get("h"),
                    "pressure": data["env"].get("p"),
                    "wind_speed": data["wind"].get("s"),
                    "wind_direction": data["wind"].get("d"),
                    "rainfall": data.get("rain"),
                    "soil_temperature": data["soil"].get("t"),
                    "soil_moisture": data["soil"].get("m"),
                    "pm25": data["air"].get("pm25"),
                    "pm10": data["air"].get("pm10"),
                    "uv_index": data["rad"].get("uv"),
                    "lux": data["rad"].get("lux"),
                    "battery_voltage": data["pwr"].get("bat"),
                    "solar_voltage": data["pwr"].get("sol"),
                }
            )
    except (ValueError, TypeError, OverflowError, OSError, ValidationError) as exc:
        raise HTTPException(
            422,
            "Invalid sensor packet: check station ID, finite measurements and timestamp.",
        ) from exc
    params = {
        "sid": payload.station_id,
        "ts": ts,
        "temp": payload.temperature,
        "hum": payload.humidity,
        "pres": payload.pressure,
        "ws": payload.wind_speed,
        "wd": payload.wind_direction,
        "rain": payload.rainfall,
        "st": payload.soil_temperature,
        "sm": payload.soil_moisture,
        "pm25": payload.pm25,
        "pm10": payload.pm10,
        "uv": payload.uv_index,
        "lux": payload.lux,
        "bat": payload.battery_voltage,
        "sol": payload.solar_voltage,
    }
    success = await asyncio.to_thread(_insert_weather, params)
    if not success:
        raise HTTPException(
            503, "Station readings could not be saved. Retry this packet."
        )
    return {
        "status": "success",
        "station_id": payload.station_id,
        "timestamp": ts.isoformat(),
    }


@router.post("/trends/store")
async def store_trends(req: TrendsStoreReq):
    """
    Called by the Trends page to persist a snapshot or simply acknowledge.
    Currently logs and returns OK; extend to write to a trends table if needed.
    """
    logger.info(
        "Trends snapshot received: station=%s period=%s points=%d",
        req.station_id,
        req.period,
        len(req.data) if req.data else 0,
    )
    return {
        "status": "acknowledged",
        "persisted": False,
        "station_id": req.station_id,
        "period": req.period,
        "message": "Trends snapshot acknowledged",
    }


@router.post("/ingest")
async def ingest_flat(payload: FlatSensorPayload):
    params = {
        "sid": payload.station_id,
        "ts": datetime.now(UTC),
        "temp": payload.temperature,
        "hum": payload.humidity,
        "pres": payload.pressure,
        "ws": payload.wind_speed,
        "wd": payload.wind_direction,
        "rain": payload.rainfall,
        "st": payload.soil_temperature,
        "sm": payload.soil_moisture,
        "pm25": payload.pm25,
        "pm10": payload.pm10,
        "uv": payload.uv_index,
        "lux": payload.lux,
        "bat": payload.battery_voltage,
        "sol": payload.solar_voltage,
    }
    if not await asyncio.to_thread(_insert_weather, params):
        raise HTTPException(
            503, "Station readings could not be saved. Retry this packet."
        )
    return {
        "status": "success",
        "station_id": payload.station_id,
        "timestamp": params["ts"].isoformat(),
    }
