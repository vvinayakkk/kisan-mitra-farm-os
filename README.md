# Kisan Mitra Farm OS

**One place to understand a farm, decide what to do next, and get the work done.**

Built by **init.io** for the **AI Builder Cup**. Kisan Mitra brings an agentic farm assistant, field records, crop care, weather, market intelligence, resource exchange and a visual farm station into one farmer-first workspace. The classic SkyView screens remain available; the new workspace makes the assistant a companion across every feature.

> This repository is the application and reproducible local data platform. Its seeded farmer and market histories are illustrative. Current weather is sourced from a regional model when available; it is not a measurement at a farmer's field. Real sensor readings, market observations and outbound WhatsApp or phone delivery depend on configured integrations and verified source data.

## The experience

| Place | What a farmer can do |
| --- | --- |
| **Mitra chat** | Ask in everyday language, including Hinglish; inspect tool progress, answer one question at a time, review a proposed write, and keep the conversation and generated files. |
| **Saathi** | See context-aware suggested work, inspect a compact preview, edit or approve a plan, and find the saved result in the notebook. |
| **Crop doctor** | Share a crop photo, get a cautious assessment, and capture observations and follow-ups. |
| **Markets** | Compare mandi quotes by crop and region and inspect dated price series with variety and unit context. |
| **Farm station** | Explore a Three.js station and sensor scene with live-status context, readings and a movable assistant. |
| **Weather** | View current regional conditions, hourly and ten-day outlooks, rainfall, wind and air quality in a time-aware scene. |
| **Exchange** | Discover resources, compare matches, discuss an exchange privately and follow the handover trail. |
| **Farm notebook & calendar** | Keep fields, crop seasons, work, expenses, reports and plans in a notebook-style workspace and a dated task view. |
| **Farm support** | Explore cited programme information and assemble a checklist for an application or visit. |


The assistant can use typed farm tools to read relevant records, compare prices, research a question, prepare plans and create DOCX, PDF, XLSX, CSV and PPTX files with previews in chat. Actions that change farm records pause for review. Approval is bound to the proposed action and replay-safe execution; a draft alone does not publish an exchange, send a message, claim a subsidy or operate hardware.

Voice input and read-aloud are available across the workspace when speech providers and browser microphone permissions are configured. The live conversation flow records a turn, transcribes it, runs the same agent tools, then speaks the reply. It is turn-based speech rather than a full-duplex call. Language preference follows the farmer across chat and workspace; translation and speech quality depend on their configured providers.

## How it fits together

```text
React + TypeScript + Vite
    ├── classic SkyView screens
    └── Kisan Mitra workspace (chat, Saathi, notebook, calendar,
        crop doctor, markets, exchange, weather, Three.js station)
                         │
                         ▼
FastAPI: authenticated routes, assistant runs, reviewed actions,
        artifact previews, media and voice adapters
                         │
                         ▼
PostgreSQL v3: farmer-scoped records, conversations, tasks,
               market series, source provenance and worker state
                         │
                         ▼
Bounded background workers and optional external data/services
```

The backend keeps observed data, modeled weather and future planning scenarios separate. Market charts require dated series and preserve the source, market, variety and unit. Assistant tool calls use validated arguments; private farmer records are owner-scoped. Background jobs use leases, retries and freshness metadata. Files live in private local artifact storage, with metadata and ownership in the database.

The local data foundation includes 400 fictional farmer profiles across India's states and union territories, crop and disease reference material, named market references, expanded crop/market coverage, synthetic price history and separate future planning rows. It supports realistic interaction and testing; it does **not** turn illustrative prices or cases into reported mandi trades or confirmed diagnoses. The source catalog documents which public feeds are integrated, researched or still awaiting access.

## Run locally

Prerequisites: Python 3.12, Node.js, npm, Docker and PostgreSQL 16 through the project provisioner. The local provisioner creates an isolated v3 database and ignored runtime credentials. Provider keys are optional for exploring the UI but required for their corresponding AI, voice, image or messaging flows. Keep keys in ignored local environment files; never commit them.

```bash
python3 -m venv .venv
.venv/bin/pip install -r infra/requirements.txt
cd frontend && npm ci && cd ..

# Fresh local data installation only; choose a writable location for generated seed files.
.venv/bin/python data_platform/v3/seed_demo.py --output /absolute/path/to/seed
.venv/bin/python data_platform/v3/provision.py --seed-dir /absolute/path/to/seed

# Start the retained database, API and frontend.
.venv/bin/python data_platform/v3/local.py
```

Open **http://127.0.0.1:5173**. The unified API listens on **http://127.0.0.1:8001**. In an ignored `frontend/.env.local`, point `VITE_API_URL` and `VITE_ASSISTANT_API_URL` at that API when your local setup needs explicit origins. `data_platform/v3/local.py` reuses an existing installation and does not reseed it. For the provisioner's exact contracts and operational checks, see [local operation](data_platform/v3/OPERATIONS.md).

Useful local checks:

```bash
.venv/bin/python data_platform/v3/check_local.py
.venv/bin/python data_platform/v3/test_backend.py
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx vitest run
npm run build
```

The backend test wrapper expects a separately prepared test database for database-backed tests; [local operation](data_platform/v3/OPERATIONS.md) describes that preparation. Never point it at a populated farmer database.

