# GCP deployment

The production topology is Firebase Hosting for React, a scale-to-zero Cloud Run API in `asia-south1`, and Neon PostgreSQL plus private object storage in Singapore. The original workstation database and its lossless backup remain intact. The deployed database is a compact, verified copy: older price-history density and distant projections were reduced, while all other table rows were copied exactly. Row counts and order-independent signatures matched across 103 tables.

## Project and cost controls

- Google Cloud project: `project-0b9b4009-1644-4477-aec`. Use the existing free-trial billing account only; never upgrade it.
- Cloud Run: one vCPU, 512 MiB, request-based CPU allocation, minimum zero instances, maximum two. Measure memory before increasing it.
- Billing budget: `kisan-mitra-trial-guard`, ₹28,000, with email thresholds at 10, 25, 50, 75, and 90 percent. Budget alerts do not stop spending.
- Artifact Registry: keep only five recent service images. The first 0.5 GiB is free; excess storage can consume trial credit.
- Neon: free plan, pooled TLS runtime connection with the limited `skyview_runtime` role. Database and private bucket do not use Google Cloud credit.
- Firebase Phone Authentication: India-only SMS region policy. Use configured fictional test numbers during development. Real SMS is billed by Firebase; add App Check and monitor authentication quotas before a wider release.

## Data and files

`SKYVIEW_DATA_MODE=v3_live` requires database `skyview_v3_live`. The deployed copy was restored from a compact dump and checked using `data_platform/v3/verify_copy.py`. Preserve the full local backup and checksums; never seed or truncate production during deploy. Use `.v3-data/neon-runtime.url` for the API, not the owner URL. Keep pool size at two with no overflow and `sslmode=require`.

The private `farm-files` bucket holds generated documents, available attachments, and source JSON. Existing database references were migrated using `data_platform/v3/migrate_assets.py`. Several source records can refer to one stored object. Four hundred legacy attachment references have no physical source file and remain unresolved. New files are uploaded before their object URI is committed. Cloud Run caches downloads under `/tmp/kisan-mitra` only for the lifetime of its instance. `ASSISTANT_S3_BUCKET`, `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` are required at startup.

## Secrets and identity

The root `Dockerfile` starts `skyview.bootstrap`, which loads one JSON secret from `APP_SECRET_ENV` before importing API settings. Put the Neon runtime URL, bucket credentials, and provider API keys in this Secret Manager value. Never include this JSON in Git, source builds, image layers, or frontend assets. Keep only public Firebase Web config and the Cloud Run API URL in the frontend build environment. The backend uses `FIREBASE_PROJECT_ID` to validate Firebase ID tokens and requires a verified phone provider before issuing a farm session.

For Firebase Hosting, `firebase.json` serves `frontend/dist` with SPA rewrites. Build using `npm ci && npm run build`. Set `VITE_API_URL` to the HTTPS Cloud Run URL and `CORS_ORIGINS` to the exact Hosting origin. Register the Hosting domain in Firebase Authentication's authorized domains. Test the configured Firebase test-number flow before sending a real SMS.

Current origins:

- Website: `https://growwithmitra.web.app`
- Original Hosting address remains available: `https://project-0b9b4009-1644-4477-aec.web.app`
- API: `https://kisan-mitra-api-344920654513.asia-south1.run.app`
- Scheduled refresh: `kisan-mitra-refresh` in `asia-south1`, every two hours, with a dedicated OIDC identity.
- WhatsApp queue: `kisan-mitra-whatsapp` in `asia-south1`, one dispatch per second and one concurrent request.

## Background work and WhatsApp

Set `V3_BACKGROUND_WORKER=false`. A Cloud Scheduler request to `/internal/sources/refresh` should use OIDC from a dedicated service account. The endpoint validates identity and uses a PostgreSQL advisory lease so updates can run while the API scales to zero. Do not run an always-on background loop.

Twilio requires `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`, and `SKYVIEW_PUBLIC_URL`. Configure Twilio's inbound webhook as `<public-url>/webhook/whatsapp` and status callback as `<public-url>/webhook/whatsapp/status`. Configure a Cloud Tasks queue in `asia-south1`, `WHATSAPP_TASK_QUEUE`, and `WHATSAPP_TASK_SERVICE_ACCOUNT`. Signed inbound requests validate the Twilio signature and recipient, deduplicate the message SID, and enqueue one job. The drain endpoint validates its task service identity. Documents and voice media use expiring signed URLs from the stable public API URL.

The current Twilio One Console limited trial accepts a custom inbound webhook for its verified test phone. It permits outbound API calls only with Twilio-provided `ContentSid` templates and does not support direct TwiML replies. The agent's free-form answers, documents, charts, and voice replies therefore cannot be delivered through this trial. Keep WhatsApp marked as test-only until a sender with those capabilities is available; do not equate a saved webhook with end-to-end delivery. This restriction is separate from the GCP trial and its credit.

## Release checks

1. Confirm the hosted database health check, table parity report, and private bucket retrieval. Keep the lossless local backup.
2. Run backend tests, frontend tests and production build, then deploy the Cloud Run revision with minimum zero and maximum two instances. Check `/health` and authentication rejection paths.
3. Build and publish Firebase Hosting with the API URL. Test test-number sign-in, chat, profile, files, exchange, weather, old and new routes, and mobile viewport.
4. Enable and test scheduled refreshes and Cloud Tasks, then configure Twilio webhooks. Exercise text, photo, document, and voice-note paths and delivery receipts.
5. Build the Android application against the same HTTPS API, use a private release keystore, and attach the APK to a GitHub Release. An installation check and a physical-phone smoke test are advisable before submission.
6. Inspect budget alerts, Cloud Run scale settings, image cleanup, Neon storage usage, failed jobs, and provider quotas. Roll back by redeploying the prior Cloud Run revision and Hosting release if required.


### Branded Firebase Hosting site

The primary public address is `https://growwithmitra.web.app` (Firebase site ID `growwithmitra` in the existing project). The site also has `https://growwithmitra.firebaseapp.com`. These are Firebase-provided subdomains, not a purchased custom domain. Hosting usage still counts against the existing project quotas and billing.

`firebase.json` targets the branded site. With the REST deployment helper, use:

```bash
.venv/bin/python infra/deploy_firebase_hosting.py \
  --project project-0b9b4009-1644-4477-aec \
  --site growwithmitra --directory frontend/dist
```

To update the original address as well, run the same helper with `--site project-0b9b4009-1644-4477-aec`. Each site has its own release history. Both new hostnames are registered in Firebase Authentication's authorized domains and the backend's exact-origin CORS list, while the original origins remain allowed. `FRONTEND_URL` points to the branded address. The API URL and Android package remain unchanged.

Browser sign-in state, caches and unfinished local drafts are scoped to each origin. Users may need to sign in once at the new address; saved server-side profiles and records remain attached to the same account. Keep the original address available for users with unfinished local drafts.
