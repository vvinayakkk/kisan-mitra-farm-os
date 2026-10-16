# HTTP endpoint inventory

The FastAPI application selects one route lane at startup using `SKYVIEW_DATA_MODE`. The canonical lane serves the Farm OS workspace and classic compatibility views; the legacy lane remains available when canonical mode is disabled. These tables summarize router decorators in `skyview/api/`. They describe registered route shapes, not an authorization bypass or a claim that an external provider is configured.

The live OpenAPI schema at `/openapi.json` is authoritative for request fields and response schemas. Private routes require the server-verified session or account identity documented in [overview](overview.md).

## Canonical lane

### `v3_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/` | `root` |
| GET | `/health` | `health` |
| GET | `/api/data/status` | `data_status` |
| GET | `/api/sensors/stations` | `stations` |
| GET | `/api/sensors/latest/{station_id}` | `latest` |
| GET | `/api/sensors/history/{station_id}` | `history` |
| GET | `/api/sensors/health` | `system_health` |
| GET | `/api/system-health` | `system_health` |
| GET | `/api/sensors/recent-alerts` | `alerts` |
| GET | `/api/recent-alerts` | `alerts` |
| GET | `/api/alerts/recent` | `alerts` |
| GET | `/api/sensors/trends/history` | `trends` |
| GET | `/api/trends/history` | `trends` |
| POST | `/api/sensors/trends/store` | `trends_store` |
| GET | `/api/mandi/commodities` | `commodities` |
| GET | `/api/mandi/catalog` | `market_catalogue` |
| GET | `/api/mandi/catalogue` | `market_catalogue` |
| GET | `/api/mandi` | `rates` |
| GET | `/api/mandi/rates` | `rates` |
| GET | `/api/mandi/history` | `market_history` |
| GET | `/api/mandi/scenarios` | `price_scenarios` |
| GET | `/api/mandi/msp` | `msp` |
| GET | `/api/profile` | `profile` |
| POST | `/api/profile/save` | `save_profile` |
| GET | `/api/schemes` | `schemes` |
| GET | `/api/schemes/recommendations` | `scheme_recommendations` |
| GET | `/api/schemes/{scheme_id}` | `scheme` |
| GET | `/api/marketplace/farmers` | `directory` |
| GET | `/api/marketplace/directory` | `directory` |
| POST | `/api/marketplace/match` | `matches` |
| POST | `/api/marketplace/circular-barter` | `loops` |
| GET | `/api/marketplace/pooling` | `pooling` |
| POST | `/api/marketplace/negotiate` | `negotiate` |
| POST | `/api/advisor/insights` | `advice` |
| GET | `/api/weather/forecast` | `forecast` |
| GET | `/api/weather/dashboard` | `weather_dashboard` |
| GET | `/api/weather/cities` | `weather_cities` |
| GET | `/api/weather/city-dashboard` | `weather_city_dashboard` |
| POST | `/api/sensors/ingest` | `ingest` |
| POST | `/api/sensors/data` | `ingest` |
| POST | `/api/auth/send-otp` | OTP request |
| POST | `/api/auth/verify-otp` | OTP verification |
| POST | `/api/auth/signup` | `signup` |
| GET | `/api/fpga/status` | `fpga_status` |

### `v3_support_folder_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/support-folder/{scheme_id}` | `read_preparation` |
| PUT | `/api/support-folder/{scheme_id}` | `save_preparation` |

### `v3_compat_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/chat` | `consult` |
| POST | `/api/weather-insight` | `consult` |
| POST | `/api/agriculture/qa` | `consult` |
| POST | `/api/chat/overview/ask` | `consult` |
| POST | `/api/chat/overview` | `overview` |
| POST | `/api/fpga/fusion` | `accelerator` |
| POST | `/api/fpga/rain-predict` | `accelerator` |
| POST | `/api/fpga/combined-analysis` | `accelerator` |
| POST | `/api/fpga/test` | `accelerator_tests` |

### `v3_explorer_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/admin/tables` | `tables` |
| GET | `/admin/tables/{table}` | `table_records` |

### `v3_voice_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/speech/capabilities` | `speech_capabilities` |
| POST | `/api/speech/transcribe` | `transcribe` |
| POST | `/api/speech/synthesize` | `synthesize` |
| POST | `/api/translate` | `translate` |
| POST | `/api/profile/voice-update` | `voice_update` |
| POST | `/api/voice/process` | `voice_process` |
| POST | `/api/voice/agent` | `voice_agent` |

### `v3_whatsapp_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/whatsapp` | `channel` |
| POST | `/api/whatsapp/link` | `link` |
| DELETE | `/api/whatsapp/link` | `unlink` |
| POST | `/webhook/whatsapp` | `incoming` |
| POST | `/webhook/whatsapp/status` | `delivery_status` |
| GET, HEAD | `/webhook/whatsapp/media/{identifier}` | `media_file` |

### `v3_companion_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/companion` | `summary` |
| PATCH | `/api/companion/preferences` | `preferences` |
| POST | `/api/companion/activity/{identifier}/read` | `mark_read` |
| GET | `/api/companion/proposals` | `proposals` |
| POST | `/api/companion/prepare` | `prepare` |
| POST | `/api/companion/proposals/{identifier}/review` | `review_proposal` |

### `v3_exchange_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/exchange/listings` | `listings` |
| POST | `/api/exchange/listings` | `create_listing` |
| PATCH | `/api/exchange/listings/{lid}` | `edit_listing` |
| GET | `/api/exchange/matches` | `matches` |
| GET | `/api/exchange/conversations` | `conversations` |
| POST | `/api/exchange/conversations` | `connect` |
| GET | `/api/exchange/conversations/{cid}/messages` | `messages` |
| GET | `/api/exchange/conversations/{cid}` | `conversation` |
| POST | `/api/exchange/conversations/{cid}/messages` | `send_message` |
| POST | `/api/exchange/conversations/{cid}/actions` | `act` |

### `v3_exchange_ai_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/exchange/assist` | `assist` |

### `v3_onboarding_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/onboarding/options` | `options` |
| POST | `/api/onboarding` | `onboarding` |
| GET | `/api/farms` | `farms` |
| POST | `/api/farms` | `create_farm` |
| PUT | `/api/farms/{identifier}` | `update_farm` |
| DELETE | `/api/farms/{identifier}` | `delete_farm` |
| GET | `/api/plots` | `plots` |
| POST | `/api/plots` | `create_plot` |
| PUT | `/api/plots/{identifier}` | `update_plot` |
| DELETE | `/api/plots/{identifier}` | `delete_plot` |
| GET | `/api/crop-cycles` | `cycles` |
| POST | `/api/crop-cycles` | `create_cycle` |
| PUT | `/api/crop-cycles/{identifier}` | `update_cycle` |
| DELETE | `/api/crop-cycles/{identifier}` | `delete_cycle` |
| POST | `/api/stations/enroll` | `enroll` |
| POST | `/api/stations/{identifier}/revoke` | `revoke` |
| GET | `/api/soil-report/options` | `soil_options` |
| POST | `/api/soil-reports` | `soil_report` |
| GET | `/api/soil-reports` | `soil_reports` |
| POST | `/api/farms/{identifier}/weather-link` | `link_weather` |
| DELETE | `/api/farms/{identifier}/weather-link` | `unlink_weather` |

### `v3_shared_work_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/farm-workspace/service-requests` | `services` |
| POST | `/api/farm-workspace/service-requests` | `create_service` |
| PATCH | `/api/farm-workspace/service-requests/{sid}` | `edit_service` |
| GET | `/api/farm-workspace/groups` | `groups` |
| POST | `/api/farm-workspace/groups` | `create_group` |
| POST | `/api/farm-workspace/groups/join` | `join_group` |
| GET | `/api/farm-workspace/groups/{gid}/members` | `members` |
| DELETE | `/api/farm-workspace/groups/{gid}/members/{person}` | `revoke_member` |
| POST | `/api/farm-workspace/groups/{gid}/invites` | `create_invite` |
| GET | `/api/farm-workspace/groups/{gid}/invites` | `invites` |
| DELETE | `/api/farm-workspace/groups/{gid}/invites/{iid}` | `revoke_invite` |
| GET | `/api/farm-workspace/groups/{gid}/tasks` | `tasks` |
| POST | `/api/farm-workspace/groups/{gid}/tasks` | `create_task` |
| PATCH | `/api/farm-workspace/groups/{gid}/tasks/{tid}` | `edit_task` |

### `v3_farm_workflow_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/farm-workspace/ledger` | `ledger` |
| POST | `/api/farm-workspace/ledger` | `add_ledger` |
| PATCH | `/api/farm-workspace/ledger/{identifier}` | `edit_ledger` |
| DELETE | `/api/farm-workspace/ledger/{identifier}` | `remove_ledger` |
| GET | `/api/farm-workspace/cases` | `cases` |
| POST | `/api/farm-workspace/cases` | `add_case` |
| PATCH | `/api/farm-workspace/cases/{identifier}` | `edit_case` |
| GET | `/api/farm-workspace/cases/{identifier}/notes` | `case_notes` |
| POST | `/api/farm-workspace/cases/{identifier}/notes` | `add_note` |
| GET | `/api/farm-workspace/missions` | `missions` |
| POST | `/api/farm-workspace/missions` | `add_mission` |
| PATCH | `/api/farm-workspace/missions/{identifier}` | `edit_mission` |
| GET | `/api/farm-workspace/missions/{identifier}/receipts` | `receipts` |
| GET | `/api/farm-workspace/memories` | `memories` |
| PATCH | `/api/farm-workspace/memories/{identifier}` | `correct_memory` |
| DELETE | `/api/farm-workspace/memories/{identifier}` | `forget_memory` |
| GET | `/api/farm-workspace/timeline` | `timeline` |
| GET | `/api/farm-workspace/today` | `today` |
| GET | `/api/farm-workspace/weather-brief` | `weather_brief` |

### `assistant_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/assistant/catalog` | `catalog` |
| POST | `/api/assistant/sessions` | `new_session` |
| POST | `/api/assistant/sessions/{sid}/revoke` | `revoke_session` |
| GET | `/api/assistant/sessions/{sid}` | `session` |
| GET | `/api/assistant/sessions/{sid}/events` | `replay_events` |
| POST | `/api/assistant/sessions/{sid}/answers/{message_id}/rewrite` | `rewrite_answer` |
| POST | `/api/assistant/sessions/{sid}/attachments` | `upload` |
| POST | `/api/assistant/sessions/{sid}/run` | `run` |
| POST | `/api/assistant/sessions/{sid}/reset` | `reset` |
| POST | `/api/assistant/sessions/{sid}/restore/{cid}` | `restore` |
| GET | `/api/assistant/sessions/{sid}/files/{file_id}` | `download` |
| PATCH | `/api/assistant/sessions/{sid}/tasks/{tid}` | `edit_task` |
| DELETE | `/api/assistant/sessions/{sid}/tasks/{tid}` | `delete_task` |
| POST | `/api/assistant/sessions/{sid}/tasks/{tid}/restore` | `restore_task` |
| GET | `/api/assistant/station/{station_id}` | `station_data` |
| POST | `/api/assistant/sessions/{sid}/inspect/{tool}` | `inspect_tool` |
| POST | `/api/assistant/sessions/{sid}/attachments-json` | `upload_encoded` |

### `disease_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/disease/detect` | `detect_crop_disease` |
| POST | `/api/disease/detect` | `detect_crop_disease` |
| POST | `/disease/detect-base64` | `detect_crop_disease_base64` |
| POST | `/api/disease/detect-base64` | `detect_crop_disease_base64` |
| GET | `/disease/info` | `get_pathology_catalog` |
| GET | `/api/disease/info` | `get_pathology_catalog` |

## Legacy lane

These routers are registered only when the canonical data mode is disabled. The assistant and crop-disease routers also appear in the canonical lane.

### `core_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/` | `root` |
| GET | `/health` | `health` |
| GET | `/api/llm-pool` | `llm_pool_status` |

### `sensor_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/sensors/stations` | `list_stations` |
| GET | `/api/sensors/latest/{station_id}` | `latest_reading` |
| GET | `/api/sensors/history/{station_id}` | `history` |
| POST | `/api/sensors/data` | `ingest_sensor_data_nested` |
| POST | `/api/sensors/trends/store` | `store_trends` |
| POST | `/api/sensors/ingest` | `ingest_flat` |

### `auth_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/auth/live-otps` | `get_live_otps` |
| DELETE | `/api/auth/live-otps` | `clear_live_otps` |
| POST | `/api/auth/record-live-otp` | `record_live_otp` |
| POST | `/api/auth/send-otp` | `send_otp` |
| POST | `/api/auth/verify-otp` | `verify_otp` |
| POST | `/api/auth/signup` | `signup` |

### `chat_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/chat` | `chat` |
| POST | `/api/weather-insight` | `weather_insight` |
| POST | `/api/agriculture/qa` | `agriculture_qa` |
| POST | `/api/chat/overview` | `get_overview` |
| POST | `/api/chat/overview/ask` | `ask_overview_followup` |

### `assistant_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/assistant/catalog` | `catalog` |
| POST | `/api/assistant/sessions` | `new_session` |
| POST | `/api/assistant/sessions/{sid}/revoke` | `revoke_session` |
| GET | `/api/assistant/sessions/{sid}` | `session` |
| GET | `/api/assistant/sessions/{sid}/events` | `replay_events` |
| POST | `/api/assistant/sessions/{sid}/answers/{message_id}/rewrite` | `rewrite_answer` |
| POST | `/api/assistant/sessions/{sid}/attachments` | `upload` |
| POST | `/api/assistant/sessions/{sid}/run` | `run` |
| POST | `/api/assistant/sessions/{sid}/reset` | `reset` |
| POST | `/api/assistant/sessions/{sid}/restore/{cid}` | `restore` |
| GET | `/api/assistant/sessions/{sid}/files/{file_id}` | `download` |
| PATCH | `/api/assistant/sessions/{sid}/tasks/{tid}` | `edit_task` |
| DELETE | `/api/assistant/sessions/{sid}/tasks/{tid}` | `delete_task` |
| POST | `/api/assistant/sessions/{sid}/tasks/{tid}/restore` | `restore_task` |
| GET | `/api/assistant/station/{station_id}` | `station_data` |
| POST | `/api/assistant/sessions/{sid}/inspect/{tool}` | `inspect_tool` |
| POST | `/api/assistant/sessions/{sid}/attachments-json` | `upload_encoded` |

### `fpga_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/fpga/status` | `fpga_status` |
| POST | `/api/fpga/fusion` | `sensor_fusion` |
| POST | `/api/fpga/rain-predict` | `rain_predict` |
| POST | `/api/fpga/combined-analysis` | `combined_analysis` |
| POST | `/api/fpga/test` | `fpga_test` |

### `advisor_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/advisor/insights` | `advisor_insights` |

### `mandi_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/mandi/rates` | `mandi_rates` |
| GET | `/api/mandi/commodities` | `commodity_list` |
| GET | `/api/mandi/history` | `mandi_history` |
| GET | `/api/mandi/msp` | `msp_history` |

### `webhook_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/webhook/whatsapp` | `whatsapp_get` |
| POST | `/webhook/whatsapp` | `whatsapp_webhook` |
| POST | `/webhook/whatsapp/farm-qa` | `farm_qa_webhook` |

### `voice_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/vapi/call` | `trigger_vapi_call` |
| POST | `/api/speech/transcribe` | `transcribe_audio` |
| POST | `/api/speech/synthesize` | `synthesize_speech` |
| POST | `/api/translate` | `translate_texts` |
| POST | `/api/profile/voice-update` | `voice_profile_update` |
| POST | `/api/voice/process` | `voice_process` |

### `voice_agent.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/api/voice/agent` | `voice_agent` |

### `profile_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/schemes` | `get_schemes_catalog` |
| GET | `/api/schemes/{scheme_id}` | `get_scheme_detail` |
| GET | `/api/profile` | `get_profile` |
| POST | `/api/profile/save` | `save_profile` |
| GET | `/api/schemes/recommendations` | `scheme_recommendations` |

### `marketplace_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/marketplace/farmers` | `get_all_farmers` |
| POST | `/api/marketplace/match` | `marketplace_match` |
| POST | `/api/marketplace/circular-barter` | `circular_barter` |
| POST | `/api/marketplace/negotiate` | `negotiate_deal` |
| GET | `/api/marketplace/pooling` | `geographical_pooling` |

### `disease_routes.py`

| Method | Path | Handler |
| --- | --- | --- |
| POST | `/disease/detect` | `detect_crop_disease` |
| POST | `/api/disease/detect` | `detect_crop_disease` |
| POST | `/disease/detect-base64` | `detect_crop_disease_base64` |
| POST | `/api/disease/detect-base64` | `detect_crop_disease_base64` |
| GET | `/disease/info` | `get_pathology_catalog` |
| GET | `/api/disease/info` | `get_pathology_catalog` |
