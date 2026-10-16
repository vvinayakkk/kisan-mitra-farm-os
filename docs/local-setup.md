# Local operation

The fresh v3 provisioner creates isolated PostgreSQL settings and refuses to reset populated data. `data_platform/v3/local.py` starts or reuses the retained local database, API and frontend. It does not seed again on routine startup. Runtime credentials, raw downloads, generated artifacts and PostgreSQL files stay in ignored local paths.

Once all modules are imported, the API is available at `http://127.0.0.1:8001` and Vite at `http://127.0.0.1:5173`. Keep the backend process running for its background worker. Back up the database and artifact bytes together.
