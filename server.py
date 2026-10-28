"""Minimal FastAPI server exposing the ADK agent, as in the sdd-adk-antigravity codelab.

    uv run uvicorn server:app --host 0.0.0.0 --port 8080

`get_fast_api_app` serves every agent folder under AGENTS_DIR (here: warehouse_agent) with the ADK
REST API (/run, /run_sse, session endpoints) and, with SERVE_WEB_INTERFACE=true, the ADK dev UI.
Cloud Run sets PORT.
"""

import os

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    session_service_uri=os.environ.get("SESSION_SERVICE_URI"),  # e.g. a Postgres URL; in-memory when unset
    allow_origins=os.environ.get("ALLOW_ORIGINS", "*").split(","),
    web=os.environ.get("SERVE_WEB_INTERFACE", "true").lower() == "true",
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
