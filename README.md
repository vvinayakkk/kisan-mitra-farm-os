![Kisan Mitra — an agentic Farm OS](docs/media/readme-cover.svg)

# 🌾 Kisan Mitra (Mitra & Saathi) — Multilingual, Multi-Agentic AI Farm OS

### **An autonomous, multi-agentic AI orchestrator with 22 specialized skills, 52 typed tool contracts, neural TTS/STT voice pipelines, and background preparation workers that turn a farmer's question into finished farm work**

*Speak or ask in 22+ Indian languages & Hinglish · Multi-agent orchestration & sub-agent delegation · Real-time tool calling & planning · Token-budgeted agentic memory · Reviewable human-in-the-loop execution*

---

[![AI Builder Cup](https://img.shields.io/badge/AI%20Builder%20Cup-init.io-355B3C?style=for-the-badge)](https://github.com/vvinayakkk/kisan-mitra-farm-os)
[![Multi-Agent Orchestrator](https://img.shields.io/badge/Agentic%20AI-Orchestrator%20%2B%20Sub--Agents-2E6B47?style=for-the-badge)](#%EF%B8%8F-agentic-system-design--multi-agent-orchestration)
[![Skills & Tools](https://img.shields.io/badge/22%20Skills-52%20Typed%20Tools-3E7B52?style=for-the-badge)](#the-22-farm-skills)
[![Multilingual Voice](https://img.shields.io/badge/Multilingual%20STT%2FTTS-22%2B%20Indian%20Languages-48885C?style=for-the-badge)](#%EF%B8%8F-multilingual-voice-pipeline-stt--tts--live-turn-taking)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Live%20deployment-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://growwithmitra.web.app/workspace)
[![Firebase](https://img.shields.io/badge/Firebase-Hosting%20%2B%20Auth-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://growwithmitra.web.app/workspace)
[![Web](https://img.shields.io/badge/Web-Farm%20OS%20%2B%20Classic-50784C?style=for-the-badge&logo=react&logoColor=white)](frontend/)
[![Mobile](https://img.shields.io/badge/Mobile-Flutter-638C56?style=for-the-badge&logo=flutter&logoColor=white)](mobile/)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Connected%20channel-77A966?style=for-the-badge&logo=whatsapp&logoColor=white)](docs/api/websocket-and-webhooks.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-A5C48A?style=for-the-badge)](LICENSE)

**Kisan Mitra**, built by **init.io** for Google's **AI Builder Cup**, is a **fully agentic, multilingual AI Farm Operating System** powered by a central **Agentic Orchestrator (`Mitra`)**, proactive **Background Companion Sub-Agents (`Saathi`)**, and domain-specialized sub-agents across agronomy, meteorology, mandi intelligence, crop diagnostics, and resource routing. Equipped with **22 versioned domain skills**, **52 schema-validated tool contracts**, **token-budgeted agentic memory management**, **multilingual neural STT/TTS voice pipelines**, and **lease-coordinated background workers**, Kisan Mitra brings farm records, crop care, weather, mandi markets, seasonal planning, document synthesis, and farmer exchange into one unified agentic runtime. **Firebase and Google Cloud provide its live web delivery, identity, API runtime, scheduled work, and message queue.**

**Explore the live deployment:** [Open Farm OS](https://growwithmitra.web.app/workspace) · [Open Classic SkyView](https://growwithmitra.web.app/overview) · [API health](https://kisan-mitra-api-344920654513.asia-south1.run.app/health) · [Android release](https://github.com/vvinayakkk/kisan-mitra-farm-os/releases/latest) · [Administration](https://growwithmitra.web.app/control)

> **A question is the beginning of an autonomous multi-agent workflow, not the end of a chat.** Ask or speak in your own language; Mitra orchestrates specialist sub-agents, loads domain skills dynamically, executes parallel tool calls against live farm & public data, manages multi-turn working memory, synthesizes documents/charts, and stages version-checked farm writes for one-tap human-in-the-loop approval.

---

<a id="our-hardware-in-action"></a>

## 🛰️ Our hardware in action

Frames from our recorded hardware walkthrough show the field station, ESP32 sensor assembly and Raspberry Pi / FPGA setup. Each image combines two views; click to inspect the full-resolution image. Timestamps refer to the original recording.

[![Solar-powered field station: solar panel and power module alongside the installed wind sensors](docs/media/hardware/01-field-station.jpg)](docs/media/hardware/01-field-station.jpg)

[![ESP32 sensor assembly: controller wiring overview and a close-up of the sensor board](docs/media/hardware/02-esp32-sensors.jpg)](docs/media/hardware/02-esp32-sensors.jpg)

[![Recorded wind-speed and rain-gauge demonstrations with the accompanying dashboard readings](docs/media/hardware/03-live-demonstration.jpg)](docs/media/hardware/03-live-demonstration.jpg)

[![Main computing hardware: Raspberry Pi and FPGA development board close-ups](docs/media/hardware/04-edge-hardware.jpg)](docs/media/hardware/04-edge-hardware.jpg)

The field demonstration pairs physical wind and rainfall tests with the dashboard shown in the video. The separate compute-board views show the Raspberry Pi and FPGA hardware used in the walkthrough; see [how the station connects to Mitra](#hardware-integration).

---

## 🌾 Four ways to use Kisan Mitra

| **Website · the full farm workspace** | **Flutter app · help in the field** |
| :--- | :--- |
| [![Illustration of the Kisan Mitra web workspace and a prepared farm checklist](docs/media/channels/web.svg)](https://growwithmitra.web.app/workspace) | [![Illustration of the Kisan Mitra Flutter app with voice and farm actions](docs/media/channels/app.svg)](mobile/) |
| Firebase Hosting delivers Farm OS and Classic; Cloud Run connects both to Mitra. | Firebase phone sign-in connects the Flutter companion to the same farmer account and API. |

| **Voice & call · speak naturally** | **WhatsApp · send a question or crop photo** |
| :--- | :--- |
| [![Illustration of Kisan Mitra browser live voice and the website call control](docs/media/channels/voice.svg)](https://growwithmitra.web.app/workspace) | [![Illustration of a WhatsApp crop question entering the signed Kisan Mitra webhook](docs/media/channels/whatsapp.svg)](docs/api/websocket-and-webhooks.md) |
| Browser live voice reaches Mitra on Cloud Run; the separate call control opens the configured support line. | Twilio receives the message; a signed Cloud Run webhook and Cloud Tasks process the inbound request. |

*The four channel cards illustrate product flows; explore captured screens in the [Farm OS gallery](#-farm-os-design-system) and [Flutter app gallery](#flutter-app-screenshots).*

---

## ⚡ Agentic AI Platform at a Glance

| Capability | What is in the repository | Why it matters |
| :--- | :--- | :--- |
| **Multi-Agent Orchestrator & Sub-Agents** | Central `Mitra` runtime ([`engine.py`](skyview/assistant/engine.py)), proactive `Saathi` planning sub-agent ([`companion_plans.py`](skyview/assistant/companion_plans.py)), and supervisor/specialist agents ([`skyview/agents/`](skyview/agents/)) | Coordinates multi-step reasoning, fast-path execution, and background plan synthesis across domains |
| **22 Versioned Domain Skills** | On-demand procedural workflows in [the assistant skill catalog](skyview/assistant/skills/) loaded via `load_skill` | Gives the agent deep domain planning playbooks without bloating base prompt context |
| **52 Typed Tool Contracts** | Schema-validated read, calculation, research, artifact, and guarded-write tools in [`tools.py`](skyview/assistant/tools.py) | Deterministic tool calling with strict argument validation, bounded outputs, and execution receipts |
| **Agentic Memory Management** | Token-budgeted working memory (`12k` context budget, `1.8k` compaction summary) in [`memory.py`](skyview/assistant/memory.py) + durable fact store ([`memory_facts.py`](skyview/assistant/memory_facts.py)) | Preserves long-horizon farmer facts, attributions, and tool outcomes across compactions without losing raw transcripts |
| **Multilingual Neural STT / TTS & Voice** | 22+ Indian language codes, Sarvam AI (`saaras:v4` / `bulbul:v2`) + Groq Whisper (`whisper-large-v3-turbo`) fallback in [`v3_voice_routes.py`](skyview/api/v3_voice_routes.py) | Farmers speak naturally in Hindi, Marathi, Tamil, Telugu, Hinglish, and more with automatic turn-taking and spoken replies |
| **Autonomous Background Workers** | PostgreSQL advisory-leased workers ([`worker.py`](skyview/data/v3/worker.py)), Cloud Scheduler & Cloud Tasks queues ([`whatsapp_tasks.py`](skyview/assistant/whatsapp_tasks.py)) | Continuously ingests weather/mandi feeds, pre-computes `Saathi` proposals, and processes async WhatsApp media/voice turns |
| **Multi-Model Consensus & Provider Pool** | Multi-key LLM router ([`provider.py`](skyview/assistant/provider.py), [`llm_pool.py`](skyview/utils/llm_pool.py)) with automatic health cooldowns and fallback | High resilience across tool-calling turns, vision diagnostics, and multilingual synthesis |
| **Four Connected Surfaces** | Website (`Farm OS` + `Classic`), Flutter Android app, signed WhatsApp webhook channel, and voice/call controls | One owner-scoped agentic brain accessible from any device or field condition |

The counts describe the current code and catalog. They are not latency or production-scale claims.

---

## 🗺️ Table of Contents

- [Our hardware in action](#our-hardware-in-action)
- [Four ways to use Kisan Mitra](#-four-ways-to-use-kisan-mitra)
- [Agentic AI Platform at a Glance](#-agentic-ai-platform-at-a-glance)
- [Agentic System Design & Multi-Agent Orchestration](#-agentic-system-design--multi-agent-orchestration)
- [Meet Saathi — Your Always-Active 24/7 Background Companion](#-meet-saathi--your-always-active-247-background-companion)
- [Complex Multi-Agent Workflows & 52+ Real Farm Tasks](#-complex-multi-agent-workflows--52-real-farm-tasks)
- [Multilingual Voice Pipeline (STT · TTS · Live Turn-Taking)](#-multilingual-voice-pipeline-stt--tts--live-turn-taking)
- [Overview & Vision](#-overview--vision)
- [System Architecture](#-system-architecture)
- [UltraCache & Background Data](#-ultracache--background-data)
- [Backend Execution & Data Integrity](#-backend-execution--data-integrity)
- [Farm OS Design System](#-farm-os-design-system)
- [Flutter app screenshots](#flutter-app-screenshots)
- [Onboarding on app and web](#onboarding-on-app-and-web)
- [Guided tours on app and web](#guided-tours-on-app-and-web)
- [Administration workspace](#administration-workspace)
- [Verification & Quality](#-verification--quality)
- [Autonomous Agentic Workflows](#-autonomous-agentic-workflows)
- [Core Functional Engines](#-core-functional-engines)
- [Farm station & hardware integration](#hardware-integration)
- [Monorepo Directory Structure](#-monorepo-directory-structure)
- [Quick Start & Development](#-quick-start--development)
- [OpenAPI REST Endpoints](#-openapi-rest-endpoints)
- [Live Google Cloud Deployment](#-live-google-cloud-deployment)
- [License & Open Source Dedication](#-license--open-source-dedication)

---

## 🧠 Agentic System Design & Multi-Agent Orchestration

Kisan Mitra is architected from the ground up as an **agentic operating system** rather than a single-prompt wrapper. Every interaction flows through a layered orchestration pipeline that combines **deterministic fast actions**, **multi-round tool-calling loops**, **specialized domain sub-agents**, **dynamic skill injection**, **token-budgeted working memory**, and **background companion preparation**.

```mermaid
flowchart TB
    subgraph Channels["Multimodal & Multilingual Ingress"]
        WebUI["Web Farm OS & Classic"]
        MobileApp["Flutter Field Companion"]
        VoiceStream["Neural STT / TTS & Live Voice Turns"]
        WAWebhook["Signed WhatsApp Webhook & Media"]
    end

    subgraph Orchestrator["Central Agentic Runtime (skyview/assistant/)"]
        FastPath["Deterministic Fast-Action Router (fast_actions.py)"]
        ExecEngine["Bounded ReAct & Plan-Execute Loop (engine.py · 12 rounds / 24 tool calls)"]
        Contract["Execution Contract & Approval Gate (execution_contract.py)"]
        SkillLoader["Dynamic Skill Loader (22 Markdown Playbooks)"]
        MemoryMgr["Token-Budgeted Working Memory & Compaction (memory.py + memory_facts.py)"]
    end

    subgraph SubAgents["Specialized Sub-Agents & Background Planners"]
        Saathi["Saathi Proactive Planner Sub-Agent (companion_plans.py)"]
        VisionAgent["Crop Doctor & Document Vision Sub-Agent (document_vision.py + disease_service.py)"]
        ResearchAgent["Grounded Web & Scheme Research Sub-Agent (research.py)"]
        Supervisor["Classic Supervisor & Domain Agents (Weather · Mandi · Alert · Agronomy · FPGA)"]
        ArtifactGen["Artifact Synthesis Sub-Agent (DOCX · PDF · XLSX · CSV · PPTX)"]
    end

    subgraph ToolPlane["52 Schema-Validated Tool Contracts (tools.py)"]
        ReadTools["Farm, Plot, Ledger, Task & Station Readers"]
        MarketWeather["Mandi Price Series & Weather Outlook Tools (weather_tools.py)"]
        CalcTools["Irrigation, Budget & Sale Take-Home Calculators (planning_tools.py)"]
        WriteTools["Guarded Mutation Tools (Version-Checked + Replay-Safe)"]
    end

    subgraph Workers["Autonomous Background Workers & Persistence"]
        LeasedWorker["PostgreSQL Advisory-Leased Worker (worker.py)"]
        CloudTasks["Cloud Tasks Async WhatsApp & Media Queue"]
        NeonDB[("Neon PostgreSQL (RLS + Canonical v3 Store)")]
    end

    Channels --> FastPath
    FastPath -->|"Explicit command"| ToolPlane
    FastPath -->|"Complex / multi-step goal"| ExecEngine
    ExecEngine <--> MemoryMgr
    ExecEngine --> SkillLoader
    ExecEngine --> Contract
    ExecEngine --> SubAgents
    ExecEngine --> ToolPlane
    SubAgents --> ToolPlane
    ToolPlane <--> NeonDB
    LeasedWorker <--> NeonDB
    LeasedWorker --> Saathi
    CloudTasks --> ExecEngine
```

### 1. Multi-Agent Hierarchy & Specialist Sub-Agents
- **Primary Orchestrator (`Mitra` — [`skyview/assistant/engine.py`](skyview/assistant/engine.py)):** Manages the stateful execution loop (`MAX_ROUNDS = 12`, `MAX_CALLS = 24`), coordinates parallel tool execution, enforces output token bounding (`bounded_result`), streams real-time progress heartbeats ([`progress.py`](skyview/assistant/progress.py)), and arbitrates between autonomous reads and human-gated writes.
- **Deterministic Fast-Action Sub-Router ([`skyview/assistant/fast_actions.py`](skyview/assistant/fast_actions.py)):** Intercepts unambiguous operational commands (such as adding dated tasks) for low-latency deterministic preparation while routing ambiguous, analytical, or multi-step goals to the full reasoning engine.
- **Proactive Companion Sub-Agent (`Saathi` — [`skyview/assistant/companion_plans.py`](skyview/assistant/companion_plans.py)):** Operates across six farm domains (`today`, `markets`, `schemes`, `records`, `crops`, `exchange`). It snapshots the owner's live crops, open tasks, active disease cases, 30-day ledger totals, and exchange listings, combines them with dated mandi/weather evidence, and drafts multilingual action proposals in the background.
- **Multimodal Vision & Diagnostic Sub-Agents ([`document_vision.py`](skyview/assistant/document_vision.py), [`disease_service.py`](skyview/agents/disease_service.py)):** Inspects uploaded crop leaf photographs, soil lab reports, bills, and receipts to extract structured agronomic observations, differential diagnoses, and follow-up care plans.
- **Grounded Web & Policy Research Sub-Agent ([`skyview/assistant/research.py`](skyview/assistant/research.py)):** Executes source-attributed public research for government schemes, university advisories, and market arrival guidance, preserving URLs and citations across session restores.
- **Artifact Generation Sub-Agent ([`skyview/assistant/artifacts.py`](skyview/assistant/artifacts.py)):** Transforms structured tool outputs and plans into downloadable `.docx`, `.pdf`, `.xlsx`, `.csv`, and `.pptx` files stored in private owner-scoped object storage.
- **Supervisor & Telemetry Specialist Agents ([`skyview/agents/supervisor.py`](skyview/agents/supervisor.py)):** Coordinates domain specialists (`weather_agent`, `alert_agent`, `farm_agent`, `trend_agent`, `sensor_agent`, `mandi_agent`, `scheme_agent`, and `fpga_agent`) for telemetry fusion and classic advisor workflows.

### 2. Dynamic Skill Injection & 52 Typed Tool Contracts
Instead of stuffing every domain rule into a monolithic system prompt, Mitra uses **progressive skill disclosure** ([`skyview/assistant/skills/`](skyview/assistant/skills/)):
- **Preloaded & On-Demand Skills:** Recognized workflows preload their matching skill markdown playbook automatically, or the orchestrator calls `load_skill(name)` mid-run to pull in specialized instructions (e.g., `irrigation`, `sale-planning`, `insurance-pack`, `soil-report-review`, `expert-handoff`).
- **52 Schema-Validated Tools ([`skyview/assistant/tools.py`](skyview/assistant/tools.py)):** Every tool is backed by strict JSON Schema validation and an owner-scoped `Executor`. Tool results are automatically compacted (`bounded_result`) so large mandi series or weather charts render in full on the UI while feeding concise statistical summaries and top-N rows to the LLM context window.
- **Execution Contracts & Pause/Resume State Machine ([`skyview/assistant/execution_contract.py`](skyview/assistant/execution_contract.py)):** If a tool requires missing parameters, Mitra emits a structured `ask_user` turn and pauses the run. If a tool mutates farm state (creating tasks, logging ledger expenses, updating crop cases, publishing exchange offers), Mitra stages a cryptographic approval payload with version checks and resumes execution only after explicit farmer confirmation.

### 3. Token-Budgeted Agentic Memory Management
Long-running farm relationships require memory that neither overflows the context window nor hallucinates past instructions ([`skyview/assistant/memory.py`](skyview/assistant/memory.py) & [`memory_facts.py`](skyview/assistant/memory_facts.py)):
- **Token-Budgeted Sliding Window (`CONTEXT_BUDGET = 12,000` tokens):** Before every reasoning turn, `memory.context()` measures the active transcript using `tiktoken` (`cl100k_base`).
- **Turn-Boundary Compaction (`SUMMARY_LIMIT = 1,800` tokens):** When the active conversation exceeds budget, the memory manager finds a clean user-turn boundary (never splitting tool-call/tool-result pairs) and compacts older turns into an attributed evidence summary while keeping the full raw transcript archived in PostgreSQL (`sv3.assistant_sessions`).
- **Prompt-Injection & Authority Isolation:** Compacted memory summaries are explicitly marked as untrusted historical evidence—quoted text in summaries or external documents can never self-authorize a tool write or override system safety boundaries.
- **Redundant Skill Pruning:** Older `load_skill` payloads are automatically pruned from the active token window when the conversation grows, preserving token budget for fresh tool observations.

### 4. Lease-Coordinated Background Workers & Async Queues
- **PostgreSQL Advisory-Leased Worker ([`skyview/data/v3/worker.py`](skyview/data/v3/worker.py)):** Coordinates recurring background jobs across stateless Cloud Run instances without duplicate execution—refreshing weather forecasts, syncing mandi price arrivals, tracking source health, and warming `Saathi` companion plans.
- **Asynchronous WhatsApp & Media Worker ([`skyview/assistant/whatsapp_tasks.py`](skyview/assistant/whatsapp_tasks.py)):** Signed Twilio webhooks enqueue inbound farmer voice notes, crop photos, and messages into **Google Cloud Tasks**, allowing a background worker to transcribe audio, run the multi-step Mitra orchestrator, and deliver the response reliably.

---

## 🌱 Meet Saathi — Your Always-Active 24/7 Background Companion

<table>
  <tr>
    <td width="150" align="center">
      <img src="docs/media/saathi-mascot.svg" width="125" alt="Saathi — Cute sprout-crowned 24/7 farm companion mascot" />
      <br />
      <sub><b>Saathi · Watching 24/7</b></sub>
    </td>
    <td>
      <b>While Mitra answers when you ask, <i>Saathi</i> works quietly in the background so your next farm move is already prepared before you even type a prompt.</b><br /><br />
      Represented across the web workspace and Flutter app by its signature <b>sprout-crowned pebble mascot</b> (<a href="frontend/src/components/assistant/CompanionPanel.tsx"><code>CompanionAvatar</code></a>), <b>Saathi</b> (<a href="skyview/assistant/companion_plans.py"><code>skyview/assistant/companion_plans.py</code></a>) is an autonomous background planning sub-agent that continuously watches six core farm areas—<code>today</code>, <code>markets</code>, <code>schemes</code>, <code>records</code>, <code>crops</code>, and <code>exchange</code>—and gets actionable checklists, mandi comparisons, and scheme drafts ready in the farmer's preferred language.
    </td>
  </tr>
</table>

### How Saathi Works 24/7 in the Background
- **Autonomous Farm Snapshot & Signal Detection:** On scheduled check-in intervals (configurable every `1h`, `6h`, `12h`, `24h`, or `weekly`, respecting the farmer's `quiet_start`–`quiet_end` sleeping hours in `Asia/Kolkata`), Saathi snapshots the farmer's live plots, growing crop cycles, open/overdue calendar tasks, unresolved Crop Doctor disease cases, 30-day ledger balances, and published exchange listings.
- **Durable Leased Background Jobs (`/api/companion/prepare`):** When a farmer opens Markets, Schemes, Crops, Notebook, or Exchange—or when the background worker runs—Saathi claims a durable database lease (`sv3.companion_preparation_jobs`), pulls dated mandi arrivals or grounded Google Search evidence (`research.py`), and synthesizes a step-by-step proposal with linked evidence cards.
- **Native Multilingual Translation:** Every background plan drafted by Saathi is automatically translated into the farmer's chosen Indian language (`hi-IN`, `mr-IN`, `ta-IN`, `te-IN`, `kn-IN`, `pa-IN`, etc.) while keeping every number, date, unit (`INR/quintal`), and official source link intact.
- **Zero Unapproved Mutations (1-Tap Review, Voice Edit, or Dismiss):** Saathi *prepares* the work in the background (`PreparedBySaathi.tsx` & `CompanionPanel.tsx`) so it is waiting when the farmer arrives. The farmer can inspect the evidence, **speak or type edits** to the steps, and click **Approve plan** to convert the draft into a persistent multi-step farm mission (`sv3.farm_missions`) with version-checked safety (`row_version`).

---

## 🚀 Complex Multi-Agent Workflows & 52+ Real Farm Tasks

Kisan Mitra handles everything from **single-sentence deterministic fast actions** to **10-step cross-domain agentic workflows** that chain weather, sensors, vision, mandi economics, web research, and document generation in a single turn.

### 6 Deep End-to-End Complex Workflow Examples

#### Workflow 1 · Pre-Monsoon / Heavy Rain Risk Audit & Calendar Rescheduling
> **Farmer says (Hindi / English / Voice):** *"Kal aur parso barish ka kya haal hai? Mere is hafte ke kaam check karo, spray ya khad dalne ka kaam khatre mein ho toh aage badha do aur checklist bana do."*
> *(“What does the rain look like over the next few days? Audit my tasks this week, move any risky spraying or fertilizer work, and build a checklist.”)*
1. **Skill & Context Load:** Orchestrator loads `weather-outlook`, `daily-workspace`, and `crop-calendar` skills (`load_skill`).
2. **Parallel Evidence Gathering:** Calls `field_context` (plots & crop stages), `list_tasks` (this week's scheduled tasks), `station_snapshot` (current soil moisture & wind), and `weather_forecast` (16-day grid forecast with precipitation windows).
3. **Cross-Domain Reasoning:** Identifies that a scheduled pesticide spray and urea top-dressing collide with a high-rainfall window and high wind speed.
4. **Guarded Action Staging:** Returns a prioritized rain-readiness checklist, renders an inline precipitation chart, and stages `update_task` / `save_task` approval cards to shift spraying to a dry window and add a field-drainage inspection task.

#### Workflow 2 · Multimodal Crop Doctor Diagnosis $\rightarrow$ Follow-Up Case $\rightarrow$ Official KVK Expert Handoff PDF
> **Farmer uploads a leaf photo + says:** *"Patti pe peele dhabbe aa rahe hain, dekho kya bimari hai, case save karo aur KVK expert ko dikhane ke liye PDF report bana do."*
1. **Vision Sub-Agent Execution:** Calls `diagnose_crop` on the uploaded leaf image to extract visual symptom patterns, differential causes, confidence/uncertainty, and safe field inspection checks.
2. **Historical Case Continuity:** Calls `crop_cases` to check if this plot already has an open symptom timeline, then stages `create_crop_case` / `record_crop_note` with the dated observation.
3. **Official Referral Lookup:** Loads `expert-handoff` skill and calls `expert_referrals` for official ICAR / KVK and crop-insurance portal references.
4. **Artifact Synthesis:** Calls `create_file(format="pdf")` to generate a downloadable **Crop Case Handoff Report PDF** containing the symptom timeline, plot context, uncertainty caveats, and inspection checklist.

#### Workflow 3 · Mandi Arbitrage & Net Take-Home Realization after Transport & Handling
> **Farmer says:** *"Mere paas 45 quintal gehu (wheat) hai. Aas-paas ki mandiyon ka bhav compare karo, bhada aur hammali kaat ke batao kahan bechna faydemand rahega, aur Excel sheet bana do."*
1. **Market & Trend Retrieval:** Loads `market-prices` and `sale-planning` skills; calls `market_prices` and `market_trend` to fetch dated `data.gov.in` mandi arrivals and modal prices across nearby markets.
2. **Missing Cost Clarification (`ask_farmer`):** If transport or loading rates aren't in memory (`recall_memory`), pauses with a focused `ask_farmer` card to confirm transport distance/cost per quintal.
3. **Deterministic Realization Math:** Calls `net_sale` and `calculate_budget` across candidate mandis to compute exact Gross INR vs. Net Take-Home INR after transport, bagging, and market fees.
4. **Workbook Generation:** Calls `create_file(format="xlsx")` to produce a side-by-side **Mandi Net Realization Excel Workbook** + inline price trend chart.

#### Workflow 4 · Soil Lab Report OCR $\rightarrow$ Nutrient Basis Verification $\rightarrow$ Deficit Irrigation Plan
> **Farmer uploads a photo of a printed Soil Health Card / lab report:** *"Yeh meri mitti ki जांच report hai, isko padh ke save karo aur agle 7 din ka sinchai (irrigation) plan batao."*
1. **Document Vision OCR:** Calls `read_document_image` to extract literal visible text (`pH`, `EC`, `Organic Carbon`, `N`, `P`, `K`, micronutrients) and calls `soil_report_options` to verify supported units and nutrient basis (`P` vs `P2O5`, `K` vs `K2O`—never converting silently).
2. **Farmer Verification Gate:** Stages `save_soil_report` so the farmer confirms the exact extracted numbers, sample date, and depth before saving to `sv3.soil_reports`.
3. **Sensor + Forecast Fusion:** Calls `station_snapshot` (live soil-moisture probe reading) and `weather_forecast` (evapotranspiration & rain outlook) to build a 7-day crop-stage irrigation schedule.

#### Workflow 5 · Government Scheme Discovery $\rightarrow$ Grounded Web Verification $\rightarrow$ Application Pack
> **Farmer says:** *"Drip irrigation aur solar pump pe kaunsi सरकारी सब्सिडी mil rahi hai? Eligibility check karo aur zaroori kagazat ki Word file bana do."*
1. **Catalog + Live Google Search Grounding:** Loads `scheme-checklist` and `web-research` skills; calls `scheme_search` (internal verified catalog) and `web_research` (live Google Search grounding with cited official `.gov.in` URLs and `retrieved_at` timestamps).
2. **Farm Profile Matching:** Cross-checks the farmer's owned land size, state/district, and crop cycles via `field_context`.
3. **Document Generation:** Calls `create_file(format="docx")` to create a printable **Scheme Eligibility & Document Checklist (`.docx`)** and stages a calendar reminder task (`save_task`) for document submission.

#### Workflow 6 · FPO / Cooperative Resource Exchange & Shared Group Mission Planning
> **Farmer says:** *"Mujhe is hafte rotavator chahiye, exchange mein dekho aas-paas kisike paas hai, aur humare FPO group ke liye kutaai-buwai ka shared plan aur PPT presentation bana do."*
1. **Exchange Matching:** Loads `farmer-exchange` and `shared-work` skills; calls `exchange_listings` and `exchange_matches` to find district-level consenting rotavator/tractor listings and calls `exchange_journeys` to check active negotiations.
2. **Cooperative Task Coordination:** Calls `shared_groups` and `shared_group_tasks`, staging `create_shared_task` for the FPO group members.
3. **Slide Deck Synthesis:** Calls `create_file(format="pptx")` to generate a **Cooperative Seasonal Operations Presentation (`.pptx`)** ready for the village/FPO meeting.

---

### Complete Catalog of 52+ Agentic Tasks & Tool Capabilities Across the Farm OS

Every single item below is wired to a real schema-validated tool in [`skyview/assistant/tools.py`](skyview/assistant/tools.py), a domain skill in [`skyview/assistant/skills/`](skyview/assistant/skills/), or a canonical API route:

| # | Domain | Task / Capability | Backing Tool / Sub-Agent | Execution Mode |
| :- | :--- | :--- | :--- | :--- |
| **1** | **Search & Grounding** | Search live public agricultural advisories & rules with Google Search citations | `web_research` | Autonomous Read |
| **2** | **Search & Grounding** | Query curated canonical ICAR / university crop guidance excerpts | `knowledge_search` | Autonomous Read |
| **3** | **Search & Grounding** | Inspect all active agent skills, tools, examples & safety boundaries | `assistant_capabilities` | Autonomous Read |
| **4** | **Memory & Context** | Search archived past conversations for farmer-stated facts & prior results | `recall_memory` | Autonomous Read |
| **5** | **Memory & Context** | Dynamically load any of the 22 specialized markdown skill playbooks mid-turn | `load_skill` | Autonomous Orchestration |
| **6** | **Memory & Context** | Pause execution & render a 1–5 field interactive clarification form in chat | `ask_farmer` | Interactive Pause/Resume |
| **7** | **Memory & Context** | Auto-compact >12k token conversations at clean user-turn boundaries | `memory.context` | Background Memory Manager |
| **8** | **Farms & Plots** | Read owned farms, plot boundaries, hectares & active/planned crop cycles | `field_context` | Autonomous Read |
| **9** | **Farms & Plots** | Build regional seasonal crop & sowing-window plans from soil/water records | `seasonal_planning_context` | Autonomous Read |
| **10** | **Tasks & Calendar** | List open, overdue, and upcoming dated farm tasks | `list_tasks` | Autonomous Read |
| **11** | **Tasks & Calendar** | Create a dated farm task (via deterministic fast-path or reviewed proposal) | `save_task` + `fast_actions.py` | Fast-Path / Guarded Write |
| **12** | **Tasks & Calendar** | Reschedule or update an existing task's title, due date, and notes | `update_task` | Guarded Write (Reviewed) |
| **13** | **Tasks & Calendar** | Mark a farm task completed with version-checked receipt | `complete_task` | Guarded Write (Reviewed) |
| **14** | **Tasks & Calendar** | Soft-delete/remove a farm task while keeping it recoverable | `delete_task` | Guarded Write (Reviewed) |
| **15** | **Tasks & Calendar** | Audit today's overdue work, active crop follow-ups, missions & ledger summary | `farm_today` | Autonomous Read |
| **16** | **Missions & Saathi** | Read multi-step persistent farm missions & step completion progress | `farm_missions` | Autonomous Read |
| **17** | **Missions & Saathi** | Create a multi-day step-by-step farm mission checklist in the notebook | `create_mission` | Guarded Write (Reviewed) |
| **18** | **Missions & Saathi** | Proactively draft background plans across 6 areas (`today`, `markets`, `schemes`, `records`, `crops`, `exchange`) | `Saathi` (`companion_plans.py`) | 24/7 Background Sub-Agent |
| **19** | **Soil & Agronomy** | Read supported soil lab parameters, depth limits & explicit nutrient bases (`P` vs `P2O5`) | `soil_report_options` | Autonomous Read |
| **20** | **Soil & Agronomy** | OCR & extract structured values from a photographed Soil Health Card or lab sheet | `read_document_image` | Multimodal Vision Read |
| **21** | **Soil & Agronomy** | Save a farmer-verified soil report transcription linked to a specific plot & photo | `save_soil_report` | Guarded Write (Reviewed) |
| **22** | **Soil & Agronomy** | Query historical dated soil sample transcriptions & nutrient indicators | `soil_reports` | Autonomous Read |
| **23** | **Crop Doctor & Vision** | Run multimodal AI visual diagnosis on an uploaded diseased leaf/plant photo | `diagnose_crop` | Multimodal Vision Sub-Agent |
| **24** | **Crop Doctor & Vision** | Read open and historical crop symptom cases & model uncertainty notes | `crop_cases` | Autonomous Read |
| **25** | **Crop Doctor & Vision** | Open a new tracked crop symptom follow-up case on a plot | `create_crop_case` | Guarded Write (Reviewed) |
| **26** | **Crop Doctor & Vision** | Append a dated field observation note to an existing crop case timeline | `record_crop_note` | Guarded Write (Reviewed) |
| **27** | **Crop Doctor & Vision** | Retrieve official KVK, ICAR, and crop-insurance referral portals & handoff checklists | `expert_referrals` | Autonomous Read |
| **28** | **Weather & Sensors** | Read latest authenticated ESP32 field station telemetry (temp, humidity, wind, rain, soil probe) | `station_snapshot` | Autonomous Read |
| **29** | **Weather & Sensors** | Query 1 to 168 hours of timestamped physical field station history | `weather_history` | Autonomous Read |
| **30** | **Weather & Sensors** | Fetch 1–16 day source-backed grid weather forecasts for the farmer's coordinates | `weather_forecast` | Autonomous Read |
| **31** | **Weather & Sensors** | Query 1–366 days of historical regional weather reanalysis/archive data | `weather_archive` | Autonomous Read |
| **32** | **Weather & Sensors** | Look up current weather & 10-day forecast for any external city/mandi hub | `city_weather` | Autonomous Read |
| **33** | **Weather & Sensors** | Hardware AXI4-Lite register bridge for FPGA Q8.8 sensor fusion acceleration | `fpga_agent.py` | Edge Hardware Bridge |
| **34** | **Mandi & Economics** | Query dated `data.gov.in` mandi arrival prices by commodity and state | `market_prices` | Autonomous Read |
| **35** | **Mandi & Economics** | Generate historical mandi price trend charts & range statistics (`min`, `max`, `modal`) | `market_trend` | Autonomous Read + Chart |
| **36** | **Mandi & Economics** | Run explicitly labeled 1–365 day synthetic price planning scenarios with uncertainty bands | `price_scenarios` | Scenario Simulation |
| **37** | **Mandi & Economics** | Calculate gross vs. net INR take-home sale realization after transport, bagging & mandi fees | `net_sale` | Deterministic Calculator |
| **38** | **Finance & Ledger** | Calculate itemized input budgets (`quantity × unit_price`) in INR with exact totals | `calculate_budget` | Deterministic Calculator |
| **39** | **Finance & Ledger** | Read full farm ledger (actual, estimated & receivable income/expenses + net balance) | `farm_ledger` | Autonomous Read |
| **40** | **Finance & Ledger** | Record a reviewed actual, estimated, or receivable INR ledger transaction | `record_ledger` | Guarded Write (Reviewed) |
| **41** | **Finance & Ledger** | Record a quick workspace farm expense entry | `record_expense` | Guarded Write (Reviewed) |
| **42** | **Finance & Ledger** | List workspace expense entries for cost review | `list_expenses` | Autonomous Read |
| **43** | **Schemes & Benefits** | Search verified government schemes (`PM-KISAN`, `PMFBY`, `PM-KUSUM`, state subsidies) with links | `scheme_search` | Autonomous Read |
| **44** | **Farmer Exchange** | Browse district-level published farmer resource offers & requests (tractors, seeds, tools) | `exchange_listings` | Autonomous Read |
| **45** | **Farmer Exchange** | Compute explainable resource matches for an owned exchange listing | `exchange_matches` | Autonomous Matching |
| **46** | **Farmer Exchange** | Track participant-only exchange negotiations, terms, and handover confirmations | `exchange_journeys` | Autonomous Read |
| **47** | **FPO & Shared Work** | Read household or FPO cooperative planning groups & member roles | `shared_groups` / `shared_group_tasks` | Autonomous Read |
| **48** | **FPO & Shared Work** | Create a private household/FPO group or assign a shared checklist task | `create_farm_group` / `create_shared_task` | Guarded Write (Reviewed) |
| **49** | **Service Notebook** | Read & record labour, harvester, transport, or custom-hiring quotes and arrangements | `service_notebook` / `record_service` | Read + Guarded Write |
| **50** | **Document & File Studio** | Generate downloadable Word (`.docx`), PDF (`.pdf`), Excel (`.xlsx`), CSV (`.csv`), and PowerPoint (`.pptx`) files | `create_file` (`artifacts.py`) | Autonomous Artifact Gen |
| **51** | **Document & File Studio** | Read uploaded/generated files or revise an existing artifact into a new version/format | `read_file` / `revise_file` | Autonomous File I/O |
| **52** | **Multilingual Voice & WhatsApp** | Transcribe 22+ Indian languages (`Sarvam` + `Groq Whisper`), speak replies (`Bulbul v2`), & process WhatsApp voice/photos via Cloud Tasks | `v3_voice_routes.py` + `whatsapp_tasks.py` | Voice & Async Channel |

---

## 🎙️ Multilingual Voice Pipeline (STT · TTS · Live Turn-Taking)

Kisan Mitra treats voice as a first-class agentic interface across **22+ Indian language codes** (`hi-IN`, `mr-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `bn-IN`, `gu-IN`, `pa-IN`, `od-IN`, `as-IN`, `ur-IN`, `ne-IN`, `kok-IN`, `mai-IN`, `sa-IN`, `en-IN`, and Hinglish):

```mermaid
flowchart LR
    Mic["Farmer Speaks (Web / Flutter / WhatsApp Audio)"] --> Validate["Container & RIFF/WAVE Integrity Check (<=5MB, <=30s)"]
    Validate --> PrimarySTT["Primary Neural STT: Sarvam AI (saaras:v4 / saaras:v3)"]
    PrimarySTT -->|"Fallback on timeout/503"| FallbackSTT["Fallback LPU STT: Groq Whisper (whisper-large-v3-turbo)"]
    PrimarySTT --> Orchestrator["Mitra Agentic Orchestrator (Language-Locked Context)"]
    FallbackSTT --> Orchestrator
    Orchestrator --> ReplyText["Grounded Response + Action / Review Cards"]
    ReplyText --> NeuralTTS["Neural TTS Synthesis: Sarvam Bulbul (bulbul:v2 · 11 Indian Languages)"]
    NeuralTTS --> AudioOut["Streaming Audio Playback + Live Captions"]
```

- **Multi-Provider Speech-to-Text (STT) with Automatic Failover ([`skyview/api/v3_voice_routes.py`](skyview/api/v3_voice_routes.py)):** Audio uploads undergo binary signature validation (`WAV`, `WebM`, `Ogg`, `FLAC`, `MP3`, `MP4`) and duration bounds before routing to **Sarvam AI (`saaras:v4`)** for Indian-accent and code-mixed recognition, with automatic multi-key failover to **Groq LPU Whisper (`whisper-large-v3-turbo`)**.
- **Neural Text-to-Speech (TTS) & Spoken Onboarding:** Responses, guided tours, and onboarding prompts are synthesized via **Sarvam AI (`bulbul:v2`)** with preprocessing enabled for natural Indian cadence across 11 spoken output languages.
- **Hands-Free Live Conversation Mode ([`LiveConversation.tsx`](frontend/src/components/assistant/LiveConversation.tsx)):** Supports automatic speech turn detection (`automatic_speech_turns`), live streaming captions, and voice-driven tool execution while strictly preserving review gates—voice input never bypasses farmer approval for record changes.
- **Structured Voice-to-Field Extraction:** Spoken farmer introductions are transcribed and parsed into editable profile/farm proposal fields without silently overwriting existing database records.

---

## 🌍 Overview & Vision

A farmer should be able to describe a problem in their own words without first choosing a dashboard, tool or form. Kisan Mitra connects five parts of that work:

1. **Understand the farm:** Profile, farms, plots, crop cycles, equipment, readings, notes, expenses and upcoming tasks form a usable working context.
2. **Look beyond the farm:** Weather, mandi prices, crop guidance and scheme references carry dates and source context into a decision.
3. **Prepare the work:** Mitra can research, compare, calculate, create plans and generate Word, PDF, spreadsheet, CSV and presentation files.
4. **Keep the farmer in control:** Focused questions resolve missing details. Record changes, exchange terms and prepared plans are reviewable before they are saved.
5. **Meet farmers where they are:** The same product has a web workspace, the original Classic interface, a Flutter companion, linked WhatsApp and a call control.

### The channels in practice

![Four Indian farmers using Kisan Mitra through the web, mobile app, messaging and a phone call](docs/media/four-ways-to-farm.png)

*From a cooperative desk to a crop row, a mandi stall or an orchard: one connected farm companion, reached in the way that fits the moment.*

| Access | Where it fits | Farmer experience |
| :--- | :--- | :--- |
| **Website** | Reviewing the season at home or at a cooperative desk | Explore the full Farm OS or Classic workspace: chat, calendar, weather, Crop Doctor, mandi research, notebook, exchange, profile and the 3D station. |
| **Flutter app** | Walking a plot and making decisions in the field | Use a pocket-sized assistant with feature chips, calendar, station, weather, crops, markets, notebook, exchange, Saathi and profile. |
| **WhatsApp** | Sharing a crop photo, voice note or question from an existing conversation | Send text and supported media to a linked account. A signed Twilio webhook brings the request into Mitra; reply delivery depends on the sender's capabilities. |
| **Phone** | Speaking with support when typing is inconvenient | Use the website's call control to reach the configured support line. Browser live voice is available separately through the Mitra API. |

Farmers can type or speak naturally in supported languages, including Hinglish. The assistant keeps the original-language question and uses the farmer's selected language and conversation context when answering. Speech recognition and synthesis depend on configured services.

```mermaid
flowchart LR
    Farmer["Farmer"] --> Website["Website"]
    Farmer --> App["Flutter app"]
    Farmer --> WhatsApp["Linked WhatsApp"]
    Farmer --> Phone["Call button"]
    Website --> Chat["Mitra chat + live voice"]
    App --> MobileChat["Mobile assistant"]
    WhatsApp --> WAChat["Signed Twilio webhook"]
    Chat --> Context["Owned farm context"]
    MobileChat --> Context
    WAChat --> Context
    Phone --> Line["Configured support line"]
```

The three digital assistant routes reach Mitra through account- or session-bound access. The call button opens the device dialer for a configured support line; it does not imply that a phone conversation is already connected to the agent runtime.

---

## 🏗️ System Architecture

The whole system fits in one picture:

```mermaid
flowchart LR
    Farmer["Farmer"] --> Web["Firebase Hosting · website"]
    Farmer --> Mobile["Flutter app"]
    Farmer --> WA["Twilio · WhatsApp"]
    Web --> Auth["Firebase Authentication"]
    Mobile --> Auth
    Web --> API["Cloud Run · FastAPI + Mitra"]
    Mobile --> API
    Auth -. "Verified ID token" .-> API
    WA --> API
    API --> Data[("Neon PostgreSQL · farm data")]
    API --> Sources["Weather, markets, guidance"]
    API --> Files["Private Neon files"]
    Station["Enrolled station"] --> API
    Scheduler["Cloud Scheduler"] --> API
    API --> Tasks["Cloud Tasks · message work"]
    Tasks --> API
    Web --> Call["Configured phone line"]
```

**One account, two web modes.** Farm OS lives at `/workspace`; Classic SkyView keeps its overview, advisor, dashboards, crop care, mandi, marketplace, maps and reporting pages. Both read the same canonical farm data in v3 mode. [The architecture guide](docs/architecture.md) explains the identity, database, worker and device boundaries in detail.

**One agent, several surfaces.** The website, app and configured WhatsApp channel use the Mitra service. The website's phone button dials a configured line; it is separate from browser live voice unless a telephony integration is provisioned.

---

## ⚡ UltraCache & Background Data

Speed matters most when a farmer moves between tasks. The [browser cache](frontend/src/lib/ultraCache.ts) deduplicates owner-scoped reads, warms likely routes after login and invalidates relevant entries after writes or a session switch. Protected server responses remain `no-store`; the cache improves navigation without becoming the record of truth.

On Google Cloud, **Cloud Scheduler** initiates source refreshes and **Cloud Tasks** dispatches WhatsApp work while **Cloud Run** scales the API between requests. The [background worker](skyview/data/v3/worker.py) uses a PostgreSQL advisory lease to coordinate recurring jobs across API processes. Source calls have bounded requests, retries and backoff. Provider payloads retain observation and retrieval metadata; source-health records distinguish a delayed update from a current observation. The [data platform](data_platform/v3/) defines schema evolution, provider catalogs, ingestion and read functions.

```mermaid
flowchart LR
    Provider["Weather + market providers"] --> Capture["Capture source and retrieval time"]
    Capture --> Check["Validate units, dates and quality"]
    Check --> Store[("Canonical PostgreSQL records")]
    Store --> API["Owner-scoped API read"]
    API --> Cache["Bounded browser cache"]
    Cache --> View["Farm view or Mitra tool"]
    Worker["Leased refresh worker"] --> Capture
```

An answer can distinguish a current observation, a historical record and a forecast. A failed refresh stays visible in source health instead of becoming an invented zero reading.

| Layer | Responsibility |
| :--- | :--- |
| **Client read cache** | Keep navigation responsive and avoid duplicate reads |
| **FastAPI routes** | Validate identity, parameters, time context and response shapes |
| **Google Cloud execution** | Run the API on Cloud Run; schedule refreshes and queue message work with Cloud Scheduler and Cloud Tasks |
| **PostgreSQL** | Persist owned farm data, conversations, approvals, source records and job state |
| **Leased worker** | Refresh external data and prepare background work without duplicate runs |
| **Private file storage** | Hold generated documents and uploads with owner-scoped metadata |

See [data model](docs/data-model.md), [source connectors](data_platform/v3/CONNECTORS.md) and [operations](docs/operations.md).

---

## 🏎️ Backend Execution & Data Integrity

Mitra's runtime is a bounded task engine, not an unbounded loop. It restores the relevant conversation and farm context, chooses typed tools, streams public activity, and pauses for a focused question or an exact approval when needed. The [execution contract](skyview/assistant/execution_contract.py) and [assistant guide](docs/assistant.md) describe how a paused run resumes without guessing at the farmer's intent.

- **Farmer ownership:** Server-resolved identity, transaction scope and PostgreSQL row policies protect private records.
- **Dated evidence:** Market observations, forecasts, station measurements and farm entries keep their own dates and origins.
- **Reviewable writes:** A proposed change carries exact arguments; version checks and execution receipts prevent stale or repeated application.
- **Controlled media:** Uploads, previews and downloads have type, size and ownership checks. Generated files keep metadata and checksums.
- **Device integrity:** Enrolled stations validate credentials, units, timestamps and replay before readings enter the farm record.
- **Provider routing:** Configured model keys have cooldown and fallback behavior; source and model failures are surfaced rather than hidden.

The database also supports market and station reads through stored functions. Read-only research is distinct from farm-changing actions; an answer does not silently publish an exchange offer, send a message or control equipment.

---

## 🎨 Farm OS Design System

The website has **two deliberate experiences**. Classic SkyView keeps dense dashboards and dedicated tools. Farm OS turns the same capabilities into a quieter, task-led workspace with a feature dock, contextual Mitra helpers and Saathi's prepared work. On mobile, the interface keeps the app's feature chips and adapts conversation, review and calendar flows to a smaller screen.

| **The assistant workspace** | **The farm at a glance** |
| :--- | :--- |
| [![Mitra running tools in the web workspace](docs/media/assistant-tool-activity.png)](docs/media/assistant-tool-activity.png) | [![Farm station with interactive equipment and readings](docs/media/farm-station.png)](docs/media/farm-station.png) |
| Ask in ordinary language; inspect steps and the resulting work. | Explore the Three.js station without losing the practical readings. |

The visual language uses a warm, light farm palette, clear dark text, restrained borders, compact controls and page-aware help. The station gives equipment feedback on interaction; the notebook takes the form of a page-turning field journal; the exchange shows a resource journey instead of a wall of forms. Controls remain labeled and keyboard reachable, with reduced-motion handling for transitions.

---

## Flutter app screenshots

[Download the latest Android APK](https://github.com/vvinayakkk/kisan-mitra-farm-os/releases/latest) · [Mobile setup and development](docs/mobile/README.md)

The farm workspace in your pocket: speak with Mitra, review your day, explore farm conditions and keep your records close. These are captures of the implemented Flutter screens using controlled review data, not production customer records. Tap any image to open the full-resolution screenshot.

| **Home** | **Chat** | **Voice & captions** |
| :--- | :--- | :--- |
| [![Kisan Mitra Flutter app: Home](docs/media/app/home.png)](docs/media/app/home.png) | [![Kisan Mitra Flutter app: Chat](docs/media/app/chat.png)](docs/media/app/chat.png) | [![Kisan Mitra Flutter app: Voice & captions](docs/media/app/voice.png)](docs/media/app/voice.png) |
| A personal welcome, quick actions and work prepared by Mitra. | Farm conversations with follow-up actions. | A dedicated voice screen with caption and call controls. |

| **Farm weather** | **Farm station** | **Crop Doctor** |
| :--- | :--- | :--- |
| [![Kisan Mitra Flutter app: Farm weather](docs/media/app/weather.png)](docs/media/app/weather.png) | [![Kisan Mitra Flutter app: Farm station](docs/media/app/station.png)](docs/media/app/station.png) | [![Kisan Mitra Flutter app: Crop Doctor](docs/media/app/crop-doctor.png)](docs/media/app/crop-doctor.png) |
| Hourly outlook, days ahead and a suggested plan. | Field readings with their source and context. | Crop observations, photos and follow-up care. |

| **Tasks & calendar** | **Notebook** | **Saved plans** |
| :--- | :--- | :--- |
| [![Kisan Mitra Flutter app: Tasks & calendar](docs/media/app/tasks.png)](docs/media/app/tasks.png) | [![Kisan Mitra Flutter app: Notebook](docs/media/app/notebook.png)](docs/media/app/notebook.png) | [![Kisan Mitra Flutter app: Saved plans](docs/media/app/plans.png)](docs/media/app/plans.png) |
| Upcoming work and saved farm tasks. | Fields, money, crop checks and plans in one place. | Review and revisit plans prepared with Mitra. |

| **Markets** | **Farmer exchange** | **Schemes** |
| :--- | :--- | :--- |
| [![Kisan Mitra Flutter app: Markets](docs/media/app/markets.png)](docs/media/app/markets.png) | [![Kisan Mitra Flutter app: Farmer exchange](docs/media/app/exchange.png)](docs/media/app/exchange.png) | [![Kisan Mitra Flutter app: Schemes](docs/media/app/schemes.png)](docs/media/app/schemes.png) |
| Crop prices and mandi comparisons. | Community listings for resources and farm needs. | Explore support and scheme information. |

| **Farmer profile** | **Saathi** | **Offline continuity** |
| :--- | :--- | :--- |
| [![Kisan Mitra Flutter app: Farmer profile](docs/media/app/profile.png)](docs/media/app/profile.png) | [![Kisan Mitra Flutter app: Saathi](docs/media/app/saathi.png)](docs/media/app/saathi.png) | [![Kisan Mitra Flutter app: Offline continuity](docs/media/app/offline.png)](docs/media/app/offline.png) |
| Your details, land and farming context. | A companion for check-ins and prepared work. | Clear offline status alongside previously loaded content. |

*The voice capture illustrates the caption UI; it is not evidence of measured live transcription latency or audible playback on a physical phone. Offline availability depends on cached content and the supported synchronization flow.*

Continue to [app and web onboarding](#onboarding-on-app-and-web) and [guided tours](#guided-tours-on-app-and-web) for the first-run experience and in-app help.

---

## Onboarding on app and web

A little hello, a place, a farm, and a review before saving. Mitra offers spoken guidance and voice input alongside typing, with **Skip for now** when a farmer wants to explore first. Saved profile details belong to the same account across phone and laptop; unfinished setup can be resumed on the device where it was started.

*The galleries below are captures of the implemented web and Flutter interfaces using controlled review data. Names, records and counts are illustrative, not production customer data. Click any screenshot to inspect it at full size.*

### Website · make yourself at home

| **A little hello** | **Review your farm and starter routines** |
| :--- | :--- |
| [![Web onboarding with Saathi, name, language and Talk to Mitra](docs/media/product-journey/web-onboarding-welcome.png)](docs/media/product-journey/web-onboarding-welcome.png) | [![Web onboarding review with profile details and optional starter routines](docs/media/product-journey/web-onboarding-review.png)](docs/media/product-journey/web-onboarding-review.png) |
| Speak or type your details, with a visible four-step journey. | Review the profile and choose editable starter routines before saving. |

### Flutter app · one small step at a time

| **Meet Mitra** | **Introduce your farm** | **A little head start** |
| :--- | :--- | :--- |
| [![Flutter onboarding welcome with spoken guidance and name input](docs/media/product-journey/app-onboarding-welcome.png)](docs/media/product-journey/app-onboarding-welcome.png) | [![Flutter onboarding crop, field area and watering inputs](docs/media/product-journey/app-onboarding-farm.png)](docs/media/product-journey/app-onboarding-farm.png) | [![Flutter onboarding profile review and starter routines](docs/media/product-journey/app-onboarding-review.png)](docs/media/product-journey/app-onboarding-review.png) |
| Listen to the guidance or speak into a field; typing stays available. | Add crops, area and land details at your own pace. | Check the details and starter routines before opening your farm. |

Starter routines are editable suggestions for a morning farm walk, crop observations and a money notebook. They are not automatically scheduled tasks. The farmer reviews them before making them part of their plan.

---

## Guided tours on app and web

**Mitra’s little guide** highlights the control being explained and offers **Next, Back and Skip tour**. Guidance covers onboarding, the assistant and farm tools, including calendar, weather, station, crops, markets, notebook, exchange, schemes, profile and Saathi. Use **Take a tour** on the website or the **compass button** in the app to replay a guide. The tour does not activate the microphone or change farm records.

[![Website guided tour anchored to the Saathi control, with Back, Next and Skip tour](docs/media/product-journey/web-tour-chat.png)](docs/media/product-journey/web-tour-chat.png)

*Website: a spotlight and anchored explanation show exactly where to go next.*

| **App · help during setup** | **App · help inside chat** |
| :--- | :--- |
| [![Flutter onboarding tour highlighting Read this to me](docs/media/product-journey/app-tour-onboarding.png)](docs/media/product-journey/app-tour-onboarding.png) | [![Flutter chat tour highlighting the message input](docs/media/product-journey/app-tour-chat.png)](docs/media/product-journey/app-tour-chat.png) |
| A guide points to spoken guidance without starting recording. | The next action stays highlighted above the native tour controls. |

---

## Administration workspace

[Open Mitra administration](https://growwithmitra.web.app/control) · [Capabilities, access and deployment notes](docs/releases/admin-workspace.md)

A web workspace for authorized administrators to look after farmers, farm records, markets, crop guidance, weather and service data. **43 registered resources** include **34 editable resources and 9 read-only views**. Viewer, editor and owner permissions are verified on the server.

| **The community at a glance** | **Review before applying** |
| :--- | :--- |
| [![Mitra administration overview with resource groups and illustrative totals](docs/media/product-journey/admin-overview.png)](docs/media/product-journey/admin-overview.png) | [![Administrator change preview comparing before and after values with typed confirmation](docs/media/product-journey/admin-preview.png)](docs/media/product-journey/admin-preview.png) |
| Navigate people, knowledge, markets, weather, services and activity. | Inspect exact changes and type the confirmation before saving. |

| **Bring data into Mitra** | **Every change, accounted for** |
| :--- | :--- |
| [![Admin CSV import with a template, example rows and reason for the change](docs/media/product-journey/admin-import.png)](docs/media/product-journey/admin-import.png) | [![Read-only administrator audit log showing resource, role and reason](docs/media/product-journey/admin-audit.png)](docs/media/product-journey/admin-audit.png) |
| Import up to 100 CSV rows, validate them and review the batch. | Keep a read-only record of who changed what, when and why. |

Administrators can create and update supported records, edit selected records in bulk, and export the current page. Owners can delete eligible records; linked records remain protected. Changes require a reason, a database-validated preview and confirmation, and each batch is atomic and audited. Accounts with linked history can be suspended. Farmer sign-in alone never grants administrator access.

---

## 🛡️ Verification & Quality

The repository includes backend and database tests, frontend type checks and component tests, and Flutter analysis and tests. Run them against the correct development services and a **dedicated test database**:

```bash
# Backend: first prepare a separate test database as described in docs/local-setup.md
.venv/bin/python data_platform/v3/test_backend.py

# Frontend
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx vitest run
npm run build

# Mobile, with the Flutter SDK installed
cd ../mobile
flutter analyze
flutter test
```

The [setup guide](docs/local-setup.md) gives database preparation and native development steps. [Contributing](CONTRIBUTING.md) covers expectations for source provenance, owned data and reviewed changes. This repository does not claim a hosted build or release pipeline.

---

## ⚡ Autonomous Agentic Workflows

The farmer does not need to name a skill. “What should I do before the rain?”, “Compare rice prices near me,” or “Make a weekly plan and ask me anything missing” can each involve several tools, a question, a chart, a document or a proposed calendar change.

### What makes the assistant agentic

**Mitra works toward an outcome across several steps.** It restores the farmer's conversation and saved context, chooses relevant skill instructions and typed tools, reads farm and public evidence, then decides whether it has enough information to continue. It can ask for one missing detail, perform more reads, calculate a result, create an artifact, or prepare a change for review. The farmer sees public activity during the run and can revisit the finished work in history.

| Capability | How it appears in a real farm task |
| :--- | :--- |
| **Contextual planning** | “Plan my week” starts with the farmer's crops, dated tasks and weather instead of a blank checklist. |
| **Tool use** | Mitra can read a station snapshot, compare mandi observations, search public guidance and calculate a budget in one request. |
| **Focused clarification** | If a crop stage or target date is missing, it asks for that detail and resumes the same task. |
| **Evidence-aware synthesis** | The answer carries relevant dates, units, market or provider context, and uncertainty. |
| **Real outputs** | A task can return an inline chart, a downloadable document, a spreadsheet, a presentation or a proposed record change. |
| **Guarded execution** | The exact proposed write pauses for farmer review; approval resumes that saved action with replay and version protection. |
| **Persistent continuity** | Conversation history, bounded memory and owned files preserve useful facts and unfinished work for a later visit. |
| **Proactive assistance** | Saathi prepares contextual follow-ups for the farmer to preview, edit, approve or dismiss. |

```mermaid
flowchart LR
    Ask["Ask or speak"] --> Gather["Read farm + current context"]
    Gather --> Work["Research, calculate, create"]
    Work --> Result["Answer, chart, file or draft"]
    Result --> Review{"Changes needed?"}
    Review -->|Yes| Approval["Farmer reviews"]
    Review -->|No| Finish["Keep result"]
    Approval --> Finish
```

For example, “Check this week's work against the rain, make a checklist and move anything risky” is one request with several stages:

```mermaid
sequenceDiagram
    actor Farmer
    participant Mitra
    participant Farm as Farm records
    participant Weather as Weather source
    Farmer->>Mitra: Review my week against the rain
    par Read current work
        Mitra->>Farm: Load dated tasks and crop context
    and Read conditions
        Mitra->>Weather: Load forecast with issue time
    end
    Mitra-->>Farmer: Prioritized checklist and reasons
    Mitra-->>Farmer: Proposed task changes for review
    Farmer->>Mitra: Approve exact changes
    Mitra->>Farm: Apply version-checked writes
    Mitra-->>Farmer: Confirm saved calendar result
```

The diagram shows the execution boundary: Mitra may prepare an answer and a proposal on its own, but a farm-changing write waits for explicit review. A public source or uploaded document cannot grant that approval.

| Step | What a farmer sees |
| :--- | :--- |
| **Understanding** | The request remains in the language used by the farmer. |
| **Working** | Public tool activity and relevant evidence appear during the run. |
| **Clarifying** | One focused question appears at a time, then the task continues. |
| **Delivering** | A chart, file preview, plan or action card accompanies the answer. |
| **Reviewing** | The farmer approves, edits or declines the exact proposed change. |
| **Returning** | History, bounded memory and saved results make the next visit useful. |

| **A reviewed task** | **A generated file in chat** |
| :--- | :--- |
| [![Mitra preparing a task for approval](docs/media/assistant-task-preview.png)](docs/media/assistant-task-preview.png) | [![Inline preview of an assistant-generated file](docs/media/assistant-file-preview.png)](docs/media/assistant-file-preview.png) |

| **Language stays in the conversation** | **Skills explain themselves** |
| :--- | :--- |
| [![Hindi assistant conversation](docs/media/assistant-hindi.png)](docs/media/assistant-hindi.png) | [![Assistant skill and tool detail](docs/media/assistant-toolkit-detail.png)](docs/media/assistant-toolkit-detail.png) |

### The 22 farm skills

| Skill | What it helps do | Skill | What it helps do |
| :--- | :--- | :--- | :--- |
| **Web research** | Find current public guidance with sources | **Farmer exchange** | Compare resources and exchange progress |
| **Field check** | Review station readings and next checks | **Weather outlook** | Read forecast and climate history |
| **Irrigation** | Plan water work around crop context | **Crop calendar** | Turn stage and dates into farm tasks |
| **Market prices** | Compare dated mandi records | **Farm budget** | Calculate costs from real quantities |
| **Scheme checklist** | Prepare benefit application steps | **Crop scouting** | Turn symptoms into an inspection plan |
| **Daily workspace** | Prioritize today's farm work | **Sale planning** | Estimate take-home value after costs |
| **Soil report review** | Explain results without losing units | **Insurance pack** | Assemble dated loss evidence |
| **Expert handoff** | Prepare a crop case for official help | **Crop follow-up** | Maintain observations and next checks |
| **Shared work** | Plan household or FPO tasks | **Service plan** | Record labour, machinery and transport |
| **Farm records** | Maintain tasks and expenses | **Documents** | Create Word and PDF reports |
| **Spreadsheets** | Create Excel workbooks and CSV files | **Presentations** | Build a farm or cooperative deck |

The current catalog is exposed at `GET /api/assistant/catalog`; the [assistant guide](docs/assistant.md) documents the lifecycle, memory, approvals and tool inventory.

---

## 🔬 Core Functional Engines

Every feature has a short job description here. The images are clickable for a full-size view.

### 1. 🧠 Mitra: Conversational Farm Work

**Ask a natural-language question and leave with something useful.** Mitra can investigate, plan, make a file, ask for missing details, stream tool activity and prepare a reviewed change. History reopens earlier work; answer actions allow copying, sharing, feedback, listening and retrying. Compact helpers bring the same context into individual pages.

### 2. 🗓️ Farm Calendar & Seasonal Planning

**Turn farm intentions into dated work.** Create, edit, complete and remove tasks; use crop stage, weather and available labour to prepare a weekly or seasonal checklist. Mitra can propose a change, and the farmer reviews it before it appears on the calendar.

[![Farm calendar with dated tasks and contextual Mitra help](docs/media/farm-calendar.png)](docs/media/farm-calendar.png)

### 3. 📓 Farm Notebook, Fields & Money

**Keep the season's work in one field journal.** The notebook connects farms, plots, crop cycles, observations, expense entries, follow-ups, plans and files. It also supports soil-report review, insurance evidence, expert handoff, shared work and service arrangements.

[![Page-style farm notebook](docs/media/farm-notebook.png)](docs/media/farm-notebook.png)

### 4. 🩺 Crop Doctor & Follow-up

**Use a crop image and symptoms to decide what to inspect next.** Crop Doctor prepares an assessment with uncertainty, practical checks and a case timeline; subsequent observations stay with the same crop concern.

[![Crop Doctor showing a crop assessment and follow-up](docs/media/farm-crop-doctor.png)](docs/media/farm-crop-doctor.png)

### 5. 🌦️ Farm Weather & City Outlooks

**Read current conditions in the context of farm work.** Current and hourly conditions, rainfall, wind, air quality, outlook and other-city views help decide when to inspect, irrigate, spray or harvest. Weather history and forecast retain distinct time context.

| **Weather workspace** | **Weather evidence inside chat** |
| :--- | :--- |
| [![Farm weather dashboard](docs/media/farm-weather.png)](docs/media/farm-weather.png) | [![Weather chart rendered in an assistant answer](docs/media/assistant-weather-chart.png)](docs/media/assistant-weather-chart.png) |

### 6. 📈 Mandi Directory, Rates & Sale Planning

**Find a relevant market before deciding where to sell.** Search by crop, state, mandi and variety; inspect dated rates and historical charts; compare likely take-home value after transport and other costs. Market directory entries, observations and planning calculations are kept distinct.

[![Mandi search and price history](docs/media/farm-markets.png)](docs/media/farm-markets.png)

### 7. 🏛️ Farm Support & Schemes

**Find benefits and prepare the next application step.** Source-linked scheme references, eligibility context, requirements and a saved support checklist help a farmer move from discovery to preparation.

[![Farm support and scheme guidance](docs/media/farm-support.png)](docs/media/farm-support.png)

### 8. 🤝 Farmer Exchange & Resource Routing

**Share a resource or find a fair exchange.** Farmers can describe what they have or need, inspect matches, discuss terms, track an agreement and confirm handover. The Classic marketplace keeps farmer discovery, geographic view, pooling and matching screens available.

[![Farmer exchange resource journey](docs/media/farm-exchange.png)](docs/media/farm-exchange.png)

<a id="hardware-integration"></a>

### 9. 🛰️ 3D Farm Station & Connected Hardware

**From a measurement in the field to context Mitra can use.** An enrolled station sends authenticated sensor packets to the backend. Validated, dated measurements are stored against its farmer and station, then read by the website, Flutter app and Mitra’s station tools.

[View the physical hardware gallery](#our-hardware-in-action) for the ESP32 assembly, field demonstrations and Raspberry Pi / FPGA boards.

#### The farm station in the interface

[![Interactive 3D farm station showing wind direction, wind speed, rainfall, ESP32 controller, status display, solar array and soil-moisture probe](docs/media/farm-station.png)](docs/media/farm-station.png)

*The React Three Fiber station visualization labels the wind vane, anemometer, rain collector, ESP32 controller, display, solar array and soil probe. This is a captured software visualization, not a photograph or proof of a connected physical installation. Displayed equipment and animations do not create sensor readings.*

#### How the station connects

```mermaid
flowchart LR
    Sensors["Calibrated field sensors"] --> Device["Enrolled device / gateway"]
    Device -->|"HTTPS · device credential"| Ingest["POST /api/sensors/ingest"]
    Ingest --> Check["Validate identity, units, time and replay"]
    Check --> DB[("Owned station measurements + packet receipts")]
    DB --> Read["Owner-scoped station API"]
    Read --> Web["Web farm station"]
    Read --> App["Flutter station screen"]
    DB --> Mitra["Mitra station snapshot and history tools"]
    Mitra --> Plan["Explain readings and prepare next steps for review"]
```

| Stage | Integration in the repository |
| :--- | :--- |
| **Enroll** | Create the farm and plot, then call `POST /api/stations/enroll` as the owner. Enrollment binds the station to that account and returns a device key; the server stores its hash. |
| **Send** | Device or gateway firmware calls `POST /api/sensors/ingest` with `Authorization: Device <key>`, a station ID, device observation time, per-boot UUID, increasing sequence and calibrated measurements. |
| **Validate and save** | The backend verifies the credential and validates the measurement envelope. Identical packet retries are safe; conflicting reuse of a boot/sequence is rejected. Receipt updates `last_received_at`. |
| **Read in app and web** | `GET /api/sensors/latest/{station_id}` exposes the owned station snapshot. The screens retain dates and measurement context; provider forecasts remain distinct from physical readings. |
| **Use with Mitra** | Station snapshot and history tools bring measured conditions into a conversation or proposed plan. Receiving telemetry does not itself activate irrigation or other equipment. |

The [connection guide](docs/hardware/README.md#connect-a-station) includes the JSON packet format, units, boot/sequence rules and commissioning notes. Firmware must implement this HTTPS contract; a rendered ESP32 in the scene is not device enrollment.

#### Optional FPGA sensor fusion

The repository also includes [C++ HLS sources and testbenches](hardware/hls/README.md), [Verilog RTL and the Vivado register map](hardware/rtl/VIVADO_GUIDE.md), and a [Python register bridge](skyview/agents/fpga_agent.py). On a Linux host physically connected to the board, the bridge accesses the fusion accelerator through a 32-bit AXI4-Lite memory map (`/dev/mem` or a UIO device).

`GET /api/fpga/status` probes the configured IP version. `POST /api/fpga/fusion` writes Q8.8 sensor inputs, waits for a fresh completion and returns the raw hardware results, with AI interpretation kept separately. Enable the bridge only on the host that can access the FPGA registers; Cloud Run cannot directly access a remote board’s memory map. The rain-prediction RTL has a separate address map and is not wired into this fusion bridge.

**Physical commissioning remains a separate step:** sensor wiring, calibration, firmware uploads, board configuration and end-to-end delivery must be verified on the actual installation. The source code, screenshots and software tests alone do not establish a live connected board or measured hardware latency.

### 10. ✨ Saathi: Always-Active 24/7 Companion & Prepared Work to Review

<img src="docs/media/saathi-mascot.svg" width="76" align="right" alt="Cute Saathi sprout mascot" />

**Let your cute 24/7 farm companion prepare useful next moves in the background.** While you tend to your fields, Saathi continuously watches your farm context across `today`, `markets`, `schemes`, `records`, `crops`, and `exchange`, preparing ready-to-review previews for crop follow-ups, mandi comparisons, scheme checklists, notebook upkeep, and exchange planning. A farmer can open, voice-edit, approve, or dismiss each proposal; approved work is saved directly into the relevant farm workspace.

| **Saathi in the workspace** | **A plan ready for approval** |
| :--- | :--- |
| [![Saathi open over the assistant workspace with a prepared farm plan](docs/media/saathi-review.png)](docs/media/saathi-review.png) | [![Saathi plan details with a visible approval action](docs/media/saathi-approval.png)](docs/media/saathi-approval.png) |

```mermaid
flowchart LR
    Signals["Saved tasks, crop follow-ups and farm context"] --> Prepare["Saathi prepares a proposal"]
    Prepare --> Preview["Farmer opens the preview"]
    Preview --> Choice{"Farmer's choice"}
    Choice -->|Edit| Preview
    Choice -->|Dismiss| Stop["Leave records unchanged"]
    Choice -->|Approve| Save["Save reviewed plan"]
    Save --> Activity["Show confirmation and recent activity"]
```

### 11. 👤 Farmer Profile & Farm Context

**Keep identity, location, language, farms, plots and crop cycles together.** The profile makes advice, weather, tasks and records relevant to the right person and field.

[![Farmer profile showing location, crops, resources and saved fields in the workspace](docs/media/farm-profile.png)](docs/media/farm-profile.png)

### 12. 🎙️ Voice, WhatsApp & Files

**Choose the form that fits the moment.** The browser supports voice input and spoken responses when configured. WhatsApp can receive text, crop photos, voice notes and supported documents through a linked account. Mitra can create DOCX, PDF, XLSX, CSV and PPTX outputs, preview them in chat and provide private downloads. The web call button dials a configured support number.

### 13. 🧭 Classic SkyView & Developer Views

**Keep dedicated screens for deeper inspection.** Classic routes retain overview, advisor, dashboard, Crop Doctor, mandi, trends, marketplace, map, reports, profile, accelerator and database views. Hardware setup and procurement pages are also available. The switch into Farm OS keeps farmers in the same account and data context.

---

## 📁 Monorepo Directory Structure

```text
kisan-mitra-farm-os/
├── frontend/             React, TypeScript, Farm OS, Classic and Three.js
├── mobile/               Flutter companion
├── skyview/
│   ├── assistant/        Agent, skills, tools, memory, files and approvals
│   ├── api/              Farm, market, weather, exchange, voice and channel routes
│   └── data/v3/          Repositories, ingestion and recurring worker
├── data_platform/v3/     PostgreSQL schema, migrations and provider contracts
├── hardware/             Device source, RTL, HLS and register maps
├── infra/                Container images, requirements and Nginx
├── tests/                Backend and data contracts
├── docs/                 Product, API, operations, data and hardware guides
└── docker-compose.yml    Development stack
```

Start with the [project map](docs/project-map.md) if you are changing code, and the [architecture guide](docs/architecture.md) for data flow and ownership.

---

## 🚀 Quick Start & Development

### Prerequisites

Docker and Docker Compose are the shortest route to the full web stack. Native development additionally uses Python 3.12 and Node.js 20+. Flutter SDK is required for the mobile target.

### 1. Start PostgreSQL, API, worker and web client

```bash
cp .env.docker.example .env.docker
# Set distinct POSTGRES_PASSWORD and V3_APP_PASSWORD values in .env.docker.
docker compose --env-file .env.docker up --build
```

### 2. Open the two web experiences

- **Farm OS:** [http://127.0.0.1:5173/workspace](http://127.0.0.1:5173/workspace)
- **Classic SkyView:** [http://127.0.0.1:5173/overview](http://127.0.0.1:5173/overview)
- **API health:** [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

### 3. Configure optional channels

AI providers, speech, public data connectors and Twilio require server-side credentials. Keep secrets in ignored environment files or a managed secret store. The [configuration guide](docs/configuration.md), [operations guide](docs/operations.md) and [mobile guide](docs/mobile/README.md) explain their settings. No credential belongs in a `VITE_` variable or packaged Flutter define.

For separate Python and Node processes, follow [local operation](docs/local-setup.md). The Docker volumes preserve data across ordinary restarts.

---

## 📡 OpenAPI REST Endpoints

The running FastAPI service exposes `/docs` and `/openapi.json`. These are representative route groups; the [endpoint inventory](docs/api/endpoints.md) lists the registered canonical paths and [API overview](docs/api/overview.md) explains identity and scope.

| Area | Representative path | Purpose |
| :--- | :--- | :--- |
| **Readiness** | `GET /health` | API and database health |
| **Source state** | `GET /api/data/status` | Data mode and source health |
| **Assistant** | `POST /api/assistant/sessions` | Open an owner-scoped conversation |
| **Assistant run** | `POST /api/assistant/sessions/{sid}/run` | Stream a task and its visible activity |
| **Capabilities** | `GET /api/assistant/catalog` | Inspect available tools and skills |
| **Weather** | `GET /api/weather/dashboard` | Current farm weather and outlook |
| **Markets** | `GET /api/mandi/history` | Dated mandi price history |
| **Station** | `GET /api/sensors/latest/{station_id}` | Latest enrolled-device reading |
| **Saathi** | `GET /api/companion/proposals` | Prepared work for review |
| **WhatsApp** | `POST /webhook/whatsapp` | Signed inbound channel callback |

Private endpoints require verified account or assistant-session access; client-supplied identifiers cannot select another farmer's records.

---

## ☁️ Live Google Cloud Deployment

Kisan Mitra's website and API are deployed on **Google Cloud**. Firebase Hosting serves both web experiences over HTTPS; Firebase Authentication verifies phone sign-in; Cloud Run runs the FastAPI agent in Mumbai. Cloud Build creates the backend image, Artifact Registry stores it, and Secret Manager provides runtime credentials. Cloud Scheduler triggers source refreshes while Cloud Tasks dispatches WhatsApp work, so the API can scale to zero between requests. The [deployment runbook](docs/gcp-deployment.md) documents the live topology and operational checks.

```mermaid
flowchart LR
    Farmer["Farmer"] --> Web["Firebase Hosting · Farm OS + Classic"]
    Web --> Auth["Firebase Authentication · phone identity"]
    Web --> Run["Cloud Run · FastAPI + Mitra"]
    Mobile["Flutter · mobile"] --> Run
    Twilio["Twilio · WhatsApp"] --> Run
    Auth --> Run
    Build["Cloud Build"] --> Registry["Artifact Registry · backend image"]
    Registry --> Run
    Secrets["Secret Manager"] --> Run
    Run --> Postgres[("Neon PostgreSQL · farm data")]
    Run --> Files["Private Neon object storage · files"]
    Run --> Tasks["Cloud Tasks · replies"]
    Scheduler["Cloud Scheduler · source refresh"] --> Run
    Run --> Sources["Weather + market sources"]
```

The live web and API run on Google's platform; **Neon hosts the PostgreSQL database and private files**. The Android APK is distributed through GitHub Releases. The configured Twilio trial channel accepts inbound WhatsApp messages, while outbound free-form agent replies require a sender with that capability. Firebase test-number sign-in and the API's database health path have been verified; a physical-phone SMS test remains a release check.

### Built with Google

| Google technology | Role in Kisan Mitra |
| :--- | :--- |
| **Firebase Hosting** | Global HTTPS delivery for Farm OS and Classic SkyView |
| **Firebase Authentication** | Phone identity shared by the website, app and backend session flow |
| **Cloud Run** | Request-driven FastAPI and Mitra agent runtime in `asia-south1` |
| **Cloud Build + Artifact Registry** | Reproducible backend image builds and storage |
| **Secret Manager** | Runtime database, storage and provider credentials |
| **Cloud Scheduler + Cloud Tasks** | Timed data refresh and queued WhatsApp processing |
| **Google Antigravity** | AI-assisted architecture exploration, implementation and interface iteration during development |

Google Antigravity assisted the team throughout planning, code exploration, implementation, UI iteration, debugging and documentation. The team reviewed and tested the resulting work against the running web and API. Antigravity is a **development tool**; the services above form the deployed application. The [architecture guide](docs/architecture.md) covers the runtime boundaries in detail.

---

## 📄 License & Open Source Dedication

Kisan Mitra is built by **init.io** for the **AI Builder Cup** and released under the [MIT License](LICENSE). Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md), then explore the [feature guide](docs/features.md), [assistant guide](docs/assistant.md) and [project map](docs/project-map.md).

**Build for the farmer's next useful action.**
