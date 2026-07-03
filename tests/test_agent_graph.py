"""Ajan etkileşim haritası — çevrimdışı testler (manifest'ten grafik + web).

Grafik yapısı (düğüm/kenar/ana-ajan) ve salt-okuma web ucu doğrulanır. Canlı durum
best-effort olduğundan yapıya bakılır, spesifik duruma değil.
"""

from __future__ import annotations

import pytest

from app.web.agent_graph import build_agent_graph

_VALID_STATUS = {"idle", "running", "blocked", "error", "done"}


def test_graph_has_nodes_and_new_agents() -> None:
    g = build_agent_graph()
    ids = {n["id"] for n in g["nodes"]}
    # Bu seansta eklenen ajanlar haritada olmalı
    assert {
        "training-orchestrator",
        "orchestration-autodrive",
        "echo-feedback",
        "sentinel-monitor",
    } <= ids
    assert len(g["nodes"]) >= 20


def test_main_agent_flagged() -> None:
    g = build_agent_graph()
    assert g["main_agent"] == "orchestration-autodrive"
    main = [n for n in g["nodes"] if n["is_main"]]
    assert len(main) == 1 and main[0]["id"] == "orchestration-autodrive"


def test_nodes_have_valid_shape() -> None:
    g = build_agent_graph()
    for n in g["nodes"]:
        assert n["status"] in _VALID_STATUS
        assert isinstance(n["reads"], list) and isinstance(n["writes"], list)
        assert n["group"] in {grp["key"] for grp in g["groups"]}


def test_edges_reference_existing_nodes() -> None:
    g = build_agent_graph()
    ids = {n["id"] for n in g["nodes"]}
    kinds = set()
    for e in g["edges"]:
        assert e["from"] in ids and e["to"] in ids
        assert e["from"] != e["to"]  # kendine kenar yok
        kinds.add(e["kind"])
    # chain topolojisi en az bir akış kenarı üretmeli
    assert "chain" in kinds


def test_chain_flow_edge_present() -> None:
    g = build_agent_graph()
    chain_edges = {(e["from"], e["to"]) for e in g["edges"] if e["kind"] == "chain"}
    # bilinen topoloji: arxiv-fetcher → rag-learning-loop
    assert ("arxiv-fetcher", "rag-learning-loop") in chain_edges


# ── web ─────────────────────────────────────────────────────────────────────

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.web.server import app  # noqa: E402


def test_graph_endpoint_ok() -> None:
    client = TestClient(app)
    r = client.get("/api/agents/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["main_agent"] == "orchestration-autodrive"
    assert isinstance(body["nodes"], list) and body["nodes"]
    assert isinstance(body["edges"], list)
