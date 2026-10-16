# Configuration inventory

This inventory is extracted from literal `os.getenv` calls in the backend and data-platform Python source. It identifies configuration entry points; it does not contain credentials. Some values are used only in the classic lane, optional provider adapters or local tools. A client-side `VITE_` or Flutter `--dart-define` value is bundled into the app and must never contain a secret.

| Variable | Code path | Source default |
| --- | --- | --- |
| `API_HOST` | `skyview/utils/config.py` | `0.0.0.0` |
| `API_PORT` | `skyview/api/voice_agent.py` | `8000` |
| `API_WORKERS` | `skyview/utils/config.py` | `4` |
| `ASSISTANT_DATA_URL` | `skyview/assistant/data_sources.py` | `` |
| `ASSISTANT_MODEL` | `skyview/assistant/provider.py` | `openai/gpt-oss-120b` |
| `ASSISTANT_STORAGE_DIR` | `skyview/assistant/store.py` | `` |
| `CORS_ORIGINS` | `skyview/utils/config.py` | `http://localhost:5173,http://localhost:3000,http://127.` |
| `CROP_VISION_MODEL` | `skyview/agents/disease_service.py` | `qwen/qwen3.8-27b` |
| `DATABASE_URL` | `skyview/utils/config.py` | `` |
| `DATAGOV_API_KEY` | `skyview/data/v3/ingestion.py` | `` |
| `DATA_GOV_API_KEY` | `skyview/data/v3/ingestion.py` | `` |
| `DB_ECHO` | `skyview/utils/config.py` | `False` |
| `DB_FALLBACK_SQLITE` | `skyview/utils/config.py` | `sqlite:///sensor_data.db` |
| `DB_MAX_OVERFLOW` | `skyview/utils/config.py` | `10` |
| `DB_POOL_PRE_PING` | `skyview/utils/config.py` | `True` |
| `DB_POOL_SIZE` | `skyview/utils/config.py` | `5` |
| `DEBUG` | `skyview/utils/config.py` | `False` |
| `DOCUMENT_VISION_MODEL` | `skyview/assistant/document_vision.py` | `` |
| `ENABLE_FPGA` | `skyview/utils/config.py` | `False` |
| `ENABLE_LLM_WORKFLOW` | `skyview/utils/config.py` | `True` |
| `ENABLE_MQTT` | `skyview/utils/config.py` | `True` |
| `FPGA_PORT` | `skyview/utils/config.py` | `COM4` |
| `FRONTEND_URL` | `skyview/utils/config.py` | `http://localhost:5173` |
| `GEMINI_API_KEY` | `skyview/agents/disease_service.py` | `` |
| `GEMINI_MODEL` | `skyview/utils/config.py` | `gemini-2.5-flash` |
| `GROQ_API_KEY` | `skyview/utils/config.py` | `` |
| `GROQ_API_KEYS` | `skyview/utils/config.py` | `` |
| `LLM_MODEL` | `skyview/utils/config.py` | `qwen/qwen3.8-27b` |
| `LLM_TIMEOUT` | `skyview/utils/config.py` | `30` |
| `LOG_FORMAT` | `skyview/utils/config.py` | `%(asctime)s [%(name)s] %(levelname)s: %(message)s` |
| `LOG_LEVEL` | `skyview/utils/config.py` | `INFO` |
| `MANDI_RESOURCE_ID` | `skyview/utils/config.py` | `9ef84268-d588-465a-a308-a864a43d0070` |
| `MQTT_BROKER` | `skyview/utils/config.py` | `localhost` |
| `MQTT_KEEPALIVE` | `skyview/utils/config.py` | `60` |
| `MQTT_PASSWORD` | `skyview/utils/config.py` | `` |
| `MQTT_PORT` | `skyview/utils/config.py` | `1883` |
| `MQTT_RECONNECT_DELAY` | `skyview/utils/config.py` | `5` |
| `MQTT_USERNAME` | `skyview/utils/config.py` | `` |
| `OGD_API_KEY` | `skyview/data/v3/ingestion.py` | `` |
| `PGDATABASE` | `data_platform/v3/bootstrap.py` | `` |
| `PGHOST` | `data_platform/v3/bootstrap.py` | `127.0.0.1` |
| `PGPASSWORD` | `data_platform/v3/bootstrap.py` | `` |
| `PGPORT` | `data_platform/v3/bootstrap.py` | `5432` |
| `PGUSER` | `data_platform/v3/bootstrap.py` | `postgres` |
| `PORT` | `skyview/api/voice_agent.py` | `` |
| `SARVAM_AI_API_KEY` | `skyview/utils/config.py` | `` |
| `SARVAM_TTS_MODEL` | `skyview/api/v3_voice_routes.py` | `bulbul:v4-flash` |
| `SENSOR_DATA_MIN_INTERVAL` | `skyview/utils/config.py` | `8` |
| `SKYVIEW_DATA_MODE` | `skyview/assistant/v3_store.py` | `` |
| `SKYVIEW_PUBLIC_URL` | `skyview/api/v3_whatsapp_routes.py` | `` |
| `STATION_ID` | `skyview/utils/config.py` | `WS01` |
| `TWILIO_ACCOUNT_SID` | `skyview/utils/config.py` | `` |
| `TWILIO_ALERT_RECIPIENT` | `skyview/utils/config.py` | `` |
| `TWILIO_AUTH_TOKEN` | `skyview/utils/config.py` | `` |
| `TWILIO_WHATSAPP_NUMBER` | `skyview/utils/config.py` | `` |
| `V3_APP_PASSWORD` | `data_platform/v3/bootstrap.py` | `` |
| `V3_AUTH_AUDIENCE` | `skyview/assistant/auth.py` | `` |
| `V3_AUTH_ISSUER` | `skyview/assistant/auth.py` | `` |
| `V3_AUTH_JWKS_URL` | `skyview/assistant/auth.py` | `` |
| `V3_BACKGROUND_WORKER` | `skyview/data/v3/worker.py` | `true` |
| `V3_DATABASE_URL` | `skyview/data/v3/db.py` | `` |
| `V3_DEMO_FARMER_KEY` | `data_platform/v3/check_local.py` | `` |
| `V3_INGEST_LOCATION_KEY` | `skyview/data/v3/worker.py` | `` |
| `V3_RAW_DIR` | `skyview/data/v3/ingestion.py` | `.v3-data/raw` |
| `V3_RAW_STORAGE_DIR` | `skyview/data/v3/ingestion.py` | `` |
| `VAPI_AI_API_KEY` | `skyview/utils/config.py` | `` |
| `VAPI_ASSISTANT_ID` | `skyview/utils/config.py` | `default_assistant_id` |
| `WHATSAPP_WEBHOOK_URL` | `skyview/api/v3_whatsapp_routes.py` | `` |

For Docker, start with `.env.docker.example`. For native server settings, use ignored environment files or a secret store. `skyview/.env.example` lists the common provider variables with empty values. Canonical database credentials belong in `V3_DATABASE_URL` or the provisioner-owned `.v3-data/runtime.env`; do not commit either. Live account verification requires the issuer, audience and JWKS settings. Review [operations](operations.md) for worker, backup and deployment boundaries.
