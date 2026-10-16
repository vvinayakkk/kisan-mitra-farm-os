# Unified backend v3: local operation

The running UI uses the unified API at `http://127.0.0.1:8001`; Vite serves `http://127.0.0.1:5173`. Data is persisted in PostgreSQL 16, schema `sv3`, database `skyview_v3_demo`. The Docker volume is `skyview_v3_backend_data`. The separate `skyview_v3_live` database is reserved for verified identities and consented onboarding. `skyview_v3_test` contains integration fixtures only. The legacy remote database is not repointed or written by v3.

## Start and preserve data

For the existing local installation, the single-command launcher starts the retained
PostgreSQL container, applies the additive Saathi/support-folder migrations, and
starts missing API and UI processes:

```sh
.venv/bin/python data_platform/v3/local.py
```

It never reseeds or resets data. Keep the terminal running for background workers;
sleeping or shutting down the computer pauses local work. Ctrl+C stops only servers
started by that invocation. Existing running servers are reused.

Run `.venv/bin/python data_platform/v3/check_local.py` for a read-only coverage,
worker-heartbeat, file-integrity and source-health report. Results are saved in
ignored `.v3-data/local-verification.json`. Local readiness and external provider
health are reported separately; a provider outage does not erase stored data.

### October 15 local verification

The expanded local database contains 152 crops, 1,346 markets, 4,591,980 historical
price observations and 2,352,060 future planning rows. History ends on the current
day; future planning rows stay separate from historical chart queries. Eight
crop/state combinations returned rates and 90-point histories in 60–81 ms during
the local database check. This is measured query time, not a guarantee for every
device or first page load. Open-Meteo and NASA POWER are healthy; the configured
AGMARKNET source reports an outage and retains its retry state.

Saathi preparation now uses durable owner-scoped jobs, leases, bounded retries,
source evidence, optional Google Search grounding and reviewable draft steps.
Approval atomically saves a notebook plan; replay does not duplicate the plan.
Drafting does not place orders, operate hardware or send external messages.
Support-folder checklist flags are persisted per farmer/programme with version
checks. Login warmup now populates the same bounded cache consumed by views;
mutations, session changes and returning online invalidate cached reads. Local date
rollover runs just after midnight in Asia/Kolkata.

The previous review-fixture cleanup left 24 orphaned assistant metadata records.
Exact IDs from its backup are now retired without deleting user history or
restoring old test files. File listing, download lookup, legacy import and
reconciliation all honor retirement. The dry-run reconciliation reports one
active canonical file, 21 retired file records, no pending repairs and no failures.
Use `python -m skyview.assistant.v3_reconcile --help` for explicit, idempotent
recovery of genuinely missing legacy files; it never overwrites existing files.

Validation: 393 backend tests, 213 frontend tests, TypeScript and production build
passed. The build reports an existing large-chunk warning. Browser checks covered
market comparisons, grounded research, support checklist persistence, responsive
notebook/support layouts, stationary chat-history layout and refreshing station readings.

From the repository root:

```sh
docker start skyview_v3_backend_db
.venv/bin/python data_platform/v3/run_backend.py
```

In another terminal, run `npm run dev` from `frontend`. Its ignored `.env.local` must point both `VITE_API_URL` and `VITE_ASSISTANT_API_URL` to port 8001. Existing browser sessions, calendar records, files and transcripts survive API restarts.

For a fresh installation, generate a seed with `seed_demo.py`, then call `provision.py --seed-dir /absolute/path/to/generated/seed`. Provisioning creates private runtime settings with random credentials and refuses to reset an existing database. Run using Python 3.12 and `infra/requirements.txt`. `schema.sql` is a fresh-database migration, not a migration to reapply to populated storage. Runtime migrations are independently idempotent.

Credentials are stored in ignored `.v3-data/runtime.env` and `.v3-data/postgres.env` with restricted permissions. Do not publish them. Back up PostgreSQL **and** `.assistant-data-v3` artifact bytes and `.v3-data` raw-object storage together; database metadata alone does not reconstruct downloaded files.

## Feature paths

- Station packets, alerts, trends, prices, schemes, profile, directory and advisor routes read canonical repositories. Compatibility routes support classic views without the old database.
- Assistant capabilities select the farmer server-side. PostgreSQL row security protects private records; request-supplied phone numbers do not select another farmer. Task changes use row versions. Durable run events support replay, and writes require explicit review.
- Conversation messages, archives, facts, compactions, tasks, expenses, crop assessments and artifact metadata share canonical storage. Earlier local chat records were imported without importing untrusted legacy price/sensor tables.
- Word, PDF, Excel, CSV and presentation outputs have downloadable bytes, checksums and chat previews. Files are owned by the authenticated farmer.
- Crop Doctor validates and strips uploaded image metadata, calls configured vision, persists the photo and uncertainty, and returns errors rather than invented healthy results. Voice uses configured speech services and offers editable transcription; it does not place calls or send messages.
- Capabilities expire after 30 days. Logout requests server revocation while retaining farmer history; a newly verified session can retrieve its owner’s records.
- The classic data explorer exposes only an allowlist of the authenticated farmer’s tables, with validated sort/filter identifiers and bound values. It never exposes raw logs, capability hashes, other farmers or a SQL execution console.
- Verified live identity uses an HTTPS OIDC issuer/JWKS/audience. Without those credentials, live session bootstrap fails closed. Demo OTP is explicitly synthetic and cannot authenticate arbitrary real phone numbers.
- Live onboarding supports farms, plots, crop cycles, farmer-provided soil reports and registered devices. `POST /api/farms/{id}/weather-link` requires an owned plot and explicit `consent_to_share_coarse_grid: true`; coordinates are snapped to a shared 0.25-degree grid before any source request. The worker activates it automatically. `DELETE` on the same route revokes the link and future fetches. A device secret is returned once; only its hash is stored. Packets validate units, timestamp, station ownership and replay identity. Enrollment alone does not claim hardware connectivity.

## Source behavior

The single leased worker updates mock telemetry every five seconds for the selected demo farm and rotates other mock stations. It fetches Open-Meteo short-range modeled forecasts, ERA5 reanalysis and NASA POWER modeled history for a public regional grid. These are model products, not on-farm sensors. Provider observation days, fetch time and source attribution remain separate. Open-Meteo does not supply a numerical model initialization time in this adapter response; the forecast issuance field identifies a captured provider-response snapshot, with that basis explicit in provenance. Grid resolution is a nominal estimate, not precision confirmed by the response.

The 400 fictional profiles cover all 36 states and union territories. The expanded local history covers two years, with future planning scenarios kept in a separate table. They remain labeled synthetic/scenario. The configured OGD mandi probe timed out during validation: no real mandi prices were substituted. Source health records outage and retry state. Weather adapters are actually deployed; the wider source research catalog does not imply all 26 categories are integrated.

Physical hardware is absent. Device ingress is implemented and tested with isolated packets; hardware execution and external delivery are disabled. FPGA outputs are explicitly unvalidated software simulations. No pump, SMS, WhatsApp message or outbound call is claimed to have run.

## Validation

Prepare the isolated database with `python data_platform/v3/prepare_test_db.py --seed-dir /absolute/path/to/generated/seed`; this never resets existing storage. Then run `.venv/bin/python data_platform/v3/test_backend.py`. The wrapper derives only the named test URL from ignored runtime settings and does not print credentials. Use `V3_TEST_DATABASE_URL` pointing only to the dedicated test database for opt-in PostgreSQL tests. Legacy isolated SQLite tests run in legacy mode; individual PG fixtures select v3. Enable `SKYVIEW_V3_INGEST_TESTS=1` for rollback-only ingestion contracts. Run `tests/assistant`, `tests/data_v3`, `tests/test_disease_screening.py`, and `tests/test_v3_voice.py`. Frontend verification uses Vitest, TypeScript and the Vite production build.

`/health` reports database health; `/api/data/status` reports source freshness and data mode. A live deployment additionally needs configured identity, permitted source access, HTTPS, managed backups and actual device commissioning.

## Farmer workspace release 3.1

The four core controls and four side icons remain. Farm notebook progressively opens Today, fields/crop seasons, money, crop follow-ups, plans, memory and files. Services and family/FPO checklists are secondary collapsed sections under Plans. Farming pages work before hardware commissioning; this does not mark a station connected. Classic remains the default entry.

Additive `workflows-runtime.sql` and `shared-work-runtime.sql` migrations preserve existing data. They introduce private ledger entries, crop notes, missions/receipts, replay receipts, service records and isolated group plans. Plot names extend the existing onboarding migration. Provisioning and test preparation apply these repeatable migrations; existing installations must apply them before starting this release.

The actual runtime catalog contains **20 skills and 45 tools**. Today uses India-local due dates and open crop cases. Ledger keeps paid/received amounts separate from estimates and receivables, labels synthetic fixtures, and shares the canonical path with older assistant expenses. Approved workflow writes commit their results and replay receipts atomically. Mission work invokes actual assistant tools and retains progress receipts across questions, approvals and restarts; it does not infer physical checklist completion or run indefinitely without a farmer request.

Crop follow-ups have dated notes and uncertain assessments. Documents can be revised into new owned versions while retaining original bytes. Photo reading extracts literal receipt/soil-report text through configured vision, requires confirmation, and never records a payment automatically. Soil-report saving has a reviewed tool, owned field/source checks, explicit depth/units/nutrient basis, replay protection and no laboratory-verification claim. Field sketches use saved coordinates/boundaries locally, without map tiles or satellite claims.

Shared groups expose only group checklists and consented member display names. Reader/contributor/owner roles, one-use seven-day invitations, explicit server-validated consent, revocation and optimistic task edits do not expand access to private ledger, fields, coordinates, diagnoses, files or conversations. Invitation secrets are shown once; only hashes persist. Service arrangements and quotes are farmer-entered records, not app-made bookings or payments.

Voice is shared across chat, helpers, questions, searches and farming forms. It records actual microphone amplitude, offers optional disclosed browser captions, then transcribes a completed recording through the configured provider. Words remain editable before insertion; no chat or farm write is submitted automatically. Number/date dictation refuses ambiguous values or silent unit conversion. Read-aloud playback is explicit. Security codes are typed/pasted instead of sent to speech services. Application recording limits are 30 seconds/5 MB; real field accents/noise still need benchmarking. Existing speech/vision account quotas and charges apply; no new subscription or paid library was introduced.

Offline reading is explicit opt-in, session-scoped, dated and expires after 24 hours. Native IndexedDB holds at most three selected files, 5 MB each, until manual upload; local IDs cannot reach server tools. Reconnection never replays writes or uploads. Logout/disabling copies clears local bytes and invalidates in-flight work. The production service worker precaches a build-fingerprinted public shell and all lazy code bundles, never authenticated API responses. Shared memberships/invitations are excluded from snapshot caching. Browser offline opening is reported ready only after an active worker exists. Application drafts also survive refresh without automatic submission.

### Deployment and evidence boundaries

This release implements the software workflows; it does not complete the entire field-validation roadmap. Verified live identity still needs a configured OIDC provider. Actual mandi ingestion remains dependent on permitted source access and a successful fetch; demo history/scenarios stay synthetic. Comprehensive reviewed regional crop/treatment guidance, satellite connectors, verified supplier booking, insurer submission and supervised physical irrigation are not deployed. The expert and insurance skills prepare sourced referrals/checklists/documents, not external appointments or claims. Farmer pilots, language/diagnosis quality measurement, device calibration and a production backup/restore exercise require real participants and infrastructure.

Memory controls supersede/expire retained facts. Original chat messages, archives and summaries can still contain the old statement; forgetting a fact is not deletion of the whole conversation. Native PostgreSQL full-text retrieval and compaction remain the free local memory foundation.

Release checks include backend owner/role isolation, exact review/replay handling, mission questions/receipts, all five generated artifact formats and revision lineage, photo extraction, voice cancellation/late responses, native offline file transfer, frontend regression tests, TypeScript and production build. Clean synthetic live-provider tests verified speech generation/transcription and receipt OCR; these are not field-accuracy benchmarks. Desktop/mobile visual reviews and a real browser local-file save/reload/manual-upload check were performed. Local smoke latencies are development measurements, not production SLA guarantees.

## Farmer exchange release

The additive `exchange-runtime.sql` migration adds four tables (93 total in this local v3 schema). Existing databases must apply it before the exchange router is started. New provisioning and isolated-test preparation include it. See [EXCHANGE.md](EXCHANGE.md) for identity, publication consent, bilateral state transitions, indexes, replay rules and live-community rollout limits.

The workspace's Farmer exchange icon opens the resource stream and private in-site inbox; the mandi page links to the same workflow. Resource matching is explained by named-resource and exchange-wish fit plus stated district/state context, never invented road distances. Whole notices remain reserved after agreement, completion or dispute. Messages are incrementally polled only while visible, with bounded history and per-participant volume limits. Mitra's farmer-exchange skill and three read tools can inspect listings, matches and owned exchange progress; they cannot publish, send messages or accept terms on a farmer's behalf.

Local UI acceptance used explicitly synthetic demo accounts and listings, verified independent messages, acceptance, both handovers and both completion confirmations, and withdrew the separate test labour offer. No physical exchange, payment or contact with an outside farmer occurred.

## Website profile, exports and answer controls

The top-left profile icon opens owned farmer details and saved farm/field summaries. Only supported profile attributes can be edited; land-boundary editing stays in the farm notebook. Relevant record views expose local CSV/JSON exports, with export timestamps, provenance/units notes, loaded-record limits and spreadsheet formula protection. Native generated artifacts retain their original download formats. Answers expose copy, browser-session feedback, explicit sharing, read aloud, Markdown/text export and browser print/save-as-PDF.

The redo icon rewrites only the latest completed owned answer through an authenticated endpoint with no tools. It preserves the original answer and displays an explicitly unsaved alternative. It does not repeat tasks, approvals, bookings or writes. Ratings are scoped to the browser session and are not represented as model training or collected backend feedback.

Website offline controls are hidden at the user's request while website work remains the focus. The existing production-only cached shell and opt-in snapshot foundation remain in code for later app work. Offline opening requires an earlier online installation/cache; the Vite development server does not install the service worker. AI requests, new data and participant messaging require a connection. No first visit without a connection is promised.

## Resource catalogue and review cleanup

`python data_platform/v3/seed_exchange_demo.py --apply` restores a coherent fictional sharing catalogue in the fixed local `skyview_v3_demo` database: 400 synthetic profiles across 36 states/UTs, one inventory resource and three offer/need notices per farmer. IDs are deterministic, edited notices are preserved, and reruns retain counts. No participant messages, agreements, bookings, payments or real contact numbers are fabricated. Classic matching and the new exchange read the same notices; classic cards can open a specific published notice for review in the workspace. Contact buttons appear only for valid public numbers; otherwise farmers coordinate within the site.

`python -m data_platform.v3.clean_review_fixtures` reports identified local QA records; `--apply` removes only the explicitly named review fixtures and retains a private backup under ignored `.v3-data`. This cleanup removed the known QA files/uploads, calendar tasks, estimated-cost row, exchange test notices and their thread, test archives, and test memories. Seeded farming records and genuine user conversations are preserved. Run automated mutation tests only in `skyview_v3_test`.

## Reference coverage and seasonal planning

`python data_platform/v3/refresh_reference_catalog.py --apply` idempotently imports the reviewed public references into the local practice database. Current coverage includes 29 Indian programme references and 14 citable documents/chunks, including official discovery resources for the United States, European Union, England, Canada and Australia, FAOLEX global policy discovery, and regional January–March agronomic examples. This is an index of programme existence and broad purpose, not every scheme worldwide or an eligibility decision. Application windows, local implementation, benefits and country-specific rules require current official verification. The ingestion worker now checks each source/content version instead of skipping all new references once PM-KISAN exists.

Mitra's capability tool derives its descriptions from the actual skill/tool catalogue. Seasonal planning combines owned farm context, the requested future period, available references and conditional general agronomy; missing future measurements do not prohibit a useful plan. It distinguishes ordinary winter sowing, an already growing crop, spring crops and harvest dates. It asks for location, water, soil and local sowing-window confirmation where necessary, and does not fabricate future weather, yields or profit.

Durable memory now retains explicit reported farm facts/preferences rather than every user question or command. Corrections supersede prior versions; deterministic evidence identities prevent replay from resurrecting old or forgotten facts. Full conversations remain the evidence trail. Both recall and the notebook exclude historical question-only memory pollution.

### Inline live voice conversation

The chat composer includes a Live voice button. Its centered orb/transcript is inline;
there is no modal or separate voice conversation. Speech turns use microphone endpoint
detection (1.3 seconds of silence after speech; 30-second upper bound), configured
Sarvam STT with existing Groq fallback, the same authenticated `sendAssistant` agent
stream/tools/memory, and Sarvam TTS. It is consecutive speech turns, **not** a full-duplex
WebRTC/OpenAI Realtime connection. Provider/agent latency remains real and cannot be
promised below one second. Live mode does not enable a separate browser speech recognition service. The microphone
meter and turn status are live; the configured provider supplies the final transcript
that appears in the chat.

Microphone access begins only after pressing Live voice. Microphone recording pauses
while the agent responds or speaks and while a question/approval card needs review.
Spoken commands never auto-approve cards. Mute stops recording; Interrupt cancels the
response and playback; End stops microphone/transcription/playback and cancels only a
currently voice-owned agent run, preserving separately typed work. Typed chat and uploads
remain available. Twelve seconds without detected speech pauses listening with Resume;
provider failures preserve the text response rather than inventing a call state. The
capability endpoint reports actual provider/language availability without keys. Audio is
not persisted by this application; configured providers process transmitted recordings.
The current TTS response speaks at most 2,500 characters; full answers remain in chat.

### Broad sample domain coverage and daily rollover

`expand_domain_demo.py --apply` enriches only the fixed `skyview_v3_demo` database. It preserves existing ownership, edited records, prices and all live data. The bounded catalogue supplies 150 named crop codes across 36 states/UTs, 1,080 explicitly named sample markets, two years of daily illustrative price history and a separate 365-day scenario horizon. Existing lookup/user crops remain. Current history is never populated with future dates. Stable series IDs and cross-release day guards prevent duplicating the entire history or scenario horizon when an operator reruns on another date. Missing monthly partitions are provisioned and committed before the large transaction; run the initial bulk import during a maintenance window.

`enam_market_reference.json` contains 158 market names from the official eNAM aspirational-district mapping, retrieved 2026-10-15. This is a partial name/district directory, not all Indian mandis. Directory references are a separate curated release, with no fabricated quotes, exact GPS, contacts or trading-status claims. Fictional quotations belong only to sample market IDs. AGMARKNET observations require the separately configured live connector and source mappings.

`domain_roll.statements(local_today)` is the ingestion-worker maintenance contract. It adds at most 30 missing history days per sample series and only missing future scenario tail points. It never invokes the bulk seed or overwrites existing observations. A 365-day scenario is an illustrative envelope, not a weather/price forecast, and does not establish future observed prices. New releases retain the synthetic origin. Historical API queries must continue to bound dates by India local today; scenario storage is separate and hidden from ordinary historical charts.

`refresh_reference_catalog.py --apply` imports official-source summaries for crop planning and disease differentiation. `refresh_disease_references.py --apply` adds 31 citable condition references linked only to reviewed TNAU documents. No fictitious expert diagnosis or chemical dosage is supplied. Synthetic field cases have no real image, no clinical label and explicitly unconfirmed assessments; they cannot train or validate disease detection. Do not fill lookup, approval, authentication, message or artifact tables with meaningless volume records.

Ten common vegetable/fruit crops additionally have three sample market series per state for useful comparisons (tomato, brinjal, okra, cabbage, cauliflower, chilli, peas, mango, guava and papaya). Per-series deterministic regional factors retain coherent historical seasonality while avoiding identical rates across all states. The guarded `regionalize_domain_demo.py --apply` migration upgrades only early `domain-v1` generated releases once, records an idempotent `domain-regional-v2:<dataset>` ingestion audit job, preserves immutable release lineage, and never touches original seed, live or user datasets. The expansion command includes this migration automatically; the background worker does not repeat bulk migrations.

### Saathi follow-ups and WhatsApp

`companion-runtime.sql` installs owner-scoped preferences and a narrow, leased worker
sweep. Follow-ups are **off by default**. The farmer chooses a name, cadence and
quiet hours in Saathi. Only due farm tasks and ageing open crop cases generate
in-app receipts; checks never invent a weather alert, run an endless model loop,
operate hardware or send an unsolicited external message. Receipts deduplicate
per source record and local day. The UI reports `waiting_for_worker` when the
worker heartbeat is missing, rather than claiming the companion is online.

For WhatsApp, keep `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and
`TWILIO_WHATSAPP_NUMBER` in `skyview/.env`. Set `SKYVIEW_PUBLIC_URL` to the **public
HTTPS backend/tunnel origin**, not the frontend Vite URL. Alternatively set the
exact `WHATSAPP_WEBHOOK_URL=https://your-host/webhook/whatsapp`. Configure the
Twilio sender/sandbox incoming-message webhook to that URL using POST; delivery
callbacks use `/webhook/whatsapp/status`. Restart the backend after changing env.
Join the Twilio sandbox first if applicable. In Saathi choose Connect WhatsApp,
then send its one-time `LINK ...` message from your own phone. Codes expire after
ten minutes. Reply `STOP`, or disconnect in the website, to unlink. A public URL
and a real signed inbound message are required before the site reports connected.
No live external messages were sent during automated verification.

The signed webhook validates the exact public URL, account and recipient. Incoming
message SIDs deduplicate a durable queue; processing happens after the quick empty
TwiML acknowledgement. It uses the same farm agent, owned memory, questions,
review/approval flow and document builders as the website. Questions accept
`1=answer; 2=answer`; writes require `APPROVE <current review code>`, or `CANCEL`.
No default demo phone or arbitrary query phone grants access to a farmer account.

Supported inbound files are JPEG/PNG/WebP, PDF, DOCX, XLSX, PPTX, CSV/text and short
audio notes. This service deliberately caps **each file at 5 MB**, one attachment
per message, and decoded voice notes at **one minute**. Office uploads are checked
for zip expansion; macros/code never execute. Generated PDF/Word/Excel/PowerPoint
files are delivered as media, with dated price charts rendered as PNG. Voice-note
answers retain the complete text; configured Sarvam TTS plus `ffmpeg` can also send
an MP3 spoken summary. Speech availability never implies that an audio reply was
successfully delivered. Downloads use owner-scoped signed URLs expiring after
fifteen minutes, with proper MIME headers and HEAD support.

Twilio delivery acceptance is separate from delivered/read receipts. An ambiguous
network send is recorded as unknown and is **not automatically replayed**, avoiding
duplicate messages. Re-linking cancels queued replies to the previous number.
Replies are confined to the farmer-initiated 24-hour session; proactive WhatsApp
campaigns/templates are not enabled by this implementation.

Provider references: [Twilio request validation](https://www.twilio.com/docs/usage/security),
[WhatsApp media formats and limits](https://www.twilio.com/docs/whatsapp/guidance-whatsapp-media-messages),
[messaging webhooks](https://www.twilio.com/docs/usage/webhooks/messaging-webhooks).

### Verification snapshot — 15 October 2026

The local sample database contains 4,591,980 historical price observations and
2,352,060 separate future scenario points, covering 152 crop records and all 36
states/UTs. Its 1,346 markets comprise 1,188 sample markets and 158 official eNAM
directory references. There are 1,600 plots, 1,600 soil samples, 2,800 field
observations, 2,401 disease cases, 31 reviewed disease references, 33 support
catalogue entries and 26 official knowledge documents. Counts are a deployment
snapshot, not an assertion of complete real-world coverage. Background rollover
will change price counts. Generated regional prices are not real mandi quotes.

Browser verification covered Tomato/Karnataka, Rice/Tamil Nadu, Cotton/Gujarat,
Onion/Maharashtra, Banana/Kerala, Arhar/Uttar Pradesh, Bhindi/Bihar and Wheat/Punjab,
with dated rates and market-specific history. Support searches covered insurance
in Maharashtra, solar in Rajasthan, credit in Punjab and soil in Tamil Nadu.
Desktop and 390px mobile layouts were inspected. Saathi opens without moving the
chat; Talk opens inline voice, and leaving the chat releases its microphone.

The backend suite passed 315 tests against the separate test database. WhatsApp
transport tests generate and retrieve real PDF, DOCX, XLSX, PPTX and CSV bytes via
signed media links while mocking every outbound provider call. A synthetic
speech sample verified configured STT/TTS; live field-noise conversation and real
WhatsApp delivery remain manual acceptance tests. The OGD credential is present,
but the public feed timed out during verification; source health and retries
record that outage. A public HTTPS webhook URL must be configured before linking
WhatsApp. No external message was sent during this release verification.
