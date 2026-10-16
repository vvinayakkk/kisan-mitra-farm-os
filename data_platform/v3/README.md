# Kisan Mitra data platform v3

This directory contains the current PostgreSQL schema and the tooling that builds, provisions, migrates, tests and refreshes it. It is source code, not a checked-in database. The local seed represents fictional farmers and practice scenarios; source-backed observations keep separate provenance.

| Path | Responsibility |
| --- | --- |
| `sql/schema.sql` | Generated PostgreSQL 16 fresh-database schema: 75 base tables, RLS, constraints and partitions. |
| `sql/*-runtime.sql` | Additive feature migrations, functions and grants. Ordered once in `layout.py`. |
| `catalog/schema-catalog.json` | Machine-readable 75-table design and 29 explicit base indexes. |
| `catalog/source-catalog.json` | 26 researched public-source contracts and access boundaries. |
| `catalog/reviewed_sources.json` | Curated reference extracts for reviewed imports. |
| `catalog/enam_market_reference.json` | Partial official directory of market names; not price quotes. |
| `catalog/agent-catalog.json` | Seed-time assistant registry. Runtime skill/tool inventory is in `skyview/assistant/tools.py`. |
| `build_schema.py` | Regenerates `sql/schema.sql`, `sql/roles.sql` and the schema catalog. |
| `seed_demo.py` | Generates an ignored, deterministic 400-farmer seed outside Git. |
| `bootstrap.py` | Installs a fresh, explicitly named v3 PostgreSQL database or reapplies additive runtime SQL. |
| `provision.py` / `prepare_test_db.py` | Guarded local Docker provisioning and isolated test preparation. |
| `local.py` / `run_backend.py` | Existing local database, API and frontend launcher. |

`bootstrap.py` requires `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` and `V3_APP_PASSWORD`. It only accepts `skyview_v3_demo`, `skyview_v3_live` or `skyview_v3_test`; `--seed-demo` is restricted to the demo database. It never drops or reseeds populated data. `provision.py` remains the convenient first-run local path and writes credentials only to ignored `.v3-data/`.

The ordered SQL inventory is checked by `layout.py`. The market and station read functions are invoker-rights contracts with explicit grants. Other application code still uses parameterized SQL under scoped roles; full SP-only conversion remains a separate security-reviewed change, not an implied property of this package.

See [CONNECTORS.md](CONNECTORS.md) for external ingestion and worker cadence, [OPERATIONS.md](OPERATIONS.md) for data and privacy operations, and [EXCHANGE.md](EXCHANGE.md) for the exchange contract. The [root README](../../README.md) documents the whole application and Docker stack.
