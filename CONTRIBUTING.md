# Contributing to Kisan Mitra Farm OS

Kisan Mitra is built by init.io for the AI Builder Cup. This private competition repository uses focused changes that reviewers can understand before a later public release.

## Make a focused change

Describe the farmer problem, work on a short-lived branch and use a Conventional Commit subject such as `fix(markets): preserve variety when opening history`. Keep backend contracts, frontend behavior and documentation aligned. Add tests for meaningful behavior and report the local checks you ran.

## Local checks

```bash
.venv/bin/python data_platform/v3/test_backend.py
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx vitest run
npm run build
```

## Source evidence

Do not commit keys, local databases, generated artifacts, private farmer data or recordings. Keep illustrative prices and field cases separate from verified observations. A provider URL alone is not proof of a working integration: include source, license, units, time and failure behavior when adding one.
