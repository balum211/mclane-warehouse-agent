# McLane warehouse agent: common tasks. Run `make help`.
PY ?= python
PROJECT ?= $(GOOGLE_CLOUD_PROJECT)
REGION ?= us-central1
DATASET ?= mclane_wms

.PHONY: help install data test web run bq-load alloydb-load deploy-agent-engine deploy-cloud-run register-gemini-enterprise

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-28s %s\n", $$1, $$2}'

install: ## Install dependencies with uv (creates .venv)
	uv sync --extra dev

data: ## Generate synthetic WMS data and load local SQLite (data/wms.db)
	$(PY) -m warehouse_data.load_sqlite --csv data/csv --db data/wms.db --generate

test: ## Run unit, portability and end-to-end agent tests (no Gemini calls)
	$(PY) -m pytest -q

web: ## Start the ADK dev UI on http://localhost:8000
	adk web .

run: ## Chat with the agent in the terminal
	adk run warehouse_agent

bq-load: ## Load the CSVs into BigQuery (PROJECT, DATASET)
	$(PY) -m warehouse_data.load_bigquery --project $(PROJECT) --dataset $(DATASET) --csv data/csv

alloydb-load: ## Load the CSVs into AlloyDB (ALLOYDB_* env vars)
	$(PY) -m warehouse_data.load_alloydb --csv data/csv --drop

deploy-agent-engine: ## Deploy to Vertex AI Agent Engine (needs WMS_DB_BACKEND=bigquery or alloydb)
	bash deploy/deploy_agent_engine.sh

deploy-cloud-run: ## Deploy the agent + ADK web UI to Cloud Run
	adk deploy cloud_run --project $(PROJECT) --region $(REGION) --service_name mclane-warehouse-agent --with_ui warehouse_agent

register-gemini-enterprise: ## Register the Agent Engine agent in a Gemini Enterprise app
	bash deploy/register_gemini_enterprise.sh
