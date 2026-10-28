#!/usr/bin/env bash
# Add the spec-kit slash commands (/speckit.constitution, .specify, .clarify, .plan, .tasks, .analyze,
# .implement) to this repo, the same way the sdd-adk-antigravity codelab starter ships them.
#
# Option 1 (recommended): copy them from your clone of the codelab starter (sdd-adk-agents-agy):
#   bash scripts/install_speckit.sh ~/sdd-adk-agents-agy
# Option 2: no clone available: initialise spec-kit with its CLI, keeping this repo's constitution:
#   bash scripts/install_speckit.sh --specify-cli
#
# Never overwrites .specify/memory/constitution.md, AGENTS.md, .agents/rules or .agents/skills here.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--specify-cli" ]]; then
  cp .specify/memory/constitution.md /tmp/wms-constitution.md
  # spec-kit asks which agent to target; pick the one your Antigravity build supports (gemini works).
  uvx --from git+https://github.com/github/spec-kit.git specify init --here --force
  cp /tmp/wms-constitution.md .specify/memory/constitution.md
  echo "spec-kit initialised; constitution kept. If its commands landed outside .agents/workflows, move them there."
  exit 0
fi

SRC="${1:?usage: install_speckit.sh <path-to-sdd-adk-agents-agy> | --specify-cli}"
[[ -d "$SRC/.agents/workflows" ]] || { echo "No .agents/workflows in $SRC"; exit 1; }
mkdir -p .agents/workflows .specify
cp -n "$SRC"/.agents/workflows/speckit.*.md .agents/workflows/ 2>/dev/null || true
for d in templates scripts; do
  [[ -d "$SRC/.specify/$d" ]] && cp -rn "$SRC/.specify/$d" .specify/
done
chmod +x .specify/scripts/*/*.sh 2>/dev/null || true
echo "Installed: $(ls .agents/workflows | tr '\n' ' ')"
echo "Next: in Antigravity run /speckit.specify for the next feature (see specs/ for 001 and 002)."
