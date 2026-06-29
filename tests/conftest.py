"""Shared test fixtures: isolated temp DB / chroma per test session."""

from __future__ import annotations

import os

import httpx
import pytest


def _ollama_running() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    if _ollama_running():
        return
    skip = pytest.mark.skip(reason="Ollama çalışmıyor — @pytest.mark.ollama testi atlandı")
    for item in items:
        if item.get_closest_marker("ollama"):
            item.add_marker(skip)


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


@pytest.fixture(autouse=True)
def _reset_web_rate_limiter():
    """Her testten ÖNCE global hız sınırlayıcı pencerelerini temizle.

    TestClient tüm web testlerinde aynı IP'den ("testclient") vurur ve global
    `_rate_limiter` (120/dk, 60s kayan pencere) süreç-boyu paylaşılır. CI suite'i
    ~26s'de bitince TÜM web istekleri tek 60s penceresine paketlenir; toplam 120'yi
    aşınca geç çalışan alakasız testler 429 alır (örn. test_web_training_gate KeyError
    'ok'). Yerelde (yavaş) pencere kendiliğinden sıfırlandığı için gizliydi. Çözüm:
    her teste taze pencere → test-izolasyonu. Yalnız server zaten import edilmişse
    dokunur (import yan etkisi yok). Dedicated rate-limit testi kendi RateLimiter
    örneğini kurar → etkilenmez."""
    import sys

    mod = sys.modules.get("app.web.server")
    if mod is not None:
        for attr in ("_rate_limiter", "_upload_rate_limiter"):
            limiter = getattr(mod, attr, None)
            if limiter is not None:
                limiter._hits.clear()
    yield


@pytest.fixture
def store():
    from app.memory.sqlite_store import SqliteStore

    return SqliteStore()
