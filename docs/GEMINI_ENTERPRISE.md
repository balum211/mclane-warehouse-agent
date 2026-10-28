# Deploying to Vertex AI Agent Engine and Gemini Enterprise

## 1. Prerequisites
```bash
gcloud auth login
gcloud auth application-default login
export PROJECT={{PROJECT_ID}} REGION=us-central1
bash deploy/setup_gcp.sh            # enables APIs, generates data, loads BigQuery dataset mclane_wms
```
Optional AlloyDB backend: `ALLOYDB_PASSWORD=... bash deploy/setup_alloydb.sh`. Optional Cloud SQL
backend (for example the sdd-adk-antigravity codelab instance): `DB_PASSWORD=... bash deploy/setup_cloudsql.sh`.

## 2. Configure the agent
```bash
cp .env.example warehouse_agent/.env
# edit: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global, WMS_DB_BACKEND=bigquery, WMS_AGENT_MODEL
make test
```
Try it locally against BigQuery first: `adk web .` and ask "Give me the shift briefing for MTX".

## 3. Deploy to Agent Engine
```bash
bash deploy/deploy_agent_engine.sh
```
This runs `adk deploy agent_engine ... warehouse_agent` (the agent folder is self-contained:
`requirements.txt` and `.env` inside it) and grants the Agent Engine service agent
(`service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com`) BigQuery job/data and
AlloyDB / Cloud SQL client roles. Note the `projects/.../locations/.../reasoningEngines/...` name it prints and
smoke-test in the console playground.

## 4. Register in Gemini Enterprise
Console: Gemini Enterprise > your app > **Agents** > **Add agent** > **Custom agent via Agent
Engine**, paste the reasoning engine resource name, name it "McLane Warehouse Copilot", and add the
description from `deploy/register_gemini_enterprise.sh`.

CLI:
```bash
GE_APP_ID={{GEMINI_ENTERPRISE_APP_ID}} \
REASONING_ENGINE=projects/{{PROJECT_NUMBER}}/locations/us-central1/reasoningEngines/{{ID}} \
bash deploy/register_gemini_enterprise.sh
```
The registration API is v1alpha; if the request shape has changed, use the console path.

## 5. Use it
Open Gemini Enterprise, choose **McLane Warehouse Copilot** from Agents and run the questions in
[DEMO_SCRIPT.md](DEMO_SCRIPT.md). Share the agent with the hackathon team from the agent's
sharing settings.

## Cloud Run alternative (ADK web UI)
```bash
make deploy-cloud-run PROJECT=$PROJECT REGION=$REGION
```

## Clean up
```bash
gcloud alloydb clusters delete wms-cluster --region=$REGION --force   # if created
bq rm -r -f $PROJECT:mclane_wms
# delete the Agent Engine instance from the Vertex AI console (Agent Engine > select > Delete)
```
