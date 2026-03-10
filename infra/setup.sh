#!/usr/bin/env bash
# One-time GCP infrastructure setup for the ST Viewer.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project selected (gcloud config set project <PROJECT_ID>)
#   - Billing enabled on the project
#
# Usage: bash infra/setup.sh
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west4"
AR_REPO="st-viewer-docker"

echo "=== GCP Setup for project: ${PROJECT_ID} ==="
echo "Region: ${REGION}"
echo ""

# 1. Enable required APIs
echo "--- Enabling APIs ---"
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com

# 2. Create Artifact Registry repository
echo "--- Creating Artifact Registry repo: ${AR_REPO} ---"
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="ST Viewer Docker images" \
    2>/dev/null || echo "  (already exists)"

# 3. Grant Cloud Build permissions to default compute service account
echo "--- Granting build permissions ---"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.builder" \
    --condition=None --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectViewer" \
    --condition=None --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/artifactregistry.writer" \
    --condition=None --quiet

# 4. Create viewer service account
echo "--- Creating service account ---"
gcloud iam service-accounts create st-viewer \
    --display-name="ST Viewer" \
    2>/dev/null || echo "  st-viewer@ already exists"

VIEWER_SA="st-viewer@${PROJECT_ID}.iam.gserviceaccount.com"

# 5. Grant viewer read-only access to GCS (for downloading .db files)
echo "--- Granting GCS read access to viewer ---"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${VIEWER_SA}" \
    --role="roles/storage.objectViewer" \
    --condition=None --quiet

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Upload your database to GCS (if not already there):"
echo "     gcloud storage cp spatial_transcriptomics.db gs://samples_scraper/"
echo "  2. Deploy the viewer:  bash infra/deploy-viewer.sh"
