"""LoRA kontrol düzlemi (orkestratör) testleri."""

from __future__ import annotations

from pathlib import Path

from app.lora.control_plane import LoRAControlPlane
from app.memory.sqlite_store import SqliteStore


def _save_approved_card(store: SqliteStore, card_id: str, difficulty: float) -> None:
    store.save_knowledge_card(
        card_id=card_id,
        paper_id=f"paper_{card_id}",
        model="test",
        card={
            "title": "RSI",
            "summary": (
                "RSI, fiyatın aşırı alım ve aşırı satım bölgelerini ölçen bir "
                "momentum osilatörüdür ve 0-100 arasında değer alır."
            ),
            "formulas": [],
        },
        review_status="approved",
        lora_eligible=1,
        difficulty=difficulty,
    )


def test_run_audit_produces_report() -> None:
    """run_audit Gate kümesini çalıştırıp rapor üretmeli."""
    store = SqliteStore()
    _save_approved_card(store, "c1", 0.3)
    plane = LoRAControlPlane(store=store)

    report = plane.run_audit()
    assert report.total_input >= 1
    assert len(report.stages) >= 8


def test_run_full_includes_split() -> None:
    """run_full Gate 8'i ekleyip dataset_split üretmeli."""
    store = SqliteStore()
    for i in range(6):
        _save_approved_card(store, f"f{i}", 0.4)
    plane = LoRAControlPlane(store=store)

    report = plane.run_full(dry_run=True)
    assert report.dataset_split is not None
    gate_ids = {s.gate_id for s in report.stages}
    assert 8 in gate_ids


def test_generate_report_writes_markdown(tmp_path: Path) -> None:
    """generate_report Markdown üretip dosyaya yazmalı."""
    store = SqliteStore()
    _save_approved_card(store, "c1", 0.5)
    plane = LoRAControlPlane(store=store)
    report = plane.run_audit()

    out = tmp_path / "report.md"
    markdown = plane.generate_report(report, output_path=out)
    assert "# LoRA Denetim Raporu" in markdown
    assert out.exists()
