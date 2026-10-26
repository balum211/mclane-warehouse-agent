"""Runtime configuration (read from environment / .env)."""

import os

from dotenv import load_dotenv

load_dotenv()

# Gemini model for every agent. Override per environment, e.g. WMS_AGENT_MODEL=gemini-3.5-pro.
MODEL = os.environ.get("WMS_AGENT_MODEL", "gemini-3.5-flash")
# Optional cheaper / faster model for the parallel briefing collectors.
SNAPSHOT_MODEL = os.environ.get("WMS_SNAPSHOT_MODEL", MODEL)
TEMPERATURE = float(os.environ.get("WMS_AGENT_TEMPERATURE", "0.2"))
