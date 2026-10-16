"""Refresh personal local price fixtures with reproducible, irregular price paths.

Only synthetic datasets in skyview_v3_demo are eligible. Original values are
retained in a private local_price_backup schema; --restore reverses this version.
No provenance, market identities, observation dates, or real prices are changed.
Run with the repository Python environment and --apply (default: preview).
"""

import argparse
import hashlib
import io
import json
import math
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import psycopg2

VERSION = "irregular-paths-v1"
DATABASE = "skyview_v3_demo"
STATE = Path(__file__).resolve().parents[2] / ".v3-data"


def generate_path(series_id, base, days, category="cereal"):
    """Mean-reverting daily prices with changing volatility and supply shocks.

    Unlike a periodic sine curve, trend regimes and shocks do not repeat on an
    annual schedule. Every series has its own stable random seed. Prices stay
    within 60–170% of their original series mean, with varying bid/ask ranges.
    """
    seed = int.from_bytes(
        hashlib.sha256(f"{VERSION}:{series_id}".encode()).digest()[:8], "big"
    )
    rng = np.random.default_rng(seed)
    perishable = any(
        word in category.lower() for word in ("vegetable", "fruit", "flower")
    )
    sigma = rng.uniform(0.009, 0.018) if perishable else rng.uniform(0.004, 0.009)
    target, value, velocity, shock, volatility = (
        rng.normal(0, 0.045),
        0.0,
        0.0,
        0.0,
        1.0,
    )
    value = target
    result = np.empty((days, 3))
    for day in range(days):
        if rng.random() < 1 / 49:
            target = max(-0.23, min(0.26, target + rng.normal(0, 0.07)))
        if rng.random() < 1 / 95:
            shock += rng.choice([-1, 1]) * rng.uniform(0.025, 0.095)
        shock *= 0.94
        volatility = max(
            0.5, min(1.8, 0.96 * volatility + 0.04 * rng.uniform(0.45, 1.9))
        )
        velocity = 0.23 * velocity + rng.normal(0, sigma * volatility)
        value += 0.026 * (target + shock - value) + velocity
        value = max(math.log(0.60), min(math.log(1.70), value))
        modal = max(1, round(base * math.exp(value)))
        spread = rng.uniform(0.025, 0.085) * (1.25 if perishable else 1)
        result[day] = (
            round(modal * (1 - spread), 2),
            modal,
            round(modal * (1 + spread * rng.uniform(0.8, 1.4)), 2),
        )
    return result


def connect_local():

    password = next(
        line.split("=", 1)[1]
        for line in (STATE / "postgres.env").read_text().splitlines()
        if line.startswith("POSTGRES_PASSWORD=")
    )
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=15433,
        dbname=DATABASE,
        user="postgres",
        password=password,
        application_name="local-price-path-maintenance",
    )
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        database = cur.fetchone()[0]
        if database != DATABASE:
            conn.close()
            raise RuntimeError("Expected the local Docker demo database")
    return conn


def integrity_snapshot(cur):
    """Fingerprint immutable keys/date/source and check ranges in two scans."""
    cur.execute("""SELECT count(*),coalesce(sum(hashtextextended(concat_ws(':',p.dataset_id,p.series_id,p.observed_on,d.origin),0)::numeric),0),
        count(*) FILTER(WHERE p.min_price<0 OR p.min_price>p.modal_price OR p.modal_price>p.max_price)
        FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id""")
    history = cur.fetchone()
    cur.execute("""SELECT count(*),coalesce(sum(hashtextextended(concat_ws(':',p.run_id,p.series_id,p.valid_on,p.kind,d.origin),0)::numeric),0),
        count(*) FILTER(WHERE p.lower_price<0 OR p.lower_price>p.central_price OR p.central_price>p.upper_price)
        FROM sv3.price_projections p JOIN sv3.forecast_runs r ON r.id=p.run_id JOIN sv3.datasets d ON d.id=r.dataset_id""")
    return history, cur.fetchone()


def update_prices(cur, statement):
    """Skip redundant date/FK trigger reads only for this price-only operation.

    Fixed statements never modify dates, source IDs, keys, or kind. Numeric CHECK
    constraints remain active. SET LOCAL is reset immediately on success and by
    transaction rollback on any error; no persisted trigger state is changed.
    """
    cur.execute("EXPLAIN (FORMAT JSON) " + statement)
    plan = cur.fetchone()[0][0]["Plan"]

    def nodes(node):
        return [node["Node Type"]] + [
            name for child in node.get("Plans", []) for name in nodes(child)
        ]

    print("Update plan: " + ", ".join(sorted(set(nodes(plan)))), flush=True)
    cur.execute("SET LOCAL session_replication_role='replica'")
    cur.execute(statement)
    count = cur.rowcount
    cur.execute("SET LOCAL session_replication_role='origin'")
    print(f"Updated {count:,} rows", flush=True)
    return count


def apply(conn, restore=False):
    started = time.monotonic()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(741569023)")
        cur.execute(
            "SET LOCAL statement_timeout='20min'; SET LOCAL lock_timeout='15s'; SET LOCAL work_mem='128MB'"
        )
        cur.execute(
            "CREATE SCHEMA IF NOT EXISTS local_price_backup; REVOKE ALL ON SCHEMA local_price_backup FROM PUBLIC"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS local_price_backup.runs(version text PRIMARY KEY, status text NOT NULL, completed_at timestamptz, report jsonb)"
        )
        cur.execute(
            "SELECT status FROM local_price_backup.runs WHERE version=%s", (VERSION,)
        )
        prior = cur.fetchone()
        if not restore and prior and prior[0] == "complete":
            return {"status": "already_applied", "version": VERSION}
        if restore and (not prior or prior[0] != "complete"):
            return {"status": "nothing_to_restore"}
        before = integrity_snapshot(cur)
        if restore:
            history_count = update_prices(
                cur,
                """UPDATE sv3.price_observations p SET min_price=b.min_price,modal_price=b.modal_price,max_price=b.max_price
                FROM local_price_backup.history b,sv3.datasets d WHERE p.dataset_id=b.dataset_id AND p.series_id=b.series_id
                AND p.observed_on=b.observed_on AND d.id=p.dataset_id AND d.origin='synthetic'""",
            )
            projection_count = update_prices(
                cur,
                """UPDATE sv3.price_projections p SET lower_price=b.lower_price,central_price=b.central_price,upper_price=b.upper_price
                FROM local_price_backup.projections b,sv3.forecast_runs r,sv3.datasets d WHERE p.run_id=b.run_id
                AND p.series_id=b.series_id AND p.valid_on=b.valid_on AND r.id=p.run_id AND d.id=r.dataset_id AND d.origin='synthetic'""",
            )
            report = {
                "history": history_count,
                "projections": projection_count,
                "seconds": round(time.monotonic() - started, 2),
                "status": "restored",
            }
        else:
            print("Backing up original synthetic price values…", flush=True)
            cur.execute("""CREATE TABLE IF NOT EXISTS local_price_backup.history AS SELECT p.dataset_id,p.series_id,p.observed_on,p.min_price,p.modal_price,p.max_price
                FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id WHERE d.origin='synthetic'""")
            cur.execute("""CREATE TABLE IF NOT EXISTS local_price_backup.projections AS SELECT p.run_id,p.series_id,p.valid_on,p.lower_price,p.central_price,p.upper_price
                FROM sv3.price_projections p JOIN sv3.forecast_runs r ON r.id=p.run_id JOIN sv3.datasets d ON d.id=r.dataset_id WHERE d.origin='synthetic' AND p.kind='scenario'""")
            cur.execute("""WITH horizons AS (SELECT series_id,max(valid_on) AS last_day FROM local_price_backup.projections GROUP BY series_id)
                SELECT h.series_id::text,avg(h.modal_price)::float,min(h.observed_on),
                greatest(max(h.observed_on),max(hz.last_day)),c.category
                FROM local_price_backup.history h JOIN sv3.market_series s ON s.id=h.series_id JOIN sv3.crops c ON c.id=s.crop_id
                LEFT JOIN horizons hz ON hz.series_id=h.series_id
                GROUP BY h.series_id,c.category ORDER BY h.series_id""")
            series = cur.fetchall()
            cur.execute(
                "CREATE TEMP TABLE natural_paths(series_id uuid, day date, low numeric(14,2), price numeric(14,2), high numeric(14,2)) ON COMMIT DROP"
            )
            print(
                f"Generating independent daily paths for {len(series):,} market series…",
                flush=True,
            )
            for offset in range(0, len(series), 80):
                buffer = io.StringIO()
                for series_id, base, first, last, category in series[
                    offset : offset + 80
                ]:
                    for i, (low, price, high) in enumerate(
                        generate_path(
                            series_id, base, (last - first).days + 1, category
                        )
                    ):
                        buffer.write(
                            f"{series_id}\t{first + timedelta(days=i)}\t{low}\t{price}\t{high}\n"
                        )
                buffer.seek(0)
                cur.copy_from(
                    buffer,
                    "natural_paths",
                    columns=("series_id", "day", "low", "price", "high"),
                )
            cur.execute(
                "CREATE UNIQUE INDEX ON natural_paths(series_id,day); ANALYZE natural_paths"
            )
            print(
                "Applying prices; source metadata and dates remain unchanged…",
                flush=True,
            )
            history_count = update_prices(
                cur,
                """UPDATE sv3.price_observations p SET min_price=n.low,modal_price=n.price,max_price=n.high
                FROM natural_paths n,sv3.datasets d WHERE p.series_id=n.series_id AND p.observed_on=n.day AND d.id=p.dataset_id AND d.origin='synthetic'""",
            )
            projection_count = update_prices(
                cur,
                """UPDATE sv3.price_projections p SET lower_price=round(n.price*.7,2),central_price=n.price,upper_price=round(n.price*1.3,2)
                FROM natural_paths n,sv3.forecast_runs r,sv3.datasets d WHERE p.series_id=n.series_id AND p.valid_on=n.day
                AND p.kind='scenario' AND r.id=p.run_id AND d.id=r.dataset_id AND d.origin='synthetic'""",
            )
            report = {
                "series": len(series),
                "history": history_count,
                "projections": projection_count,
                "seconds": round(time.monotonic() - started, 2),
                "status": "complete",
            }
        after = integrity_snapshot(cur)
        if before != after or any(part[2] for part in after):
            raise RuntimeError(
                "Price key/date/source or range integrity changed; rolling back"
            )
        report["integrity_verified"] = True
        cur.execute(
            "INSERT INTO local_price_backup.runs VALUES(%s,%s,now(),%s::jsonb) ON CONFLICT(version) DO UPDATE SET status=excluded.status,completed_at=excluded.completed_at,report=excluded.report",
            (VERSION, report["status"], json.dumps(report)),
        )
        cur.execute("ANALYZE sv3.price_observations; ANALYZE sv3.price_projections")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if not args.apply and not args.restore:
        path = generate_path("preview-wheat", 2500, 731)
        print(
            json.dumps(
                {
                    "mode": "preview",
                    "version": VERSION,
                    "days": len(path),
                    "min": float(path[:, 1].min()),
                    "max": float(path[:, 1].max()),
                    "apply": "Pass --apply to update only local synthetic prices; --restore recovers originals.",
                }
            )
        )
        return
    conn = connect_local()
    try:
        print(json.dumps(apply(conn, restore=args.restore)))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
