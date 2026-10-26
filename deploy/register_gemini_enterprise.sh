#!/usr/bin/env bash
# Register the deployed Agent Engine agent in a Gemini Enterprise app so employees can use it from
# the Gemini Enterprise web app. Console alternative: Gemini Enterprise > Agents > Add agent >
# "Custom agent via Agent Engine" and paste the reasoning engine resource name.
#
# Required:
#   PROJECT            project id that owns the Gemini Enterprise app
#   GE_APP_ID          Gemini Enterprise app (engine) id, from the app's URL / Apps list
#   REASONING_ENGINE   projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID
# Optional:
#   GE_LOCATION        global (default) | us | eu, the Gemini Enterprise app location
#
# The API surface is v1alpha and has changed names in the past; if this call fails, check the
# current "Register and manage ADK agents hosted on Agent Engine" page of the Gemini Enterprise docs.
set -euo pipefail
PROJECT="${PROJECT:-${GOOGLE_CLOUD_PROJECT:?set PROJECT}}"
: "${GE_APP_ID:?set GE_APP_ID}"
: "${REASONING_ENGINE:?set REASONING_ENGINE}"
GE_LOCATION="${GE_LOCATION:-global}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
if [ "$GE_LOCATION" = "global" ]; then HOST="discoveryengine.googleapis.com"; else HOST="${GE_LOCATION}-discoveryengine.googleapis.com"; fi

curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT}" \
  "https://${HOST}/v1alpha/projects/${PROJECT_NUMBER}/locations/${GE_LOCATION}/collections/default_collection/engines/${GE_APP_ID}/assistants/default_assistant/agents" \
  -d @- <<JSON
{
  "displayName": "McLane Warehouse Copilot",
  "description": "Ask about inventory, replenishment, expiring product, slotting, waves, labor, dock appointments and WMS interfaces across Manhattan Active, Blue Yonder and Argent DCs.",
  "adk_agent_definition": {
    "tool_settings": {
      "tool_description": "Warehouse operations copilot for McLane distribution centers. Use for DC inventory, FEFO/expiry, replenishment, slotting, wave progress, labor gaps, dock exceptions, shift briefings and disruption re-plans."
    },
    "provisioned_reasoning_engine": { "reasoning_engine": "${REASONING_ENGINE}" }
  }
}
JSON
echo
