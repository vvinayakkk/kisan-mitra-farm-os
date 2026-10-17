# Mitra administration — web workspace

Open `/control`; old `/admin.html`, `/admin/index.html` and `/db` redirect there. This replaces the legacy static page and removes its hardcoded-password login, fabricated tokens and unauthenticated user CRUD.

## Available controls

43 installed resources are supported by the explicit registry in `skyview/admin/admin_routes.py`: 34 allow editing and 9 are read-only. The UI discovers which resources exist in the selected database; missing modules are not fabricated.

- Live overview counts; farmer search, profile editing and linked farms, plots, tasks, expenses, conversations and plans.
- Account suspension revokes all current assistant sessions in the same transaction. Reactivation does not restore revoked sessions. Session creation locks the account against concurrent suspension. Editing contact data clears contact verification.
- Crops, varieties, regions, markets, price observations, MSP, guides, schemes, weather, stations, soil, exchange listings, service and ledger data.
- Single-record create/update, selected-record bulk update/delete, CSV create import (1–100 rows / 500 KB), CSV column templates, and current-page CSV export with spreadsheet formula protection.
- Read-only conversation/agent/task/exchange activity, source health, ingest history, dataset provenance and generated plans/proposals.
- Every write requires a reason, a real-database dry run and typed confirmation. Preview writes are rolled back. Preview expires after ten minutes; commit revalidates constraints, authorization and optimistic record hashes under row locks. A failed batch rolls back completely. Repeated commit is idempotent.
- Audit entries record actor, role, resource, reason, affected keys/fields and before/after hashes. No API to edit/delete the audit. Profile snapshots are not duplicated there.
- Viewer: browse/export; editor: create/update; owner: create/update/delete. All roles require a verified identity and a server allowlist. Farmer sessions and local-storage flags confer no admin access.

## Deliberate boundaries

Accounts originate through verified phone registration, not fabricated administrator-created identities. Administrator grants are deployment-owned configuration, never editable through a farmer profile. Identity bindings, ownership, provenance IDs, generated columns, verification flags and row versions cannot be overwritten through generic forms. Linked non-owner fields (such as a region) can be corrected subject to database constraints.

Deletes never silently cascade; restrictive FK links block deletion, and resources with cascading relationships reject deletion entirely. Use suspension for a farmer with linked history. A full account-erasure/retention workflow is not implemented here. Farmer consent and generated plan approvals remain in the farmer workflow. No credentials, OTPs, session state, raw prompts, device commands or unrestricted SQL are exposed. This is a product-data administration surface, not a GCP console.

Exports cover the visible page (25 records), explicitly labeled. Bulk selection is page-local. There is no unattended import queue or offline mutation queue. Private data is fetched with bearer authorization and `no-store`, held in memory, and cleared on identity changes. The admin API is excluded from the existing service-worker cache.

## Deployment — completed 2026-10-17

This release requires **both web and backend deployment**, a reviewed SQL migration, and administrator configuration. No APK update is required. The normal app remains usable if administrator configuration is absent; admin data requests fail closed.

1. Back up the target database and review `data_platform/v3/sql/admin-runtime.sql`. Apply it manually as a database owner after the existing runtime migrations. It is intentionally NOT added to automatic runtime provisioning. It creates a NOLOGIN, NOSUPERUSER, NOBYPASSRLS `sv3_admin` role and explicit policies/grants only on the listed resources. Admin audit/preview tables have forced RLS. Existing tenant policies are retained. There is no database-wide write grant or RLS bypass. The local tests apply this inside a rollback-only transaction.
2. Provision a separate least-privilege database login that can SET ROLE `sv3_admin`. Do not grant this role to the normal application login. Store its connection string in Secret Manager as `ADMIN_DATABASE_URL`; use the matching v3 database and TLS (`sslmode=require` or stronger remotely). Revoke the credential independently when necessary.
3. Set `ADMIN_IDENTITIES` to a server-owned JSON mapping of verified `auth_subject` hashes to `owner`, `editor`, or `viewer`. For Firebase, the identity is `oidc:` + SHA-256 of `https://securetoken.google.com/<project-id>` + a NUL byte + the actual Firebase UID. Derive this from a verified account, never a supplied farmer ID, phone number or client flag. An empty mapping grants nobody access. Use the existing production Firebase project; admin checks include Firebase revocation/disabled-account verification. OIDC deployments use their configured verified issuer/subject; revocation semantics then depend on that provider/token expiry.
4. Deploy the backend and web build together and verify an authorized owner, an unauthorized farmer, all three roles, a harmless preview/commit, audit creation and session suspension. Production credentials, live writes and Firebase SMS delivery were not exercised by local review.
5. Preview payloads are cleared after commit; uncommitted previews expire after ten minutes and are pruned on a subsequent preview after one day. If no admins use the panel they remain until the next cleanup. Add a scheduled retention cleanup if a strict deletion deadline is required. Audit retention/backup is an operator policy.

Production activation is complete on the existing Cloud Run service and Firebase Hosting site. The existing 1 CPU / 512 MiB / maximum 2 instances configuration is retained. Ordinary compute, storage, network, database and authentication usage remains metered; no free-deployment guarantee is implied.

## Verification

- 19 backend admin tests using real local PostgreSQL for rollback, commit, replay, stale changes, constraint failures, linked deletes, role isolation, protected fields, readonly history, suspension and atomic races. All migration DDL and record changes roll back at fixture teardown.
- 12 existing authentication and main-app admin access tests; 21 PostgreSQL session/storage contracts.
- Full frontend suite: 253 tests; TypeScript and production build.
- Playwright: profile edit → preview → typed confirmation → success; bulk update; CSV import preview; audit; 390px containment. Review screenshots use synthetic records and schema metadata, not production farmer data.

Production release: backend revision `kisan-mitra-api-00005-yus` serves 100% of traffic, with image digest `sha256:5c8f8c097dad3af47a240eecb9b3887547d6fd2c1dd028f95795c2b0eba5e643`. Firebase Hosting release: `1792259360430000`. Application source commit: `50b06ccdd69893b15ac16338e782c3304e26ca88`.

Before migration, the live database was backed up and the PostgreSQL archive catalog validated. The separate admin login is NOBYPASSRLS and the ordinary app login has no admin membership. One existing, verified Firebase account was configured as owner in Secret Manager version 6. The backend service account received only `firebaseauth.users.get` through a custom role for revocation checks.

Live read-only checks discovered 43 resources, 34 editable, and existing counts of 402 farmers, 400 farms, 2,401 tasks and 1,201 exchange listings. Recursive schema discovery was replaced with batched reflection; the combined local-to-production resource/count check completed in 3.20 seconds. All 19 admin integration tests passed again after the fix.

Canary and production checks passed: healthy live database, unauthenticated admin requests rejected, malformed bearer token rejected, allowed website CORS. No error-level startup logs were reported during the canary check. The live `/control` sign-in page rendered without JavaScript errors in a fresh browser context; `/`, `/control`, `/onboarding`, `/workspace` and entry JS/CSS exactly matched the tested build. No production customer records were changed for smoke testing.

Owner OTP sign-in, authenticated production admin CRUD, physical APK installation, audible TTS and live voice captions were not exercised in this rollout. CRUD/authorization behavior was covered by the local integration suite; these limits must not be represented as end-to-end production verification.

APK v1.1.3 (version code 5) is published at GitHub Releases with matching upload SHA-256 and the existing signing certificate; see `v1.1.3.md`. The admin panel remains web-only.

Rollback references: previous backend revision `kisan-mitra-api-00004-6cn` and previous Hosting version `8289d74f7d0b0dbf`. The additive database migration does not need to be undone to restore those versions. Deployment used the immutable previous image as its base with current application directories replaced, because dependencies and Dockerfile are unchanged and the local package mirror was unavailable.
