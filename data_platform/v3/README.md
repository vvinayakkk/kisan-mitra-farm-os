# SkyView data platform v3

A researched fresh-database foundation with an implemented unified backend. The local UI now uses persistent PostgreSQL v3, canonical feature routes, assistant storage and deployed public weather adapters. The legacy remote database remains untouched. See [OPERATIONS.md](OPERATIONS.md) for the current implementation and tested source boundaries. Reviewed revision: 3.1.0; `final-review.json` records 32 findings and launch gates. Research date and reproducible demo cutoff: 2026-10-14.

## Deliverables and boundaries

- `schema.sql`: PostgreSQL 16+ DDL, 75 base tables, keys, constraints, monthly partitions, evidence guards and farmer-scoped row security.
- `schema-catalog.json`: every table, column definition, purpose, ownership and additional access-path indexes.
- `source-catalog.json`: 26 researched source categories, links, access constraints, formats, refresh schedules, destination tables and mock policies.
- `roles.sql`: read-only non-superuser application role. Actual LOGIN credentials/authentication and narrowly scoped write services must be provisioned separately.
- `seed_demo.py`: standard-library deterministic generator for 400 fictional profiles in all 36 states/UTs; CSV, transactional COPY seed and checksums. No network calls or genuine contacts.
- `validate.py`: constraints, RLS, scenario separation and query plans against a specifically named disposable test container.

The generated seed contains 412,905 logical rows, including 400 farmers, 400 farms, 800 plots, 1,600 crop cycles, 108 fictional markets, 324 comparable price series, 118,260 historical price points and 118,260 future scenario points. Weather has 13,140 historical rows plus 13,140 future scenario rows. Eighty mock stations produce 57,472 hourly packets over 30 days plus receipt records and daily completeness aggregates. Four hundred profiles have source-backed message/memory fixtures, calendar plans, expenses, resources and synthetic soil examples. Tables requiring verified source evidence deliberately remain empty.

History is **2025-10-15 through 2026-10-14**, inclusive. Future scenarios are **2026-10-15 through 2027-10-14**, inclusive. Today is a dataset cutoff rather than proof that all observations have arrived. Real ingest rejects timestamps beyond actual receipt/clock tolerances.

Balanced coverage gives each region 11 profiles and the first four regions one extra. It is test coverage, not a population or crop-area representative sample. Regional crop mixes are illustrative; dates, yields and agronomic suitability require localized verification. Prices use arbitrary synthetic baselines in explicit INR/quintal, not actual prices or MSP. Long-range ranges are uncalibrated planning envelopes. Soil numbers are not lab reports; fictional boundaries are not official land parcels. All outbound delivery is disabled by default. No Aadhaar, usable phones, verification tokens, actual disease labels or official approval results are generated.

## Real data first

P0: canonical LGD geography; consent-based farmer/plot onboarding; daily OGD mandi snapshots with original units; reviewed official MSP; licensed weather history/reanalysis and short-range forecasts; NASA agroclimate; reviewed ICAR crop guidance and scheme links; farmer-uploaded lab reports; hardware/mock envelope.

P1: IMD access, eNAM permitted exports, cached SoilGrids maps, cloud-masked Sentinel indices, regional agricultural statistics, current pesticide-label guidance, insurance notices and map extracts. P2: licensed disease-image benchmark evaluation and validated price prediction models.

A source endpoint returning HTTP 200 proves one sample access, not a full reliable integration. The included probes returned 200 for Open-Meteo, NASA POWER, SoilGrids and Copernicus catalog metadata, and 401 for IMD. No full mandi backfill, credentials-based export or satellite processing was validated. SoilGrids REST is explicitly optional because the official docs warn of a pause. Open-Meteo's free hosted API has noncommercial conditions; data licensing differs from hosted commercial access. eNAM, myScheme and LGD are not assumed to have unrestricted stable JSON APIs.

## Data flow

1. A provider record declares access, license, attribution, cadence and allowed usage. A dataset release declares origin, live/demo lane, cutoff and checksum. Sources never share a fake blanket license.
2. Workers take a lease on bounded ingest jobs, fetch with timeout/retry/backoff and store original payloads outside PostgreSQL. `raw_objects` retains content hash, URI and request identity; keys and PII are redacted from URLs/logs. Content-addressed storage can reuse identical bodies.
3. A staging adapter maps provider identifiers to versioned canonical geography/crop/variety/grade/unit records. Source time, ingestion time and forecast issuance are distinct. Reject impossible measurements; quarantine ambiguous units and conflicting duplicate values in `quality_issues`.
4. Promote validated records transactionally. Price upsert key is dataset + market/crop/variety/grade/unit series + observation day; preserve raw revisions and increment revision only for legitimate changed source observations. Do not multiply rows after retry. Separate release revisions mean intentional alternate-source provenance, not accidental duplicate ingestion.
5. Sensor registration determines ownership server-side. Authenticate the device; retain original packet/device/boot/sequence identity. Insert receipt ledger then packet in one transaction; duplicate boot/sequence is rejected even across monthly partitions. Preserve late arrival and missing data. Check device clock drift before promotion. Device command queues and acknowledgments are a separate integration: this foundation does not run actuators.
6. History stays in observation tables; issued forecasts and scenarios stay in projection tables. Normalize units explicitly, never silently connect different series. Missing market days, cloud-covered imagery and broken sensors remain missing rather than zero or invented real measurements.
7. Endpoint query responses carry `origin`, `source`, `as_of`, `fetched_at`, `freshness`, `unit`, `evidence`, `confidence/method` and missing-data status. UI must show Observed / Reanalysis / Forecast / Scenario / Demo labels. All charts preserve gaps and compare equivalent series.
8. Agent tools read repository methods rather than arbitrary SQL. Preview write intent, bind approvals to exact arguments/hash/expiry, then execute with an idempotency key and scoped privileges. Hardware actions, external messages and official submissions require the actual connector and acknowledgment. An assistant sentence is never execution evidence.

## Feature-to-table map

| Feature | Primary tables | Handling |
|---|---|---|
| Farmer account/onboarding | farmers, consents, farms, plots, crop_cycles | Owner derived from verified auth; ask missing location/crop/sowing details |
| Farm station | stations, station_sensors, packet_receipts, sensor_packets, sensor_daily | Event time + last receipt + calibration + completeness + mock badge |
| Weather/irrigation | weather_series, weather_daily, weather_forecasts, soil_samples, soil_indicators | Modeled weather and measured soil are separate; explain water assumptions |
| Mandi/history/charts | markets, market_series, price_observations, msp_announcements | Exact units and grade; stale badge; source provenance and actual gaps |
| Future price planning | model_versions, forecast_runs, price_projections | Scenarios available now; real forecasts require validated model/backtests |
| Crop doctor | diseases, disease_cases, documents, document_chunks, crop_guides | Ask for actual image and stage; retain uncertainty; expert-reviewed guidance |
| Schemes/support | scheme_versions, scheme_checks, documents | Missing-answer question prompts; potential match, not approval |
| Calendar/edit/delete | tasks, task_events, notifications | Soft delete, undo evidence, timezone and delivery opt-in |
| Expense/notebook | expenses, farm_operations, crop_cycles | Decimal amounts, execution identity, real event evidence |
| Sharing | resources, resource_listings, resource_matches | Private default; opt-in filtered listing endpoint needed before neighbor sharing |
| DOCX/PDF/XLSX preview | artifacts, agent_runs, retrieval_citations | Objects outside DB, checksum + safe excerpt + scoped download |
| Chat/tools/approval | conversations, messages, agent_runs, tool_calls, approvals | Bounded runs, replay identity, cancellation, exact argument approval |
| Memory/compaction | memories, messages, conversations | Durable facts with message evidence, correction chain and validity; summary cursor |

## Farmer privacy and permissions

Use separate `skyview_v3_live` and `skyview_v3_demo` databases and credentials, not just a UI toggle. Live rejects demo datasets. Schema application is guarded to fresh v3 database names. The seed refuses live and nonempty profile tables. The app role is deliberately read-only; service roles receive minimum required mutations after implementing their validation/approval paths.

Set `SET LOCAL app.farmer_id` from a server-verified identity within each transaction, reset pooled context, and never allow browser/client arbitrary SQL or untrusted owner selection. GUC-based RLS is not independent authentication: a trusted SQL-capable application can choose the GUC. PostgreSQL owners and superusers bypass RLS. Tests explicitly use a non-owner role. Composite owner FKs prevent cross-farmer private parent links, including memory evidence. Never directly grant browser access to partition children or administrative functions. A production gateway needs purpose-consent checks, audit and verified session binding.

Private sharing records are intentionally owner-only. Do not broaden whole-table RLS to expose farmer IDs or stock records just to display neighbors. Build an authorized, sanitized projection of opted-in listings (resource category, availability, coarse region, opaque listing identity), enforce neighbor/location rules and participant consent, and keep contacts off listings. Matching returns owner/requester-specific proposals. The foundation contains storage, not that gateway implementation.

Artifact storage needs per-farmer access, expiring downloads, malware/type validation and retention. Do not expose object-storage credentials. Revoked consent blocks new ingestion and sharing. A deletion workflow must explicitly remove or de-identify owned messages, memories, objects and derived artifacts after applicable retention policy; relational FKs intentionally prevent silent orphaning rather than providing a blanket automatic cascade.

## Indexes and performance

- UUID PK/FKs and exact natural uniqueness constraints prevent retry duplicates. Prices retain series/date and source release. Packet receipts enforce station/boot/sequence globally; partition PKs also include event time as PostgreSQL requires.
- Monthly range partitions only for price observations and high-volume packets; precreate upcoming partitions using an admin job. No DEFAULT partition hides routing errors. Initially 13 price partitions and 2 telemetry partitions.
- B-tree owner/date indexes for calendar, expenses, plots, artifacts and messages; partial indexes for open tasks, pending ingestion and allowed notification delivery. Covering series/day price index serves history and latest queries. Station/owner/time index serves latest readings. BRIN supports broad time scans on append-heavy tables.
- GIN text search on knowledge chunks and durable memory. PostgreSQL `simple` dictionary is a baseline that preserves multilingual tokens; region/language metadata and tested tokenization/normalization are needed for actual multilingual quality. Semantic embeddings are optional, not assumed solved by this schema.
- For 400 users, start with PostgreSQL plus a bounded async worker and object storage. Redis, TimescaleDB, Kafka, Pinecone and a separate vector database are not prerequisites. Add cache/queues only from measured pressure. Optional PostGIS becomes useful for real distance/geometry queries; GeoJSON validation and geometry indexing are not implemented here.
- Cache weather by shared provider grid/issuance, not repeated farmer requests. Avoid querying all historical rows for one station. Use keyset pagination, preaggregated daily readings, bounded chart windows and last-good data with a stale label. CDN/cache public source metadata, not private profiles.
- At 80 mock hourly stations, ~700,800 packets/year before outages. Real firmware every five minutes would produce ~8.4 million packets/year; size retention, partitioning, storage and aggregates from measured firmware cadence.

Local query timings in `validation.json` are examples for this dataset/container, not production SLA claims. Never infer real prediction accuracy from synthetic data.

## Real forecasting and memory acceptance gates

Price models need at least verified 365-day history; longer multi-season history is preferable. Include market/crop/grade/units, arrival volume and holidays as available. Sparse series can lack enough data. Start seasonal-naive and last-price baselines, use rolling-origin splits and strict training cutoffs, evaluate MAE/MASE plus interval coverage against real observations by crop/market/horizon. Train and validate separately by relevant series. Promote only supported horizons (e.g. 7/14/30 days) after outperforming baselines with documented sample sizes. A 365-day daily path remains a scenario unless rigorous evidence supports it. Annual MSP is an announced policy, not a trading price forecast. Synthetic fixture metrics cannot qualify a model as validated.

Memory keeps the complete user-visible transcript and a summary-through sequence, recent turns plus selectively retrieved durable facts, never private chain-of-thought. Facts record user-confirmed evidence, corrections/superseded IDs and validity. Summaries do not override newer corrections. Expire transient prices/weather and prefer tool freshness over recalled facts. Build compaction under explicit token budgets; maintain unfulfilled tasks/questions/tool outcomes in the summary; test retrieval relevance, correction propagation, tenant isolation, restart/resume and deletion. No free framework guarantees these behaviors automatically. The runtime now persists compactions, pending work, farmer-scoped recall and correction-aware memory. Multilingual relevance benchmarks remain a separate evaluation task.

## Fresh build and migration stages

1. Create separate fresh PostgreSQL 16 databases and least-privilege service credentials. Apply `schema.sql` and `roles.sql` to each. These are one-shot fresh migrations, not idempotent upgrades.
2. Generate and load fixtures into demo only. Enable external deliveries and hardware writes nowhere in demo. Confirm labels and user flows against faults, missing fields, stale sources and conflicting inputs.
3. In live, load official reference IDs and reviewed source documents first, then collect consented profiles and ingest actual sources. Preserve source snapshots, licenses, import logs and source freshness. Historical backfill is conditional on available permitted exports; do not represent synthetic history as real just to fill a chart.
4. Add a v3 repository/service layer behind the current route contracts. Match farm station, calendar, crop doctor, market chart, scheme questions, artifact preview and sharing behaviors. Weather grid data becomes shared rather than repeated station data. Use new `DATABASE_URL` only after that code exists and passes endpoint tests.
5. Quarantine legacy data by provenance/units/date/duplicate conflicts. Do not import all 340,087 legacy rows as trusted observations. In the prior audit, weather had 144,868 exact repeated measurement payloads and 108 additional distinct payloads sharing timestamp keys; do not discard legitimate revisions merely because timestamps repeat. Preserve a raw archive and reconciliation report. Current demo IDs never map to real legacy identities.
6. Replay acceptable source records into staging, reconcile totals/units/date coverage and run owner-access tests and UI acceptance. Stage a backup, reversible cutover and last-good fallback. Do not switch production before user-facing behavior and ingest freshness are verified.

## Reproduce locally

From the repository root:

```sh
python3 data_platform/v3/build_schema.py
python3 data_platform/v3/seed_demo.py --output /tmp/skyview-v3-demo --as-of 2026-10-14 --seed 20261014
# Create a NEW EMPTY skyview_v3_demo with your own administrator connection.
psql -X -v ON_ERROR_STOP=1 -d skyview_v3_demo -f data_platform/v3/schema.sql
psql -X -v ON_ERROR_STOP=1 -d skyview_v3_demo -f /tmp/skyview-v3-demo/seed.sql
psql -X -v ON_ERROR_STOP=1 -d skyview_v3_demo -f data_platform/v3/roles.sql
```

Use a local disposable container for validation only, without host port/network, and remove it afterward. `validate.py` intentionally limits the container name to `skyview-v3-design-check`; its live-named database is an empty test namespace inside that container, not production. It may recreate that test namespace. Review the script before running against any environment. The checked-in scripts contain no credentials.

## Final review additions (revision 3.1.0)

The review expands the schema from 58 to 75 base tables. Seventeen additions are source mappings/health; measurement definitions and soil calibrations; attachments and field observations; harvest batches and sale records; skill/tool versions; public run events; question requests/answers; context compactions; alert events; and device commands/events.

Demo now has a fictional district/block/village under each state/UT (144 geography rows), 21 soil property definitions and 12 SHC parameters per plot, 800 synthetic soil calibration records, 400 harvest batches/sales, 400 field observations and attachment placeholders, 400 resumable agent run/question/compaction fixtures, and the current application's 11 skill / 19 tool definition snapshot. Placeholder input files explicitly do not exist and stay scan-pending; no real file or diagnosis has been fabricated. Registry entries are inactive until v3 runtime binding and output validation exist. Model code is not execution evidence.

Total soil nitrogen is distinct from lab plant-available nitrogen; SoilGrids pH and texture scale/offset must be decoded before canonical storage. The property catalog accepts typed units and records original report basis. Lab phosphorus/potassium forms (elemental versus oxide), extraction method, conductivity conditions, soil depth and bulk density matter. Soil-health fixtures are synthetic, not dosage recommendations. Relative sensor percentages are not volumetric water content. Calibration and reviewed crop-stage coefficients are required before liters or pump-duration advice. Seasonal demo cycles remain illustrative, particularly for perennial crops; never train a real agronomic model from them.

Source health distinguishes unknown, stale, outage and rate-limited scopes. Alias mappings are reviewed and time-valid. Import canonical market identities once and reuse them across daily releases rather than creating new markets for each source snapshot. Official warnings need geographic applicability, source authority, expiry and update/cancel handling. SACHET advertises RSS, but its feed parser/endpoint has not been integrated here. BHASHINI docs describe PoC use and production access conditions; do not promise free production voice. KVK/NPSS are referral/curation sources, not assumed unrestricted diagnosis APIs. NABARD templates supply budgeting structure, not current prices or an actual loan offer.

Partition children cannot be granted to the app role because direct child reads do not apply the parent's farmer policy. The revised roles grant base tables/views only; raw ingest/quality logs remain admin-only. Fresh login/service grants must preserve this restriction. Both base and restored-database ownership checks are executed. Provisioning a LOGIN and binding identity/consent at the API are still required.

Market-price units must be mass/count. Sale amounts use decimal generated totals; a sale cannot exceed stock or precede harvest, and harvest edits cannot invalidate already-recorded sales. Task `row_version` increments on edit; the API must use an expected-version predicate and return conflict rather than overwriting an offline edit. Case photo/file ingestion requires MIME/signature/size validation, quarantine, ownership, safe parsing and restricted object downloads. Artifact metadata by itself does not implement those controls.

Hardware commands bind matching unexpired approval to the exact station/action/mode/payload hash using `sv3.command_argument_hash`; API previews and approval persistence must use that database function for the same canonical representation. Command target/payload changes recheck approval. Mock stations cannot accept live-mode commands. The DB prevents demo external email/SMS/WhatsApp delivery. It does not authenticate a device, enforce firmware interlocks, run a dispatcher or independently prove a physical action happened. Never enable hardware dispatch simply because these tables exist.

`validate.py` tests new ownership/unit/stock/approval/memory constraints, independently regenerates identical fixtures, and performs pg_dump/pg_restore inside the isolated container. Restoration compares all base-table row counts and owner access. This is not a complete production recovery test: real database PITR, object-storage backup, credential restoration, worker restart and user-facing acceptance must be rehearsed before launch. `database-catalog.json` in the output bundle reflects actual PostgreSQL columns, constraints and indexes.

Freeze this as the baseline for the current farmer features. Before launch, actual adapters/imports, authenticated v3 repositories, scoped writes, SSE/question resume, compaction quality, upload/file generation, offline conflict behavior and UI truth labels need endpoint acceptance checks. These are explicit gates in `final-review.json`, not silently treated as complete. Livestock/veterinary, fisheries, lending/payments and autonomous machinery are separate future modules.

Weather series carry `max_forecast_lead_days` (default 15, equivalent to 16 days including issue day); the source adapter must set the actual provider/model limit, e.g. six lead days for a seven-day inclusive forecast. Daily forecasts beyond that configured lead are rejected; 365-day scenario rows remain allowed.
