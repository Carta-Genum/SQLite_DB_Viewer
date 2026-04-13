#!/usr/bin/env bash
# One-time GCP infrastructure setup for the ST Viewer + Scraper.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project selected (gcloud config set project <PROJECT_ID>)
#
# Usage: bash infra/setup.sh
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west4"
BUCKET_NAME="carta-genum-st-data"
AR_REPO="st-viewer-docker"

echo "=== GCP Setup for project: ${PROJECT_ID} ==="
echo "Region: ${REGION}"
echo ""

# 1. Enable required APIs
echo "--- Enabling APIs ---"
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com

# 2. Create Artifact Registry repository
echo "--- Creating Artifact Registry repo: ${AR_REPO} ---"
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Carta-Genum Docker images" \
    2>/dev/null || echo "  (already exists)"

# 3. Create GCS bucket with versioning
echo "--- Creating GCS bucket: ${BUCKET_NAME} ---"
gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    2>/dev/null || echo "  (already exists)"

gcloud storage buckets update "gs://${BUCKET_NAME}" --versioning

# 4. Create service accounts
echo "--- Creating service accounts ---"
for SA in st-scraper st-viewer; do
    gcloud iam service-accounts create "${SA}" \
        --display-name="${SA}" \
        2>/dev/null || echo "  ${SA}@ already exists"
done

SCRAPER_SA="st-scraper@${PROJECT_ID}.iam.gserviceaccount.com"
VIEWER_SA="st-viewer@${PROJECT_ID}.iam.gserviceaccount.com"

# 5. Grant IAM permissions
echo "--- Granting IAM permissions ---"

# Scraper: read/write GCS + read secrets
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SCRAPER_SA}" \
    --role="roles/storage.objectAdmin" \
    --condition=None --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SCRAPER_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet

# Viewer: read-only GCS
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${VIEWER_SA}" \
    --role="roles/storage.objectViewer" \
    --condition=None --quiet

# 6. Create secret for scraper config (if config.yaml exists locally)
echo "--- Setting up secrets ---"
if gcloud secrets describe st-scraper-config &>/dev/null; then
    echo "  Secret st-scraper-config already exists."
    echo "  To update: gcloud secrets versions add st-scraper-config --data-file=config.yaml"
else
    echo "  Creating secret st-scraper-config."
    echo "  You will need to add a version with the scraper's config.yaml:"
    echo "    gcloud secrets versions add st-scraper-config --data-file=/path/to/scraper/config.yaml"
    gcloud secrets create st-scraper-config --replication-policy=automatic
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Upload the scraper config.yaml to the secret:"
echo "     gcloud secrets versions add st-scraper-config --data-file=/path/to/config.yaml"
echo "  2. Seed the database:"
echo "     gcloud storage cp spatial_transcriptomics.db gs://${BUCKET_NAME}/"
echo "  3. Deploy the scraper:  bash infra/deploy-scraper.sh"
echo "  4. Deploy the viewer:   bash infra/deploy-viewer.sh"
