# stdb-viewer

A lightweight, zero-dependency Python web server for browsing SQLite databases in the browser. Built for sharing spatial transcriptomics data with collaborators who don't know SQL.

## Quick Start

```bash
# Clone and cd into the repo
git clone <repo-url> && cd stdb-viewer

# Place your .db file(s) in the project root, then:
python server.py

# Or specify paths explicitly:
python server.py -d /path/to/spatial_transcriptomics.db

# Multiple databases:
python server.py -d spatial_transcriptomics.db -d clients.db

# Custom port:
python server.py -d spatial_transcriptomics.db -p 9000
```

Open **http://localhost:8025** in your browser. That's it.

## Features

- **Server-side everything** — filtering, sorting, search, pagination all happen in SQLite. Scales to millions of rows.
- **Faceted checkbox filters** — auto-generated from categorical columns. No config needed.
- **Full-text search** — across all columns simultaneously.
- **Light / Dark theme** — toggle in the header, preference saved in browser.
- **CSV export** — downloads filtered results.
- **Row detail panel** — click any row to see all fields.
- **Multiple databases** — dropdown switcher when serving more than one .db file.
- **Zero external dependencies** — Python 3.8+ standard library only (cloud deployment adds `google-cloud-storage`).

## Project Structure

```
stdb-viewer/
├── server.py                    # Convenience launcher (just delegates to package)
├── stdb_viewer/
│   ├── __init__.py              # Package metadata
│   ├── __main__.py              # CLI entry point & HTTP server bootstrap
│   ├── database.py              # SQLite abstraction: introspection, facets, queries
│   ├── handler.py               # HTTP routing & API endpoints
│   ├── templates/
│   │   └── index.html           # Page skeleton
│   └── static/
│       ├── css/
│       │   └── style.css        # All styles, light/dark theme tokens
│       └── js/
│           └── app.js           # Client-side: state, rendering, API calls
├── cloud/
│   └── startup.py               # GCS download on container startup
├── infra/
│   ├── setup.sh                 # One-time GCP provisioning
│   ├── deploy-scraper.sh        # Build + deploy scraper Cloud Run Job
│   └── deploy-viewer.sh         # Build + deploy viewer Cloud Run Service
├── tests/
│   └── test_database.py         # Unit tests for the database layer
├── requirements.txt             # Dev/test deps (core has zero deps)
├── pyproject.toml               # Modern Python packaging
├── Dockerfile                   # Container deployment
├── .dockerignore                # Excludes .git, .db, .env from builds
├── .gitignore
└── README.md
```

## Architecture

```
Browser  ←→  Python HTTPServer  ←→  SQLite (read-only)
  app.js      handler.py             database.py
  style.css   (routes + API)         (queries + introspection)
  index.html
```

All data flows through 4 API endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/databases` | List databases, tables, row counts |
| `GET /api/facets?table=X` | Distinct values + counts for filter columns |
| `GET /api/query?table=X&filter.col=val&search=...&sort=col&page=N` | Paginated, filtered data |
| `GET /api/export?table=X&...` | CSV download of filtered results |

## Sharing with Colleagues

**Same network** — run on your machine, share your IP:
```bash
python server.py -d data.db
# → http://192.168.x.x:8025
```

**Lab server** — run as a background process:
```bash
nohup python server.py -d data.db -p 8025 > viewer.log 2>&1 &
```

**Docker (local)** — mount your .db files at runtime:
```bash
docker build -t stdb-viewer .
docker run -p 8025:8025 -v /path/to/data.db:/app/data.db stdb-viewer
```

### Cloud Deployment (GCP)

The viewer can be deployed to GCP Cloud Run with a GCS-backed database that updates weekly via a companion scraper job.

```
Cloud Scheduler (Monday 06:00 UTC)
  → Cloud Run Job (scraper): downloads .db from GCS, runs pipeline, uploads
  → GCS bucket: carta-genum-st-data
  → Cloud Run Service (viewer): downloads .db on startup, serves on port 8025
```

```bash
# One-time setup (APIs, bucket, service accounts, secrets)
bash infra/setup.sh

# Deploy the scraper job + weekly schedule
bash infra/deploy-scraper.sh /path/to/scraper/repo

# Deploy the viewer service (public URL)
bash infra/deploy-viewer.sh
```

See `infra/` scripts for details. The Dockerfile installs `google-cloud-storage` for GCS access; when `GCS_BUCKET` is not set, the download is skipped (local dev mode).

## Configuration

Edit constants at the top of `stdb_viewer/database.py`:

| Constant | Default | Purpose |
|---|---|---|
| `SKIP_TABLES` | system tables | Tables hidden from the UI |
| `MAX_FACET_CARDINALITY` | 80 | Max distinct values for a filter column |
| `NEVER_FACET` | ids, descriptions, urls… | Columns excluded from filters |
| `DEFAULT_PAGE_SIZE` | 200 | Rows per page |

## Development

```bash
# Run tests
pip install -r requirements.txt
pytest tests/ -v

# Run with auto-discovered databases
python -m stdb_viewer
```

## License

MIT
