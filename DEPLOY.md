# Deploying SQLite DB Viewer on Google Cloud (Free Tier)

This guide covers deploying the SQLite DB Viewer to **Google Cloud Run**, which is the best fit for this project on the free tier. Cloud Run gives you 2 million requests/month free, auto-scales to zero (so you pay nothing when idle), and requires minimal changes to the existing code.

---

## What Changed from `main`

Only two files were modified and three files were added:

**Modified:**
- `Dockerfile` — uses `PORT` env var (Cloud Run requirement), adds `--no-browser` flag
- `stdb_viewer/__main__.py` — reads `PORT` from environment as the default port

**Added:**
- `.gcloudignore` — excludes tests/dev files from the deploy bundle
- `deploy.sh` — one-command deployment script
- `DEPLOY.md` — this file

The core application code (`database.py`, `handler.py`, frontend) is **unchanged**.

---

## Prerequisites

1. **Google Cloud account** with a project (free tier is fine)  
   → Sign up at https://cloud.google.com/free  
2. **Google Cloud SDK** (`gcloud` CLI) installed  
   → https://cloud.google.com/sdk/docs/install  
3. **At least one `.db` file** in the repo root

---

## Git Instructions: Create and Switch to the Branch

```bash
# 1. Clone the repo (if you haven't already)
git clone https://github.com/YOUR_USER/SQLite_DB_Viewer.git
cd SQLite_DB_Viewer

# 2. Make sure you're on main and up to date
git checkout main
git pull origin main

# 3. Create and switch to the new branch
git checkout -b feature/googlecloud

# 4. Copy in the updated/new files (see below), then stage and commit
git add -A
git commit -m "feat: add Google Cloud Run deployment support"

# 5. Push the branch
git push -u origin feature/googlecloud
```

---

## Quick Deploy (One Command)

After switching to the `feature/googlecloud` branch:

```bash
# Set your project (once)
gcloud config set project YOUR_PROJECT_ID

# Make sure your .db files are in the repo root, then:
chmod +x deploy.sh
./deploy.sh
```

This builds the container, pushes it to Artifact Registry, and deploys to Cloud Run. At the end it prints the public URL.

---

## Step-by-Step Manual Deploy

### 1. Authenticate and set project

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable required APIs

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

### 3. Place your database files

Copy your `.db` files into the repo root. The Dockerfile copies all `*.db` files into the container image.

```bash
cp /path/to/your/data.db .
```

### 4. Deploy from source

```bash
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

Cloud Run will automatically build the Docker image and deploy it.

### 5. Get your URL

```bash
gcloud run services describe sqlite-db-viewer \
    --region us-central1 \
    --format='value(status.url)'
```

---

## Free Tier Limits

Google Cloud Run free tier includes (per month):

| Resource           | Free Allowance              |
|--------------------|-----------------------------|
| Requests           | 2 million                   |
| CPU                | 180,000 vCPU-seconds        |
| Memory             | 360,000 GiB-seconds         |
| Networking (egress)| 1 GB to North America       |

With `min-instances 0` and `max-instances 1`, the service scales to zero when not in use — you only consume resources when someone is actively using it.

---

## Updating Your Database

Since the `.db` file is baked into the container image, redeploy after updating:

```bash
cp /path/to/updated/data.db .
gcloud run deploy sqlite-db-viewer --source . --region us-central1
```

---

## Restricting Access (Optional)

The deploy script uses `--allow-unauthenticated` for easy access. To require Google login:

```bash
# Remove public access
gcloud run deploy sqlite-db-viewer \
    --source . \
    --region us-central1 \
    --no-allow-unauthenticated

# Grant specific users access
gcloud run services add-iam-policy-binding sqlite-db-viewer \
    --region us-central1 \
    --member="user:someone@gmail.com" \
    --role="roles/run.invoker"
```

---

## Troubleshooting

**"No .db files found"** — Make sure your `.db` files are in the repo root (not in a subfolder). Check that `.gitignore` excludes `*.db` — you may need to force-add: `git add -f mydata.db`.

**Container crashes on startup** — Check logs: `gcloud run services logs read sqlite-db-viewer --region us-central1`

**502 Bad Gateway** — The app might be starting slowly with a large database. Increase timeout: add `--timeout 600` to the deploy command.

**Exceeding free tier** — Set `--max-instances 1` (already set in deploy.sh) to cap resource usage.
