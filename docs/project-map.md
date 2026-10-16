# Repository map

| Path | Responsibility |
| --- | --- |
| `frontend/src/pages/` | Classic pages and the Farm OS route shell. |
| `frontend/src/components/assistant/` | Chat, calendar, station embedding, weather, exchange, notebook, profile and page helpers. |
| `frontend/src/lib/` | Typed API clients, cache, language and export helpers. |
| `skyview/main.py` | FastAPI entry point and data-mode router registration. |
| `skyview/api/` | Canonical, compatibility, voice, WhatsApp, exchange and classic routers. |
| `skyview/assistant/` | Agent loop, provider routing, skills, tools, memory, approvals and file creation. |
| `skyview/data/v3/` | PostgreSQL connection scope, repositories, ingestion and leased worker. |
| `data_platform/v3/sql/` | Base schema, ordered additive migrations and stored read contracts. |
| `data_platform/v3/catalog/` | Schema and source catalogs. |
| `data_platform/v3/` | Provisioning, validation and operational tools. |
| `mobile/` | Flutter source project; APK output stays in ignored `mobile/build/`. |
| `hardware/` | Device and HLS source. |
| `infra/` | Container build definitions and Nginx configuration. |
| `tests/` | Backend, database, assistant and contract tests. |
| `docs/` | Architecture, interface, API, data, operations and build guides. |

The repository root owns `docker-compose.yml`, `README.md`, `CONTRIBUTING.md` and the MIT `LICENSE`. Secrets, local databases, raw media, built APKs and generated outputs are outside Git.
