# Local operation

The recommended workstation setup is [Docker Compose](../README.md#run-locally). For separate Python and Node processes, use Python 3.12, Node.js 20+, npm and Docker with a PostgreSQL 16 image.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r infra/requirements.txt
(cd frontend && npm ci)

# First run only: create the database and its initialization files.
.venv/bin/python data_platform/v3/seed_demo.py --output /absolute/path/to/seed
.venv/bin/python data_platform/v3/provision.py --seed-dir /absolute/path/to/seed

# Start the retained database, API/worker and frontend.
.venv/bin/python data_platform/v3/local.py
```

The workspace is at `http://127.0.0.1:5173/workspace`; API health is at `http://127.0.0.1:8001/health`. The launcher reuses the existing database and applies additive migrations on later starts. Runtime credentials, raw downloads and generated artifacts stay in ignored local paths. Back up database and artifact bytes together.

## Verification

Prepare a dedicated test database before the backend checks:

```bash
.venv/bin/python data_platform/v3/prepare_test_db.py --seed-dir /absolute/path/to/seed
.venv/bin/python data_platform/v3/test_backend.py
(cd frontend && npx tsc --noEmit -p tsconfig.app.json && npx vitest run && npm run build)
```

The test database is separate from working farm records. Database preparation preserves existing records on repeat runs.
