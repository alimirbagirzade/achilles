"""Achilles agent runtime — gözlem (observer) katmanı, Phase 1.

İçerik:
  * ``schemas``  — AgentSpec / AgentRun / AgentEvent + enum'lar
  * ``registry`` — ``automation_manifest.yaml`` okuyucu/sorgulayıcı
  * ``tracker``  — koşu + olay kaydedici (SQLite + JSONL), ``tracked`` dekoratörü

Phase 2 (task_queue, approvals, supervisor) HENÜZ YOK — bilinçli kapsam dışı.
"""

from __future__ import annotations

from app.agents.runtime.registry import (
    ManifestError,
    agents_requiring_approval,
    dangerous_agents,
    get_agent,
    list_agents,
    load_agent_registry,
)
from app.agents.runtime.schemas import (
    AgentAutonomy,
    AgentEvent,
    AgentEventKind,
    AgentRun,
    AgentRunStatus,
    AgentSpec,
)
from app.agents.runtime.tracker import (
    RunTracker,
    get_tracker,
    log_step,
    set_tracker,
    track_agent_run,
    tracked,
)

__all__ = [
    # schemas
    "AgentAutonomy",
    "AgentEvent",
    "AgentEventKind",
    "AgentRun",
    "AgentRunStatus",
    "AgentSpec",
    # registry
    "ManifestError",
    # tracker
    "RunTracker",
    "agents_requiring_approval",
    "dangerous_agents",
    "get_agent",
    "get_tracker",
    "list_agents",
    "load_agent_registry",
    "log_step",
    "set_tracker",
    "track_agent_run",
    "tracked",
]
