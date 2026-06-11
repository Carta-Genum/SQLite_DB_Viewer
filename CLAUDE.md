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
- [x] Deploy viewer to Cloud Run (live: `st-viewer`, europe-west4, project `databases-489214`)
- [ ] Confirm scraper Cloud Run Job deployed + scheduled
- [ ] Verify end-to-end: scraper job -> GCS -> viewer serves latest data

## Project Journal

### 2026-05-28: Fix ontology-ID facets; deploy v1.1.1
- Excluded `*_uberon_id`/`*_mondo_id`/`*_ncbi_taxon_id` from facets; raised `MAX_FACET_CARDINALITY` 80->100 (so `pathology` shows); force-included samples `tissue/region/disease` with a per-facet search box; made facet discovery lazy; switched to `ThreadingHTTPServer` + thread-local SQLite conn.
- Learned: `main` was ahead of `devel` (admin toggle, Source filter, smarter facets already there) — always branch from `main`. Cloud Run filesystem is memory-backed, so the 1.2GB DB needs headroom -> bumped viewer to 4Gi/2cpu.
- Deployed revision `st-viewer-00026-hkq`; tags `v1.1.0` (facets) + `v1.1.1` (memory).
- Next: scraper job deploy/verify still pending.

### 2026-03-06: Add GCP cloud deployment infrastructure
- Created `cloud/startup.py`, `infra/setup.sh`, `infra/deploy-scraper.sh`, `infra/deploy-viewer.sh`
- Modified `Dockerfile` to download DB from GCS at runtime instead of baking it in
- Provided scraper repo files (`Dockerfile`, `cloud/entrypoint.sh`, `cloud/gcs_sync.py`) for separate session
- Next: Run setup.sh, seed DB, deploy both services


---

## Knowledge Base (LLM Wiki)

The `knowledge/` directory is an LLM-maintained wiki (Karpathy three-layer
pattern). The shared contract lives in `~/.claude/rules/llm-wiki.md`; the
per-project schema lives in `knowledge/WIKI_SCHEMA.md`.

**At session start**: read `knowledge/index.md` for the page catalog. For
architectural or interface questions, consult wiki pages before answering
from scratch.

**Layer separation**: wiki stores epistemic facts ("component X has
interface Y", "ADR-003 chose A over B because Z"). CLAUDE.md project
journal and `knowledge/log.md` store operational events ("we shipped X on
date Y").

**Operations**: INGEST (after new sources / decisions), QUERY (when
answering an architectural question), LINT (periodic audit for
contradictions / orphan pages / stale claims). Each operation appends to
`knowledge/log.md`.

**Decision pages**: file under `knowledge/decisions/<YYYY-MM-DD>_<slug>.md`
whenever a significant architectural choice is made (R↔Python pivot,
container choice, schema change, dependency bump with semantic consequences,
pipeline refactor). Content: WHAT decided, WHY, EVIDENCE, ALTERNATIVES
considered.
