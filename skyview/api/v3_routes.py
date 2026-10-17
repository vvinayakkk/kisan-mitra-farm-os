"""Unified farmer-facing v3 API. All private reads use server-verified capabilities."""

import hashlib
import json
import math
import secrets
import time
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from skyview.assistant import store
from skyview.data.v3 import db
from skyview.data.v3 import repository as repo

router = APIRouter(tags=["Canonical v3"])


def identity(
    authorization: str | None = Header(default=None),
    x_assistant_session: str | None = Header(default=None),
):
    from skyview.api.assistant_routes import authorize

    authorize(x_assistant_session or "", authorization)
    return store.farmer_id(x_assistant_session)


Owner = Annotated[str, Depends(identity)]


@router.get("/")
def root():
    return {
        "system": "SkyView farmer API v3",
        "status": "running",
        "docs": "/docs",
        "data_mode": db.mode(),
    }


@router.get("/health")
def health():
    try:
        ok = db.health()
    except (SQLAlchemyError, RuntimeError):
        ok = False
    return {
        "status": "healthy" if ok else "degraded",
        "database": "✅" if ok else "❌",
        "data_mode": db.mode(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/api/data/status")
def data_status():
    with db.connection() as conn:
        sources = repo.rows(
            conn,
            "SELECT DISTINCT ON (p.code) p.code AS id,p.name,CASE WHEN h.scope_key='demo-outage-fixture' THEN 'simulated outage fixture' ELSE h.status END AS status,h.last_success_at,h.source_valid_through,h.retry_after,count(*) OVER(PARTITION BY p.code) AS tracked_scopes FROM sv3.source_health h JOIN sv3.providers p ON p.id=h.provider_id ORDER BY p.code,h.checked_at DESC",
        )
        tables = conn.execute(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='sv3' AND c.relkind IN ('r','p') AND NOT c.relispartition"
            )
        ).scalar()
    return {
        "mode": db.mode(),
        "database": db.mode().replace("v3_", "skyview_v3_"),
        "schema": "sv3",
        "tables": tables,
        "connectors": sources,
        "hardware": "mock"
        if db.mode() == "v3_demo"
        else "device-authenticated ingestion",
        "delivery_enabled": False,
        "legacy_database_used": False,
    }


@router.get("/api/sensors/stations")
def stations(owner: Owner):
    with db.connection(owner) as conn:
        items = repo.rows(
            conn,
            "SELECT id,station_key AS station_id,device_type,installed_at,last_received_at FROM sv3.stations ORDER BY station_key",
        )
    return {"stations": items}


@router.get("/api/sensors/latest/{station_id}")
def latest(station_id: str, owner: Owner):
    return repo.station_snapshot(owner, station_id)


@router.get("/api/sensors/history/{station_id}")
def history(
    station_id: str,
    owner: Owner,
    hours: int = Query(24, ge=1, le=8760),
    limit: int = Query(200, ge=1, le=2000),
):
    return repo.weather_history(owner, station_id, hours, limit)


@router.get("/api/sensors/health")
@router.get("/api/system-health")
def system_health(owner: Owner):
    snapshot = repo.station_snapshot(owner)
    return {
        "status": "success",
        "health": {
            "station_online": snapshot.get("available", False)
            and not snapshot.get("provenance", {}).get("stale", True),
            "data_mode": db.mode(),
            "mqtt_connected": False,
            "database_connected": True,
        },
        "data_origin": snapshot.get("data_origin"),
        "provenance": snapshot.get("provenance"),
    }


@router.get("/api/sensors/recent-alerts")
@router.get("/api/recent-alerts")
@router.get("/api/alerts/recent")
def alerts(owner: Owner, limit: int = Query(20, ge=1, le=100)):
    with db.connection(owner) as conn:
        items = repo.rows(
            conn,
            "SELECT a.id,a.category AS title,a.message,a.severity,a.issued_at AS timestamp,a.expires_at,a.status,a.acknowledged_at,d.origin AS data_origin FROM sv3.alert_events a JOIN sv3.datasets d ON d.id=a.dataset_id WHERE status='active' AND expires_at>now() ORDER BY issued_at DESC LIMIT :limit",
            {"limit": limit},
        )
    return {"status": "success", "alerts": items, "count": len(items)}


@router.get("/api/sensors/trends/history")
@router.get("/api/trends/history")
def trends(
    owner: Owner,
    station_id: str = "WS01",
    period: str = "24h",
    limit: int = Query(200, ge=1, le=1000),
):
    hours = {"24h": 24, "7d": 168, "30d": 720}.get(period, 24)
    data = repo.weather_history(owner, station_id, hours, limit)
    return {**data, "history": data["data"], "records": data["data"], "period": period}


@router.post("/api/sensors/trends/store")
def trends_store(owner: Owner):
    return {
        "status": "acknowledged",
        "persisted": False,
        "message": "Trend views use canonical packets; no duplicate snapshot is stored.",
    }


@router.get("/api/mandi/commodities")
def commodities():
    with db.connection() as conn:
        items = repo.rows(conn, "SELECT name FROM sv3.crops ORDER BY name")
    return {"commodities": [r["name"] for r in items]}


@router.get("/api/mandi/catalog")
@router.get("/api/mandi/catalogue")
def market_catalogue(
    commodity: str = "",
    state: str = "",
    q: str = "",
    limit: int = Query(200, ge=1, le=200),
    observed_only: bool = False,
):
    return repo.market_catalogue(commodity, state, q, limit, observed_only)


@router.get("/api/mandi")
@router.get("/api/mandi/rates")
def rates(
    commodity: str = "",
    state: str = "",
    limit: int = Query(50, ge=1, le=200),
    market: str = "",
    observed_only: bool = False,
):
    return repo.market_rates(commodity, state, limit, market, observed_only)


@router.get("/api/mandi/history")
def market_history(
    commodity: str = "",
    state: str = "",
    market: str = "",
    limit: int = Query(100, ge=1, le=3000),
    year: int | None = None,
    month: int | None = Query(None, ge=1, le=12),
    week: int | None = Query(None, ge=1, le=53),
    observed_only: bool = False,
):
    return repo.market_history(
        commodity, state, market, limit, year, month, week, observed_only
    )


@router.get("/api/mandi/scenarios")
def price_scenarios(
    commodity: str = "", state: str = "", limit: int = Query(365, ge=1, le=1000)
):
    from skyview.assistant.reference_tools import price_scenarios as planning_scenarios

    return planning_scenarios(commodity, state, days=min(limit, 365), compact=False)


@router.get("/api/mandi/msp")
def msp(crop: str = "", limit: int = Query(50, ge=1, le=200)):
    with db.connection() as conn:
        items = repo.rows(
            conn,
            """SELECT c.name AS crop,a.marketing_season AS effective_season,a.amount_inr_quintal AS msp_rs_quintal,a.announced_on,a.effective_from,a.official_url AS source_url,'INR/quintal' AS unit,d.origin AS data_origin
     FROM sv3.msp_announcements a JOIN sv3.crops c ON c.id=a.crop_id JOIN sv3.datasets d ON d.id=a.dataset_id WHERE (:crop='' OR lower(c.name)=lower(:crop)) ORDER BY announced_on DESC LIMIT :limit""",
            {"crop": crop, "limit": limit},
        )
    return {
        "status": "success",
        "available": bool(items),
        "count": len(items),
        "records": items,
        "message": None
        if items
        else "No reviewed MSP announcement has been imported yet; no rate is invented.",
    }


@router.get("/api/profile")
def profile(owner: Owner, phone: str | None = None):
    return repo.profile(owner)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    name: str | None = Field(None, min_length=1, max_length=100)
    preferred_language: str | None = Field(None, max_length=12)

    @field_validator("preferred_language")
    @classmethod
    def supported_language(cls, value):
        from skyview.languages import normalize_language

        return normalize_language(value) if value is not None else None

    location: str | None = Field(None, max_length=200)
    district: str | None = Field(None, max_length=100)
    land_size_acres: float | None = Field(None, gt=0, le=100000)
    crops: list[str] | str | None = None
    excess_resources: list[str] | str | None = None
    required_resources: list[str] | str | None = None
    sharing_public: bool | None = None


@router.post("/api/profile/save")
def save_profile(body: ProfileUpdate, owner: Owner):
    changes = body.model_dump(exclude_none=True)
    name = changes.pop("name", None)
    language = changes.pop("preferred_language", None)
    for key in ("crops", "excess_resources", "required_resources"):
        if isinstance(changes.get(key), str):
            changes[key] = [
                part.strip() for part in changes[key].split(",") if part.strip()
            ]
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.farmers SET display_name=coalesce(:name,display_name),preferred_language=coalesce(:language,preferred_language),profile_attributes=profile_attributes||CAST(:attrs AS jsonb) WHERE id=:owner"
            ),
            {
                "name": name,
                "language": language,
                "attrs": json.dumps(changes),
                "owner": owner,
            },
        )
        if changes.get("sharing_public") is True:
            conn.execute(
                text(
                    "INSERT INTO sv3.consents(farmer_id,purpose,granted_at,evidence_hash) VALUES(:owner,'public_listing',now(),:hash)"
                ),
                {
                    "owner": owner,
                    "hash": hashlib.sha256(
                        json.dumps(changes, sort_keys=True).encode()
                    ).hexdigest(),
                },
            )
        elif changes.get("sharing_public") is False:
            conn.execute(
                text(
                    "UPDATE sv3.consents SET revoked_at=now() WHERE purpose='public_listing' AND revoked_at IS NULL"
                )
            )
    return repo.profile(owner)


@router.get("/api/schemes")
def schemes(
    state: str = "", crop: str = "", q: str = "", limit: int = Query(100, ge=1, le=100)
):
    return repo.schemes(state, crop, limit, q=q)


@router.get("/api/schemes/recommendations")
def scheme_recommendations(
    owner: Owner, state: str = "", crop: str = "", phone: str | None = None
):
    data = repo.schemes(state, crop)
    for item in data["schemes"]:
        item["match_status"] = "missing_information"
        item["questions"] = item["requirements"].get("questions", [])
    return {**data, "recommendations": data["schemes"], "official_approval": False}


@router.get("/api/schemes/{scheme_id}")
def scheme(scheme_id: str):
    return next(
        (
            r
            for r in repo.schemes()["schemes"]
            if scheme_id in (r["scheme_id"], r["scheme_code"])
        ),
        {"available": False, "message": "Scheme reference not found."},
    )


@router.get("/api/marketplace/farmers")
@router.get("/api/marketplace/directory")
def directory(owner: Owner):
    return repo.directory()


def distance(a, b):
    if any(
        v is None
        for v in (
            a.get("latitude"),
            a.get("longitude"),
            b.get("latitude"),
            b.get("longitude"),
        )
    ):
        return None
    lat1, lon1, lat2, lon2 = map(
        math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"])
    )
    return (
        6371
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin((lat2 - lat1) / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
                ),
            )
        )
    )


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    required_resources: list[str] | str | None = None
    max_distance_km: float = Field(1000, ge=0, le=20000)


@router.post("/api/marketplace/match")
def matches(body: MatchRequest, owner: Owner):
    own = repo.profile(owner)["profile"]

    def resources(value):
        if isinstance(value, str):
            value = value.split(",")
        return list(
            dict.fromkeys(
                str(resource).strip()
                for resource in (value or [])
                if str(resource).strip()
            )
        )

    needed_resources = resources(
        body.required_resources or own.get("required_resources", [])
    )
    needed = {value.casefold() for value in needed_resources}
    offered = {value.casefold() for value in resources(own.get("excess_resources", []))}
    found = []
    for item in repo.directory()["farmers"]:
        if str(item["id"]) == str(owner):
            continue
        their_offers = resources(item.get("excess_resources", []))
        their_needs = resources(item.get("required_resources", []))
        incoming = [value for value in their_offers if value.casefold() in needed]
        outgoing = [value for value in their_needs if value.casefold() in offered]
        if not incoming and not outgoing:
            continue
        km = distance(own, item)
        if km is None or km > body.max_distance_km:
            continue
        mutual = bool(incoming and outgoing)
        covered = len({value.casefold() for value in incoming}) + len(
            {value.casefold() for value in outgoing}
        )
        total_needs = len(needed) + len({value.casefold() for value in their_needs})
        percentage = round(100 * covered / total_needs) if total_needs else 0
        found.append(
            {
                **item,
                "distance_km": round(km, 1),
                "distance_kind": "approximate_straight_line",
                "matched_resources": list(dict.fromkeys(incoming + outgoing)),
                "match_score": covered,
                "match_percentage": percentage,
                "match_percentage_basis": "Coverage of both farmers' stated resource needs; not trust or guaranteed availability",
                "match_type": "mutual"
                if mutual
                else "provider"
                if incoming
                else "consumer",
                "is_mutual": mutual,
                "is_provider": bool(incoming),
                "is_consumer": bool(outgoing),
                "what_they_have": their_offers,
                "what_they_need": their_needs,
                "i_provide_they_need": outgoing,
                "they_provide_i_need": incoming,
                "contact_status": "Request mutual consent before sharing contacts",
                "agreements_executed": False,
            }
        )
    found.sort(
        key=lambda item: (
            not item["is_mutual"],
            -item["match_percentage"],
            item["distance_km"],
            str(item["id"]),
        )
    )
    return {
        "status": "success",
        "search_context": own,
        "matches": found[:40],
        "ai_advisory": "Matches are possible sharing proposals, not completed agreements.",
    }


@router.post("/api/marketplace/circular-barter")
def loops(owner: Owner, body: MatchRequest):
    own = repo.profile(owner)["profile"]
    people = [own] + [r for r in repo.directory()["farmers"] if r["id"] != owner][:400]
    found = []

    def overlap(a, b):
        return next(
            (
                x
                for x in a.get("excess_resources", [])
                if x.casefold()
                in {y.casefold() for y in b.get("required_resources", [])}
            ),
            None,
        )

    for b in people[1:]:
        ab = overlap(own, b)
        if not ab:
            continue
        for c in people[1:]:
            if c["id"] == b["id"]:
                continue
            bc, ca = overlap(b, c), overlap(c, own)
            if not (bc and ca):
                continue
            legs = [distance(own, b), distance(b, c), distance(c, own)]
            if any(k is None or k > body.max_distance_km for k in legs):
                continue
            found.append(
                {
                    "id": f"{b['id']}:{c['id']}",
                    "farmers": [own, b, c],
                    "trades": [
                        {
                            "from": own["name"],
                            "to": b["name"],
                            "item": ab,
                            "distance_km": round(legs[0], 1),
                        },
                        {
                            "from": b["name"],
                            "to": c["name"],
                            "item": bc,
                            "distance_km": round(legs[1], 1),
                        },
                        {
                            "from": c["name"],
                            "to": own["name"],
                            "item": ca,
                            "distance_km": round(legs[2], 1),
                        },
                    ],
                    "total_distance_km": round(sum(legs), 1),
                    "ai_schedule": "Proposed only: confirm availability, dates and mutual terms.",
                    "agreements_executed": False,
                }
            )
            if len(found) >= 10:
                return {"status": "success", "count": len(found), "loops": found}
    return {"status": "success", "count": len(found), "loops": found}


@router.get("/api/marketplace/pooling")
def pooling(owner: Owner):
    grouped = {}
    for person in repo.directory()["farmers"]:
        key = person["state"]
        cluster = grouped.setdefault(
            key,
            {
                "region": key,
                "state": key,
                "district": "Coarse shared region",
                "farmers": [],
                "total_land_acres": 0,
                "excess_pool": [],
                "required_pool": [],
            },
        )
        cluster["farmers"].append(person)
        cluster["total_land_acres"] += person["land_size_acres"] or 0
        cluster["excess_pool"] += person["excess_resources"]
        cluster["required_pool"] += person["required_resources"]
    for cluster in grouped.values():
        cluster["farmer_count"] = len(cluster["farmers"])
        cluster["excess_pool"] = sorted(set(cluster["excess_pool"]))
        cluster["required_pool"] = sorted(set(cluster["required_pool"]))
        cluster["optimization_plan"] = [
            "Confirm which equipment owners want to share.",
            "Agree dates and costs before booking.",
            "Record acceptance from each participant.",
        ]
    return {"status": "success", "clusters": list(grouped.values())}


class Negotiate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    farmer_b_phone: str = Field(max_length=100)
    item_a: str | None = None
    item_b: str | None = None


@router.post("/api/marketplace/negotiate")
def negotiate(body: Negotiate, owner: Owner):
    candidate = next(
        (
            r
            for r in repo.directory()["farmers"]
            if r["phone"] == body.farmer_b_phone or r["id"] == body.farmer_b_phone
        ),
        None,
    )
    if not candidate:
        raise HTTPException(404, "Only consenting public listings can be proposed.")
    return {
        "status": "success",
        "agreement_executed": False,
        "negotiation_log": [
            "Proposal prepared; no participant has accepted terms.",
            "Confirm equipment availability, dates, transport and price.",
        ],
        "proposal": {
            "owner": owner,
            "listing": candidate["id"],
            "item_a": body.item_a,
            "item_b": body.item_b,
        },
        "message": "This is an unsigned sharing proposal, not a completed deal.",
    }


class AdvisorRequest(BaseModel):
    category: str = "overview"
    station_id: str = "WS01"


@router.post("/api/advisor/insights")
def advice(body: AdvisorRequest, owner: Owner):
    snap = repo.station_snapshot(owner, body.station_id)
    if not snap.get("available"):
        return {
            "status": "unavailable",
            "category": body.category,
            "sensor_snapshot": snap,
            "ai_insights": None,
            "message": "Register a station or upload field observations first.",
        }
    category = body.category
    if category == "water":
        insight = {
            "moisture_status": "Relative sensor trend; volumetric calibration not confirmed",
            "schedule": "Check field moisture, crop stage and current rain forecast before planning watering.",
            "liters_per_acre": None,
            "tips": [
                "Confirm rooting depth and field capacity.",
                "Check the forecast and actual field conditions.",
            ],
            "warnings": [
                "No pump operation or calibrated watering quantity has been inferred."
            ],
        }
    elif category == "soil":
        insight = {
            "score": None,
            "status": "Lab evidence needed",
            "nutrients": "Read the dated soil report; telemetry does not measure NPK.",
            "risk": "Unknown until soil/field evidence is reviewed.",
            "recommendations": [
                "Upload a soil report to review pH, conductivity and nutrients."
            ],
        }
    elif category == "pests":
        insight = [
            {
                "name": "Photo and scouting needed",
                "risk": "Unknown",
                "symptoms": "Describe affected crop, plant stage and symptoms.",
                "remedy": "Use Crop Doctor with a clear photo; no chemical treatment inferred.",
                "prevention": "Inspect several plants and retain symptom photos.",
            }
        ]
    elif category == "crops":
        insight = []
    elif category == "alerts":
        insight = alerts(owner)["alerts"]
    elif category == "tips":
        insight = [
            "Record what you observe in the field.",
            "Compare dated prices for the same crop, variety and unit.",
            "Review due tasks before changing the plan.",
        ]
    else:
        insight = {
            "summary": "Your farm context is available from canonical v3 records.",
            "focus_points": [
                "Review station freshness",
                "Check crop stage and due tasks",
                "Compare source-labeled prices",
            ],
            "details": "Ask Mitra for a source-backed plan. Demo inputs remain explicitly synthetic.",
        }
    return {
        "status": "success",
        "category": category,
        "sensor_snapshot": snap,
        "ai_insights": insight,
        "provenance": snap["provenance"],
        "action_executed": False,
    }


@router.get("/api/weather/forecast")
def forecast(
    owner: Owner,
    days: int = Query(7, ge=1, le=16),
    farm_key: str = Query("", max_length=100),
):
    from skyview.assistant.weather_tools import forecast as canonical_forecast

    return canonical_forecast(owner, days, farm_key)


@router.get("/api/weather/dashboard")
def weather_dashboard(owner: Owner, farm_key: str = Query("", max_length=100)):
    from skyview.api.weather_dashboard import dashboard

    return dashboard(owner, farm_key)


@router.get("/api/weather/location-dashboard")
def weather_location_dashboard(
    owner: Owner,
    latitude: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    longitude: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
):
    """Coarse device-area forecast, deliberately separate from saved farm data."""
    from skyview.api.weather_dashboard import location_dashboard
    try:
        return location_dashboard(round(latitude, 2), round(longitude, 2))
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Nearby forecast is temporarily unavailable") from None


@router.get("/api/weather/cities")
def weather_cities(owner: Owner, q: str = Query("", max_length=100)):
    from skyview.api.weather_dashboard import search_cities

    try:
        return {"cities": search_cities(q)}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "City search is temporarily unavailable") from None


@router.get("/api/weather/city-dashboard")
def weather_city_dashboard(owner: Owner, city_id: int = Query(..., ge=1)):
    from skyview.api.weather_dashboard import city_dashboard

    try:
        return city_dashboard(city_id)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "City forecast is temporarily unavailable") from None


@router.post("/api/sensors/ingest")
@router.post("/api/sensors/data")
async def ingest(request: Request, authorization: str | None = Header(None)):

    from skyview.data.v3.ingestion import ingest_sensor_envelope

    payload = await request.json()
    station_key = payload.get("station_id") or payload.get("id")
    if not station_key or not authorization or not authorization.startswith("Device "):
        raise HTTPException(401, "An enrolled device credential is required.")
    with db.connection() as conn:
        credential = (
            conn.execute(
                text("SELECT * FROM sv3.verify_device(:station)"),
                {"station": station_key},
            )
            .mappings()
            .first()
        )
    if not credential or not secrets.compare_digest(
        credential["key_hash"], hashlib.sha256(authorization[7:].encode()).hexdigest()
    ):
        raise HTTPException(401, "Invalid or revoked device credential.")
    try:
        with db.connection(credential["farmer_id"], write=True, ingest=True) as conn:
            result = ingest_sensor_envelope(
                conn,
                str(credential["farmer_id"]),
                str(credential["station_id"]),
                {k: v for k, v in payload.items() if k not in ("station_id", "id")},
                lane=db.mode().removeprefix("v3_"),
            )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return result


_demo_challenges = {}


class DemoLogin(BaseModel):
    phone: str = Field(min_length=1, max_length=20)
    otp: str | None = Field(None, max_length=12)
    is_signup: bool = False


@router.post("/api/auth/send-otp")
def send_demo_otp(body: DemoLogin):
    if db.mode() != "v3_demo" or "".join(c for c in body.phone if c.isdigit()) not in (
        "9999999999",
        "919999999999",
        "9876543210",
        "919876543210",
    ):
        raise HTTPException(
            503,
            "Real OTP login needs a configured verification provider. No SMS has been sent. Use the explicit demo account for local demo mode.",
        )
    if len(_demo_challenges) > 100:
        _demo_challenges.clear()
    _demo_challenges[body.phone] = time.monotonic() + 300
    return {
        "status": "success",
        "sms_sent": False,
        "demo_bypass": True,
        "otp": "999999",
        "message": "Local demo challenge only; no message was delivered.",
    }


@router.post("/api/auth/verify-otp")
def verify_demo_otp(body: DemoLogin):
    expiry = _demo_challenges.pop(body.phone, 0)
    if db.mode() != "v3_demo" or expiry < time.monotonic() or body.otp != "999999":
        raise HTTPException(401, "Invalid or expired demo challenge.")
    session = store.create_session()
    return {
        "status": "success",
        "token": session["token"],
        "session_id": session["id"],
        "session": session,
        "demo": True,
        "phone_verified": False,
    }


@router.post("/api/auth/signup")
def signup(owner: Owner):
    return {
        "status": "success",
        "profile": repo.profile(owner)["profile"],
        "phone_verified": False,
    }


@router.get("/api/fpga/status")
def fpga_status(owner: Owner):
    from skyview.agents.fpga_agent import get_fpga_bridge

    hardware = get_fpga_bridge().get_status()
    if hardware["connected"]:
        return {
            "status": "ok",
            "hardware_mode": "real_hardware",
            "fpga_status": hardware,
            "physical_hardware_confirmed": True,
        }
    return {
        "status": "ok",
        "hardware_mode": "mock" if db.mode() == "v3_demo" else "not_connected",
        "fpga_status": {**hardware, "simulation": db.mode() == "v3_demo"},
        "physical_hardware_confirmed": False,
    }
