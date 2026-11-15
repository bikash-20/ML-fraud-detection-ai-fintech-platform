"""Pytest config: use a temporary SQLite file so tests are isolated from
the real wallet.db."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Ensure backend directory is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "test_wallet.db"
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("PENDING_TTL_SECONDS", "60")
    monkeypatch.setenv("SWEEPER_INTERVAL_SECONDS", "999")

    # Reload config so DB_PATH points at the temp file.
    from app import config
    importlib.reload(config)
    # Rebuild the engine against the new DB_PATH and re-seed.
    from app import db as app_db
    app_db.reset_engine()
    app_db.init_db()
    importlib.reload(importlib.import_module("app.seed"))
    from app.seed import seed
    with app_db.SessionLocal() as s:
        seed(s)
        s.commit()
    yield db