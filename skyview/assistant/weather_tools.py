"""Read-only canonical grid weather. No station impersonation or synthetic fallback."""

import math
from datetime import UTC, datetime, timedelta

from skyview.data.v3 import db, repository

UNITS = {
    "temperature_min_c": "°C",
    "temperature_max_c": "°C",
    "rainfall_mm": "mm",
    "rainfall_probability": "fraction 0–1",
    "humidity_mean_pct": "%",
    "et0_mm": "mm/day",
}


def rain_chart(records, kind, farm):
    date_key = "valid_on" if kind == "weather_forecast" else "day"
    points = []
    for row in records:
        value = row.get("rainfall_mm")
        if value is not None and math.isfinite(float(value)):
            points.append({"date": str(row[date_key]), "value": float(value)})
    if len(points) < 2:
        return None
    return {
        "type": "line",
        "kind": kind,
        "title": f"{farm} · rainfall",
        "unit": "mm",
        "value_name": "Forecast rainfall"
        if kind == "weather_forecast"
        else "Grid rainfall",
        "caption": "Captured grid-model weather forecast"
        if kind == "weather_forecast"
        else "Historical grid weather / reanalysis",
        "points": points,
    }


def monthly_summary(records):
    groups = {}
    for row in records:
        groups.setdefault(str(row["day"])[:7], []).append(row)
    summary = []
    for month, rows in sorted(groups.items()):
        rain = [
            float(row["rainfall_mm"])
            for row in rows
            if row.get("rainfall_mm") is not None
            and math.isfinite(float(row["rainfall_mm"]))
        ]
        summary.append(
            {
                "month": month,
                "days_recorded": len(rows),
                "rainfall_days_available": len(rain),
                "rainfall_total_mm": round(sum(rain), 3) if rain else None,
            }
        )
    return summary


def _farm(conn, owner, key):
    farms = repository.rows(
        conn,
        "SELECT farm_key,name,location_id FROM sv3.farms WHERE farmer_id=:owner AND (:key='' OR farm_key=:key) ORDER BY farm_key",
        {"owner": owner, "key": key},
    )
    if not farms:
        return None, {
            "available": False,
            "records": [],
            "message": "No owned farm with a weather location was found. Complete your farm profile first.",
        }
    if not key and len({f["location_id"] for f in farms if f["location_id"]}) > 1:
        return None, {
            "available": False,
            "records": [],
            "requires_farm_selection": True,
            "farm_choices": [
                {"farm_key": f["farm_key"], "name": f["name"]} for f in farms
            ],
            "message": "Ask which farm the farmer wants; these farms have different weather locations.",
        }
    farm = farms[0]
    if not farm["location_id"]:
        return None, {
            "available": False,
            "records": [],
            "message": "This farm has no linked weather location. Complete its location before requesting a forecast.",
        }
    return farm, None


def select_forecast(records, now):
    """Pick one captured forecast response and one value per day, never mixed snapshots."""
    groups = {}
    for row in records:
        if row.get("kind") != "forecast" or row.get("data_origin") not in {
            "modeled",
            "derived",
        }:
            continue
        issued = datetime.fromisoformat(str(row["issued_at"]))
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=UTC)
        if issued > now or now - issued > timedelta(hours=48):
            continue
        key = (str(row["series_id"]), issued)
        groups.setdefault(key, {})

        groups[key].setdefault(str(row["valid_on"]), row)
    if not groups:
        return []
    key = max(groups, key=lambda key: (key[1], len(groups[key]), key[0]))
    return [groups[key][day] for day in sorted(groups[key])]


def forecast(owner, days=7, farm_key="", now=None):
    if not 1 <= days <= 16:
        raise ValueError("Weather forecasts cover 1 to 16 days only.")
    if not db.enabled():
        return {
            "available": False,
            "records": [],
            "message": "Canonical weather forecasts are unavailable in legacy mode. No forecast was invented.",
        }
    now = now or datetime.now(UTC)
    from zoneinfo import ZoneInfo

    start = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    with db.connection(owner) as conn:
        farm, missing = _farm(conn, owner, farm_key)
        if missing:
            return missing
        data = repository.rows(
            conn,
            """SELECT w.series_id,w.issued_at,w.valid_on,w.kind,w.temperature_min_c,w.temperature_max_c,w.rainfall_mm,w.rainfall_probability,w.method,
          d.origin AS data_origin,d.origin,d.lane,d.created_at AS fetched_at,d.source_url,p.name AS provider_name,s.model_name,s.resolution_m,s.max_forecast_lead_days
          FROM sv3.weather_forecasts w JOIN sv3.weather_series s ON s.id=w.series_id JOIN sv3.datasets d ON d.id=w.dataset_id JOIN sv3.providers p ON p.id=s.provider_id
          WHERE s.location_id=:location AND w.kind='forecast' AND d.origin IN ('modeled','derived') AND w.issued_at<=:now AND w.issued_at>=:now-interval '48 hours'
          AND w.valid_on>=:start AND w.valid_on<:end AND w.valid_on<=(w.issued_at AT TIME ZONE 'Asia/Kolkata')::date+s.max_forecast_lead_days
          ORDER BY w.issued_at DESC,d.created_at DESC,w.valid_on LIMIT 2048""",
            {
                "location": farm["location_id"],
                "now": now,
                "start": start,
                "end": start + timedelta(days=days),
            },
        )
    records = select_forecast(data, now)
    if not records:
        return {
            "available": False,
            "records": [],
            "farm": farm["name"],
            "message": "No recent source-backed forecast is available for this farm. Demo scenarios were not substituted.",
        }
    issued = datetime.fromisoformat(str(records[0]["issued_at"]))
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=UTC)
    provenance = {
        "origin": "forecast",
        "data_origin": records[0]["data_origin"],
        "lane": records[0]["lane"],
        "source": records[0]["provider_name"],
        "source_url": records[0]["source_url"],
        "issued_at": issued.isoformat(),
        "timestamp_basis": "provider_response_snapshot_capture; provider model initialization time is unavailable",
        "model_selection": "provider default, not a pinned model run",
        "resolution_basis": "nominal estimate, not confirmed by this provider response",
        "fetched_at": records[0]["fetched_at"],
        "stale": now - issued > timedelta(hours=24),
        "model": records[0]["model_name"],
        "resolution_m": records[0]["resolution_m"],
    }
    return {
        "available": True,
        "farm": farm["name"],
        "farm_key": farm["farm_key"],
        "chart": rain_chart(records, "weather_forecast", farm["name"]),
        "records": records,
        "days_requested": days,
        "coverage_days": len(records),
        "source": provenance["source"],
        "provenance": provenance,
        "units": UNITS,
        "note": "A captured grid-model forecast, not farm sensor readings. Its timestamp identifies our provider-response snapshot; the provider did not supply a model initialization time. Missing dates are not filled. Rain likelihood is a probability, not guaranteed rain or an irrigation instruction.",
    }


def archive(owner, days=30, farm_key="", now=None):
    if not 1 <= days <= 366:
        raise ValueError("Weather archives cover 1 to 366 days per request.")
    if not db.enabled():
        return {
            "available": False,
            "records": [],
            "message": "Canonical weather archives are unavailable in legacy mode. No climate history was invented.",
        }
    now = now or datetime.now(UTC)
    from zoneinfo import ZoneInfo

    end = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    with db.connection(owner) as conn:
        farm, missing = _farm(conn, owner, farm_key)
        if missing:
            return missing
        rows = repository.rows(
            conn,
            """SELECT w.series_id,w.day,w.kind,w.temperature_min_c,w.temperature_max_c,w.rainfall_mm,w.humidity_mean_pct,w.et0_mm,
          d.origin AS data_origin,d.origin,d.lane,d.created_at AS fetched_at,d.source_url,p.name AS provider_name,s.model_name,s.resolution_m
          FROM sv3.weather_daily w JOIN sv3.weather_series s ON s.id=w.series_id JOIN sv3.datasets d ON d.id=w.dataset_id JOIN sv3.providers p ON p.id=s.provider_id
          WHERE s.location_id=:location AND d.origin<>'synthetic' AND w.kind<>'synthetic' AND w.day>=:start AND w.day<:end
          ORDER BY d.created_at DESC,w.day DESC LIMIT 10000""",
            {
                "location": farm["location_id"],
                "start": end - timedelta(days=days),
                "end": end,
            },
        )
    groups = {}
    for row in rows:
        groups.setdefault(str(row["series_id"]), {}).setdefault(str(row["day"]), row)
    if not groups:
        return {
            "available": False,
            "records": [],
            "farm": farm["name"],
            "message": "No source-backed grid weather history has been imported for this farm. Demo history was not substituted.",
        }
    key = max(
        groups,
        key=lambda key: (
            len(groups[key]),
            str(next(iter(groups[key].values()))["fetched_at"]),
            key,
        ),
    )
    records = [groups[key][day] for day in sorted(groups[key])]
    provenance = repository.provenance(records[-1])

    latest = datetime.fromisoformat(str(records[-1]["day"])).date()
    provenance["stale"] = (end - latest).days > 7
    provenance["resolution_m"] = records[-1]["resolution_m"]
    provenance["observed_at"] = str(records[-1]["day"])
    return {
        "available": True,
        "farm": farm["name"],
        "farm_key": farm["farm_key"],
        "days_requested": days,
        "coverage_days": len(records),
        "missing_days": max(0, days - len(records)),
        "source": records[-1]["provider_name"],
        "provenance": provenance,
        "units": UNITS,
        "note": "Regional grid history/reanalysis, not measurements from your station or lab. One model series is shown without filling gaps or merging incompatible grids. Monthly totals use available rainfall values only; check coverage counts.",
        "chart": rain_chart(records, "weather_history", farm["name"]),
        "monthly_summary": monthly_summary(records),
        "records": records,
    }
