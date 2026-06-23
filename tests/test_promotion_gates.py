"""Terfi kapıları testleri (çevrimdışı; sentetik)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.memory.sqlite_store import SqliteStore
from app.registry import RegistryStore
from app.registry.promotion_gates import (
    approve_dataset,
    check_rag_index_eval,
    gate_reward_dataset,
    reject_dataset,
    scan_secret_pii,
)


@pytest.fixture
def reg(tmp_path: Path) -> RegistryStore:
    return RegistryStore(SqliteStore(db_path=tmp_path / "gate.db"))


# --- dataset onayı ---------------------------------------------------------
def test_approve_dataset_transitions_and_logs(reg: RegistryStore) -> None:
    ds = reg.register_dataset(name="d", n_records=1)
    assert ds["approval_status"] == "pending"
    out = approve_dataset(reg, ds["dataset_version_id"], approver_id="ali")
    assert out["ok"] and not out["already"]
    assert out["dataset"]["approval_status"] == "approved"
    decisions = reg.list_decisions(target_id=ds["dataset_version_id"])
    assert len(decisions) == 1
    assert decisions[0]["decision"] == "approved"
    assert decisions[0]["from_status"] == "pending"


def test_approve_dataset_idempotent(reg: RegistryStore) -> None:
    ds = reg.register_dataset(name="d", n_records=1)
    approve_dataset(reg, ds["dataset_version_id"], approver_id="ali")
    again = approve_dataset(reg, ds["dataset_version_id"], approver_id="ali")
    assert again["already"] is True
    # ikinci onay yeni karar yazmamalı
    assert len(reg.list_decisions(target_id=ds["dataset_version_id"])) == 1


def test_approve_unknown_dataset_raises(reg: RegistryStore) -> None:
    with pytest.raises(ValueError):
        approve_dataset(reg, "ds_nope", approver_id="ali")


def test_reject_dataset(reg: RegistryStore) -> None:
    ds = reg.register_dataset(name="d", n_records=1)
    out = reject_dataset(reg, ds["dataset_version_id"], approver_id="ali", reason="kalite düşük")
    assert out["dataset"]["approval_status"] == "rejected"
    assert reg.list_decisions(target_id=ds["dataset_version_id"])[0]["decision"] == "rejected"


# --- RAG indeks retrieval-eval kapısı --------------------------------------
def test_rag_index_eval_pass(reg: RegistryStore) -> None:
    metrics = {
        "recall_at_10": 0.80,
        "citation_accuracy": 0.90,
        "grounding_score": 0.85,
        "abstention_correct": 0.95,
    }
    out = check_rag_index_eval(reg, "rag_x", metrics)
    assert out["passed"] is True
    assert out["decision"]["decision"] == "approved"


def test_rag_index_eval_fail_logs_blocked(reg: RegistryStore) -> None:
    metrics = {
        "recall_at_10": 0.50,  # eşik 0.70 → düşer
        "citation_accuracy": 0.90,
        "grounding_score": 0.85,
        "abstention_correct": 0.95,
    }
    out = check_rag_index_eval(reg, "rag_y", metrics)
    assert out["passed"] is False
    assert out["failures"]
    assert out["decision"]["decision"] == "blocked"


# --- sır / PII taraması ----------------------------------------------------
def test_scan_detects_secret_and_pii() -> None:
    text = "key sk-ABCDEFGHIJKLMNOPQRSTUVWX iletişim: john@example.com"
    res = scan_secret_pii(text)
    assert not res.clean
    assert res.has_secret
    assert res.has_pii
    # sır loglanırken maskelenmeli (tam dizge görünmemeli)
    assert all("sk-ABCDEFG" not in f["preview"] for f in res.secret_findings)


def test_scan_clean_text_passes() -> None:
    res = scan_secret_pii("Volatilite rejimi momentum gücünü etkiler; bu bir hipotezdir.")
    assert res.clean
    assert not res.has_secret and not res.has_pii


def test_scan_does_not_flag_bare_11_digit_number() -> None:
    # Finansal veride çıplak uzun sayılar PII değildir (yanlış-pozitif önlemi).
    res = scan_secret_pii("İşlem hacmi 12345678901 birim, fiyat 1850.25")
    assert res.clean


def test_gate_reward_blocks_on_secret(reg: RegistryStore) -> None:
    rew = reg.register_reward(name="r", method="dpo", n_examples=3)
    out = gate_reward_dataset(
        reg,
        rew["reward_version_id"],
        ["normal örnek", "AKIA0123456789ABCDEF sızdı"],
    )
    assert out["clean"] is False
    assert out["decision"]["decision"] == "blocked"
    rows = reg.list_rewards()
    assert rows[0]["secret_scanned"] == 2  # bulgu


def test_gate_reward_passes_on_clean(reg: RegistryStore) -> None:
    rew = reg.register_reward(name="r", method="dpo", n_examples=3)
    out = gate_reward_dataset(reg, rew["reward_version_id"], ["temiz örnek", "başka örnek"])
    assert out["clean"] is True
    assert out["decision"]["decision"] == "approved"
    assert reg.list_rewards()[0]["secret_scanned"] == 1  # temiz
