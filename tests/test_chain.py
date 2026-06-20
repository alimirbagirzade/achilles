"""Çalıştırma zinciri (chain) testleri — offline; gerçek manifest + sentetik bozuk manifest."""

from __future__ import annotations

import pytest
import yaml

from app.agents.runtime.chain import ChainError, resolve_chain


# --- gerçek manifest -----------------------------------------------------
def test_chain_resolves_without_cycle() -> None:
    steps = resolve_chain()
    assert steps
    ids = [s.step for s in steps]
    assert len(ids) == len(set(ids))  # tekrarlanan adım yok


def test_chain_is_topologically_ordered() -> None:
    steps = resolve_chain()
    pos = {s.step: s.order for s in steps}
    for s in steps:
        for dep in s.after:
            assert pos[dep] < s.order  # her bağımlılık daha önce gelir


def test_chain_steps_are_known_agents() -> None:
    from app.agents.runtime.registry import list_agents

    known = {a.agent_id for a in list_agents()}
    for s in resolve_chain():
        assert s.step in known


def test_chain_human_gates_flagged() -> None:
    steps = {s.step: s for s in resolve_chain()}
    assert steps["auto-lora-pipeline"].requires_approval is True  # tehlikeli + onay
    assert steps["rules-updater"].requires_approval is True
    assert steps["arxiv-fetcher"].requires_approval is False  # otonom


# --- sentetik bozuk manifest (doğrulama) ---------------------------------
def _agent(aid: str) -> dict:
    return {"agent_id": aid, "name": aid, "file": "x.py", "entrypoint": "x"}


def _manifest(tmp_path, agents: list[dict], chain: list[dict]):
    p = tmp_path / "automation_manifest.yaml"
    p.write_text(
        yaml.safe_dump({"version": 1, "agents": agents, "chain": chain}, allow_unicode=True),
        encoding="utf-8",
    )
    return p


def test_cycle_raises(tmp_path) -> None:
    p = _manifest(
        tmp_path,
        [_agent("a"), _agent("b")],
        [{"step": "a", "after": ["b"]}, {"step": "b", "after": ["a"]}],
    )
    with pytest.raises(ChainError):
        resolve_chain(p)


def test_unknown_step_raises(tmp_path) -> None:
    p = _manifest(tmp_path, [_agent("a")], [{"step": "zzz", "after": []}])
    with pytest.raises(ChainError):
        resolve_chain(p)


def test_bad_after_ref_raises(tmp_path) -> None:
    p = _manifest(tmp_path, [_agent("a")], [{"step": "a", "after": ["nope"]}])
    with pytest.raises(ChainError):
        resolve_chain(p)


def test_missing_chain_section_raises(tmp_path) -> None:
    p = tmp_path / "automation_manifest.yaml"
    p.write_text(yaml.safe_dump({"version": 1, "agents": [_agent("a")]}), encoding="utf-8")
    with pytest.raises(ChainError):
        resolve_chain(p)
