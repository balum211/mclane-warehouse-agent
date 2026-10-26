#!/usr/bin/env bash
# Optional: provision AlloyDB for PostgreSQL and load the synthetic WMS data.
# Creates private services access on the default VPC, a cluster, a primary instance with a public IP
# (so the AlloyDB Python Connector works from Cloud Shell, a laptop or Agent Engine), and the `wms` database.
# Usage: PROJECT=my-project REGION=us-central1 ALLOYDB_PASSWORD=... bash deploy/setup_alloydb.sh
set -euo pipefail
PROJECT="${PROJECT:-${GOOGLE_CLOUD_PROJECT:?set PROJECT}}"
REGION="${REGION:-us-central1}"
CLUSTER="${CLUSTER:-wms-cluster}"
INSTANCE="${INSTANCE:-wms-primary}"
: "${ALLOYDB_PASSWORD:?set ALLOYDB_PASSWORD}"

gcloud compute addresses create alloydb-psa --global --purpose=VPC_PEERING --prefix-length=16 \
  --network=default --project "$PROJECT" || true
gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com --ranges=alloydb-psa \
  --network=default --project "$PROJECT" || true

gcloud alloydb clusters create "$CLUSTER" --region="$REGION" --password="$ALLOYDB_PASSWORD" \
  --network=default --project "$PROJECT"
gcloud alloydb instances create "$INSTANCE" --cluster="$CLUSTER" --region="$REGION" \
  --instance-type=PRIMARY --cpu-count=2 --assign-inbound-public-ip=ASSIGN_IPV4 --project "$PROJECT"

export ALLOYDB_INSTANCE_URI="projects/$PROJECT/locations/$REGION/clusters/$CLUSTER/instances/$INSTANCE"
export ALLOYDB_USER=postgres ALLOYDB_DATABASE=wms
python -m warehouse_data.load_alloydb --csv data/csv --drop --create-db
echo "AlloyDB ready. Set in warehouse_agent/.env:"
echo "  WMS_DB_BACKEND=alloydb"
echo "  ALLOYDB_INSTANCE_URI=$ALLOYDB_INSTANCE_URI"
