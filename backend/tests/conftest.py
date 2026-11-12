"""Pytest fixtures providing isolated temporary SQLite databases and test FastAPI client."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_app(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test_council.db"
    ckpt_file = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", ckpt_file.as_posix())
    monkeypatch.setenv("COST_POLICY_MODE", "zero_paid")
    monkeypatch.setenv("ALLOW_PAID_PROVIDERS", "false")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    # Clear cached settings & rebind database session engine for isolated test DB
    from app import config
    from app.database import session as db_session

    config.get_settings.cache_clear()
    new_engine = db_session._build_engine()
    monkeypatch.setattr(db_session, "engine", new_engine)
    db_session.SessionLocal.configure(bind=new_engine)
    db_session.init_db()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client, db_session
    config.get_settings.cache_clear()
