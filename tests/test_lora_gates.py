"""Doğrulama kapıları (Gate 0-8) entegrasyon testleri."""

from __future__ import annotations

from app.lora.dataset_builder import SYSTEM_PROMPT
from app.lora.gates import (
    gate_0_source,
    gate_1_schema,
    gate_2_curriculum,
    gate_3_domain,
    gate_4_quality,
    gate_5_math,
    gate_7_safety,
    gate_8_split,
)


def _approved_card(card_id: str, summary: str, difficulty: float = 0.5) -> dict:
    return {
        "card_id": card_id,
        "paper_id": f"paper_{card_id}",
        "review_status": "approved",
        "lora_eligible": 1,
        "difficulty": difficulty,
        "created_at": "2026-01-01T00:00:00Z",
        "card_json": {
            "title": "RSI",
            "summary": summary,
            "formulas": [],
        },
    }


def _example(source_id: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "RSI nedir?"},
            {"role": "assistant", "content": "RSI bir momentum osilatörüdür."},
        ],
        "metadata": {"source_id": source_id},
    }


def test_gate_0_passes_for_valid_card() -> None:
    """Geçerli onaylı kart (domain + created_at) Gate 0'ı geçmeli."""
    card = _approved_card("c1", "RSI momentum göstergesi ve formül içerir.")
    result = gate_0_source([card])
    assert result.passed is True


def test_gate_0_rejects_unapproved() -> None:
    """Onaysız kart Gate 0'da reddedilmeli."""
    card = _approved_card("c1", "momentum formül")
    card["review_status"] = "pending"
    result = gate_0_source([card])
    assert result.passed is False
    assert result.rejected_count == 1


def test_gate_1_schema_validates_message_order() -> None:
    """Doğru rol sıralı örnek Gate 1'i geçmeli."""
    result = gate_1_schema([_example("s1")])
    assert result.passed is True


def test_gate_2_rejects_invalid_difficulty() -> None:
    """0-1 dışı difficulty Gate 2'de reddedilmeli."""
    card = _approved_card("c1", "momentum", difficulty=1.5)
    result = gate_2_curriculum([card])
    assert result.passed is False


def test_gate_3_requires_domain() -> None:
    """Domain bulunamayan kart Gate 3'te reddedilmeli."""
    card = _approved_card("c1", "xyzzy plugh")
    card["card_json"]["title"] = "qqq"
    result = gate_3_domain([card])
    assert result.passed is False


def test_gate_4_quality_returns_clean_list() -> None:
    """Gate 4 temiz kart listesini de döndürmeli."""
    card = _approved_card(
        "c1",
        "RSI fiyatın aşırı alım ve aşırı satım bölgelerini ölçen momentum osilatörüdür.",
    )
    result, clean = gate_4_quality([card])
    assert result.passed is True
    assert len(clean) == 1


def test_gate_5_math_flags_overconfident() -> None:
    """Aşırı emin ifade Gate 5'te reddedilmeli."""
    card = _approved_card("c1", "Bu strateji kesinlikle garanti kazandırır her zaman.")
    result = gate_5_math([card])
    assert result.passed is False


def test_gate_7_safety_blocks_secret() -> None:
    """Sır içeren kart Gate 7'de (BLOCKER) reddedilmeli."""
    card = _approved_card("c1", "password=hunter2 ile giriş yapılır gerçekten uzun metin.")
    result = gate_7_safety([card])
    assert result.passed is False


def test_gate_8_split_no_leakage_for_distinct_sources() -> None:
    """Farklı kaynaklı örnekler Gate 8'de sızıntısız bölünmeli."""
    examples = [_example(f"src_{i}") for i in range(12)]
    result, split = gate_8_split(examples)
    assert result.passed is True
    assert len(split.train) + len(split.valid) + len(split.test) == 12
