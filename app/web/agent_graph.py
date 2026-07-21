"""agent_graph.py — canlı ajan etkileşim haritası verisi (14 arayüz "ışıklı yol"u besler).

Manifest'ten (automation_manifest.yaml) ajan DÜĞÜMLERİ + kenarlar üretir:
  - chain kenarı: topolojik `after` (akış yönü A→B; "ordan buraya gider").
  - data kenarı: A `writes` bir kaynağı, B `reads` ederse veri-bağı A→B (kim kimle ilişkili).

Her düğüme CANLI durum (idle/running/blocked/error/done) BEST-EFFORT çözülür (orchestration
koşusu / auto-lora / rag-loop / training state'lerinden). Durum çözülemezse 'idle'; asla çökmez.
Salt-okuma — hiçbir şeyi tetiklemez.
"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Ajanı yaşam-döngüsü grubuna eşle (arayüz katmanlaması; bilinmeyen → "other").
_GROUP: dict[str, str] = {
    "arxiv-fetcher": "arastirma",
    "auto-researcher": "arastirma",
    "rag-trend-scanner": "arastirma",
    "literature-scout": "arastirma",
    "makale-arastirma": "arastirma",
    "rag-learning-loop": "ogrenme",
    "ingestion-quality-scorer": "ogrenme",
    "paper-mastery-agent": "ogrenme",
    "status-manager": "ogrenme",
    "reflection-agent": "ogrenme",
    "research-orchestrator": "ogrenme",
    "scientific-tool-runtime": "dogrulama",
    "hypothesis-evaluator": "dogrulama",
    "rlm-controller": "dogrulama",
    "lora-control-plane": "egitim",
    "dataset-quality-gate": "egitim",
    "model-data-registry": "egitim",
    "auto-lora-pipeline": "egitim",
    "adapter-eval": "egitim",
    "tool-use-trainer": "egitim",
    "rules-updater": "egitim",
    "model-advisor": "egitim",
    "training-orchestrator": "orkestrasyon",
    "orchestration-autodrive": "orkestrasyon",
    "echo-feedback": "geri-bildirim",
    "sentinel-monitor": "izleme",
}

_GROUP_LABELS: dict[str, str] = {
    "arastirma": "Araştırma & Kaynak",
    "ogrenme": "Öğrenme & Anlama",
    "dogrulama": "Doğrulama",
    "egitim": "Eğitim Hattı",
    "orkestrasyon": "Orkestrasyon (Ana Ajan)",
    "geri-bildirim": "Geri Bildirim",
    "izleme": "İzleme",
    "other": "Diğer",
}

# "Ana ajan" — eğitim tuşuna bağlı, diğerlerini devreye sokan (claude -p AutoDriver).
_MAIN_AGENT = "orchestration-autodrive"


def _resource_keys(raw: str) -> set[str]:
    """reads/writes girdisini normalize kaynak anahtar(lar)ına indirger.

    "sqlite: papers, chunks, knowledge_cards (not)" → {sqlite:papers, sqlite:chunks,
    sqlite:knowledge_cards} (çoklu tablo ayrıştırılır → gerçek veri-bağı eşleşir).
    Diğer kaynaklar (dosya/yol) tek anahtar."""
    s = raw.strip().lower()
    s = re.split(r"\s*\(", s, maxsplit=1)[0]  # açıklama parantezini at
    s = s.split("#", 1)[0].strip().rstrip("/")
    if not s:
        return set()
    if s.startswith("sqlite:"):
        tables = s[len("sqlite:") :].strip()
        return {f"sqlite:{t.strip()}" for t in tables.split(",") if t.strip()}
    return {s}


def _autonomy_value(spec: Any) -> str:
    a = getattr(spec, "autonomy", "manual")
    return getattr(a, "value", str(a))


def _agent_status(agent_id: str, orch_stage_status: dict[str, str]) -> str:
    """Best-effort canlı durum. Bilinmeyen/çözülemeyen → 'idle' (asla çökmez)."""
    # Aktif orkestrasyon koşusundaki aşamalar (orchestrator/autodrive'ı da aydınlatır).
    if agent_id in ("training-orchestrator", "orchestration-autodrive"):
        if orch_stage_status.get("_run") == "running":
            return "running"
        if orch_stage_status.get("_run") == "blocked":
            return "blocked"
        if orch_stage_status.get("_run") == "failed":
            return "error"
    try:
        if agent_id == "auto-lora-pipeline":
            from app.lora.auto_pipeline import get_auto_pipeline

            stage = str(get_auto_pipeline().get_status().get("stage", "idle"))
            if stage in ("checking", "training", "evaluating"):
                return "running"
            if stage in ("gate_failed", "train_failed", "eval_failed"):
                return "error"
            if stage in ("ready_to_train", "eval_passed"):
                return "blocked"  # insan onayı bekliyor
        elif agent_id == "rag-learning-loop":
            import json
            from pathlib import Path

            p = Path("storage") / "rag_learning_state.json"
            if p.exists():
                stg = str(json.loads(p.read_text(encoding="utf-8")).get("stage", ""))
                if stg and stg not in ("idle", "error", "paused_training"):
                    return "running"
                if stg == "error":
                    return "error"
    except Exception as exc:  # durum kaynağı okunamasa bile harita çökmesin
        log.debug("agent_graph: %s durumu çözülemedi: %s", agent_id, exc)
    return "idle"


def build_agent_graph() -> dict[str, Any]:
    """Manifest + canlı durumdan {nodes, edges, groups, main_agent} üret (salt-okuma)."""
    from app.agents.runtime.registry import list_agents

    specs = list_agents()

    # Aktif orkestrasyon koşusunun bütünsel durumu (ana-ajan düğümlerini aydınlatmak için).
    orch_stage_status: dict[str, str] = {}
    try:
        from app.orchestration.orchestrator import TrainingOrchestrator

        runs = TrainingOrchestrator().list_runs(limit=1)
        if runs:
            orch_stage_status["_run"] = str(runs[0].get("status", ""))
    except Exception as exc:
        log.debug("agent_graph: orkestrasyon durumu okunamadı: %s", exc)

    nodes: list[dict[str, Any]] = []
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for spec in specs:
        aid = spec.agent_id
        group = _GROUP.get(aid, "other")
        nodes.append(
            {
                "id": aid,
                "name": spec.name,
                "group": group,
                "group_label": _GROUP_LABELS.get(group, group),
                "autonomy": _autonomy_value(spec),
                "dangerous": bool(getattr(spec, "dangerous", False)),
                "approval_required": bool(getattr(spec, "approval_required", False)),
                "is_main": aid == _MAIN_AGENT,
                "trigger": getattr(spec, "trigger", ""),
                "reads": list(getattr(spec, "reads", []) or []),
                "writes": list(getattr(spec, "writes", []) or []),
                "safety_gates": list(getattr(spec, "safety_gates", []) or []),
                "status": _agent_status(aid, orch_stage_status),
            }
        )
        for w in getattr(spec, "writes", []) or []:
            for k in _resource_keys(w):
                writers.setdefault(k, []).append(aid)
        for r in getattr(spec, "reads", []) or []:
            for k in _resource_keys(r):
                readers.setdefault(k, []).append(aid)

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    # 1) Chain kenarları (akış yönü: after → step).
    try:
        from app.agents.runtime.chain import resolve_chain

        for step in resolve_chain():
            to_id = getattr(step, "step", None) or (
                step.get("step") if isinstance(step, dict) else None
            )
            afters = getattr(step, "after", None)
            if afters is None and isinstance(step, dict):
                afters = step.get("after", [])
            if not to_id:
                continue
            for src in afters or []:
                key = (str(src), str(to_id), "chain")
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": str(src), "to": str(to_id), "kind": "chain"})
    except Exception as exc:
        log.debug("agent_graph: chain çözülemedi: %s", exc)

    # 2) Veri kenarları (A yazar R, B okur R → A→B). Gürültüyü azalt: aynı çift bir kez.
    node_ids = {n["id"] for n in nodes}
    for resource, w_agents in writers.items():
        for wa in w_agents:
            for ra in readers.get(resource, []):
                if wa == ra or wa not in node_ids or ra not in node_ids:
                    continue
                key = (wa, ra, "data")
                if key in seen or (wa, ra, "chain") in seen:
                    continue
                seen.add(key)
                edges.append({"from": wa, "to": ra, "kind": "data", "resource": resource})

    return {
        "nodes": nodes,
        "edges": edges,
        "groups": [{"key": k, "label": v} for k, v in _GROUP_LABELS.items()],
        "main_agent": _MAIN_AGENT,
    }
