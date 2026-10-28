#!/usr/bin/env bash
# Optional: load the synthetic WMS data into Cloud SQL for PostgreSQL.
# Reuses the instance the sdd-adk-antigravity codelab creates (restaurant-db) by default, so the
# warehouse agent can live in the same sdd-adk-agents-agy project; set CREATE=1 to create an instance.
# Usage: PROJECT=my-project DB_PASSWORD=... bash deploy/setup_cloudsql.sh
set -euo pipefail
PROJECT="${PROJECT:-${GOOGLE_CLOUD_PROJECT:?set PROJECT}}"
REGION="${REGION:-us-central1}"
INSTANCE="${INSTANCE:-restaurant-db}"
: "${DB_PASSWORD:?set DB_PASSWORD}"

if [[ "${CREATE:-0}" == "1" ]]; then
  gcloud services enable sqladmin.googleapis.com --project "$PROJECT"
  gcloud sql instances create "$INSTANCE" --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-g1-small --region="$REGION" --root-password="$DB_PASSWORD" --project "$PROJECT"
fi

[[ -f data/csv/items.csv ]] || python -m warehouse_data.generate --out data/csv
export WMS_DB_BACKEND=cloudsql CLOUD_SQL_INSTANCE="$PROJECT:$REGION:$INSTANCE" POSTGRES_USER=postgres POSTGRES_DB=wms
python -m warehouse_data.load_postgres --target cloudsql --csv data/csv --drop --create-db
echo "Cloud SQL ready. Set in warehouse_agent/.env:"
echo "  WMS_DB_BACKEND=cloudsql"
echo "  CLOUD_SQL_INSTANCE=$CLOUD_SQL_INSTANCE"
echo "  DB_PASSWORD=<your password>"
