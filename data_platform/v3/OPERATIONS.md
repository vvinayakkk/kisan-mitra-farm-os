# PostgreSQL v3 operations

`data_platform/v3/layout.py` is the ordered SQL inventory. `sql/schema.sql` creates a fresh PostgreSQL 16 `sv3` schema; additive runtime migrations are designed to be reapplied to an existing named database. Do not run the base schema as a reset on populated storage. `bootstrap.py` validates the target database name and credentials. `provision.py` creates a retained local Docker database and writes credentials to ignored `.v3-data/` with restricted permissions. The [local guide](../../docs/local-setup.md) has the exact workstation commands.

## Day-to-day checks

Run `data_platform/v3/check_local.py` for a read-only local report, and inspect `/health` and `/api/data/status` from the API. A healthy database is not proof that every external provider refreshed today. The leased worker keeps source-health state, last success, retry time and quality issues separately. `V3_BACKGROUND_WORKER=false` disables the embedded scheduler when a separate worker owns recurring jobs.

## Ingestion and source boundaries

`skyview/data/v3/ingestion.py` validates provider and station payloads. `skyview/data/v3/worker.py` runs bounded weather, market, reviewed-reference, companion and delivery work under a database advisory lease. Raw payload URIs and hashes preserve auditability. A source failure retains its last known state and does not insert zero prices or rain. The [connector contract](CONNECTORS.md) names supported adapters, access requirements, validation and retry behavior. The [source catalog](catalog/source-catalog.json) includes researched candidates that are not automatically integrated.

Regional forecasts and reanalysis have their own issue/retrieval/observation basis. Market queries preserve crop, market, variety, grade, unit and date. Future planning projections are stored separately from reported observations. Directory-only mandis do not acquire a price through a join. Consent for private farm-to-weather-grid links can be revoked; external requests use coarse coordinates.

## Identity, migration and recovery

Canonical API transactions set a farmer scope and use row policies and narrow roles. Live authentication requires configured HTTPS OIDC/JWKS verification. Device enrollment returns a secret once and retains only its hash; packet receipt checks replay identity, units, timestamp and station ownership. Back up PostgreSQL together with raw payload bytes and generated artifact bytes. Test a restore into an isolated database, verify row ownership and file checksums, and only then switch traffic. Do not run tests against a working farm database.

`prepare_test_db.py` targets the dedicated test database. `test_backend.py` derives its test connection from ignored local runtime settings and runs the backend suite. The [exchange contract](EXCHANGE.md) documents listing, conversation, agreement and handover state. SQL changes should be additive, grant-reviewed and accompanied by endpoint parity tests. The application contains parameterized repository SQL as well as stored read functions; a strict stored-procedure-only policy is a separate migration project.
