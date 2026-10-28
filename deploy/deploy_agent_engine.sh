#!/usr/bin/env bash
# Deploy the agent to Vertex AI Agent Engine and grant it data access.
# The deployed agent cannot read data/wms.db: set WMS_DB_BACKEND=bigquery (or alloydb / cloudsql) in warehouse_agent/.env.
set -euo pipefail
PROJECT="${PROJECT:-${GOOGLE_CLOUD_PROJECT:?set PROJECT}}"
REGION="${REGION:-us-central1}"
DATASET="${DATASET:-mclane_wms}"

if [ ! -f warehouse_agent/.env ]; then
  echo "Create warehouse_agent/.env from .env.example first (WMS_DB_BACKEND=bigquery)." >&2; exit 1
fi
if grep -qE '^WMS_DB_BACKEND=sqlite' warehouse_agent/.env; then
  echo "WMS_DB_BACKEND=sqlite will not work in Agent Engine; use bigquery, alloydb or cloudsql." >&2; exit 1
fi

# The Agent Engine service agent runs the tools: let it query BigQuery and log proposed actions.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
for role in roles/bigquery.jobUser roles/bigquery.dataEditor roles/alloydb.client roles/cloudsql.client roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="$role" \
    --condition=None --quiet >/dev/null || echo "warn: could not grant $role (grant it after the first deploy)"
done

adk deploy agent_engine \
  --project "$PROJECT" --region "$REGION" \
  --display_name "McLane Warehouse Copilot" \
  --description "Warehouse operations copilot across Manhattan Active, Blue Yonder and Argent DCs" \
  warehouse_agent
echo "Copy the reasoningEngines/... resource name printed above into REASONING_ENGINE for register_gemini_enterprise.sh"
