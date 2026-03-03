#!/usr/bin/env bash
# deploy.sh — Deploy SQLite DB Viewer to Google Cloud Run (free tier)
#
# Prerequisites:
#   1. Google Cloud SDK installed (https://cloud.google.com/sdk/docs/install)
#   2. A GCP project with billing enabled (free tier is sufficient)
#   3. Build permissions granted (see README.md Step 3)
#   4. At least one .db file in the repo root
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

# ---- Configuration (edit these or set via environment) ----
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"          # us-central1 is free-tier eligible
SERVICE_NAME="${GCP_SERVICE_NAME:-sqlite-db-viewer}"

# ---- Preflight checks ----
if ! command -v gcloud &>/dev/null; then
    echo "ERROR: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
    if [ -z "$PROJECT_ID" ]; then
        echo "ERROR: No GCP project set."
        echo "  Run: gcloud config set project YOUR_PROJECT_ID"
        echo "  Or:  export GCP_PROJECT_ID=YOUR_PROJECT_ID"
        exit 1
    fi
fi

if ! ls *.db 1>/dev/null 2>&1; then
    echo "ERROR: No .db files found in repo root."
    echo "  Place your SQLite database files here before deploying."
    exit 1
fi

if [ ! -f ".gcloudignore" ]; then
    echo "WARNING: .gcloudignore not found. gcloud will fall back to .gitignore,"
    echo "  which excludes *.db files. Your databases won't be included in the build."
    echo "  See README.md for the correct .gcloudignore file."
    exit 1
fi

echo "=== Deploying to Cloud Run ==="
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Service:  $SERVICE_NAME"
echo "  Databases:"
for db in *.db; do
    size=$(du -h "$db" | cut -f1)
    echo "    - $db ($size)"
done
echo ""

# Enable required APIs (idempotent)
echo "→ Enabling Cloud Run & Artifact Registry APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    --project="$PROJECT_ID" --quiet

# Deploy directly from source (Cloud Build + Cloud Run in one step)
echo "→ Building and deploying..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 256Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 1 \
    --timeout 300 \
    --port 8080

echo ""
echo "=== Done! ==="
URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" --region="$REGION" \
    --format='value(status.url)' 2>/dev/null)
echo "  🚀 Your viewer is live at: $URL"