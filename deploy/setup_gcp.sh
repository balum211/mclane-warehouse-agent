#!/usr/bin/env bash
# One-time Google Cloud setup for the hackathon project: APIs + BigQuery dataset load.
# Usage: PROJECT=my-project REGION=us-central1 bash deploy/setup_gcp.sh
set -euo pipefail
PROJECT="${PROJECT:-${GOOGLE_CLOUD_PROJECT:?set PROJECT or GOOGLE_CLOUD_PROJECT}}"
REGION="${REGION:-us-central1}"
DATASET="${DATASET:-mclane_wms}"

gcloud config set project "$PROJECT"
gcloud services enable \
  aiplatform.googleapis.com bigquery.googleapis.com discoveryengine.googleapis.com \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  alloydb.googleapis.com servicenetworking.googleapis.com compute.googleapis.com \
  cloudresourcemanager.googleapis.com

# Synthetic data -> BigQuery
python -m warehouse_data.load_sqlite --csv data/csv --db data/wms.db --generate
python -m warehouse_data.load_bigquery --project "$PROJECT" --dataset "$DATASET" --location US --csv data/csv
echo "BigQuery dataset ready: $PROJECT.$DATASET"
