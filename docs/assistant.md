# Farmer assistant

Kisan Mitra at `/workspace` executes bounded, validated tools and streams their actual progress. The same conversation can be opened in a movable window on `/station`. Text, activity history, pending forms, records and files survive page reloads. A new conversation archives the previous chat while retaining workspace records. The history menu restores earlier conversations, including their pending forms and completed tool steps.

The classic pages remain the defaults at `/advisor` and `/overview`. Their Open farm workspace button enters the reimagined assistant or station with a progressive View Transition and reduced-motion fallback. `/workspace` includes the saved-task calendar; switching between Assistant and Calendar preserves the draft chat. The transparent station node can be moved and resized across the viewport.

## Memory and charts

The durable SQLite transcript and archived conversations remain recoverable. A 12,000-token working-context budget uses the free MIT-licensed [tiktoken](https://github.com/openai/tiktoken) tokenizer, with a conservative offline estimate if its cache is unavailable. Older complete user turns are compacted into a persistent summary; recent complete tool exchanges remain intact. Oversized active-turn tool results are bounded in the model's copy. Summaries are evidence, never authorization. Summarization uses the configured provider and remains subject to its quota; no paid memory service is needed. The recall_memory tool retrieves scoped excerpts from archived chats. A failed summarizer preserves verbatim farmer-statement excerpts rather than inventing memory.

Market charts use dated records for one market, variety and unit, with at least two distinct dates. The current deployed database returned no wheat history for Maharashtra during live validation; the assistant reported unavailable instead of inventing a graph. Budget results render an inline cost chart from deterministic arithmetic.

Crop-photo question cards and paperclip uploads accept bounded, verified JPEG/PNG/WebP images. Crop Doctor uses the current [Groq vision model](https://console.groq.com/docs/vision), configurable through CROP_VISION_MODEL (default qwen/qwen3.8-27b), with the existing Gemini vision path as fallback. Provider failure never returns the former fixed diagnosis. A live synthetic drawing test returned insufficient visual evidence through the real pipeline; this verifies transport and uncertainty handling, not clinical accuracy on real crop diseases.

## Run locally

Use Python 3.11 or later and install `infra/requirements.txt`. The existing `skyview/.env` supplies Groq/Gemini credentials. Keep provider keys on the server.

```sh
uvicorn skyview.assistant.dev:app --host 127.0.0.1 --port 8001
```

For a local assistant with the frontend's deployed read-only farm data, set `ASSISTANT_DATA_URL` to that backend's origin. Without it, the production router reads the application's existing database query helpers. The development server intentionally does not run production database startup migrations.

Set `VITE_ASSISTANT_API_URL=http://127.0.0.1:8001` in ignored `frontend/.env.local`. Run the Vite UI normally. In production this variable falls back to `VITE_API_URL`. Deploy the new backend router before deploying a frontend that uses it.

## Workflows and tools

The eleven versioned Markdown workflows in `skyview/assistant/skills/` cover field checks, irrigation planning, crop calendars, market comparison, budgets, scheme checklists, crop scouting, farm records, documents, spreadsheets and presentations. These are portable application workflows, not access to a running Codex agent or its connectors.

Nineteen typed tools load workflows, read station/history/market/scheme data, calculate budgets, ask for details, list/save/complete tasks, list/save expenses, read workspace files and create files. The model chooses native function calls; the server validates every argument against Pydantic schemas. Relevant workflows are automatically loaded when needed. Independent reads run concurrently. No shell, arbitrary Python, SQL, outbound messaging or physical actuator tool is exposed.

Groq is the primary provider, with Gemini's OpenAI-compatible endpoint as fallback. `ASSISTANT_MODEL` defaults to `openai/gpt-oss-120b`; `GEMINI_MODEL` comes from the existing settings. Only public answer text is streamed; private model reasoning channels are discarded. Implementations follow [Groq local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling) and [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).

Each run has at most eight model rounds, sixteen tool calls and a 180-second timeout. Stop aborts the stream. A cross-worker SQLite lease prevents simultaneous runs in one workspace. Approved writes use execution IDs to avoid duplicate records after an interruption.

## Questions and reviewed actions

`ask_farmer` pauses the run with a form. The server retains the exact pending tool call and validates submitted field IDs and values before continuing. Task saves, expense saves and task completion require a review card. Cancelling executes nothing. A saved task is a workspace record; it does not schedule a notification or operate farm hardware.

## Files

The assistant creates DOCX, PDF, XLSX, CSV and PPTX downloads. Uploaded text/CSV/Excel/Word/PDF/PowerPoint files are read as bounded source data. Generated files can also be read for follow-up revisions. Office archive expansion, file sizes, sheets, rows, pages and extracted text are bounded. Partial extraction is explicitly flagged. Macros and formulas in uploads are never executed.

Excel files contain numeric values, deterministic total formulas with cached results, optional charts and notes. Strings are never interpreted as formulas or URLs. Complex-script PDF text is rejected with a Word-format alternative rather than producing broken glyphs. Scanned PDFs need OCR before upload.

Workspace data resides in `ASSISTANT_STORAGE_DIR` (default `.assistant-data/`, ignored by Git). Configure a persistent disk for production; ephemeral hosting storage will lose files and records on restart. Bearer capabilities isolate workspace data and downloads. The workspace capability is stored in this browser; it is not a replacement for a production account authorization/ownership system.

## Data integrity

The agent rejects upstream mock telemetry and reports missing data. It labels stale readings with their age, preserves source dates and does not generate fallback market prices. The 3D UI also rejects mock readings, interprets timezone-less backend timestamps as UTC, and labels its separate demonstration mode. Device wind units follow the WS01 hardware documentation.

## Validation

```sh
pytest tests/assistant --confcutdir=tests/assistant -q
ruff check skyview/assistant skyview/api/assistant_routes.py tests/assistant
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx vitest run
npm run build
```

The assistant tests use an isolated store and mocked provider calls; the directory boundary prevents legacy application fixtures from initializing the production app. Live provider tests separately verified budget calculation, clarification/resumption, reviewed task saving, Word/PDF/Excel/CSV/PowerPoint generation and authenticated downloads using synthetic test inputs. Document pages were rendered and visually inspected. Phone and desktop UI reviews cover the node, chat, question cards and hardware scene.

Final validation: 35 isolated assistant backend tests and all 11 frontend tests passed, alongside TypeScript and the production build. A live long-conversation compaction test retained its original transcript and correctly recovered the public synthetic codename from the first turn after compaction. Live Crop Doctor transport returned insufficient evidence for a synthetic drawing in 3.26 seconds; Word/PDF/Excel/CSV/PPTX authenticated downloads were verified. The legacy backend test fixtures are not used by the isolated assistant suite because configuration loads skyview/.env with override=True before application startup.


Calendar task details sit beside the month grid on desktop, with a compact contextual assistant. Direct edits use validated capability-scoped PATCH endpoints; deletion is recoverable, with Undo and a Deleted tasks panel. Agent updates and removals still require review. `/workspace?view=station` renders the station within the same persistent header/navigation shell as Assistant and Calendar; `/station` redirects there for existing links. Station and calendar suggestions are defined in `suggestions.ts`. The closed station launcher and open node both have transparent backgrounds.

Live calendar validation verified scoped task saving through the browser, an isolated agent update with review (3.61 seconds), and an isolated recoverable agent deletion with review (2.35 seconds). The compact helper replies within the calendar, supports hiding/showing its reply, preserves its draft when switching tabs, and carries validated interface/date context separately from the visible user message. The closed station launcher computed transparent RGBA (0,0,0,0). Desktop and phone reviews found no horizontal overflow.

## Shared data and content previews

Both the workspace station and agent station tool use `skyview/assistant/data_sources.py`. The browser calls `/api/assistant/station/{station_id}` on the same backend as chat; `ASSISTANT_DATA_URL` selects the server's read-only upstream, and `VITE_STATION_ID` is used for both. Missing readings remain missing, sample upstream packets are rejected and measurement timestamps determine freshness. Deploy this route with the updated frontend.

New artifacts include a bounded semantic content preview: up to three section excerpts and six table rows/eight columns. These appear inside chat and can be collapsed. The preview shows document contents, not a pixel-identical page render; downloads retain the complete formatting and data. PPTX tables are now paginated into actual slides. Files use direct scoped lookup, so older downloads no longer disappear after the display list reaches 100 files.

The default assistant storage path is anchored to the application repository (`.assistant-data`), preserving existing data even when the server starts from another working directory. `ASSISTANT_STORAGE_DIR` can select a persistent deployment volume. See `backend-review.md` for the feature audit and operational boundaries.

## Workspace pages

Two compact icon groups provide page navigation. The top-right group contains Assistant, Calendar, Farm station and the single Classic return control. A small floating group on the left contains Crop Doctor, Market prices, Farm support and Farm notebook. There is no full-height sidebar. Labels appear immediately on hover or keyboard focus.

Four newly designed workspace screens use the same validated tools as chat through the capability-authenticated `/api/assistant/sessions/{sid}/inspect/{tool}` endpoint. Only price lookup, market trend, scheme search, crop diagnosis and listing expenses are allowed; this endpoint cannot save tasks or costs. Successful page checks are recorded as scoped observations so the chatbot can discuss a check without unnecessarily repeating it. Data remains untrusted evidence and never approval.

Crop Doctor verifies an uploaded photo before invoking the real vision service and suppresses treatment cards when evidence is insufficient. Markets separates current-price lookup from dated historical charts. Farm support preserves catalog provenance and official links. Farm notebook shows saved files, previews, recent expense totals and open task counts. Each screen includes a small assistant with page-specific suggestions. Results and drafts remain mounted across page switches.

Uploads use a bounded JSON/base64 transport for browser/webview compatibility with the same 5 MB, image and document validation as the retained multipart endpoint. The upload has a 15-second browser timeout. There is no new external upload service.

The shared `MitraHelper` component supplies the same compact calendar-style assistant on the calendar, feature pages and station. Feature pages place it beside their content on desktop; small screens stack it. The station helper collapses to a transparent bordered control and preserves its draft while closed.
