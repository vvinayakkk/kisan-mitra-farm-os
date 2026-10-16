"""Validate inside a caller-provided disposable PostgreSQL container, never the app DB."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from validate_additions import extend

HERE = Path(__file__).parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--container", required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.container != "skyview-v3-design-check":
        raise SystemExit("Only the isolated design-check container is allowed")
    results = []

    def query(sql, db="skyview_v3_test", check=True):
        r = subprocess.run(
            [
                "/opt/homebrew/bin/docker",
                "exec",
                "-i",
                a.container,
                "psql",
                "-X",
                "-At",
                "-U",
                "postgres",
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
            ],
            check=False,
            input=sql,
            text=True,
            capture_output=True,
        )
        if check and r.returncode:
            raise RuntimeError(r.stderr)
        return r

    def assertq(name, sql, expected):
        output = query(sql).stdout.strip()
        ok = output == str(expected)
        results.append({"test": name, "passed": ok, "actual": output})
        assert ok, (name, output, expected)

    def rejects(name, sql, message):
        r = query(
            "BEGIN; SET search_path=sv3,public; " + sql + "; ROLLBACK;", check=False
        )
        ok = r.returncode != 0 and message in r.stderr
        results.append({"test": name, "passed": ok})
        assert ok, (name, r.stderr, r.stdout)

    query((HERE / "sql/roles.sql").read_text())
    query("ANALYZE;")
    manifest = json.loads(a.manifest.read_text())
    actual = {}
    for table, count in manifest["rows"].items():
        result = query(f"SELECT count(*) FROM sv3.{table};").stdout.strip()
        actual[table] = int(result)
        assert int(result) == count, (table, result, count)
    results.append({"test": "Every table row count matches manifest", "passed": True})
    assertq(
        "400 farmers across 36 regions",
        "SELECT count(*)||','||count(distinct region_id) FROM sv3.farmers;",
        "400,36",
    )
    assertq(
        "No usable contacts or external identities",
        "SELECT count(*) FROM sv3.farmers WHERE contact_phone IS NOT NULL OR auth_subject IS NOT NULL OR contact_email NOT LIKE '%@example.invalid';",
        0,
    )
    assertq(
        "All releases demo synthetic",
        "SELECT count(*) FROM sv3.datasets WHERE lane<>'demo' OR origin<>'synthetic';",
        0,
    )
    assertq(
        "Price history has exactly 365 days",
        "SELECT count(distinct observed_on) FROM sv3.price_observations;",
        365,
    )
    assertq(
        "Future scenario has exactly 365 days",
        "SELECT count(distinct valid_on) FROM sv3.price_projections WHERE kind='scenario';",
        365,
    )
    assertq(
        "No historical prices beyond release cutoff",
        "SELECT count(*) FROM sv3.price_observations p JOIN sv3.datasets d ON d.id=p.dataset_id WHERE p.observed_on>d.as_of_date;",
        0,
    )
    assertq(
        "No forecasts created from synthetic model",
        "SELECT count(*) FROM sv3.price_projections WHERE kind='forecast';",
        0,
    )
    assertq(
        "Sensor outages kept missing",
        "SELECT count(*) FROM sv3.sensor_daily WHERE completeness<1;",
        16,
    )
    assertq(
        "Aggregate packet counts agree",
        "SELECT (SELECT count(*) FROM sv3.sensor_packets)=(SELECT sum(sample_count) FROM sv3.sensor_daily);",
        "t",
    )
    farmer = query(
        "SELECT id FROM sv3.farmers ORDER BY profile_key LIMIT 1;"
    ).stdout.strip()
    other = query(
        "SELECT id FROM sv3.farmers ORDER BY profile_key LIMIT 1 OFFSET 1;"
    ).stdout.strip()
    context = f"BEGIN; SET LOCAL ROLE sv3_app; SET LOCAL app.farmer_id='{farmer}'; "

    # psql command tags are omitted by -q for assertion rows through SELECT extraction.
    def rls_count(table, where, expected):
        output = (
            query(context + f"SELECT count(*) FROM sv3.{table} {where}; ROLLBACK;")
            .stdout.strip()
            .splitlines()
        )
        vals = [x for x in output if x.isdigit()]
        ok = vals == [str(expected)]
        results.append({"test": f"RLS {table} {where or 'own rows'}", "passed": ok})
        assert ok, output

    rls_count("farmers", "", 1)
    rls_count("tasks", "", 6)
    rls_count("plots", "", 2)
    rls_count("memories", "", 1)
    rls_count("farmers", f"WHERE id='{other}'", 0)
    r = query(
        "BEGIN; SET LOCAL ROLE sv3_app; SELECT count(*) FROM sv3.farmers; ROLLBACK;"
    ).stdout
    results.append(
        {"test": "No identity means zero private rows", "passed": "\n0\n" in r}
    )
    assert "\n0\n" in r
    rejects(
        "Release provenance cannot be rewritten",
        "UPDATE datasets SET as_of_date=as_of_date+1",
        "Dataset lineage is immutable",
    )
    rejects(
        "Only one current fact per farmer/key",
        "INSERT INTO memories(id,farmer_id,fact_key,value,evidence_message_id,confidence,valid_from,valid_to,supersedes_id,search_text) SELECT gen_random_uuid(),farmer_id,fact_key,value,evidence_message_id,confidence,valid_from,valid_to,supersedes_id,search_text FROM memories LIMIT 1",
        "duplicate key",
    )
    rejects(
        "Negative expense rejected",
        "INSERT INTO expenses SELECT gen_random_uuid(),farmer_id,cycle_id,description,spent_on,-1,category,'bad-negative' FROM expenses LIMIT 1",
        "check constraint",
    )
    rejects(
        "Cross-owner plot FK rejected",
        f"UPDATE plots SET farmer_id='{other}' WHERE farmer_id='{farmer}'",
        "foreign key constraint",
    )
    rejects(
        "Cross-owner memory evidence rejected",
        f"UPDATE memories SET evidence_message_id=(SELECT id FROM messages WHERE farmer_id='{other}' LIMIT 1) WHERE farmer_id='{farmer}'",
        "foreign key constraint",
    )
    rejects(
        "Duplicate price natural key rejected",
        "INSERT INTO price_observations SELECT * FROM price_observations LIMIT 1",
        "duplicate key",
    )
    rejects(
        "Global sensor boot/sequence replay rejected",
        "INSERT INTO packet_receipts SELECT dataset_id,farmer_id,station_id,boot_id,sequence,observed_at+interval '1 second' FROM packet_receipts LIMIT 1",
        "duplicate key",
    )
    rejects(
        "Future price cannot masquerade as history",
        "UPDATE price_observations SET observed_on='2026-10-15' WHERE series_id=(SELECT series_id FROM price_observations LIMIT 1) AND observed_on='2026-10-14'",
        "Future value",
    )
    rejects(
        "Future weather cannot masquerade as history",
        "UPDATE weather_daily SET day='2026-10-15' WHERE day='2026-10-14'",
        "Future value",
    )
    rejects(
        "Scenario horizon overflow rejected",
        "UPDATE price_projections SET valid_on='2027-10-15' WHERE valid_on='2027-10-14'",
        "outside issued horizon",
    )
    rejects(
        "Unvalidated model cannot generate forecast",
        "INSERT INTO forecast_runs(id,dataset_id,model_id,issued_at,training_cutoff,horizon_days,kind) SELECT '00000000-0000-0000-0000-000000000111',dataset_id,model_id,issued_at,training_cutoff,horizon_days,'forecast' FROM forecast_runs LIMIT 1; INSERT INTO price_projections SELECT '00000000-0000-0000-0000-000000000111',series_id,valid_on,'forecast',lower_price,central_price,upper_price,interval_definition FROM price_projections LIMIT 1",
        "Unvalidated model",
    )
    rejects(
        "Synthetic weather cannot claim observed",
        "UPDATE weather_daily SET kind='observed'",
        "Synthetic evidence",
    )
    rejects(
        "Synthetic soil cannot claim laboratory",
        "UPDATE soil_samples SET sample_type='lab'",
        "Synthetic evidence",
    )
    rejects(
        "Invalid humidity rejected",
        "UPDATE sensor_packets SET humidity_pct=101 WHERE observed_at=(SELECT min(observed_at) FROM sensor_packets)",
        "check constraint",
    )
    rejects(
        "App cannot mutate directly",
        "SET LOCAL ROLE sv3_app; DELETE FROM sv3.tasks",
        "permission denied",
    )
    rejects(
        "App cannot manage partitions",
        "SET LOCAL ROLE sv3_app; SELECT sv3.ensure_month_partitions('sensor_packets','2026-10-01','2026-11-01')",
        "permission denied",
    )
    query(
        "DROP DATABASE IF EXISTS skyview_v3_live; CREATE DATABASE skyview_v3_live;",
        db="postgres",
    )
    query((HERE / "sql/schema.sql").read_text(), db="skyview_v3_live")
    query(
        "INSERT INTO sv3.providers(code,name,homepage,access_method,attribution) VALUES('test','test','https://example.invalid','test','test');",
        db="skyview_v3_live",
    )
    r = query(
        "INSERT INTO sv3.datasets(provider_id,release_key,lane,origin,as_of_date,generator_version,source_url) SELECT id,'synthetic-leak','demo','synthetic','2026-10-14','test','demo://test' FROM sv3.providers;",
        db="skyview_v3_live",
        check=False,
    )
    ok = r.returncode != 0 and "Demo datasets cannot enter live" in r.stderr
    results.append({"test": "Live DB rejects demo release", "passed": ok})
    assert ok, r.stderr
    rejects(
        "Model training cutoff leakage rejected",
        "UPDATE model_versions SET trained_until='2026-10-15'; UPDATE price_projections SET central_price=central_price",
        "Training leakage",
    )
    r = query(a.manifest.with_name("seed.sql").read_text(), check=False)
    ok = r.returncode != 0 and "Seed requires empty database" in r.stderr
    results.append(
        {"test": "Repeat seed rejected without appending records", "passed": ok}
    )
    assert ok, r.stderr
    assertq(
        "Repeat seed leaves farmer count unchanged",
        "SELECT count(*) FROM sv3.farmers;",
        400,
    )
    extend(query, assertq, rejects, rls_count, farmer, other)
    # Future/live known policy not prohibited: prevention specifically applies to observed histories.
    # Reproducibility and a restore rehearsal run only against these isolated fixture namespaces.
    with tempfile.TemporaryDirectory(prefix="skyview-v3-repro-") as replay_dir:
        subprocess.run(
            [
                sys.executable,
                str(HERE / "seed_demo.py"),
                "--output",
                replay_dir,
                "--as-of",
                manifest["as_of_date"],
                "--seed",
                str(manifest["seed"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        replay_manifest = json.loads((Path(replay_dir) / "manifest.json").read_text())
        ok = replay_manifest == manifest
        results.append(
            {
                "test": "Independent regeneration matches all fixture checksums",
                "passed": ok,
            }
        )
        assert ok
    query(
        "DROP DATABASE IF EXISTS skyview_v3_demo; CREATE DATABASE skyview_v3_demo;",
        db="postgres",
    )
    dump = subprocess.run(
        [
            "/opt/homebrew/bin/docker",
            "exec",
            a.container,
            "pg_dump",
            "-U",
            "postgres",
            "-d",
            "skyview_v3_test",
            "-Fc",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "/opt/homebrew/bin/docker",
            "exec",
            "-i",
            a.container,
            "pg_restore",
            "-U",
            "postgres",
            "-d",
            "skyview_v3_demo",
            "--exit-on-error",
        ],
        input=dump.stdout,
        check=True,
        capture_output=True,
    )
    restored = {
        name: int(
            query(
                f"SELECT count(*) FROM sv3.{name};", db="skyview_v3_demo"
            ).stdout.strip()
        )
        for name in actual
    }
    ok = restored == actual
    results.append(
        {"test": "Backup restore reproduces every base-table row count", "passed": ok}
    )
    assert ok
    restored_rls = query(
        context + "SELECT count(*) FROM sv3.farmers; ROLLBACK;", db="skyview_v3_demo"
    ).stdout
    ok = "\n1\n" in restored_rls
    results.append(
        {"test": "Restored database preserves owner isolation", "passed": ok}
    )
    assert ok

    probes = {
        "market_history_90_days": "SELECT observed_on,modal_price FROM sv3.price_observations WHERE series_id=(SELECT id FROM sv3.market_series LIMIT 1) AND observed_on>='2026-07-16' ORDER BY observed_on",
        "latest_station_packet": f"SELECT observed_at,temperature_c,soil_moisture_pct FROM sv3.sensor_packets WHERE farmer_id='{farmer}' AND station_id=(SELECT id FROM sv3.stations WHERE farmer_id='{farmer}' LIMIT 1) ORDER BY observed_at DESC LIMIT 1",
        "calendar": f"SELECT title,due_at FROM sv3.tasks WHERE farmer_id='{farmer}' AND status='open' AND deleted_at IS NULL ORDER BY due_at",
        "memory_search": f"SELECT fact_key FROM sv3.memories WHERE farmer_id='{farmer}' AND search_vector @@ plainto_tsquery('simple','synthetic')",
    }
    plans = {}
    for name, sql in probes.items():
        plans[name] = json.loads(
            query("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql).stdout
        )
    indexes = json.loads(
        query(
            "SELECT json_agg(row_to_json(x)) FROM (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='sv3' ORDER BY tablename,indexname) x;"
        ).stdout
    )
    partitions = int(
        query(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='sv3' AND c.relispartition AND c.relkind='r';"
        ).stdout.strip()
    )
    columns = json.loads(
        query(
            "SELECT json_agg(row_to_json(x)) FROM (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='sv3' AND table_name NOT LIKE 'sensor_packets_%' AND table_name NOT LIKE 'price_observations_%' ORDER BY table_name,ordinal_position) x;"
        ).stdout
    )
    constraints = json.loads(
        query(
            "SELECT json_agg(row_to_json(x)) FROM (SELECT c.relname AS table_name,k.conname AS name,k.contype AS type,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON k.conrelid=c.oid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='sv3' AND NOT c.relispartition ORDER BY c.relname,k.conname) x;"
        ).stdout
    )
    a.output.with_name("database-catalog.json").write_text(
        json.dumps(
            {"columns": columns, "constraints": constraints, "indexes": indexes},
            indent=2,
        )
    )
    result = {
        "database": "disposable PostgreSQL 16 isolated container",
        "date": "2026-10-14",
        "tests": results,
        "passed": all(x["passed"] for x in results),
        "table_rows": actual,
        "total_rows": sum(actual.values()),
        "base_tables": len(actual),
        "partition_children": partitions,
        "index_count_including_pk_and_partitions": len(indexes),
        "indexes": indexes,
        "query_plans": plans,
        "limitations": [
            "Read-only app role is intentionally not production authentication provisioning",
            "Measured query times apply only to this test dataset and local container",
            "Source probes are public samples, not complete import connector tests",
        ],
    }
    a.output.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "checks_passed": len(results),
                "rows": result["total_rows"],
                "partitions": partitions,
                "query_ms": {k: v[0]["Execution Time"] for k, v in plans.items()},
            }
        )
    )


if __name__ == "__main__":
    main()
