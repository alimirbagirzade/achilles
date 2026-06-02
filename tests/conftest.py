"""Shared test fixtures: isolated temp DB / chroma per test session."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_storage(tmp_path_factory):
    base = tmp_path_factory.mktemp("achilles_test")
    os.environ["ACHILLES_SQLITE_PATH"] = str(base / "test.db")
    os.environ["ACHILLES_CHROMA_PATH"] = str(base / "chroma")
    os.environ["ACHILLES_ALLOW_FAKE_EMBEDDINGS"] = "true"
    # clear cached settings so env overrides take effect
    from app.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    yield


@pytest.fixture
def store():
    from app.memory.sqlite_store import SqliteStore

    return SqliteStore()
