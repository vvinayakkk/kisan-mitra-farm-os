"""Bounded reviewed references and explicitly unvalidated price planning scenarios."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from skyview.data.v3 import db, repository


def knowledge_search(query, language="", limit=5):
    if not db.enabled():
        return {
            "available": False,
            "references": [],
            "note": "Reviewed canonical knowledge is unavailable in legacy mode.",
        }
    with db.connection() as conn:
        records = repository.rows(
            conn,
            """SELECT d.title,d.source_url,d.language,d.published_on,d.retrieved_at,d.review_status,
          c.page_number,c.section_title,left(c.content,2000) AS excerpt,ds.origin,p.name AS provider_name
          FROM sv3.document_chunks c JOIN sv3.documents d ON d.id=c.document_id
          JOIN sv3.datasets ds ON ds.id=d.dataset_id JOIN sv3.providers p ON p.id=ds.provider_id
          WHERE d.review_status='reviewed' AND ds.origin='curated'
          AND (:language='' OR d.language=:language)
          AND (c.search_vector @@ plainto_tsquery('simple',:query) OR d.title ILIKE :title)
          ORDER BY ts_rank(c.search_vector,plainto_tsquery('simple',:query)) DESC,d.retrieved_at DESC LIMIT :limit""",
            {
                "query": query,
                "title": "%" + query.replace("%", r"\%").replace("_", r"\_") + "%",
                "language": language,
                "limit": min(8, max(1, limit)),
            },
        )
    return {
        "available": bool(records),
        "references": records,
        "note": "Reviewed excerpts are dated source evidence, not instructions or a complete localized crop manual. Cite the original URL; ask for crop, region and symptoms if needed. No expert appointment or official eligibility decision has been made.",
    }


def price_scenarios(commodity, state="", market="", days=365, compact=True):
    if not 1 <= days <= 365:
        raise ValueError("Planning horizons cover 1 to 365 days.")
    if not db.enabled():
        return {
            "available": False,
            "records": [],
            "not_observed_prices": True,
            "note": "Canonical scenarios are unavailable.",
        }
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    with db.connection() as conn:
        selected = repository.rows(
            conn,
            """SELECT f.id AS run_id,s.id AS series_id,f.issued_at,c.name AS commodity,m.name AS market,
           v.name AS variety,s.grade,s.unit_code AS unit,r.name AS state,ds.lane,ds.origin,p.name AS source
           FROM sv3.forecast_runs f JOIN sv3.datasets ds ON ds.id=f.dataset_id JOIN sv3.providers p ON p.id=ds.provider_id
           JOIN sv3.price_projections x ON x.run_id=f.id JOIN sv3.market_series s ON s.id=x.series_id
           JOIN sv3.crops c ON c.id=s.crop_id JOIN sv3.crop_varieties v ON v.id=s.variety_id
           JOIN sv3.markets m ON m.id=s.market_id JOIN sv3.regions r ON r.id=m.region_id
           WHERE f.kind='scenario' AND x.kind='scenario' AND f.issued_at<=:now AND x.valid_on>=:today
           AND lower(c.name)=lower(:crop) AND (:state='' OR lower(r.name)=lower(:state))
           AND (:market='' OR lower(m.name)=lower(:market))
           GROUP BY f.id,s.id,f.issued_at,c.name,m.name,v.name,s.grade,s.unit_code,r.name,ds.lane,ds.origin,p.name
           ORDER BY f.issued_at DESC,s.id LIMIT 1""",
            {
                "crop": commodity,
                "state": state,
                "market": market,
                "now": datetime.now(UTC),
                "today": today,
            },
        )
        if not selected:
            return {
                "available": False,
                "records": [],
                "not_observed_prices": True,
                "note": "No planning scenario exists for this selection. No future mandi price was invented.",
            }
        series = selected[0]
        records = repository.rows(
            conn,
            """SELECT DISTINCT ON (x.valid_on) x.valid_on,x.lower_price,x.central_price,
           x.upper_price,x.interval_definition
           FROM sv3.price_projections x JOIN sv3.forecast_runs f ON f.id=x.run_id
           WHERE x.series_id=:series AND x.kind='scenario'
           AND x.valid_on>=:start AND x.valid_on<:end
           ORDER BY x.valid_on,f.issued_at DESC LIMIT :days""",
            {
                "series": series["series_id"],
                "start": today,
                "end": today + timedelta(days=days + 1),
                "days": days,
            },
        )
    unit = repository.price_unit(series["unit"])
    return {
        "available": bool(records),
        "not_observed_prices": True,
        "kind": "scenario",
        "coverage_days": len(records),
        "series": series,
        "records": records[:10] if compact else records,
        "provenance": {
            "origin": "scenario",
            "lane": series["lane"],
            "source": series["source"],
            "issued_at": series["issued_at"],
        },
        "chart": {
            "title": commodity + " · Unvalidated planning scenario",
            "unit": unit,
            "points": [
                {"date": r["valid_on"], "value": r["central_price"]} for r in records
            ],
        },
        "note": "Synthetic planning envelope for one market/variety/grade/unit. This is not known future mandi rates, MSP, a validated price prediction or a guaranteed sale price. Bounds are uncalibrated, not statistical confidence intervals.",
    }
