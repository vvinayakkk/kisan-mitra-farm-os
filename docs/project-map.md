# Project entry points

The web client lives in `frontend/`; the FastAPI service lives in `skyview/`. `data_platform/v3/` owns fresh PostgreSQL provisioning, and `skyview/data/v3/` owns runtime repositories and workers. `tests/` contains backend checks. `hardware/` and `skyview_flutter_app/` are separate device and mobile surfaces.

The browser enters through the Vite app. The service enters through `skyview.main:app`; the local launcher is `data_platform/v3/local.py`. The farmer workspace and classic screens use the same canonical API.
