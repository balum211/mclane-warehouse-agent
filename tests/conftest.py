"""Test fixtures: a small, deterministic SQLite WMS database built once per test session."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def wms_db(tmp_path_factory):
    from warehouse_data.generate import generate
    from warehouse_data.load_sqlite import load
    from warehouse_agent import db

    root: Path = tmp_path_factory.mktemp("wms")
    generate(root / "csv")  # same dataset as the demo
    load(root / "csv", root / "wms.db")
    os.environ["WMS_DB_BACKEND"] = "sqlite"
    db.set_backend(db.SQLiteBackend(str(root / "wms.db")))
    yield root / "wms.db"
    db.set_backend(None)
