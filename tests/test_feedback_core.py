"""Echo feedback çekirdeği — çevrimdışı testler (tmp SQLite + tmp export).

Kayıt → Kural-1 güvenlik reddi → onay → SFT-aday export (idempotent, kanonik veriye
dokunmaz). Eğitim ASLA tetiklenmez.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.feedback.echo import APPROVED, EXPORTED, PENDING, REJECTED, EchoCollector
from app.feedback.store import FeedbackStore


@pytest.fixture
def echo(tmp_path: Path) -> EchoCollector:
    return EchoCollector(store=FeedbackStore(db_path=tmp_path / "fb.db"))


def _rec(echo: EchoCollector, correction: str, **kw: str) -> dict:
    return echo.record(
        source=kw.get("source", "rlm"),
        question=kw.get("question", "Momentum stratejisi maliyet dahil mi test edildi?"),
        bad_answer=kw.get("bad_answer", "Evet, kesinlikle çalışıyor."),
        correction=correction,
        correction_type=kw.get("correction_type", "claim_correction"),
    )


def test_clean_correction_is_pending(echo: EchoCollector) -> None:
    c = _rec(echo, "Slippage + komisyon dahil edilmeli; net Sharpe ayrı raporlanmalı.")
    assert c["status"] == PENDING
    assert c["correction_type"] == "claim_correction"


def test_guarantee_language_correction_rejected(echo: EchoCollector) -> None:
    c = _rec(echo, "Bu strateji garanti kâr sağlar, risksizdir.")
    assert c["status"] == REJECTED
    assert "Kural 1" in c["reject_reason"]


def test_guarantee_language_in_question_rejected(echo: EchoCollector) -> None:
    """Zehir 'question' alanından sızamaz (question SFT'de user-turn olur)."""
    c = echo.record(
        source="rlm",
        question="Bu stratejinin garanti kâr sağladığını test ettiniz mi?",
        bad_answer="",
        correction="Maliyet dahil test edilmeli.",
        correction_type="claim_correction",
    )
    assert c["status"] == REJECTED
    assert "Kural 1" in c["reject_reason"]


def test_guarantee_language_in_bad_answer_rejected(echo: EchoCollector) -> None:
    """Zehir 'bad_answer' alanından da reddedilir (saklanan içerik denetlenir)."""
    c = echo.record(
        source="rlm",
        question="Strateji sağlam mı?",
        bad_answer="Evet, bu garanti kâr getirir.",
        correction="Net Sharpe ayrı raporlanmalı.",
        correction_type="claim_correction",
    )
    assert c["status"] == REJECTED


def test_export_rejects_path_traversal(echo: EchoCollector) -> None:
    """out_path izinli kök (proje/temp) dışına çıkamaz (yol-geçişi savunması)."""
    with pytest.raises(ValueError):
        echo.export_approved(out_path="/etc/passwd")
    with pytest.raises(ValueError):
        echo.export_approved(out_path="C:/Windows/System32/x.jsonl")


def test_empty_correction_rejected(echo: EchoCollector) -> None:
    c = _rec(echo, "   ")
    assert c["status"] == REJECTED
    assert "Boş" in c["reject_reason"]


def test_invalid_type_falls_back_to_other(echo: EchoCollector) -> None:
    c = _rec(echo, "Maliyet kontrolü eklenmeli.", correction_type="uydurma_tip")
    assert c["correction_type"] == "other"


def test_approve_then_export_roundtrip(echo: EchoCollector, tmp_path: Path) -> None:
    c = _rec(echo, "Look-ahead'a karşı pozisyon shift(1) ile gecikmeli olmalı.")
    assert echo.approve(c["correction_id"]) is True
    assert echo.store.get(c["correction_id"])["status"] == APPROVED

    out = tmp_path / "feedback_sft.jsonl"
    res = echo.export_approved(out_path=out)
    assert res["n_exported"] == 1
    assert echo.store.get(c["correction_id"])["status"] == EXPORTED

    line = out.read_text(encoding="utf-8").strip()
    obj = json.loads(line)
    roles = [m["role"] for m in obj["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert obj["messages"][2]["content"].startswith("Look-ahead")
    assert obj["metadata"]["source"] == "feedback"
    assert obj["metadata"]["feedback_id"] == c["correction_id"]


def test_export_is_idempotent_not_data_losing(echo: EchoCollector, tmp_path: Path) -> None:
    """Export sonrası 'approved' boşalsa bile ikinci export dosyayı SİLMEZ (cumulative)."""
    c = _rec(echo, "Maliyetler (komisyon+slippage) modellenmeli.")
    echo.approve(c["correction_id"])
    out = tmp_path / "fb.jsonl"
    echo.export_approved(out_path=out)
    first = out.read_text(encoding="utf-8")
    # ikinci export: artık 'approved' yok (hepsi exported) → dosya yine aynı kalmalı
    res2 = echo.export_approved(out_path=out)
    assert res2["n_exported"] == 1
    assert out.read_text(encoding="utf-8") == first


def test_approve_rechecks_safety_after_edit(echo: EchoCollector) -> None:
    """Kayıt temizken sonradan zehir enjekte edilirse onay anında yakalanır."""
    c = _rec(echo, "Temiz düzeltme.")
    echo.store.set_status(c["correction_id"], PENDING)
    # DB'de düzeltme metnini zehirle (dış müdahale simülasyonu)
    with echo.store.session() as s:
        from app.feedback.store import FeedbackCorrection

        row = s.get(FeedbackCorrection, c["correction_id"])
        row.correction = "Bu strateji garanti kâr getirir."
    assert echo.approve(c["correction_id"]) is False
    assert echo.store.get(c["correction_id"])["status"] == REJECTED


def test_summary_counts(echo: EchoCollector) -> None:
    _rec(echo, "İyi düzeltme bir.")
    _rec(echo, "garanti kâr vaadi")  # rejected
    s = echo.summary()
    assert s["pending"] == 1
    assert s["rejected"] == 1
