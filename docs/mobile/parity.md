# Mobile ⇄ Farm OS parity matrix

Built from the current source: the web Farm OS (`frontend/src/pages/Advisor.tsx`, `frontend/src/components/assistant/`, `frontend/src/lib/assistantClient.ts`), the canonical routers in `skyview/api/` and the Flutter client in `mobile/lib/`. "Before" describes the mobile app at commit `25a80cf`. In that version no request sent session headers, so every private canonical route returned 401.

Status: **Parity**: same contract and behaviour, with a phone layout. **Adapted**: same contract with a different interaction pattern on the phone. **Gap**: not on mobile; the reason is given.

## Identity and session

| Capability | Web | Canonical API | Mobile before | Mobile now | Status |
| --- | --- | --- | --- | --- | --- |
| Detect backend lane | implicit | `GET /` → `data_mode` | none | `AuthController` reads `data_mode` and shows only the matching sign-in | Parity |
| Demo sign-in | demo OTP → `adoptAssistantSession` | `POST /api/auth/send-otp`, `/verify-otp` (demo lane only) | OTP; token stored but never sent | Explicit "demo farm" button. It uses the server-issued challenge and stores the session capability in the Keystore (`flutter_secure_storage`) | Parity |
| Live sign-in | Firebase Phone bearer → `POST /api/assistant/sessions` | server verifies the Firebase token and phone provider | none | Native Firebase phone code verification, then the ID token goes to `POST /api/assistant/sessions` | Parity (physical-phone verification pending) |
| Client farmer id | never sent | rejected (`extra="forbid"`) | sent `user_id`/`phone` in bodies and query strings | never sent; tested in `tests/assistant/test_mobile_contract.py` | Parity |
| Session headers | `Authorization` + `X-Assistant-Session` | required by `identity()` | missing | `ApiClient` sends both on every private call | Parity |
| Revoked/expired session | clears and re-creates | 401 | ignored | any 401 → `expire()` erases the capability and goes to sign-in | Parity |
| Sign-out | `revoke` + clear caches | `POST /sessions/{sid}/revoke` | deleted local token only | revokes on the server, wipes the Keystore, rebuilds the API client and cache | Parity |

## Assistant

| Capability | Canonical path | Mobile now | Status |
| --- | --- | --- | --- |
| Streamed run | `POST /sessions/{sid}/run` (NDJSON) | `ApiClient.stream` plus the `ndjsonEvents` reducer (`run_events.dart`) | Parity |
| Tool/skill activity | `tool_started/completed/failed` events | Collapsible panel showing only server events. An interrupted call shows "Not finished", never a spinner | Parity |
| Hard-coded agent steps | — | Removed with `chat_service.dart` | Fixed |
| History and restore after restart | `GET /sessions/{sid}`, `GET /events?run_id` | Snapshot on launch. A `working` run is replayed from persisted events until it ends | Parity |
| New chat / previous chats | `reset`, `restore/{cid}` | History sheet | Parity |
| Skills/tools catalog | `GET /catalog` | Sheet with Skills/Tools tabs, a "Review" badge on tools that need approval, and "Use this skill" | Parity |
| One question at a time | `question` event, `answers` + `pending_id` | `QuestionFlow` stepper: select, number, date, photo (camera or gallery) and text with voice | Parity |
| Approvals and declines | `approval` event, `approval: true/false` | `ApprovalCard` shows the exact arguments with server labels; "Save it" or "Don’t save" | Parity |
| Stop / cancel | client disconnect → server marks run `stopped` | Stop closes the stream; the turn shows "Stopped…" | Parity |
| Retry | resend | Retry on failed or stopped turns | Parity |
| Rewrite answer | `POST /answers/{id}/rewrite` | "Explain differently"; shown as not saved | Parity |
| Copy, share, read aloud | client / `POST /api/speech/synthesize` | Copy, system share sheet, TTS with script-aware language | Parity |
| Ratings (local only) | sessionStorage | not added | Gap (web keeps them only in the browser session; nothing reaches the server) |
| Attachments | `POST /attachments-json` | Camera, gallery or file picker (PDF/DOCX/XLSX/CSV/TXT/images, ≤5 MB) shown as chips and sent as `attachment_ids` | Parity |
| Inline charts | `result.chart` + provenance | `DatedChart` (fl_chart): dated axis, tooltip, collapsible, same captions (forecast, history, scenario, simulated, observed) | Parity |
| Generated files | `result.artifact`, `GET /files/{id}` | Inline preview (sections and table) → download to app-private storage → open in a system viewer or share. Revise | Parity |
| Research sources | `web_research` result | Source links, retrieval time and Google Search suggestion chips. Backend now persists these fields (see below) | Parity |
| Page context | `workspace_view`, `selected_date`, `weather_city`, `mission_id` | `RunContext` per screen. Notebook sub-pages map to `records` | Parity |
| Original language and fallback | message text; `language` = preference | Original text is always sent; preference from the language picker or server profile | Parity |
| Hindi / Hinglish | server `language_instruction` | Verified on device with a Hinglish turn and Hinglish answer. Fixed a server bug where a plain English instruction inherited an earlier Hinglish turn's language | Parity |

## Voice

| Capability | Canonical path | Mobile now | Status |
| --- | --- | --- | --- |
| Capability check | `GET /api/speech/capabilities` | Checked before any recording; unavailable → typed fallback | Parity |
| Microphone consent | browser prompt | In-app rationale, then the OS prompt; a permanent denial links to Settings | Parity |
| Dictation | `POST /api/speech/transcribe` (WAV ≤30 s) | `VoiceButton`: transcript goes into the field for review and is never auto-sent | Parity |
| Spoken answers | `POST /api/speech/synthesize` | Read aloud; language chosen from the answer's script | Parity |
| Live voice (turn-based) | `LiveConversation.tsx` loop | `LiveVoiceSheet`: listen → silence detection or "Done speaking" → same run path → speak → listen. Interrupt, mute, resume, end. Pauses on a question or approval card | Parity (on-device speech unverified, see README) |

## Farm screens

| View | Canonical path | Mobile screen | Status |
| --- | --- | --- | --- |
| Calendar | session `tasks`/`deleted_tasks`; `PATCH`/`DELETE`/`restore` with `row_version`/`If-Match` | Monday-first month grid, day agenda, mark done, edit sheet (voice), remove with Undo, deleted list, "Add with Mitra" | Parity |
| Saathi proposals | `/api/companion/proposals?area`, `/prepare`, `/review` | `PreparedBySaathi` on Calendar (today), Crop doctor, Markets, Schemes, Notebook and Exchange. Compact; you open the steps before approving. Edit, dismiss, research, then the saved state links to the plan | Adapted (approve needs "Review" first) |
| Saathi panel | `/api/companion`, `/preferences`, `/api/whatsapp/link` | Status, enable, frequency, quiet hours, activity, WhatsApp link only when the server reports it configured | Parity |
| Farm station | `GET /api/assistant/station/{id}` (10 s poll) | Reading grid, age, quality flags, simulated/sample labelling | Adapted (2D grid instead of the 3D scene) |
| Weather | `/api/weather/dashboard`, `/cities`, `/city-dashboard` | Current, 12-hour strip, 10 days, AQI, city search; always labelled as a regional model | Parity |
| Crop doctor | attachment + `inspect/diagnose_crop` | Camera or gallery → assessment with confidence → follow-up via Mitra | Parity |
| Markets | `inspect/market_prices`, `market_trend`, `/api/mandi/catalogue` | Crop/state autocomplete, provenance per card, future dates dropped, 9-per-page list, history chart, directory, take-home estimate | Parity |
| Schemes | `inspect/scheme_search`, `/api/support-folder/{id}` | Searchable folders, checklist with optimistic save and rollback, official link, "Prepare with Mitra" | Parity |
| Notebook · Today | `/farm-workspace/today`, `/weather-brief`, `/timeline` | Actions, weather flags, dated records | Parity |
| Notebook · Fields | `/api/farms`, `/plots`, `/crop-cycles`, `/onboarding/options`, weather link | List and edit farms, plots and crop seasons; weather link with consent | Adapted (coordinates typed; no map or boundary drawing) |
| Notebook · Money | `/farm-workspace/ledger` | Summary (actual vs estimate vs receivable), add/edit/delete with `row_version` | Parity |
| Notebook · Follow-ups | `/cases`, `/cases/{id}/notes` | Create, status, dated observations | Parity |
| Notebook · Plans | `/missions`, `/receipts` | Step toggles, allowed transitions, "complete" needs all steps, "Work on this with Mitra" with `mission_id` | Parity |
| Notebook · Memory | `/memories` | Correct, forget (with confirmation) | Parity |
| Notebook · Files | session `artifacts`, `inspect/list_expenses` | File cards and recorded costs | Parity |
| Shared work | `/service-requests`, `/groups/*` | Services, groups, join with consent, group tasks, invite codes (owner) | Adapted (member list and revoke left to web) |
| Exchange | `/api/exchange/*` | Browse/filter/search, my notices, matches, connect with consent, thread with 7 s polling, idempotent messages and actions, agreement trail | Parity |
| Exchange Mitra | `POST /api/exchange/assist` | Drafts marked "not saved" that fill the listing form or terms | Parity |
| Profile | `/api/profile`, `/profile/save` | View/edit, reported vs mapped area, language, theme, server, sign-out | Parity |
| Page helpers | `MitraHelper` + `suggestions.ts` | "Ask Mitra" sheet on each screen with the same four prompts, showing only turns started there | Parity |
| Suggestion chips | — | Original outlined chip style kept. Prompt chips send real prompts; feature chips open Farm OS screens | Adapted |
| Classic-only pages (`/accelerator`, `/reports`, `/trends`, FPGA) | classic routes | Removed from mobile; covered by Station, Notebook files and Markets | Gap by design (not part of Farm OS) |
| Offline use | snapshot fallback on web | Saved copies of key reads with an offline banner and their time; chat outbox sends when the network returns; writes need a connection | Parity (reads), Gap (offline writes) |

## Backend contract changes made for mobile

1. `skyview/assistant/engine.py`: `display_result` now keeps `sources`, `retrieved_at`, `search_suggestions_html` and `preparation`. Restored conversations on web and mobile keep their research evidence instead of showing an unsourced answer.
2. `skyview/assistant/execution_contract.py`: plain English instructions are detected by common function words. Such a request no longer gets an earlier Hinglish turn's reply language.
3. `docs/assistant.md`: the tool table's approval column now matches `tools.py` (13 tools pause for review).
4. Contract tests: `tests/assistant/test_mobile_contract.py`.
