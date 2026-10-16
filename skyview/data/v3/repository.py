"""Shared canonical queries used directly by HTTP routes and assistant tools."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .db import connection, mode


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def rows(db, sql, params=None):
    return clean([dict(r) for r in db.execute(text(sql), params or {}).mappings()])


def provenance(row, origin=None):
    stamp = row.get("received_at") or row.get("fetched_at") or row.get("created_at")

    def age_seconds(value):
        if not value:
            return None
        try:
            instant = datetime.fromisoformat(str(value))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=UTC)
            return max(0, (datetime.now(UTC) - instant).total_seconds())
        except (ValueError, TypeError):
            return None

    age = age_seconds(stamp)
    observed = (
        row.get("observed_at") or row.get("observed_on") or row.get("arrival_date")
    )
    observation_age = age_seconds(observed)

    freshness_window = (
        172800 if row.get("arrival_date") or row.get("observed_on") else 300
    )
    stale_age = observation_age if observation_age is not None else age
    return {
        "origin": origin or row.get("origin", "unknown"),
        "lane": row.get("lane", mode().removeprefix("v3_")),
        "source": row.get("provider_name") or row.get("source", "SkyView v3"),
        "source_url": row.get("source_url"),
        "as_of": row.get("as_of_date"),
        "observed_at": observed,
        "fetched_at": stamp,
        "age_seconds": round(age) if age is not None else None,
        "observation_age_seconds": round(observation_age)
        if observation_age is not None
        else None,
        "stale": bool(stale_age is not None and stale_age > freshness_window),
    }


def _station(db, station_id):

    return (
        db.execute(
            text("SELECT * FROM sv3.pick_station(:key,:first_station)"),
            {"key": station_id, "first_station": station_id == "WS01"},
        )
        .mappings()
        .first()
    )


def station_snapshot(farmer_id, station_id="WS01"):
    with connection(farmer_id) as db:
        station = _station(db, station_id)
        if not station:
            return {
                "available": False,
                "station_id": station_id,
                "message": "No station is registered to this farm.",
                "data_origin": "unavailable",
            }
        records = [
            row["record"]
            for row in rows(
                db,
                "SELECT sv3.latest_station_packet(:station) AS record",
                {"station": station["id"]},
            )
            if row["record"] is not None
        ]
    if not records:
        return {
            "available": False,
            "station_id": station_id,
            "message": "No valid station packets have arrived.",
            "data_origin": "unavailable",
        }
    raw = records[0]
    result = {
        "available": True,
        "station_id": str(station["station_key"]),
        "timestamp": raw["observed_at"],
        "received_at": raw["received_at"],
        "quality_flags": raw["quality_flags"],
        "_source": raw["origin"],
        "data_origin": raw["origin"],
        "provenance": provenance(raw),
    }
    mapping = {
        "temperature_c": "temperature",
        "humidity_pct": "humidity",
        "pressure_hpa": "pressure",
        "wind_kmh": "windSpeed",
        "wind_direction_degrees": "windDirection",
        "rainfall_increment_mm": "rainfall",
        "soil_temperature_c": "soilTemperature",
        "soil_moisture_pct": "soilMoisture",
        "pm25_ug_m3": "airQualityPM25",
        "pm10_ug_m3": "airQualityPM10",
        "uv_index": "uvIndex",
        "lux": "lightIntensity",
        "battery_v": "batteryVoltage",
        "solar_v": "solarVoltage",
    }
    for src, dst in mapping.items():
        result[dst] = raw[src]
    result.update(
        {
            "soil_moisture": result["soilMoisture"],
            "soil_temperature": result["soilTemperature"],
            "wind_speed": result["windSpeed"],
            "wind_direction": result["windDirection"],
            "pm25": result["airQualityPM25"],
            "pm10": result["airQualityPM10"],
            "uv_index": result["uvIndex"],
            "lux": result["lightIntensity"],
            "battery_voltage": result["batteryVoltage"],
            "solar_voltage": result["solarVoltage"],
            "soil_moisture_basis": "relative_percent_unless_calibrated",
        }
    )
    return result


def weather_history(farmer_id, station_id="WS01", hours=24, limit=100):
    with connection(farmer_id) as db:
        station = _station(db, station_id)
        if not station:
            return {
                "station_id": station_id,
                "data": [],
                "totalRecords": 0,
                "returnedRecords": 0,
            }
        records = [
            row["record"]
            for row in rows(
                db,
                "SELECT sv3.station_packet_history(:station,:hours,:limit) AS record",
                {
                    "station": station["id"],
                    "hours": min(8760, max(1, hours)),
                    "limit": min(2000, max(1, limit)),
                },
            )
        ]
    return {
        "station_id": station_id,
        "data": records,
        "totalRecords": len(records),
        "returnedRecords": len(records),
        "source": "SkyView v3 timestamped packets",
    }


def price_unit(code):
    return {
        "inr_per_quintal": "INR/quintal",
        "inr_per_tonne": "INR/tonne",
        "inr_per_100_nuts": "INR/100 nuts",
        "inr_per_kg": "INR/kg",
    }.get(code, "INR/" + code)


_MARKET_REGIONS = """WITH RECURSIVE market_regions AS (
 SELECT id, name AS state, NULL::text AS district FROM sv3.regions WHERE level IN ('state','ut')
 UNION ALL SELECT r.id,p.state,CASE WHEN r.level='district' THEN r.name ELSE p.district END
 FROM sv3.regions r JOIN market_regions p ON r.parent_id=p.id
) """
_MARKET_FILTER = """(:crop='' OR lower(c.name)=ANY(CAST(:crop_aliases AS text[])) OR lower(c.code)=ANY(CAST(:crop_aliases AS text[]))
 OR EXISTS (SELECT 1 FROM jsonb_each_text(c.names) a WHERE lower(a.value)=lower(:crop)))
 AND (:state='' OR lower(coalesce(mr.state,r.name))=lower(:state))
 AND (:market='' OR lower(m.name)=lower(:market) OR m.id::text=:market) """


def _crop_aliases(value):
    value = value.strip().casefold()
    groups = (
        ("rice", "paddy"),
        ("arhar", "pigeonpea", "pigeon pea", "pigeon-pea", "tur"),
        ("okra", "bhindi", "lady finger", "ladies finger"),
        ("eggplant", "brinjal"),
        ("chickpea", "gram", "bengal gram", "chana"),
        ("pearl millet", "bajra"),
        ("sorghum", "jowar"),
        ("mung bean", "green gram", "moong"),
        ("black gram", "urad"),
    )
    return list(next((group for group in groups if value in group), (value,)))


def _market_records(records):
    for row in records:
        row["provenance"] = provenance(row)
        row["unit"] = price_unit(row["unit"])
        row["source"] = row["provider_name"]
    return records


def market_history(
    commodity="",
    state="",
    market="",
    limit=100,
    year=None,
    month=None,
    week=None,
    observed_only=False,
):
    with connection() as db:
        records = [
            row["record"]
            for row in rows(
                db,
                """SELECT sv3.market_price_history(
                :crop,CAST(:crop_aliases AS text[]),:state,:market,
                :year,:month,:week,:observed_only,:limit
            ) AS record""",
                {
                    "crop": commodity.strip(),
                    "crop_aliases": _crop_aliases(commodity),
                    "state": state.strip(),
                    "market": market.strip(),
                    "observed_only": observed_only,
                    "year": year,
                    "month": month,
                    "week": week,
                    "limit": min(3000, max(1, limit)),
                },
            )
        ]
    records = _market_records(records)
    return {
        "status": "success",
        "available": bool(records),
        "count": len(records),
        "records": records,
        "source": "Reported mandi prices" if observed_only else "Mandi price history",
        "observed_only": observed_only,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def market_rates(commodity="", state="", limit=20, market="", observed_only=False):

    with connection() as db:
        records = [
            row["record"]
            for row in rows(
                db,
                """SELECT sv3.market_latest_prices(
                :crop,CAST(:crop_aliases AS text[]),:state,:market,
                :observed_only,:limit
            ) AS record""",
                {
                    "crop": commodity.strip(),
                    "crop_aliases": _crop_aliases(commodity),
                    "state": state.strip(),
                    "market": market.strip(),
                    "observed_only": observed_only,
                    "limit": min(200, max(1, limit)),
                },
            )
        ]
    records = _market_records(records)
    return {
        "status": "success",
        "available": bool(records),
        "count": len(records),
        "rates": records,
        "records": records,
        "source": "Reported mandi prices" if observed_only else "Mandi prices",
        "observed_only": observed_only,
        "note": "Check the reporting date before comparing prices.",
    }


def market_catalogue(commodity="", state="", q="", limit=200, observed_only=False):
    with connection() as db:
        crops = rows(db, "SELECT name FROM sv3.crops ORDER BY name")
        states = rows(
            db,
            "SELECT DISTINCT name FROM sv3.regions WHERE level IN ('state','ut') ORDER BY name",
        )
        markets = rows(
            db,
            _MARKET_REGIONS
            + """SELECT m.id::text,m.name,coalesce(mr.state,r.name) AS state,mr.district,
 coalesce(array_agg(DISTINCT c.name ORDER BY c.name) FILTER(WHERE c.name IS NOT NULL),ARRAY[]::text[]) AS commodities,
 ds.origin AS data_origin,ds.source_url,count(DISTINCT s.id)>0 AS has_price_series
 FROM sv3.markets m JOIN sv3.datasets ds ON ds.id=m.dataset_id JOIN sv3.regions r ON r.id=m.region_id LEFT JOIN market_regions mr ON mr.id=r.id
 LEFT JOIN sv3.market_series s ON s.market_id=m.id LEFT JOIN sv3.crops c ON c.id=s.crop_id
 WHERE """
            + _MARKET_FILTER.replace(":market", ":unused_market")
            + """
 AND (:observed_only=false OR ds.origin IN ('observed','curated'))
 AND (:q='' OR m.name ILIKE :pattern OR coalesce(mr.state,r.name) ILIKE :pattern OR c.name ILIKE :pattern)
 GROUP BY m.id,m.name,mr.state,r.name,mr.district,ds.origin,ds.source_url ORDER BY (ds.origin<>'synthetic') DESC,m.name,m.id LIMIT :limit""",
            {
                "crop": commodity.strip(),
                "crop_aliases": _crop_aliases(commodity),
                "state": state.strip(),
                "unused_market": "",
                "observed_only": observed_only,
                "q": q.strip(),
                "pattern": "%" + q.strip() + "%",
                "limit": min(200, max(1, limit)),
            },
        )
    return {
        "commodities": [r["name"] for r in crops],
        "states": [r["name"] for r in states],
        "markets": markets,
        "returned_markets": len(markets),
        "market_limit": min(200, max(1, limit)),
        "as_of_date": datetime.now(UTC)
        .astimezone(ZoneInfo("Asia/Kolkata"))
        .date()
        .isoformat(),
    }


def schemes(state="", crop="", limit=100, q=""):

    aliases = {
        "insurance": "insurance|pmfby|fasal bima|rwbcis",
        "loan": "credit|loan|kcc|interest",
        "water": "water|irrigation|sinchai",
        "solar": "solar|kusum",
        "organic": "organic|paramparagat|jaivik",
        "storage": "storage|warehouse|infrastructure",
        "pension": "pension|maan.*dhan",
        "women": "women|woman|mahila",
        "fertilizer": "fertilizer|fertiliser|soil",
    }
    query = q.strip().casefold()
    import re

    pattern = aliases.get(query, re.escape(query))
    with connection() as db:
        records = rows(
            db,
            """SELECT s.id::text AS scheme_id,s.scheme_code,s.name AS scheme_name,s.application_url AS official_url,s.requirements,s.benefits,s.valid_from,s.valid_to,
         coalesce(r.name,'India') AS state,d.source_url,d.title AS source_title,d.review_status,s.verified_at,
         ds.origin,ds.origin AS data_origin,ds.lane,ds.created_at,v.name AS provider_name
         FROM sv3.scheme_versions s JOIN sv3.documents d ON d.id=s.document_id JOIN sv3.datasets ds ON ds.id=d.dataset_id JOIN sv3.providers v ON v.id=ds.provider_id
         LEFT JOIN sv3.regions r ON r.id=s.region_id WHERE (s.valid_from IS NULL OR s.valid_from<=(now() AT TIME ZONE 'Asia/Kolkata')::date)
         AND (s.valid_to IS NULL OR s.valid_to>=(now() AT TIME ZONE 'Asia/Kolkata')::date)
         AND (:state='' OR r.id IS NULL OR lower(r.name)=lower(:state))
         AND (:q='' OR (s.name||' '||s.scheme_code||' '||s.requirements::text||' '||s.benefits::text) ~* :pattern)
         ORDER BY s.name LIMIT :limit""",
            {
                "state": state.strip(),
                "q": query,
                "pattern": pattern,
                "limit": min(100, max(1, limit)),
            },
        )
    for row in records:
        row.update(
            {
                "name": row["scheme_name"],
                "scheme_type": row["scheme_code"],
                "benefit_description": row["benefits"].get(
                    "description", "Review the official application details."
                ),
                "eligibility": row["requirements"].get(
                    "summary", "Answer eligibility questions; this is not an approval."
                ),
                "status": "Reviewed reference"
                if row["review_status"] == "reviewed"
                else "Needs source review",
                "applicable_crops": "Check official notified crops",
                "source": row["provider_name"],
                "provenance": provenance(row),
            }
        )
    return {
        "status": "success",
        "available": bool(records),
        "count": len(records),
        "schemes": records,
        "source": "Versioned official scheme references",
        "note": "Potential matches only; official authority makes eligibility decisions.",
    }


def profile(farmer_id):
    with connection(farmer_id) as db:
        profiles = rows(
            db,
            "SELECT f.*,r.name AS state,d.origin,d.lane FROM sv3.farmers f LEFT JOIN sv3.regions r ON r.id=f.region_id JOIN sv3.datasets d ON d.id=f.dataset_id WHERE f.id=:id",
            {"id": farmer_id},
        )
        if not profiles:
            return {"status": "unavailable", "profile": None}
        farmer = profiles[0]
        fields = rows(
            db,
            "SELECT sum(area_ha)*2.47105381 AS acres,avg(latitude) AS lat,avg(longitude) AS lon FROM sv3.plots",
        )
        crops = rows(
            db,
            "SELECT DISTINCT c.name FROM sv3.crop_cycles cc JOIN sv3.crops c ON c.id=cc.crop_id WHERE cc.status='growing'",
        )
        resources = rows(
            db, "SELECT name FROM sv3.resources WHERE category='equipment'"
        )
    attrs = farmer["profile_attributes"]
    p = {
        "id": farmer["id"],
        "phone": farmer["contact_phone"],
        "name": farmer["display_name"],
        "land_size_acres": attrs.get("land_size_acres", fields[0]["acres"]),
        "mapped_plot_area_acres": fields[0]["acres"],
        "location": attrs.get("location", farmer["state"]),
        "state": farmer["state"],
        "district": attrs.get(
            "district", "Demo village" if farmer["origin"] == "synthetic" else ""
        ),
        "crops": attrs.get("crops", [r["name"] for r in crops]),
        "active_crop_cycles": [r["name"] for r in crops],
        "latitude": fields[0]["lat"],
        "longitude": fields[0]["lon"],
        "excess_resources": attrs.get(
            "excess_resources", [r["name"] for r in resources]
        ),
        "required_resources": attrs.get("required_resources", []),
        "whatsapp_number": None,
        "preferred_language": farmer["preferred_language"],
        "data_origin": farmer["origin"],
        "provenance": provenance(farmer),
    }
    return {"status": "success", "profile": p}


def directory():
    with connection() as db:
        records = rows(db, "SELECT * FROM sv3.public_farmer_directory()")
        notices = rows(
            db,
            "SELECT id,farmer_id,title,category,kind,quantity,unit,exchange_for FROM sv3.exchange_listings WHERE status='published' AND sv3.exchange_listing_open(id) ORDER BY updated_at DESC LIMIT 2000",
        )
    by_farmer = {}
    for notice in notices:
        by_farmer.setdefault(notice["farmer_id"], []).append(notice)
    for row in records:
        row.update(
            {
                "phone": "listing:" + row["id"],
                "whatsapp_number": None,
                "data_origin": row["origin"],
                "sharing_contact_available": False,
                "exchange_listings": by_farmer.get(row["id"], [])[:8],
            }
        )
    return {
        "status": "success",
        "farmers": records,
        "source": "Explicit demo neighbors or consenting public listings; contacts withheld",
    }
