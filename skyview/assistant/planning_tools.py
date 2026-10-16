"""Planning context remains useful without future measurements or a populated KB.

The model supplies conditional agronomic guidance, not fabricated provider facts.
Owned records are evidence and user corrections take precedence.
"""

import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

from skyview.data.v3 import db, repository

from . import reference_tools, store


def planning_window(start_month, end_month, year=None, today=None):
    today = today or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    assumed = year is None
    if year is None:
        year = today.year
        if start_month <= end_month and today.month > end_month:
            year += 1
        elif start_month > end_month and today.month <= end_month:
            year -= 1
    end_year = year + (end_month < start_month)
    return {
        "start": f"{year:04d}-{start_month:02d}-01",
        "end": f"{end_year:04d}-{end_month:02d}-{calendar.monthrange(end_year, end_month)[1]:02d}",
        "year_assumed": assumed,
        "date_basis": "Nearest upcoming/ongoing month window; confirm the year before saving dated tasks"
        if assumed
        else "Farmer-selected planning year",
    }


def seasonal_context(
    sid,
    start_month=1,
    end_month=3,
    year=None,
    state="",
    district="",
    soil_texture="",
    water_availability="",
    crop_names=None,
    language="",
):
    profile = {}
    fields = []
    if db.enabled():
        owner = store.farmer_id(sid)
        profile = repository.profile(owner).get("profile") or {}
        with db.connection(owner) as conn:
            fields = repository.rows(
                conn,
                "SELECT f.name AS farm_name,f.irrigation_method,f.water_source,p.soil_texture,p.area_ha FROM sv3.farms f LEFT JOIN sv3.plots p ON p.farm_id=f.id ORDER BY f.farm_key,p.plot_key LIMIT 20",
            )
    district = district or profile.get("district") or ""
    if district.lower() in {"demo village", "not specified", "unknown"}:
        district = ""
    soil = soil_texture or ", ".join(
        sorted({f["soil_texture"] for f in fields if f.get("soil_texture")})
    )
    water = water_availability or ", ".join(
        sorted(
            {
                ": ".join(
                    filter(None, (f.get("irrigation_method"), f.get("water_source")))
                )
                for f in fields
                if f.get("irrigation_method") or f.get("water_source")
            }
        )
    )
    selected_state = state or profile.get("state") or ""
    crops = list(crop_names or [])
    queries = []
    if crops:
        queries.append(crops[0])
    if 1 <= start_month <= 3:
        queries.append("rabi")
    queries.append("crop calendar")
    references = []
    seen = set()
    for query in queries[:3]:
        result = reference_tools.knowledge_search(query, language="", limit=3)
        for ref in result.get("references", []):
            key = (
                ref.get("source_url"),
                ref.get("page_number"),
                ref.get("section_title"),
            )
            if key not in seen:
                references.append(ref)
                seen.add(key)
    missing = []
    if not selected_state:
        missing.append(
            {"id": "state", "question": "Which state and district is this field in?"}
        )
    elif not district:
        missing.append(
            {"id": "district", "question": "Which district is this field in?"}
        )
    if not soil:
        missing.append(
            {
                "id": "soil",
                "question": "What soil texture do you have—sandy, loamy, clay/black soil, or unsure?",
            }
        )
    if not water:
        missing.append(
            {
                "id": "water",
                "question": f"Will {calendar.month_name[start_month]}–{calendar.month_name[end_month]} irrigation be available, limited, or rainfed only?",
            }
        )
    return {
        "available": True,
        "planning_supported": True,
        "kind": "conditional_crop_planning",
        "window": planning_window(start_month, end_month, year),
        "farm_context": {
            "state": selected_state,
            "district": district,
            "area_acres": profile.get("land_size_acres"),
            "soil_texture": soil,
            "water_availability": water,
            "crop_preferences": crops,
            "recorded_crops": profile.get("crops", []),
            "record_origin": profile.get("data_origin"),
            "interface_mode": db.mode(),
        },
        "targeted_questions": missing[:3],
        "references": references[:6],
        "reviewed_references_available": bool(references),
        "general_guidance": [
            "Build a provisional crop shortlist by local season, growing duration, soil drainage, irrigation reliability, rotation and available labour. Clearly mark assumptions.",
            "For January–March, distinguish sowing a new crop from managing or harvesting an existing winter crop. Local windows vary by district, altitude and irrigation.",
            "Do not automatically move autumn rabi sowing to January/February, promise harvest by March, or treat drip irrigation as proof of enough water. Distinguish an established winter crop from a new late-sown crop; make sowing/harvest windows provisional unless supported by an applicable local calendar.",
            "Give useful preliminary options and explain trade-offs now; ask only the missing facts that change the recommendation. Do not require the farmer to choose a crop before helping compare crops.",
        ],
        "fact_boundaries": {
            "future_daily_weather_known": False,
            "future_mandi_prices_known": False,
            "guaranteed_yield_or_profit": False,
            "chemical_dosage_verified": False,
        },
        "note": "An empty reviewed-reference catalog or absent future sensor/price/weather records does not prevent general seasonal planning. Use reviewed excerpts when relevant; otherwise explicitly label advice as general agronomic guidance, not a sourced local prescription. Ask for the most important missing region/soil/water detail, respect user corrections, and confirm seed variety/local timing with a local adviser before purchase. No calendar task, booking or field action has been performed.",
    }
