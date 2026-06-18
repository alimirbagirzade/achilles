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
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    AutomationTask,
    RiskLevel,
    SupervisorDecision,
    TaskStatus,
)
from app.agents.runtime.tracker import (
    RunTracker,
    cancel_stale_running_agent_runs,
    get_tracker,
    log_step,
    log_system_event,
    set_tracker,
    track_agent_run,
    tracked,
)

__all__ = [
    "AgentAutonomy",
    "AgentEvent",
    "AgentEventKind",
    "AgentRun",
    "AgentRunStatus",
    "AgentSpec",
    "ApprovalDecision",
    "ApprovalRequest",
    "ApprovalStatus",
    "AutomationTask",
    "ManifestError",
    "RiskLevel",
    "RunTracker",
    "SupervisorDecision",
    "TaskStatus",
    "agents_requiring_approval",
    "cancel_stale_running_agent_runs",
    "dangerous_agents",
    "get_agent",
    "get_tracker",
    "list_agents",
    "load_agent_registry",
    "log_step",
    "log_system_event",
    "set_tracker",
    "track_agent_run",
    "tracked",
]
