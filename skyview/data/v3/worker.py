"""Supervised, process-leased local ingestion. Public location anchors only leave the server."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import text

from skyview.data.v3.db import connection, enabled, engine, mode
from skyview.data.v3.ingestion import (
    Ingestor,
    execute,
    fetch_mandi,
    fetch_power,
    fetch_weather,
    import_reviewed,
    ingest_mock_packet,
)

log = logging.getLogger(__name__)
_LEASE = 731840126
_worker = None


def _rollover_delay(now=None):
    """Refresh at the India date boundary even when the server stays up overnight."""
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Kolkata"))
    midnight = (local + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return min(21600, max(1, (midnight - local).total_seconds() + 5))


def _lease():
    db = engine().connect().execution_options(isolation_level="AUTOCOMMIT")
    if not db.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": _LEASE}
    ).scalar():
        db.close()
        return None
    return db


def _release(db):
    try:
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LEASE})
    finally:
        db.close()


def _eligible_locations():
    """Only consented coarse grids, plus explicitly configured public anchors."""
    with connection(ingest=True) as db:
        locations = list(
            execute(
                db,
                "SELECT id,latitude,longitude FROM sv3.consented_weather_locations() LIMIT 500",
            )
            .mappings()
            .all()
        )
        if mode() == "v3_demo":
            public = (
                execute(
                    db,
                    """SELECT DISTINCT l.id,l.latitude,l.longitude FROM sv3.locations l
              JOIN sv3.farms f ON f.location_id=l.id JOIN sv3.farmers p ON p.id=f.farmer_id
              JOIN sv3.datasets d ON d.id=l.dataset_id
              WHERE p.profile_key=:key AND d.origin<>'user_reported' ORDER BY l.id LIMIT 1""",
                    key=os.getenv("V3_DEMO_FARMER_KEY", "DEMO-F0001"),
                )
                .mappings()
                .first()
            )
        else:
            key = os.getenv("V3_INGEST_LOCATION_KEY")
            public = (
                execute(
                    db,
                    """SELECT l.id,l.latitude,l.longitude FROM sv3.locations l JOIN sv3.datasets d ON d.id=l.dataset_id
              WHERE l.location_key=:key AND d.origin<>'user_reported' ORDER BY l.id LIMIT 1""",
                    key=key,
                )
                .mappings()
                .first()
                if key
                else None
            )
        if public and all(item["id"] != public["id"] for item in locations):
            locations.insert(0, public)
        return locations


def _selected_location():
    locations = _eligible_locations()
    return locations[0] if locations else None


def _weather_due(health, history, now):
    if health is None:
        return True
    if health.get("retry_after") and health["retry_after"] > now:
        return False
    if health.get("status") != "healthy":
        return True
    checked = health.get("checked_at")
    if not checked:
        return True
    if history:
        valid = health.get("source_valid_through")
        return (
            not valid
            or valid < now.date() - timedelta(days=7)
            or checked < now - timedelta(days=1)
        )
    return checked < now - timedelta(hours=6)


def _weather_jobs(limit=3, now=None):
    now = now or datetime.now(UTC)
    locations = _eligible_locations()
    if not locations:
        return []
    with connection(ingest=True) as db:
        health_rows = (
            execute(
                db,
                """SELECT p.code,h.scope_key,h.checked_at,h.retry_after,h.status,h.source_valid_through
          FROM sv3.source_health h JOIN sv3.providers p ON p.id=h.provider_id
          WHERE p.code IN ('open_meteo','nasa_power')""",
            )
            .mappings()
            .all()
        )
    health = {(h["code"], h["scope_key"]): dict(h) for h in health_rows}
    candidates = []
    for location in locations:
        jobs = []
        ages = []
        for source, history, power in [
            ("open_meteo", False, False),
            ("open_meteo", True, False),
            ("nasa_power", True, True),
        ]:
            scope = str(location["id"]) + (":history" if history else ":forecast")
            item = health.get((source, scope))
            if _weather_due(item, history, now):
                jobs.append((source, history, power, scope))
                ages.append(
                    item["checked_at"]
                    if item and item.get("checked_at")
                    else datetime.min.replace(tzinfo=UTC)
                )
        if jobs:
            candidates.append((min(ages), location, jobs))
    candidates.sort(key=lambda item: item[0])
    return [
        (location, jobs) for _, location, jobs in candidates[: max(1, min(limit, 8))]
    ]


def _telemetry(selected=True, offset=0):
    if mode() != "v3_demo":
        return 0
    now = datetime.now(UTC)
    with connection(ingest=True, write=True) as db:
        execute(
            db,
            "SELECT sv3.ensure_month_partitions('sensor_packets',:day,:day)",
            day=now.date().replace(day=1),
        )
        if selected:
            stations = (
                execute(
                    db,
                    """SELECT s.id,s.farmer_id FROM sv3.stations s JOIN sv3.farmers f ON f.id=s.farmer_id JOIN sv3.datasets d ON d.id=s.dataset_id
              WHERE f.profile_key=:key AND d.origin='synthetic' AND d.lane='demo' ORDER BY s.id LIMIT 2""",
                    key=os.getenv("V3_DEMO_FARMER_KEY", "DEMO-F0001"),
                )
                .mappings()
                .all()
            )
        else:
            stations = (
                execute(
                    db,
                    """SELECT s.id,s.farmer_id FROM sv3.stations s JOIN sv3.datasets d ON d.id=s.dataset_id
              WHERE d.origin='synthetic' AND d.lane='demo' ORDER BY s.id LIMIT 12 OFFSET :offset""",
                    offset=offset,
                )
                .mappings()
                .all()
            )
    for station in stations:
        with connection(station["farmer_id"], write=True, ingest=True) as db:
            ingest_mock_packet(db, station, now)
    return len(stations)


def _reviewed():
    path = (
        Path(__file__).resolve().parents[3]
        / "data_platform/v3/catalog/reviewed_sources.json"
    )
    document = json.loads(path.read_text())
    with connection(ingest=True, write=True) as db:
        for bundle in document["bundles"]:
            done = execute(
                db,
                "SELECT 1 FROM sv3.documents WHERE source_url=:url AND checksum=:checksum AND review_status='reviewed' LIMIT 1",
                url=bundle["source_url"],
                checksum=hashlib.sha256(bundle["evidence_text"].encode()).hexdigest(),
            ).scalar()
            if done:
                continue
            for guide in bundle.get("crop_guides", []):
                code = guide.pop("crop_code", None)
                if code:
                    crop = execute(
                        db,
                        "SELECT id FROM sv3.crops WHERE lower(code)=lower(:code) OR lower(name)=lower(:code) LIMIT 1",
                        code=code,
                    ).scalar()
                    if crop:
                        guide["crop_id"] = str(crop)
            bundle["crop_guides"] = [
                g for g in bundle.get("crop_guides", []) if g.get("crop_id")
            ]
            import_reviewed(db, bundle, "demo" if mode() == "v3_demo" else "live")


def _weather(location, history=False, power=False):
    if not any(item["id"] == location["id"] for item in _eligible_locations()):
        return {"accepted": 0, "status": "consent_revoked_or_unlinked"}
    now = datetime.now(UTC)
    end = now.date() - timedelta(days=7)
    start = end - timedelta(days=364)
    if history:
        with connection(ingest=True) as db:
            summary = (
                execute(
                    db,
                    """SELECT count(DISTINCT w.day) AS count,max(w.day) AS latest FROM sv3.weather_daily w
              JOIN sv3.weather_series s ON s.id=w.series_id JOIN sv3.providers p ON p.id=s.provider_id
              JOIN sv3.datasets d ON d.id=w.dataset_id WHERE p.code=:provider AND s.location_id=:location AND d.origin='reanalysis'""",
                    provider="nasa_power" if power else "open_meteo",
                    location=location["id"],
                )
                .mappings()
                .one()
            )
            if summary["count"] >= 365 and summary["latest"] >= end:
                execute(
                    db,
                    """UPDATE sv3.source_health SET checked_at=:now,source_valid_through=:valid,status='healthy',retry_after=NULL
                  WHERE provider_id=(SELECT id FROM sv3.providers WHERE code=:provider) AND scope_key=:scope""",
                    now=now,
                    valid=summary["latest"],
                    provider="nasa_power" if power else "open_meteo",
                    scope=str(location["id"]) + ":history",
                )
                return {"accepted": 0, "status": "up_to_date", "origin": "reanalysis"}
            if summary["count"] >= 365 and summary["latest"]:
                start = summary["latest"] + timedelta(days=1)
    with httpx.Client(timeout=httpx.Timeout(8, connect=5)) as client:
        payload = (
            fetch_power(location["latitude"], location["longitude"], start, end, client)
            if power
            else fetch_weather(
                location["latitude"],
                location["longitude"],
                not history,
                start,
                end,
                client,
            )
        )
    with connection(ingest=True, write=True) as db:
        return Ingestor(db, "demo" if mode() == "v3_demo" else "live").weather(
            "nasa_power" if power else "open_meteo",
            location["id"],
            payload,
            not history,
            now,
        )


def _companion_sweep():
    with connection(ingest=True, write=True) as db:
        result = execute(db, "SELECT sv3.companion_sweep(100)").scalar_one()
        execute(db, "SELECT sv3.companion_schedule_plans()")
        return result


def _sample_roll():

    if mode() != "v3_demo" or engine().url.database != "skyview_v3_demo":
        return None

    from data_platform.v3.domain_roll import statements

    today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
    with connection(ingest=True, write=True) as db:
        execute(
            db,
            "SELECT sv3.ensure_month_partitions('price_observations',:start,:end)",
            start=(today - timedelta(days=30)).replace(day=1),
            end=today.replace(day=1),
        )
    with connection(ingest=True, write=True) as db:
        db.execute(text("SET LOCAL statement_timeout='60s'"))
        db.execute(text(statements(today)))

        execute(
            db,
            """INSERT INTO sv3.source_health(provider_id,scope_key,checked_at,last_success_at,source_valid_through,status)
         SELECT id,'daily',now(),now(),:day,'healthy' FROM sv3.providers WHERE code='domain-sample-v1'
         ON CONFLICT(provider_id,scope_key) DO UPDATE SET checked_at=now(),last_success_at=now(),
         source_valid_through=:day,status='healthy',safe_error=NULL,retry_after=NULL""",
            day=today,
        )
    return {"as_of_date": today.isoformat()}


def _mandi_due(now=None):
    now = now or datetime.now(UTC)
    with connection(ingest=True) as db:
        pending = execute(
            db,
            "SELECT next_attempt_at FROM sv3.ingest_runs WHERE job_key='ogd-agmarknet:page-cursor'",
        ).scalar()
        health = execute(
            db,
            "SELECT h.retry_after FROM sv3.source_health h JOIN sv3.providers p ON p.id=h.provider_id WHERE p.code='ogd_agmarknet' AND h.scope_key='daily'",
        ).scalar()
    return not ((pending and pending > now) or (health and health > now))


def _mandi():

    with connection(ingest=True) as db:
        saved = (
            execute(
                db,
                "SELECT cursor FROM sv3.ingest_runs WHERE job_key='ogd-agmarknet:page-cursor'",
            ).scalar()
            or {}
        )
    with httpx.Client(timeout=httpx.Timeout(8, connect=5)) as client:
        payload = fetch_mandi(
            client=client, max_pages=3, offset=int(saved.get("offset", 0))
        )
    now = datetime.now(UTC)
    with connection(ingest=True, write=True) as db:
        execute(
            db,
            "SELECT sv3.ensure_month_partitions('price_observations',:start,:end)",
            start=(
                now.astimezone(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=365)
            ).replace(day=1),
            end=now.astimezone(ZoneInfo("Asia/Kolkata")).date().replace(day=1),
        )
        ingestor = Ingestor(db, "demo" if mode() == "v3_demo" else "live")
        result = ingestor.mandi(payload, now)
        provider = ingestor.provider("ogd_agmarknet", "https://data.gov.in")
        execute(
            db,
            """INSERT INTO sv3.ingest_runs(provider_id,job_key,state,cursor,attempts,finished_at,next_attempt_at)
         VALUES(:p,'ogd-agmarknet:page-cursor','done',CAST(:cursor AS jsonb),1,:now,:next)
         ON CONFLICT(job_key) DO UPDATE SET cursor=EXCLUDED.cursor,state='done',attempts=sv3.ingest_runs.attempts+1,
         finished_at=EXCLUDED.finished_at,next_attempt_at=EXCLUDED.next_attempt_at,safe_error=NULL""",
            p=provider,
            cursor=json.dumps({"offset": payload.get("next_offset", 0)}),
            now=now,
            next=now
            + timedelta(seconds=86400 if payload.get("complete", True) else 60),
        )
        return result


def _failure(code, scope, exc):
    try:
        with connection(ingest=True, write=True) as db:
            provider = Ingestor(db, "demo" if mode() == "v3_demo" else "live").provider(
                code,
                {
                    "open_meteo": "https://open-meteo.com",
                    "nasa_power": "https://power.larc.nasa.gov",
                    "ogd_agmarknet": "https://data.gov.in",
                }.get(code, "urn:skyview:local-worker"),
            )
            execute(
                db,
                """INSERT INTO sv3.source_health(provider_id,scope_key,checked_at,status,safe_error,retry_after)
              VALUES(:p,:scope,now(),'outage',:error,now()+interval '30 minutes') ON CONFLICT(provider_id,scope_key)
              DO UPDATE SET checked_at=now(),status='outage',safe_error=:error,retry_after=now()+interval '30 minutes'""",
                p=provider,
                scope=scope,
                error=type(exc).__name__,
            )
    except Exception:
        log.error("Unable to persist v3 source health")
    log.warning("V3 source %s failed (%s)", code, type(exc).__name__)


class BackgroundWorker:
    def __init__(self, lease):
        self.lease = lease
        self.stop = asyncio.Event()
        self.wake = asyncio.Event()
        self.companion_wake = asyncio.Event()
        self.whatsapp_wake = asyncio.Event()
        self.loop = asyncio.get_running_loop()
        self.tasks = []

    async def wait(self, seconds):
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def job(self, func, *args, source="demo_hardware", scope="worker"):
        try:
            return await asyncio.to_thread(func, *args)
        except Exception as exc:
            await asyncio.to_thread(_failure, source, scope, exc)
            return None

    async def telemetry(self):
        tick = 0
        while not self.stop.is_set():
            await self.job(_telemetry, True)
            if tick % 12 == 0 and not self.stop.is_set():
                await self.job(_telemetry, False, (tick // 12 % 7) * 12)
            tick += 1
            await self.wait(5)

    async def sources(self):
        await self.job(_reviewed, source="reviewed_official_import")
        while not self.stop.is_set():
            batches = await self.job(_weather_jobs, source="open_meteo") or []
            for location, jobs in batches:
                for source, history, power, scope in jobs:
                    if self.stop.is_set():
                        break

                    await self.job(
                        _weather, location, history, power, source=source, scope=scope
                    )

            await self.wait_sources(60)

    async def whatsapp(self):
        from skyview.assistant.whatsapp import process_next

        while not self.stop.is_set():
            try:
                processed = await process_next()
            except Exception as exc:
                log.warning("WhatsApp worker unavailable (%s)", type(exc).__name__)
                processed = False
            if not processed:
                await self.wait_sources(15, self.whatsapp_wake)

    async def companion(self):
        while not self.stop.is_set():
            await self.job(
                _companion_sweep, source="farm-companion", scope="in-app-followups"
            )
            await self.wait_sources(60, self.companion_wake)

    async def companion_plans(self):
        from skyview.assistant.companion_plans import process_next

        while not self.stop.is_set():
            try:
                processed = await process_next()
            except Exception as exc:
                log.warning(
                    "Companion preparation unavailable (%s)", type(exc).__name__
                )
                processed = False
            if not processed:
                await self.wait(3)

    async def sample_rollover(self):
        while not self.stop.is_set():
            result = await self.job(
                _sample_roll, source="domain-sample-v1", scope="daily"
            )
            await self.wait(_rollover_delay() if result is not None else 1800)

    async def markets(self):

        while not self.stop.is_set():
            if any(
                os.getenv(k)
                for k in ("DATAGOV_API_KEY", "DATA_GOV_API_KEY", "OGD_API_KEY")
            ):
                due = await self.job(_mandi_due, source="ogd_agmarknet", scope="daily")
                if due and not self.stop.is_set():
                    await self.job(_mandi, source="ogd_agmarknet", scope="daily")
            await self.wait(60)

    async def wait_sources(self, seconds, wake=None):
        wake = self.wake if wake is None else wake
        waiters = [
            asyncio.create_task(self.stop.wait()),
            asyncio.create_task(wake.wait()),
        ]
        try:
            await asyncio.wait(
                waiters, timeout=seconds, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for task in waiters:
                task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
            wake.clear()

    def start(self):
        if mode() == "v3_demo":
            self.tasks.append(
                asyncio.create_task(self.telemetry(), name="sv3-demo-telemetry")
            )
            self.tasks.append(
                asyncio.create_task(self.sample_rollover(), name="sv3-sample-rollover")
            )
        self.tasks.append(
            asyncio.create_task(self.sources(), name="sv3-public-sources")
        )
        self.tasks.append(asyncio.create_task(self.markets(), name="sv3-market-prices"))
        self.tasks.append(
            asyncio.create_task(self.companion(), name="sv3-companion-followups")
        )
        self.tasks.append(
            asyncio.create_task(self.companion_plans(), name="sv3-companion-plans")
        )
        self.tasks.append(
            asyncio.create_task(self.whatsapp(), name="sv3-whatsapp-replies")
        )

    async def close(self):
        self.stop.set()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True), timeout=40
            )
        except TimeoutError:
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
        finally:
            await asyncio.to_thread(_release, self.lease)


async def start_background_worker():
    global _worker
    if (
        _worker is not None
        or not enabled()
        or os.getenv("V3_BACKGROUND_WORKER", "true").lower() != "true"
    ):
        return False
    lease = await asyncio.to_thread(_lease)
    if lease is None:
        return False
    _worker = BackgroundWorker(lease)
    _worker.start()
    return True


async def stop_background_worker():
    global _worker
    if _worker is None:
        return
    worker, _worker = _worker, None
    await worker.close()


def notify_weather_link():
    """Wake a running source worker after an authenticated weather-link mutation."""
    if _worker is not None:
        _worker.loop.call_soon_threadsafe(_worker.wake.set)


def notify_companion():
    """Wake only the follow-up worker after a committed settings change."""
    if _worker is not None:
        _worker.loop.call_soon_threadsafe(_worker.companion_wake.set)


def notify_whatsapp():
    if _worker is not None:
        _worker.loop.call_soon_threadsafe(_worker.whatsapp_wake.set)
