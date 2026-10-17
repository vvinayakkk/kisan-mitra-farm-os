# Operation and verification

## Workstation start

From the repository root, copy `.env.docker.example` to ignored `.env.docker`, set distinct URL-safe PostgreSQL passwords, then run `docker compose --env-file .env.docker up --build`. The stack starts PostgreSQL 16, a one-time schema initializer, FastAPI and the Nginx frontend. Open `http://127.0.0.1:5173/workspace`. The container network proxies API requests through the web origin. `docker compose --env-file .env.docker down` stops services but preserves volumes; `down --volumes` deletes local data. Native Python/Node instructions are in [local operation](local-setup.md).

## Configuration

Keep provider and account secrets server-side in an ignored environment file or managed secret store. `skyview/.env.example` lists optional legacy-provider variables without credential values. Canonical mode uses `SKYVIEW_DATA_MODE`, `V3_DATABASE_URL` and storage paths. Live session creation additionally needs `V3_AUTH_ISSUER`, `V3_AUTH_AUDIENCE` and `V3_AUTH_JWKS_URL`. AI needs configured Groq keys or Gemini credentials; speech and calls need their respective provider keys; public mandi ingestion needs a data.gov.in key; WhatsApp needs Twilio credentials and a public HTTPS callback origin. Leave an integration disabled when its credentials or approved access are absent.

The frontend takes its API origin from `VITE_API_URL` for separate development hosting; same-origin proxying avoids a browser cross-origin dependency in Docker. Mobile uses `API_BASE_URL` through Flutter `--dart-define`. Do not put secrets into any `VITE_` or Dart define field because those are packaged into client output.

## Background work and source health

`skyview/data/v3/worker.py` starts with the canonical API when enabled. A PostgreSQL advisory lease prevents duplicate recurring jobs across API processes. Weather and market calls have request bounds and backoff; provider outages persist in source-health state. Regional weather is a grid product. Exact private plot coordinates are not sent to public weather providers; consented links use a coarse grid. `GET /health`, `GET /api/data/status` and `data_platform/v3/check_local.py` help separate service health from external-source freshness. `V3_BACKGROUND_WORKER=false` disables the local recurring loop for environments with an external scheduler.

## Backup and recovery

Back up the PostgreSQL database together with raw payload and generated artifact directories. A database-only backup restores metadata without file bytes. Restore into a separately named database, verify owner isolation and file checksums, then switch traffic. Apply `data_platform/v3/layout.py`'s ordered runtime migrations to an existing database; do not reapply the base DDL as a reset. Stable event, message and action IDs protect replay after an interrupted process.

## Hosted deployment handoff

The backend image runs as a non-root user and honors `PORT`; the frontend image builds the SPA and serves it through Nginx. The [GCP deployment runbook](gcp-deployment.md) covers Firebase sign-in, the external PostgreSQL data gate, durable files, scheduled refresh, signed Twilio ingress, and Cloud Tasks delivery. Cloud Run's filesystem and scale-to-zero behavior do not provide durable file storage or reliable recurring work by themselves. No CI/CD or GCP resources are provisioned by this repository.

## Checks

Run backend checks using the dedicated test database, never a working farmer database. The [local guide](local-setup.md) gives the preparation command. Frontend checks are `npx tsc --noEmit -p tsconfig.app.json`, `npx vitest run` and `npm run build` from `frontend/`. Database tests cover ownership, migration inventory, ingestion, market reads, assistant approvals, exchange and worker behavior. Mobile source can be checked with `flutter analyze` and `flutter test` when the Flutter SDK is installed; there is no checked-in APK or automated release workflow.
