# API overview

The service entry point is `skyview.main:app`. Canonical v3 mode registers the routers shown in the [endpoint inventory](endpoints.md). `/docs` and `/openapi.json` expose the running service's request and response schema; they are the first place to inspect exact field definitions after starting the API.

## Identity and access

The assistant opens a session with `POST /api/assistant/sessions`. Requests for private assistant and farm data use `Authorization: Bearer <session capability>` and `X-Assistant-Session: <session id>`. In the deployed live mode, session creation requires a verified Firebase Phone ID token. `skyview/assistant/auth.py` fails closed when verification is unavailable. Session revocation invalidates the capability while preserving owned history.

The server resolves farmer scope; a query parameter or JSON field cannot select an arbitrary owner. PostgreSQL transaction scope and row policies protect private records. Review actions use row versions and stable execution keys to reject stale or conflicting writes. Uploads, file previews and downloads have owner and size boundaries.

## Status, transport and caching

`GET /health` reports API/database readiness. `GET /api/data/status` reports data mode and source state. Assistant runs stream event data through `POST /api/assistant/sessions/{sid}/run`; the streaming path bypasses response compression so incremental events are delivered promptly. Protected responses set `Cache-Control: no-store`. The browser has a bounded, owner-scoped cache for selected reads and invalidates it after mutations.

Canonical and classic compatibility routes are separate registration lanes in `skyview/main.py`. A route listed for the legacy lane is not necessarily present in canonical mode. Hardware enrollment or a visible station scene does not by itself establish connected live telemetry. External providers and WhatsApp require server-side configuration. See [channels](websocket-and-webhooks.md) and [operations](../operations.md).
