# Farmer-facing experiences

The React app has one account context and two ways to work. The Farm OS shell is implemented in `frontend/src/pages/Advisor.tsx` at `/workspace`; classic routes are registered in `frontend/src/App.tsx`. Switching views changes the presentation, not the underlying farmer record. Farm OS view state is carried in `?view=` so a page can be linked directly.

## Farm OS views

| View | Screen | Main interaction | Canonical path |
| --- | --- | --- | --- |
| `chat` | Assistant | Multilingual tasks, streamed tool activity, focused questions, approval cards, inline charts and file previews | Assistant session and farm tools |
| `calendar` | Calendar | Dated work, editing, completion and contextual helper | Owned task and workflow routes |
| `station` | Farm station | React Three Fiber layout, selected-part feedback and readings | Enrolled station snapshots and history |
| `weather` | Farm weather | Current and hourly conditions, outlook, city choice and farm relevance | Regional weather routes and provider cache |
| `crops` | Crop Doctor | Photo and symptom assessment with follow-up | Disease assessment and crop-case routes |
| `markets` | Market prices | Crop/state/mandi search, dates, variety-aware chart and comparison | Market read functions and catalog |
| `schemes` | Farm support | Source-backed benefits, requirements and owned checklist | Scheme and support-folder routes |
| `records` | Farm notebook | Today, fields, money, crop follow-ups, plans, memory and files | Farm-workspace and assistant routes |
| `exchange` | Farmer exchange | Resource listing, fit, participant conversation, agreement and handover trail | Exchange listing, match and conversation routes |
| `profile` | My farm profile | Farmer identity, farms, plots and crop-cycle context | Onboarding and farm routes |

The header keeps Assistant, Calendar and Farm station close at hand; the compact feature dock exposes weather, crop care, markets, support, notebook and exchange. Saathi's reviewable prepared proposals, contextual helpers and voice controls appear where they are relevant. The current workspace component tree is the UI source of truth for exact control placement.

## Classic routes

`/overview`, `/advisor`, `/dashboard`, `/crop-doctor`, `/mandi`, `/trends`, `/marketplace`, `/map`, `/reports`, `/profile`, `/accelerator` and `/db` retain dedicated classic screens. Login, signup, hardware setup and purchase pages are separate routes. `ClassicWorkspaceSwitch` links applicable classic pages to their corresponding Farm OS view. Compatibility API routes allow those pages to read canonical records in v3 mode.

## Task semantics

A tool result may be an answer, a dated chart, a generated file, a draft, a saved record or a completed software action. The UI surfaces the difference. A mandi directory entry is not a quote; a forecast is not a station reading; a crop-photo assessment may ask for more evidence; an exchange agreement is participant reported; a saved plan is not physical field work. The assistant requests approval before it changes owned records. External delivery and device control have separate boundaries.

## Accessibility and language

The workspace accepts text and speech, keeps the question in the language used by the farmer, and can use the selected interface language as fallback. Voice turns expose editable transcription and spoken answers when configured. Page helpers use focused prompts rather than a second full chat. Controls have labels and keyboard focus; reduced-motion handling applies to the classic-to-workspace transition.
