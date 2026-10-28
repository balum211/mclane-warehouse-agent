#!/usr/bin/env bash
# Runs every tool against DuckDB (PostgreSQL DDL) plus the SQLite tool tests.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python -m pytest -q tests/test_portability.py tests/test_tools.py tests/test_delivery.py
