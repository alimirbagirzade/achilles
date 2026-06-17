"""RAG öğrenme döngüsü testi — tamamen çevrimdışı (ağır adımlar monkeypatch'lenir).

Ağ (arXiv) ve LLM (kart/skor) çağrıları yer almaz; yalnız durum makinesi,
ayar kelepçeleme, sayaç güncellemesi ve eğitim-sırasında-duraklat davranışı test edilir.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.research.rag_learning_loop import RagLearningLoop


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RagLearningLoop:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "storage").mkdir()
    return RagLearningLoop()


def test_default_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loop = _make(tmp_path, monkeypatch)
    st = loop.get_status()
    assert st["enabled"] is False
    assert st["stage"] == "idle"
    assert st["running"] is False


def test_enable_persists_across_instances(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loop = _make(tmp_path, monkeypatch)
    loop.set_enabled(True)
    # Yeni örnek aynı state dosyasından okur → kalıcılık.
    loop2 = RagLearningLoop()
    assert loop2.get_status()["enabled"] is True


def test_config_clamped_and_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loop = _make(tmp_path, monkeypatch)
    loop.set_config(interval_min=99999, cards_per_cycle=3, fetch_enabled=False)
    st = loop.get_status()
    assert st["interval_min"] == 1440  # üst sınıra kelepçelendi
    assert st["cards_per_cycle"] == 3
    assert st["fetch_enabled"] is False


def test_cycle_runs_steps_and_updates_counters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loop = _make(tmp_path, monkeypatch)
    monkeypatch.setattr(loop, "_training_running", lambda: False)
    monkeypatch.setattr(loop, "_fetch_new_papers", lambda: (2, 2))
    monkeypatch.setattr(loop, "_build_missing_cards", lambda limit: 1)
    monkeypatch.setattr(loop, "_score_missing", lambda limit: 3)
    monkeypatch.setattr(loop, "_refresh_mastery", lambda: 42)

    res = asyncio.run(loop.run_one_cycle())

    assert res["ok"] is True
    st = loop.get_status()
    assert st["cycles_completed"] == 1
    assert st["total_fetched"] == 2
    assert st["total_cards"] == 1
    assert st["total_scored"] == 3
    assert st["mastery_percent"] == 42
    assert st["running"] is False
    assert st["stage"] == "idle"
    assert len(st["history"]) == 1


def test_cycle_skipped_during_training(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loop = _make(tmp_path, monkeypatch)
    monkeypatch.setattr(loop, "_training_running", lambda: True)
    called = {"cards": False}

    def _cards(limit: int) -> int:
        called["cards"] = True
        return 0

    monkeypatch.setattr(loop, "_build_missing_cards", _cards)
    monkeypatch.setattr(loop, "_refresh_mastery", lambda: 10)

    res = asyncio.run(loop.run_one_cycle())

    assert res.get("skipped") == "training_running"
    assert called["cards"] is False  # ağır iş atlandı
    st = loop.get_status()
    assert st["stage"] == "paused_training"
    assert st["running"] is False


def test_fetch_skipped_when_not_due(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Çekim aralığı henüz dolmadıysa makale çekilmez ama kart/skor yine yapılır."""
    loop = _make(tmp_path, monkeypatch)
    loop.set_config(fetch_interval_hours=24)
    # Az önce çekim yapılmış gibi işaretle → bu turda çekim 'due' değil.
    import datetime as dt

    loop._state.last_fetch_at = dt.datetime.now(dt.UTC).isoformat()

    fetch_called = {"n": 0}

    def _fetch() -> tuple[int, int]:
        fetch_called["n"] += 1
        return (5, 5)

    monkeypatch.setattr(loop, "_training_running", lambda: False)
    monkeypatch.setattr(loop, "_fetch_new_papers", _fetch)
    monkeypatch.setattr(loop, "_build_missing_cards", lambda limit: 2)
    monkeypatch.setattr(loop, "_score_missing", lambda limit: 2)
    monkeypatch.setattr(loop, "_refresh_mastery", lambda: 50)

    res = asyncio.run(loop.run_one_cycle())

    assert res["ok"] is True
    assert fetch_called["n"] == 0  # çekim atlandı
    assert res["cards"] == 2
    assert res["scored"] == 2
