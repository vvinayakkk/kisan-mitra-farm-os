"""Trusted connector worker: python -m skyview.data.v3.ingest_cli --help."""

import argparse
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from skyview.data.v3.db import connection, mode
from skyview.data.v3.ingestion import (
    Ingestor,
    execute,
    fetch_mandi,
    fetch_power,
    fetch_weather,
    import_reviewed,
    mock_once,
)

log = logging.getLogger("skyview.v3.ingestion")


def once(args):
    if args.source == "mock":
        return mock_once(limit=args.limit)
    if args.source == "reviewed":
        with connection(write=True, ingest=True) as conn:
            return import_reviewed(
                conn,
                json.loads(Path(args.file).read_text()),
                "live" if mode() == "v3_live" else "demo",
            )
    now = datetime.now(UTC)
    lane = "live" if mode() == "v3_live" else "demo"
    if args.source == "mandi":
        payload = fetch_mandi(max_pages=args.limit)
        with connection(write=True, ingest=True) as conn:
            execute(
                conn,
                "SELECT sv3.ensure_month_partitions('price_observations',:first,:last)",
                first=(now.date() - timedelta(days=365)).replace(day=1),
                last=now.date().replace(day=1),
            )
            return Ingestor(conn, lane).mandi(payload, now)
    with connection(ingest=True) as conn:
        locations = (
            execute(
                conn,
                "SELECT id,latitude,longitude FROM sv3.locations ORDER BY id LIMIT :limit",
                limit=args.limit,
            )
            .mappings()
            .all()
        )
    results = []
    for location in locations:
        history = args.source in ("history", "power")
        end = now.date() - timedelta(days=7)
        start = end - timedelta(days=args.days - 1)
        payload = (
            fetch_power(location["latitude"], location["longitude"], start, end)
            if args.source == "power"
            else fetch_weather(
                location["latitude"], location["longitude"], not history, start, end
            )
        )
        with connection(write=True, ingest=True) as conn:
            result = Ingestor(conn, lane).weather(
                "nasa_power" if args.source == "power" else "open_meteo",
                location["id"],
                payload,
                not history,
                now,
            )
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", choices=["mock", "forecast", "history", "power", "mandi", "reviewed"]
    )
    parser.add_argument("--file", help="local reviewed JSON evidence bundle")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="locations/stations/pages; bounded 1–400 (mandi max 20 pages)",
    )
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument(
        "--loop-seconds",
        type=int,
        default=0,
        help="0 once; mock minimum 5s, external API minimum 3600s",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= (20 if args.source == "mandi" else 400):
        parser.error("invalid limit")
    if not 1 <= args.days <= 365:
        parser.error("days must be 1–365")
    if args.source == "reviewed" and not args.file:
        parser.error("reviewed requires --file")
    minimum = 5 if args.source == "mock" else 3600
    if args.loop_seconds and args.loop_seconds < minimum:
        parser.error(f"loop must be >= {minimum} seconds")
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            print(json.dumps(once(args), default=str), flush=True)
        except Exception as exc:
            log.error(
                "connector failed: %s; inspect source health/run audit",
                type(exc).__name__,
            )
            with connection(write=True, ingest=True) as conn:
                provider = Ingestor(
                    conn, "live" if mode() == "v3_live" else "demo"
                ).provider(
                    "ogd_agmarknet"
                    if args.source == "mandi"
                    else "nasa_power"
                    if args.source == "power"
                    else "demo_hardware"
                    if args.source == "mock"
                    else "open_meteo",
                    "https://data.gov.in"
                    if args.source == "mandi"
                    else "https://power.larc.nasa.gov"
                    if args.source == "power"
                    else "urn:skyview:synthetic-realtime"
                    if args.source == "mock"
                    else "https://open-meteo.com",
                )
                execute(
                    conn,
                    """INSERT INTO sv3.source_health(provider_id,scope_key,checked_at,status,safe_error)
                  VALUES(:p,'worker',now(),'outage',:error) ON CONFLICT(provider_id,scope_key) DO UPDATE SET checked_at=now(),status='outage',safe_error=:error""",
                    p=provider,
                    error=type(exc).__name__,
                )
            if not args.loop_seconds:
                raise SystemExit(1) from None
        if not args.loop_seconds:
            break
        time.sleep(args.loop_seconds)


if __name__ == "__main__":
    main()
