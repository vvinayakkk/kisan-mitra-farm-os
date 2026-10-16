# Contributing to Kisan Mitra Farm OS

Kisan Mitra is built by init.io for the AI Builder Cup and is licensed under the repository's [MIT License](LICENSE). Keep a change focused on a farmer-visible behavior or a specific platform contract. Use a short-lived branch and a Conventional Commit subject such as `fix(markets): preserve variety in history links`.

Read the [architecture](docs/architecture.md), [feature map](docs/features.md), [API inventory](docs/api/endpoints.md) and [data model](docs/data-model.md) before changing a cross-cutting path. If a route, skill, schema or provider contract changes, update its corresponding documentation and tests in the same change. The canonical backend path uses PostgreSQL v3; classic views have compatibility routes. Do not introduce a second owner or source-of-truth path for a convenience UI.

Run the checks that cover the change. The full backend wrapper is `.venv/bin/python data_platform/v3/test_backend.py` after preparing the dedicated test database. Frontend checks from `frontend/` are `npx tsc --noEmit -p tsconfig.app.json`, `npx vitest run` and `npm run build`. Use `flutter analyze` and `flutter test` from `mobile/` when changing Flutter code. HLS source requires its separate toolchain. Report any check you could not run rather than implying it passed.

Protect farmer ownership, consent, source timestamps and review boundaries. A new write needs exact reviewed arguments and replay behavior; a new external connector needs licensing/access, units, freshness and outage handling. Do not commit provider keys, local databases, recordings, built APKs, raw media or generated farm files. Describe the farmer-facing effect, migration impact, verification and remaining limitations in the pull request.
