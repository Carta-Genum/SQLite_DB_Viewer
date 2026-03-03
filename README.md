# stdb-viewer

A lightweight, zero-dependency Python web server for browsing SQLite databases in the browser. Built for sharing spatial transcriptomics data with collaborators who don't know SQL.

## Quick Start (Local)

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
- **Zero external dependencies** — Python 3.8+ standard library only.
- **Google Cloud Run deployment** — one-command deploy to the cloud, free tier eligible.

---

## Deploy to Google Cloud Run (Free Tier)

This section walks you through deploying stdb-viewer to Google Cloud Run so anyone with the link can browse your databases — no local setup needed on their end.

### Prerequisites

- A Google Cloud account ([sign up free](https://cloud.google.com/free))
- A GCP project with billing enabled (free tier — you won't be charged within limits)
- The `gcloud` CLI installed (see below)
- At least one `.db` file in the repo root

### Install Google Cloud CLI on WSL / Linux

```bash
# 1. Install dependencies
sudo apt-get update
sudo apt-get install apt-transport-https ca-certificates gnupg curl -y

# 2. Add Google's public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

# 3. Add the Cloud SDK repo
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
  https://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# 4. Install
sudo apt-get update && sudo apt-get install google-cloud-cli -y

# 5. Initialize and log in
gcloud init
```

During `gcloud init`, it will try to open a browser for Google login. On WSL this sometimes fails — if so, it will print a URL. Copy it into your Windows browser, sign in, and paste the verification code back into the terminal. You can also force this flow with `gcloud init --no-launch-browser`.

Verify the installation:

```bash
gcloud --version
```

### Set Up Your GCP Project

If you don't have a project yet, create one at [console.cloud.google.com](https://console.cloud.google.com) → **New Project**. Then enable billing on it (required even for free tier — go to **Billing** in the console sidebar and link a billing account).

```bash
gcloud config set project YOUR_PROJECT_ID
```

### Create the Branch and Deploy

```bash
# Switch to the cloud deployment branch
git checkout main && git pull
git checkout -b feature/googlecloud

# Make sure your .db files are in the repo root, then deploy
chmod +x deploy.sh
./deploy.sh
```

The script enables the required APIs, builds the container image, and deploys to Cloud Run. At the end it prints your public URL.

### Manual Deploy (Without the Script)

```bash
# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# Deploy from source
gcloud run deploy sqlite-db-viewer \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 256Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 1 \
    --port 8080
```

### Updating Your Database

The `.db` file is baked into the container image. To update, just copy the new file and redeploy:

```bash
cp /path/to/updated/data.db .
gcloud run deploy sqlite-db-viewer --source . --region us-central1
```

### Restricting Access

By default the deploy uses `--allow-unauthenticated` so anyone with the URL can access it. To require Google login:

```bash
gcloud run deploy sqlite-db-viewer \
    --source . \
    --region us-central1 \
    --no-allow-unauthenticated

# Grant specific users
gcloud run services add-iam-policy-binding sqlite-db-viewer \
    --region us-central1 \
    --member="user:colleague@gmail.com" \
    --role="roles/run.invoker"
```

### Free Tier Limits

Google Cloud Run free tier includes monthly: 2 million requests, 180,000 vCPU-seconds, 360,000 GiB-seconds, and 1 GB egress to North America. With `min-instances 0` the service scales to zero when idle, so you consume resources only during active use.

---

## Sharing with Colleagues (Other Methods)

**Same network** — run on your machine, share your IP:
```bash
python server.py -d data.db
# → http://192.168.x.x:8025
```

**Lab server** — run as a background process:
```bash
nohup python server.py -d data.db -p 8025 > viewer.log 2>&1 &
```

**Docker** — copy your .db files next to the Dockerfile, then:
```bash
docker build -t stdb-viewer .
docker run -p 8025:8025 stdb-viewer
```

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
├── tests/
│   └── test_database.py         # Unit tests for the database layer
├── deploy.sh                    # One-command Cloud Run deployment
├── .gcloudignore                # Files excluded from cloud builds
├── requirements.txt             # Dev/test deps (core has zero deps)
├── pyproject.toml               # Modern Python packaging
├── Dockerfile                   # Container deployment (local Docker & Cloud Run)
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