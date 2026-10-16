# Kisan Mitra assistant

The assistant is a bounded task runner in `skyview/assistant/`, shared by the chat workspace, compact page helpers, voice turns and configured WhatsApp channel. It receives the farmer's original-language request, an owner-scoped session and relevant page context. It may read farm records and external evidence, ask one focused question at a time, create a file, or prepare a reviewed change. It cannot infer approval from a message, external document, retrieved page or remembered summary.

## Run lifecycle

1. `assistant_routes.py` authenticates the session and opens an event stream.
2. `engine.py` restores recent conversation, compacted memory, profile context and pending work. It enforces at most 12 model rounds and 24 tool calls per run.
3. `catalog.py` and `tools.py` expose typed, relevant tool schemas; `models.py` validates arguments before execution.
4. Independent reads can be scheduled together. Tool activity and bounded results become persisted events so the UI can show progress and recover after a refresh.
5. `ask_farmer` pauses with validated fields. Write tools pause with exact approval intent. The resumed run uses the saved call, not a new guess about what was approved.
6. Execution receipts and row versions protect writes from duplicate retries and stale edits. Declining or stopping leaves the proposed change unapplied.

The provider adapter in `provider.py` rotates configured Groq keys and can use a configured Gemini endpoint. Shared organization limits are not bypassed by cycling keys. The adapter streams public answer text and native function calls; private reasoning is not exposed as UI activity. If a provider or source is unavailable, the agent should report the gap rather than inventing an observation.

## Memory and evidence

`memory.py`, `memory_facts.py`, `v3_store.py` and the canonical SQL tables retain transcripts, compactions, owner-scoped facts and execution events. Compaction preserves farmer-stated facts, corrections, dates, unresolved goals, file identifiers and verified tool outcomes. Older content is evidence, not a command or approval. Source observation time, fetch time and forecast issuance remain distinct. Uploaded files and web pages are untrusted material. Generated files have owner-scoped metadata, checksums and bounded previews; downloads contain the complete artifact. Restored conversations keep each activity's bounded display result, including web-research sources and retrieval time, so web and mobile clients show the same evidence after a refresh or restart.

## Review and channels

Farm-changing task, record and group operations require an explicit review path. The exchange assistant prepares listing and terms drafts but publication, agreement and handover remain participant actions. Saathi prepares owner-scoped suggestions in background jobs; approving a proposal saves its plan. Voice uses transcription and synthesis around the same task path. WhatsApp requires linked identity, signature validation and configured Twilio credentials. No assistant tool silently publishes an offer, sends another farmer a message, controls a device or completes physical farm work.

## Skill catalog

Skills are versioned Markdown workflows in `skyview/assistant/skills/`. The current registry in `tools.py` is the runtime source of truth.

| Skill | Farmer-facing purpose |
| --- | --- |
| `web-research` | Research with sources: Look up current public farming guidance and schemes with Google Search, dated evidence and source links. |
| `farmer-exchange` | Farmer exchange: Compare consenting resource listings and review your exchange progress without sending messages or accepting terms for you. |
| `field-check` | Daily field check: Review station readings, freshness and practical next actions. |
| `weather-outlook` | Weather outlook: Read sourced grid forecasts and historical climate, distinct from field sensors. |
| `irrigation` | Water planning: Build a crop-aware irrigation checklist and saved tasks. |
| `crop-calendar` | Crop calendar: Turn crop stage and local dates into a practical work plan. |
| `market-prices` | Market comparison: Compare dated mandi records without invented prices. |
| `farm-budget` | Farm budget: Calculate costs from your quantities and prices. |
| `scheme-checklist` | Government benefits: Find schemes and prepare an application checklist. |
| `crop-scouting` | Crop scouting: Collect symptoms and prepare an inspection plan. |
| `daily-workspace` | Today on your farm: Prioritize dated tasks and open crop follow-ups, preserving evidence and uncertainty. |
| `sale-planning` | Take-home sale planning: Compare confirmed quantities, dated prices and transport costs. |
| `soil-report-review` | Soil report review: Read an owned soil report, preserve units and nutrient basis, and explain uncertain findings. |
| `insurance-pack` | Loss evidence pack: Prepare dated evidence documents without claiming an insurance submission. |
| `expert-handoff` | Expert handoff: Prepare a consented crop case summary and official expert referral links. |
| `crop-follow-up` | Crop follow-up: Keep an owned symptom timeline and inspection plan without inventing a diagnosis. |
| `shared-work` | Family and FPO planning: Plan shared tasks with explicit group roles and limited sharing. |
| `service-plan` | Service arrangements: Keep farmer-reported machinery, labour and transport plans and quotes. |
| `farm-records` | Farm records: Save expenses and manage farm tasks in this workspace. |
| `documents` | Documents and PDFs: Create readable Word and PDF reports with sources and caveats. |
| `spreadsheets` | Spreadsheets: Create Excel workbooks or CSV records with safe cells and totals. |
| `presentations` | Presentations: Create a slide deck for a cooperative or farm meeting. |

## Tool catalog

The `approval` column describes whether the tool itself pauses for a write review. Read results remain subject to source and ownership checks.

| Tool | Activity shown to the farmer | Approval |
| --- | --- | --- |
| `web_research` | Researching trusted sources | No |
| `assistant_capabilities` | Explaining what Mitra can help with | No |
| `seasonal_planning_context` | Preparing a seasonal crop plan | No |
| `exchange_listings` | Finding published farm resources | No |
| `exchange_matches` | Comparing resource matches | No |
| `exchange_journeys` | Checking your exchange progress | No |
| `field_context` | Reading your field records | No |
| `soil_report_options` | Checking report units | No |
| `save_soil_report` | Saving your checked soil report | Yes |
| `soil_reports` | Reading your saved soil reports | No |
| `expert_referrals` | Finding official expert help | No |
| `farm_today` | Checking today's priorities | No |
| `farm_ledger` | Reading your farm ledger | No |
| `record_ledger` | Saving your ledger entry | Yes |
| `crop_cases` | Reading your crop follow-ups | No |
| `create_crop_case` | Opening a crop follow-up | Yes |
| `record_crop_note` | Saving a crop observation | Yes |
| `farm_missions` | Reading your longer farm plans | No |
| `create_mission` | Preparing your longer farm plan | Yes |
| `service_notebook` | Reading your service arrangements | No |
| `record_service` | Saving your service arrangement | Yes |
| `shared_groups` | Reading your household or FPO groups | No |
| `shared_group_tasks` | Reading a shared group plan | No |
| `create_farm_group` | Creating your private group plan | Yes |
| `create_shared_task` | Saving a shared checklist task | Yes |
| `recall_memory` | Remembering earlier conversations | No |
| `load_skill` | Preparing a skill | No |
| `station_snapshot` | Checking your station | No |
| `weather_history` | Reviewing field history | No |
| `weather_forecast` | Reading your weather outlook | No |
| `weather_archive` | Reviewing regional weather history | No |
| `city_weather` | Checking another city's weather | No |
| `market_prices` | Checking mandi prices | No |
| `market_trend` | Charting market history | No |
| `knowledge_search` | Reading reviewed crop guidance | No |
| `price_scenarios` | Exploring price planning scenarios | No |
| `diagnose_crop` | Examining your crop photo | No |
| `scheme_search` | Finding government benefits | No |
| `ask_farmer` | A little more detail | No |
| `calculate_budget` | Calculating costs | No |
| `list_tasks` | Reading your tasks | No |
| `save_task` | Saving a farm task | Yes |
| `update_task` | Updating your farm plan | Yes |
| `delete_task` | Removing a farm task | Yes |
| `complete_task` | Completing a task | Yes |
| `record_expense` | Recording an expense | Yes |
| `list_expenses` | Reading farm expenses | No |
| `create_file` | Creating your file | No |
| `revise_file` | Revising your file | No |
| `net_sale` | Comparing your take-home sale value | No |
| `read_document_image` | Reading your receipt or soil report photo | No |
| `read_file` | Reading your file | No |

The API exposes the current catalog at `GET /api/assistant/catalog`. The table above is generated from `tools.py`; changing a skill or tool requires its implementation, schema, review behavior, tests and this catalog to remain aligned.
