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
- The `gcloud` CLI installed (see below)
- At least one `.db` file in the repo root

### Step 1: Install Google Cloud CLI (WSL / Linux)

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install apt-transport-https ca-certificates gnupg curl -y

# Add Google's public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

# Add the Cloud SDK repo
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
  https://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Install
sudo apt-get update && sudo apt-get install google-cloud-cli -y

# Initialize and log in
gcloud init
```

During `gcloud init`, it will try to open a browser for Google login. On WSL this sometimes fails — if so, it will print a URL. Copy it into your Windows browser, sign in, and paste the verification code back into the terminal. You can also force this flow with `gcloud init --no-launch-browser`.

Verify the installation:

```bash
gcloud --version
```

### Step 2: Set Up Your GCP Project

Create a project at [console.cloud.google.com](https://console.cloud.google.com) → **New Project** (or use an existing one).

**Enable billing** — required even for free tier. Go to **Billing** in the console sidebar and link a billing account. You won't be charged within free tier limits.

```bash
gcloud config set project YOUR_PROJECT_ID
```

> **Finding your Project ID:** Go to [console.cloud.google.com](https://console.cloud.google.com) — the Project ID is shown on the dashboard and in the project selector dropdown at the top. It looks like `my-project-123456`. You can also run `gcloud projects list` to see all your projects.

### Step 3: Grant Build Permissions

Newer GCP projects require you to explicitly grant the default service account the permissions needed to build and deploy containers. Without this step you'll get a `PERMISSION_DENIED` error during deploy.

Find your **Project Number** (not Project ID) — it's shown on the console dashboard or in the output of `gcloud projects list`.

```bash
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) \
  --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

Wait about 30 seconds for the permissions to propagate before deploying.

### Step 4: Deploy

Make sure your `.db` files are in the repo root, then:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script enables the required APIs, builds the container image, and deploys to Cloud Run. At the end it prints your public URL.

> **Important:** The `.gcloudignore` file in this repo is configured to include `*.db` files in cloud builds (even though `.gitignore` excludes them from git). This means your local `.db` files get uploaded and baked into the container image. Make sure the databases you want deployed are in the repo root before running `deploy.sh`.

### Updating or Adding Databases

The `.db` files are baked into the container image at build time. To update or add databases:

```bash
# Copy your new or updated database files into the repo root
cp /path/to/new_data.db .
cp /path/to/updated_existing.db .

# Redeploy (this rebuilds the container with the new files)
./deploy.sh
```

There is no need to commit the `.db` files to git — the deploy script uploads everything in the repo root that isn't excluded by `.gcloudignore`, and `.gcloudignore` allows `*.db` files through. The rebuild typically takes 1–2 minutes.

To remove a database from the deployment, simply delete the `.db` file from the repo root and redeploy.

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

### Troubleshooting

**`PERMISSION_DENIED` / service account errors** — You probably skipped Step 3. Grant the build permissions and wait 30 seconds before retrying.

**`FAILED_PRECONDITION: Billing account not found`** — Enable billing on your project at [console.cloud.google.com/billing](https://console.cloud.google.com/billing). A billing account is required even for free tier.

**`COPY failed: no source files were specified`** — Your `.db` files aren't reaching the build. Make sure `.gcloudignore` exists in the repo root and does NOT list `*.db`. Without `.gcloudignore`, gcloud falls back to `.gitignore` which excludes `*.db`.

**`Container failed to start and listen on PORT`** — Usually means no `.db` files were found inside the container, so the app exits immediately. Verify your `.db` files are in the repo root and that `.gcloudignore` is present. You can also check container logs: `gcloud run services logs read sqlite-db-viewer --region us-central1`

**502 Bad Gateway after successful deploy** — The app might be starting slowly with a large database. Increase timeout: add `--timeout 600` to the deploy command.

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
├── server.py                    # Convenience launcher (delegates to package)
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
├── .gcloudignore                # Files excluded from cloud builds (allows .db through)
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