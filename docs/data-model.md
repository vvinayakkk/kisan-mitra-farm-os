# Data model and source contracts

PostgreSQL 16 stores canonical farm, assistant, market, device and exchange state in schema `sv3`. `data_platform/v3/sql/schema.sql` is the base DDL; `data_platform/v3/layout.py` is the ordered migration inventory. Additive `*-runtime.sql` files introduce feature tables, grants and stored read contracts. The catalog is a design inventory; the running database may also contain additive tables. `data_platform/v3/bootstrap.py` installs a new named database or reapplies safe runtime migrations without dropping populated records.

## Ownership, time and provenance

Private rows carry a farmer/owner boundary enforced by scoped connections, owner keys and row-level policies. Read functions for markets and stations use invoker rights and narrow grants. Financial amounts use numeric types; timestamps retain timezone. A market series is identified by crop, market, variety, grade and unit. Observation date, retrieval date and forecast issue time are separate fields. External imports carry provider, immutable release identity, content hash, raw-object reference and quality state. Failed or ambiguous records are quarantined; missing days are not filled as observed prices.

Stored data has different origins: provider observations, modeled forecasts, farmer entries and planning projections. A directory entry establishes a market name/location, not a commodity quote. Code and tooling preserve those distinctions even when a page presents them together.

## Base table inventory

The machine-readable source is `data_platform/v3/catalog/schema-catalog.json`; the base catalog currently defines 75 tables and 29 explicit access-path indexes. The descriptions below are generated from that catalog.

| Group | Table | Purpose |
| --- | --- | --- |
| ingestion | `sv3.providers` | Source contract, license, access and refresh policy |
| ingestion | `sv3.datasets` | Immutable release boundary for live versus synthetic data |
| ingestion | `sv3.ingest_runs` | Watermark, retries, bounded jobs and source failure audit |
| ingestion | `sv3.raw_objects` | Original payload in object storage, hash and request identity |
| ingestion | `sv3.quality_issues` | Quarantine incorrect timestamps, units and conflicting duplicate values |
| reference | `sv3.regions` | Official versioned state/district/tehsil/village hierarchy; demo IDs separate |
| reference | `sv3.locations` | Shared weather grid or public location anchor |
| reference | `sv3.crops` | Canonical crops with multilingual aliases |
| reference | `sv3.crop_varieties` | Keep crop variety/grade distinct for market comparisons |
| reference | `sv3.units` | Explicit dimensions and conversion factors, never infer price units |
| reference | `sv3.markets` | Real official markets or explicitly named demo markets |
| market | `sv3.market_series` | One market/crop/variety/grade/unit series |
| farm | `sv3.farmers` | Consented account and synthetic profile; no Aadhaar or stored plaintext OTP |
| farm | `sv3.consents` | Purpose-scoped permissions, expiry and revocation |
| farm | `sv3.farms` | One farmer can own/manage several farms |
| farm | `sv3.plots` | Real user-drawn field geometry or an explicitly synthetic example |
| farm | `sv3.crop_cycles` | Crop, sowing date, harvest window and season per plot |
| farm | `sv3.farm_operations` | Irrigation/sowing/fertilizing/scouting actual events, not inferred execution |
| sharing | `sv3.resources` | Farmer inventory of equipment, produce or supplies |
| sharing | `sv3.resource_listings` | Opt-in public/neighbor sharing availability, prices and date window |
| sharing | `sv3.resource_matches` | Proposals between consenting participants; no invented agreements |
| farm | `sv3.expenses` | Exact decimal INR expenses, quantities and idempotency |
| farm | `sv3.tasks` | Owned calendar plan with recoverable deletion |
| farm | `sv3.task_events` | Audit events and before/after edits for undo |
| telemetry | `sv3.stations` | Real device or simulated station with explicit source identity |
| telemetry | `sv3.station_sensors` | Metric/unit/depth/calibration per station |
| telemetry | `sv3.packet_receipts` | Global boot/sequence replay protection across monthly partitions |
| telemetry | `sv3.sensor_packets` | Idempotent packet with event/received time and valid readings |
| telemetry | `sv3.sensor_daily` | UTC daily aggregates with counts/completeness |
| environment | `sv3.weather_series` | Shared provider/grid/model series; never pretend to be on-farm hardware |
| environment | `sv3.weather_daily` | Historical observations, reanalysis or simulated history |
| environment | `sv3.weather_forecasts` | Issued short-range forecasts or explicitly labeled long-range scenarios |
| environment | `sv3.soil_samples` | Consent-scoped real lab reports or demo samples |
| environment | `sv3.soil_indicators` | Property/unit/depth/uncertainty, with predicted values distinct from lab values |
| environment | `sv3.satellite_assets` | STAC scene metadata and immutable external asset reference |
| environment | `sv3.plot_indices` | Cloud-masked vegetation indicators with valid pixel coverage |
| market | `sv3.price_observations` | Daily market observations; synthetic history only in the demo DB |
| market | `sv3.model_versions` | Training cutoff, backtest evidence and scenario-only markers |
| market | `sv3.forecast_runs` | One issuance with training cutoff and horizon |
| market | `sv3.price_projections` | Future scenarios or backtested forecasts; never observed prices |
| market | `sv3.msp_announcements` | Official policy by crop/grade/marketing season with notification URL |
| knowledge | `sv3.documents` | Versioned official source document, language, license and review date |
| knowledge | `sv3.document_chunks` | Citable document sections; PostgreSQL text search before optional embeddings |
| knowledge | `sv3.crop_guides` | Region/season/crop stage guidance and validated assumptions |
| knowledge | `sv3.diseases` | Reference symptoms and expert-reviewed support, not fabricated dosage |
| knowledge | `sv3.disease_cases` | Real submitted image and uncertain model assessment; no invented ground truth |
| knowledge | `sv3.scheme_versions` | Versioned real scheme requirements and official application link |
| knowledge | `sv3.scheme_checks` | Explained recommendation, missing answers and reviewed application checklist |
| knowledge | `sv3.regional_statistics` | Published aggregate crop area, production and yield; no farm-level inference |
| agent | `sv3.conversations` | Owned conversation header and resumable summary cursor |
| agent | `sv3.messages` | Append-only complete public transcript, sequence and token accounting |
| agent | `sv3.agent_runs` | Bounded run, lease owner, cancellation and terminal state |
| agent | `sv3.tool_calls` | Validated arguments, result and idempotent execution identity |
| agent | `sv3.approvals` | Exact argument hash and explicit decision before a write |
| agent | `sv3.artifacts` | Owned file metadata, safe excerpt, hash and object storage reference |
| agent | `sv3.memories` | Correction-aware durable farmer facts with evidence, expiry and text search |
| agent | `sv3.retrieval_citations` | Answer evidence references with exact excerpts and source versions |
| agent | `sv3.notifications` | Transactional outbox; demo delivery disabled, never imply an actual send |
| reference | `sv3.source_mappings` | Reviewed external crop/variety/market/region identifiers, never fuzzy-merge silently |
| ingestion | `sv3.source_health` | Per-provider/scope freshness, outage, rate limiting and last-good state |
| reference | `sv3.measurement_definitions` | Soil property basis, accepted units, bounds and non-convertible nutrient forms |
| environment | `sv3.soil_calibrations` | Plot/depth field capacity and wilting point for explicit volumetric water balance |
| agent | `sv3.attachments` | Owned input image/report/audio metadata with quarantine and extraction status |
| farm | `sv3.field_observations` | Farmer reports of stage, symptoms, pests, moisture and uncertainty with optional photo |
| farm | `sv3.harvest_batches` | Actual harvest stock, moisture/grade evidence and storage; units never inferred |
| farm | `sv3.sale_records` | Recorded sale proceeds and selling costs, distinct from mandi quotes and payment claims |
| agent | `sv3.skill_versions` | Versioned skill descriptions, farmer purpose, workflow hash and allowed tools |
| agent | `sv3.tool_versions` | Versioned tool argument/output schemas and side-effect policy |
| agent | `sv3.run_events` | Resumable public progress/tool/artifact/question timeline; no hidden chain-of-thought |
| agent | `sv3.question_requests` | Persisted structured farmer question and waiting state across reconnect/restart |
| agent | `sv3.question_answers` | Typed answer payload and revision identity; server validates against request form schema |
| agent | `sv3.context_compactions` | Versioned summary checkpoints, covered sequences, open questions and token budget audit |
| farm | `sv3.alert_events` | Farmer-facing sourced/derived warning lifecycle with expiry and acknowledgment |
| telemetry | `sv3.device_commands` | Approved bounded command intent: mock/live, exact approval link, expiry and execution identity |
| telemetry | `sv3.device_command_events` | Device acknowledgment/rejection/timeout audit; broker delivery is not execution proof |

## Reviewed source inventory

The source catalog records access conditions and intended refresh contracts. Presence here does not imply that a connector is configured or that a dated observation has been imported. `data_platform/v3/CONNECTORS.md` documents executable adapters and their failure behavior.

| Code | Source | Access |
| --- | --- | --- |
| `ogd-mandi` | OGD / DMI AGMARKNET mandi prices | API key + verified historical exports |
| `enam` | eNAM trade dashboards | Permitted export or approved access; no documented stable public API verified |
| `msp` | Official MSP notifications | Reviewed public notifications |
| `open-meteo` | Open-Meteo weather and reanalysis | Anonymous hosted API for qualifying free use; commercial plan or self-hosting as applicable |
| `nasa-power` | NASA POWER | Public documented API |
| `imd` | IMD weather, warnings and agromet | Registered/approved API access where required |
| `soilgrids` | ISRIC SoilGrids | Downloaded maps/cache; REST optional |
| `lab-uploads` | Farmer-uploaded soil lab / Soil Health Card | Consent-based upload; no verified public personal-record bulk API |
| `copernicus` | Copernicus Sentinel-2 / STAC | Public catalog; asset/processing access and quotas may require account |
| `lgd` | Local Government Directory | Official versioned directory downloads |
| `osm` | OpenStreetMap maps and place context | Licensed extracts/self-hosting for bulk; public service policies apply |
| `icar` | ICAR / KVK agricultural guidance | Reviewed public documents with rights/attribution retained |
| `schemes` | myScheme + originating departments | Curated imports / approved integration; no public API verified |
| `pmfby` | PMFBY notifications / insurance guidance | Public current guidelines; personal claim access requires permission |
| `des-statistics` | DES / OGD crop area-production-yield | Published aggregate downloads |
| `ppqs` | PPQS / CIBRC current labels and notices | Reviewed current official releases |
| `plant-datasets` | PlantVillage / PlantDoc evaluation images | Dataset repository; verify release rights and image provenance |
| `fao-et0` | FAO irrigation / ET0 methodology | Public method references |
| `consented-profiles` | Farmer onboarding / authorized AgriStack | Direct consent; AgriStack only with authorized access |
| `hardware` | Real hardware protocol / mock adapter | Authenticated device registration; same validated envelope for mock |
| `bhashini` | BHASHINI language / voice services | Organization registration, authorization and pipeline access |
| `kvk-directory` | ICAR KVK / expert referral directory | Reviewed official directory, dated per record |
| `npss` | National Pest Surveillance System | Official farmer portal/app or approved integration; public API not verified |
| `disaster-cap` | NDMA SACHET / official disaster alerts | Official portal RSS subscription; verify current endpoint, terms and attribution |
| `nabard-models` | NABARD model project economics | Reviewed public model project documents |
| `ai4bharat-models` | AI4Bharat self-hosted language models | Download/self-host release with verified model and dataset licenses |

## Operational files

- `sql/market-read-runtime.sql` and `sql/station-read-runtime.sql` define stored read contracts.
- `skyview/data/v3/repository.py` contains canonical application queries. Some repositories still use parameterized SQL; the application is not stored-procedure-only.
- `skyview/data/v3/ingestion.py` validates provider payloads and device envelopes.
- `skyview/data/v3/worker.py` leases and schedules bounded recurring work.
- `catalog/reviewed_sources.json` stores reviewed reference extracts; a catalog entry is not an application approval or a verified field measurement.
- Raw payloads, artifact bytes and credentials stay outside Git and need backup with PostgreSQL.
