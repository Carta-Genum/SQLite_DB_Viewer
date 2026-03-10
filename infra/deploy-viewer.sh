#!/usr/bin/env bash
# Build and deploy the ST Viewer as a Cloud Run Service.
#
# Prerequisites:
#   - infra/setup.sh has been run
#   - Database file(s) already uploaded to GCS bucket(s)
#
# Usage: bash infra/deploy-viewer.sh
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west4"
AR_REPO="st-viewer-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/st-viewer:latest"
VIEWER_SA="st-viewer@${PROJECT_ID}.iam.gserviceaccount.com"

# ---- Database configuration ----
# Comma-separated list of bucket:filename pairs.
# The viewer will download all of these at startup and serve them
# with a dropdown switcher in the UI.
#
# To add a second database later, just append it:
#   GCS_DATABASES="samples_scraper:spatial_transcriptomics.db,other_bucket:other.db"
GCS_DATABASES="samples_scraper:spatial_transcriptomics.db"

echo "=== Deploying ST Viewer ==="
echo "Image: ${IMAGE}"
echo "Databases: ${GCS_DATABASES}"
echo ""

# 1. Build and push image via Cloud Build
echo "--- Building container image ---"
gcloud builds submit . \
    --tag="${IMAGE}" \
    --region="${REGION}"

# 2. Deploy Cloud Run Service
echo "--- Deploying Cloud Run Service ---"
gcloud run deploy st-viewer \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${VIEWER_SA}" \
    --set-env-vars="GCS_DATABASES=${GCS_DATABASES}" \
    --port=8025 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=2 \
    --allow-unauthenticated

echo ""
echo "=== Viewer deployed ==="
SERVICE_URL=$(gcloud run services describe st-viewer --region="${REGION}" --format="value(status.url)")
echo "URL: ${SERVICE_URL}"
