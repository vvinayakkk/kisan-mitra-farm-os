# Executable v3 connectors

The unified API reads PostgreSQL in v3 data mode; ingestion uses a restricted trusted service role, never a browser SQL connection. Provisioning creates a separate database and does not import or mutate legacy storage.

## Worker commands

Load the ignored `.v3-data/runtime.env` into the process environment (do not commit or print it), then run:

```sh
python -m skyview.data.v3.ingest_cli forecast --limit 1
python -m skyview.data.v3.ingest_cli history --days 365 --limit 1
python -m skyview.data.v3.ingest_cli power --days 365 --limit 1
python -m skyview.data.v3.ingest_cli mandi --limit 10
python -m skyview.data.v3.ingest_cli reviewed --file /absolute/path/evidence.json
```

The live data mode accepts authenticated station packets. External recurring imports are bounded to at least one hour between runs. Open-Meteo public hosted access is subject to its noncommercial terms, not a promise of free commercial service. Forecasts are 16 days, not one year. ERA5 history uses a seven-day lag and retains reanalysis provenance. NASA POWER is a coarse public grid, not a station; fill value `-999` remains missing.

OGD requires `DATAGOV_API_KEY` (also accepts `DATA_GOV_API_KEY` or `OGD_API_KEY`) on the server. The current-daily resource is INR/quintal; explicit incompatible units are quarantined. The CLI caps paging and does not claim a complete national snapshot or 365-day archive. Canonical crops/states must match configured reference records; unmatched records are quarantined for review. Varieties, grades, districts, and units remain distinct. A payload retry reuses its release hash; changed source content creates a new immutable release, retaining revision evidence. Latest-price queries select by observation date and retrieval time. Future planning prices are not stored as observations.

Every successful import records provider, immutable release, ingest run, original content hash/object URI, quality failures and freshness. Raw files stay in ignored local storage; database backup alone is insufficient: back up the raw/artifact directory too. CLI transport failures publish a safe source outage without leaking API credential query strings. Do not treat a failed connector as zero rainfall or a zero commodity price.

## Reviewed official import contract

The local JSON evidence bundle requires `source_url` (official HTTPS), `title`, `language`, `review_status: "reviewed"`, `reviewed_by`, `evidence_text`, and optional `published_on`. Include only reviewed extracts with permitted reuse, citations and dates; not full copyrighted publications by default.

Optional arrays:

- `msp`: `crop_id`, `grade`, `marketing_season`, `announced_on`, `effective_from`, `amount_inr_quintal`.
- `crop_guides`: `crop_id`, optional `region_id`, `season`, `growth_stage`, `guidance` object.
- `schemes`: `scheme_code`, `version`, `name`, optional `region_id`, `requirements` object, `benefits` object, official HTTPS `application_url`, optional `valid_from`/`valid_to`.

IDs must reference canonical records already present in the selected database. Database constraints reject unresolved keys. Publication import does not prove farmer eligibility or scheme approval. Crop guides do not execute chemical treatments. IMD, eNAM, SoilGrids, Copernicus processing, AgriStack, NPSS and other catalog sources require approved access, licenses, downtime handling and review before use.

## Device ingestion contract

`ingest_sensor_envelope(conn, farmer_id, station_id, envelope, lane, now)` requires server-verified device credentials mapped to station and owner. Never trust owner IDs from the JSON. Measurements use schema units; boot UUID, nonnegative sequence and timezone-aware observation timestamp are mandatory. A transaction advisory lock serializes same-device retries; boot/sequence replay across release days is checked before writing. Receipt and packet insert atomically, with raw packet evidence. Unsupported metrics, future observations, out-of-range measurements and conflicting replay are rejected.

Station records retain their origin and calibration status. A percent soil-moisture channel is not an irrigation threshold without field calibration. No worker sends actuator commands, outbound farmer messages or hardware acknowledgments on its own. Device execution requires the approval/command protocol and measured acknowledgment.

## API-managed lifecycle

The backend calls `start_background_worker()` on startup and `stop_background_worker()` on shutdown. Startup schedules jobs without waiting for external requests. A PostgreSQL advisory lease permits one worker per database across API processes. Stop signals wake sleeping tasks immediately; outstanding public fetches have bounded eight-second request timeouts and shutdown has a forty-second ceiling.

The configured local profile's two station records refresh every five seconds. Remaining local station records refresh in twelve-station batches once per minute. The selected farm's **public regional location anchor**, rather than private plot coordinates, receives a sixteen-day forecast and initial 365-day ERA5/POWER histories (ending seven days before today). Existing completed history is reused; daily updates append missing days. Forecasts refresh every six hours. OGD runs daily on success, with thirty-minute retry backoff on transport failure. Set `V3_BACKGROUND_WORKER=false` to disable supervised imports; live mode accepts only authenticated device packets. Live farmer onboarding links weather only after explicit consent via `POST /api/farms/{id}/weather-link` with an owned plot and `consent_to_share_coarse_grid: true`. The server rounds coordinates to a shared 0.25-degree grid; the worker receives only its coarse coordinates, rechecks active consent before each request, and never sends exact plot coordinates. `DELETE` removes the link and revokes weather-grid consent. `V3_INGEST_LOCATION_KEY` optionally selects an operator-configured public reference anchor; it cannot bypass consent for a user-reported grid.

`catalog/reviewed_sources.json` supplies cited official PM-KISAN and PMFBY scheme overviews and an ICAR advisory referral. These are useful knowledge references, not completed registrations, claim approvals, plot-specific crop prescriptions or guaranteed eligibility decisions. Reviewed versions are imported once; later changes require a new reviewed version.

The source loop stays alive when no farms exist, wakes after a weather link commits, and rotates at most three due locations per batch. Completed forecasts are reused for six hours; histories refresh daily and provider failures back off thirty minutes. The narrowly granted `sv3.consented_weather_locations()` function provides only coarse grid IDs/coordinates to the worker, without generic consent-table access.

## Reported-price view

`GET /api/mandi/rates?observed_only=true` and `/api/mandi/history?observed_only=true`
return only `origin=observed` quotations with original provenance and reporting dates.
The `market_prices` and `market_trend` assistant tools accept the same boolean and
default to `true`; other origins require an explicit `false`.
There is no generated-price fallback when that view is empty; historical charts need
at least two actual dated observations of the same market/variety/grade/unit series.

`GET /api/mandi/catalogue?observed_only=true` (also `/api/mandi/catalog`) exposes
reported and curated real market names. A directory reference does not establish a
commodity quote. Omit the commodity filter when browsing directory-only markets.
Existing records retain their origin metadata; the default API mode remains
backward compatible for explicit non-observed queries. No database provenance
is rewritten by a display setting.

Inspect the currently connected database with `python data_platform/v3/check_local.py`
and `GET /api/data/status` before interpreting a chart or claiming source coverage.
Counts and freshness vary by installation and by the last successful import. The
background worker records source health and retries independently; a timeout is not
evidence of an observed zero price or an empty national market directory.
