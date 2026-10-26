---
name: gemini-enterprise-deploy
description: Use when deploying the McLane warehouse agent to Vertex AI Agent Engine or Cloud Run and registering it in Gemini Enterprise, or when troubleshooting that deployment (permissions, data backend, environment variables).
---

# Deploy to Agent Engine and Gemini Enterprise

## Preconditions
- `gcloud auth login` and `gcloud auth application-default login` done; project selected.
- Data in BigQuery (`bash deploy/setup_gcp.sh`) or AlloyDB (`bash deploy/setup_alloydb.sh`).
  The deployed agent cannot use SQLite.
- `warehouse_agent/.env` created from `.env.example` with `GOOGLE_GENAI_USE_VERTEXAI=True`,
  `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `WMS_DB_BACKEND=bigquery` (or `alloydb` +
  `ALLOYDB_*`), and `WMS_AGENT_MODEL`.

## Steps
1. `make test` must pass.
2. `bash deploy/deploy_agent_engine.sh` (wraps `adk deploy agent_engine ... warehouse_agent` and
   grants the Agent Engine service agent BigQuery job/data roles and AlloyDB client). Note the
   `projects/.../reasoningEngines/...` resource name it prints.
3. Smoke test in the Vertex AI console (Agent Engine > the agent > Playground): "Give me the shift
   briefing for MTX".
4. Register in Gemini Enterprise: console Agents > Add agent > Custom agent via Agent Engine, or
   `GE_APP_ID=<app> REASONING_ENGINE=<resource> bash deploy/register_gemini_enterprise.sh`.
5. In Gemini Enterprise, open the agent from the Agents list and run the demo questions in
   `docs/DEMO_SCRIPT.md`.

## Troubleshooting
- `403 bigquery.jobs.create`: grant `roles/bigquery.jobUser` to
  `service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com`.
- `FileNotFoundError ... wms.db`: the deployed `.env` still says `WMS_DB_BACKEND=sqlite`.
- Model not found: set `WMS_AGENT_MODEL` to a Gemini model enabled in your region.
- The registration API is v1alpha; if the call fails, follow the current Gemini Enterprise docs
  for registering ADK agents hosted on Agent Engine.
