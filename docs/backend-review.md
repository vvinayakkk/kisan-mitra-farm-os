# Workspace backend review

Reviewed the complete workspace tool catalog and its upstream routes on 14 October 2026. The original dashboard remains accessible; the workspace is an alternate interface over the same measurements and catalog, with its own capability-scoped conversation, tasks and files.

| Feature / tools | Data path and decision | Validation |
| --- | --- | --- |
| Skills / load_skill | Eleven versioned local workflows; fixed catalog, typed invocation, automatically loaded when appropriate. Keep deterministic workflow loading. | Existing catalog/unknown-skill tests. |
| Station / station_snapshot | UI and assistant now share `assistant.data_sources` and `/api/assistant/station/{id}`. Server alone chooses the existing database or `ASSISTANT_DATA_URL`. Reject sample fallbacks, invalid/future timestamps; preserve missing readings and expose freshness. | Mock rejection, invalid/future time, missing/zero readings, staleness regression tests. |
| History / weather_history | Shared upstream adapter, bounded hours/records; local queries run in a worker thread. Historical records are observations, not forecasts. | Parallel-read/run tests and history route bounds. |
| Prices / market_prices | Configured data.gov.in API; bounded records and timeout. Missing configuration/provider failures cannot imply successful price retrieval. | Tool validation and error boundary tests. No current prices invented. |
| Trends / market_trend | Existing dated mandi history, grouped by market, variety and unit. Require two distinct dates before plotting. | Mixed-market regression test. |
| Schemes / scheme_search | Existing catalog, bounded search; catalog fallback remains explicitly attributed. Verify official eligibility/current terms rather than interpreting a cached entry as approval. | Existing data adapter and catalog source review. |
| Crop Doctor / diagnose_crop | Owned verified image → existing real vision service. Non-images, another workspace's images, and unavailable providers cannot produce a diagnosis. Photos read as text now produce a helpful routing error. | Photo ownership, damaged image, provider failure, incorrect read-file regression tests; earlier live synthetic vision transport check. |
| Questions / ask_farmer | Durable pending call and typed form, including photo upload. Exact pending ID and submitted field validation. | Existing question/resume and invalid-answer tests. |
| Budget / calculate_budget | Decimal arithmetic from supplied quantities/prices; chart reflects calculated amounts. No financial records saved implicitly. | Existing exact arithmetic tests and live synthetic chart test. |
| Calendar / list_tasks, save_task, update_task, delete_task, complete_task | Scoped SQLite records; reviewed AI writes, direct explicit UI edits, cross-worker lease, idempotent save and recoverable deletion. Filter deleted records before the list limit so they cannot hide active tasks. | Existing task CRUD, approval, ownership, lease tests plus >100 deleted-record regression. |
| Expenses / record_expense, list_expenses | Reviewed scoped records and idempotent execution IDs. Keep separate from the telemetry database. | Existing approval/idempotency tests. |
| Documents / create_file | Deterministic DOCX, PDF, XLSX, CSV, PPTX builders. New bounded content previews are stored with the artifact and rendered in chat. PPTX now includes supplied tables rather than only claiming them in metadata. Preview text is inert and capped; full formatted file is downloaded separately. PDF font validation now includes table cells. | Five-format readability/preview tests, live three-format generation, safe text/table frontend tests. |
| Files / read_file, download | Direct owner-scoped lookup, independent of the last-100 display list. Generated-file access still works after many newer records. Office extraction remains bounded; never execute macros or model code. | Old-file download, cross-owner rejection, file-format tests. |
| Memory / recall_memory, compaction | Keep free local SQLite + tiktoken. Full transcripts and archives remain retained while only whole older turns are compacted for the model. Existing bounded lexical archive recall does not infer approval. Storage default is now anchored to the repository, preserving the existing `.assistant-data` location regardless of launch directory. | Existing archive/compaction/ownership tests and earlier live long-conversation recall. |
| Streaming / model providers | Native tool calls, concurrent independent reads, bounded rounds/tools/runtime, public activity and answer deltas; private reasoning discarded. Do not invent successful results after interruption. | Existing SSE fragmentation, tool-call reconstruction, interruption and provider tests. |

## Original backend corrections

- `/api/sensors/latest` no longer invents fresh temperature, soil moisture or rainfall when no measurements exist.
- Nested and flat telemetry ingestion validate finite numbers, IDs and timestamps; retain unmeasured rainfall as null; use UTC; offload database writes; return HTTP 503 on failed persistence. The documented flat `/api/sensors/ingest` route is now implemented.
- History parameters are bounded. Trends acknowledgement now explicitly says `persisted: false`; it does not pretend a log entry saved a dataset.
- Legacy advisor no longer fabricates a sensor snapshot, crop suitability percentages or irrigation advice when data or the AI provider is unavailable. Legacy overview fallback no longer claims stable conditions or fabricated accelerator latency.
- Production compression bypasses NDJSON assistant streams, preserving immediate event delivery; workspace state and station responses explicitly disable caching.
- Environment variables supplied by the runtime take precedence over `.env`, allowing safe isolated tests. `LOG_FORMAT=json` now uses a real JSON formatter. Database logging omits URLs, SQL parameter values and exception bodies; permanent SQL failures do not incur repeated retries.

## Interface consistency

One header brand, two compact icon groups and one classic return control. The original four controls are at the top right; the four added pages use a small floating tool group on the left. There is no full-height sidebar. Entry links preserve the classic source page while changing workspace views. Each companion page uses the same small calendar-style helper.

## Operational boundaries

Hardware measurement transport, field accuracy, live market availability and cloud deployment depend on their real services; deterministic synthetic tests cannot establish those real-world outcomes. Saved calendar tasks are plans, not scheduled hardware actions or notifications. Marketplace matching, profile/authentication, voice, WhatsApp and FPGA endpoints remain separate legacy services; the workspace does not advertise those as executable tools. New backend routes must be deployed with the frontend for production use. Assistant storage needs a persistent volume and backups; the capability token is a local workspace key, not full multi-device user-account authentication.

Validation: 52 isolated backend tests, 13 frontend tests, TypeScript and production build; live XLSX/DOCX/PDF generation and desktop/mobile visual checks. Full production database startup and outbound OTP/WhatsApp delivery were deliberately excluded from local verification; tests do not modify the configured remote database or message real recipients.
