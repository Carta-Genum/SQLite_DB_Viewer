#!/usr/bin/env bash
# Build and deploy the ST Scraper as a Cloud Run Job.
#
# Prerequisites:
#   - infra/setup.sh has been run
#   - Scraper repo cloned at ${SCRAPER_REPO_PATH}
#
# Usage: bash infra/deploy-scraper.sh [/path/to/scraper/repo]
set -euo pipefail

SCRAPER_REPO_PATH="${1:-../scraper}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west4"
AR_REPO="carta-genum-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/st-scraper:latest"
BUCKET_NAME="carta-genum-st-data"
SCRAPER_SA="st-scraper@${PROJECT_ID}.iam.gserviceaccount.com"

if [ ! -d "${SCRAPER_REPO_PATH}" ]; then
    echo "Error: Scraper repo not found at ${SCRAPER_REPO_PATH}"
    echo "Usage: bash infra/deploy-scraper.sh /path/to/scraper/repo"
    exit 1
fi

echo "=== Deploying ST Scraper ==="
echo "Image: ${IMAGE}"
echo "Source: ${SCRAPER_REPO_PATH}"
echo ""

# 1. Build and push image via Cloud Build
echo "--- Building container image ---"
gcloud builds submit "${SCRAPER_REPO_PATH}" \
    --tag="${IMAGE}" \
    --region="${REGION}"

# 2. Create or update Cloud Run Job
echo "--- Creating/updating Cloud Run Job ---"
gcloud run jobs deploy st-scraper \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --service-account="${SCRAPER_SA}" \
    --set-env-vars="GCS_BUCKET=${BUCKET_NAME},DB_FILENAME=spatial_transcriptomics.db,SCRAPE_DAYS=7" \
    --set-secrets="/app/config.yaml=st-scraper-config:latest" \
    --task-timeout=3600s \
    --memory=1Gi \
    --cpu=1 \
    --max-retries=1

# 3. Create Cloud Scheduler trigger (weekly Monday 06:00 UTC)
echo "--- Setting up weekly schedule ---"
SCHEDULER_NAME="st-scraper-weekly"

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location="${REGION}" &>/dev/null; then
    echo "  Scheduler job already exists, updating..."
    gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
        --location="${REGION}" \
        --schedule="0 6 * * 1" \
        --time-zone="UTC" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/st-scraper:run" \
        --http-method=POST \
        --oauth-service-account-email="${SCRAPER_SA}"
else
    gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
        --location="${REGION}" \
        --schedule="0 6 * * 1" \
        --time-zone="UTC" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/st-scraper:run" \
        --http-method=POST \
        --oauth-service-account-email="${SCRAPER_SA}"
fi

echo ""
echo "=== Scraper deployed ==="
echo ""
echo "Test with: gcloud run jobs execute st-scraper --region ${REGION}"
echo "Schedule:  Every Monday at 06:00 UTC"
