# SQLite DB Viewer

## Project Goal
Provide team-wide web access to the spatial transcriptomics database with zero friction. Paired with the [scraper](https://github.com/Carta-Genum/scraper) for weekly automated updates via GCP.

## Tech Stack
- **Language**: Python 3.12
- **Dependencies**: None (stdlib `http.server` only). `google-cloud-storage` added for cloud deployment only.
- **Testing**: pytest
- **Packaging**: pyproject.toml, setuptools

## Architecture
```
Browser  <-->  Python HTTPServer  <-->  SQLite (read-only)
  app.js       handler.py               database.py
  style.css    (routes + API)            (queries + introspection)
  index.html
```

Four API endpoints:
| Endpoint | Purpose |
|---|---|
| `GET /api/databases` | List databases, tables, row counts |
| `GET /api/facets?table=X` | Distinct values + counts for filter columns |
| `GET /api/query?table=X&...` | Paginated, filtered, sorted data |
| `GET /api/export?table=X&...` | CSV download of filtered results |

## Cloud Deployment (GCP)
```
Cloud Scheduler (Monday 06:00 UTC)
  -> Cloud Run Job: st-scraper (downloads .db from GCS, runs pipeline, uploads)
  -> GCS bucket: carta-genum-st-data (europe-west4)
  -> Cloud Run Service: st-viewer (downloads .db on startup, serves on 8025)
```
- Region: europe-west4
- Viewer: public, scale-to-zero
- Infra scripts in `infra/`, GCS startup in `cloud/`

## Key Files
- `server.py` — convenience launcher, delegates to `stdb_viewer.__main__`
- `stdb_viewer/__main__.py` — CLI entry, auto-discovers `*.db` in cwd
- `stdb_viewer/database.py` — SQLite wrapper, facet detection, query building
- `stdb_viewer/handler.py` — HTTP routing, API endpoints
- `cloud/startup.py` — GCS download on container startup (no-op locally)
- `infra/setup.sh` — one-time GCP provisioning
- `infra/deploy-scraper.sh` — build + deploy scraper Cloud Run Job
- `infra/deploy-viewer.sh` — build + deploy viewer Cloud Run Service

## Branch Model
No `devel` branch. Feature branches from `main`.

## Quick Commands
```bash
python server.py                        # serve all .db in cwd
python server.py -d mydata.db -p 9000   # specific db + port
python server.py --no-browser           # headless mode
pytest tests/ -v                        # run tests
docker build -t stdb-viewer . && docker run -p 8025:8025 stdb-viewer
```

## Active Goals
- [ ] Run `infra/setup.sh` for one-time GCP provisioning
- [ ] Seed DB to GCS: `gcloud storage cp spatial_transcriptomics.db gs://carta-genum-st-data/`
- [ ] Deploy scraper and viewer to Cloud Run
- [ ] Verify end-to-end: scraper job -> GCS -> viewer serves latest data

## Project Journal

### 2026-03-06: Add GCP cloud deployment infrastructure
- Created `cloud/startup.py`, `infra/setup.sh`, `infra/deploy-scraper.sh`, `infra/deploy-viewer.sh`
- Modified `Dockerfile` to download DB from GCS at runtime instead of baking it in
- Provided scraper repo files (`Dockerfile`, `cloud/entrypoint.sh`, `cloud/gcs_sync.py`) for separate session
- Next: Run setup.sh, seed DB, deploy both services
