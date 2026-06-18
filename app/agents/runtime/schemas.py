"""Agent runtime gözlem (observer) Pydantic v2 modelleri — Phase 1.

Bu katman YALNIZCA gözlemdir: ajan koşularını (``AgentRun``) ve koşu içindeki
olayları (``AgentEvent``) tanımlar. Kontrol/onay düzlemi (task queue, approvals,
supervisor) bilinçli olarak Phase 2'ye bırakılmıştır — burada YOK.

Şemalar ``automation_manifest.yaml`` (registry) ve ``tracker`` tarafından kullanılır.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentAutonomy(StrEnum):
    """Bir ajanın insan müdahalesi olmadan ne kadar ileri gidebileceği."""

    manual = "manual"  # her zaman elle tetiklenir
    semi_auto = "semi_auto"  # tetiklenince tek tur kendi yürür
    autonomous = "autonomous"  # arka planda kendi döngüsünde yürür (varsayılan KAPALI olabilir)
    requires_approval = "requires_approval"  # tehlikeli adım insan onayı bekler
    dangerous_without_approval = "dangerous_without_approval"  # onaysız çalıştırılması RİSKLİ


class AgentRunStatus(StrEnum):
    """Bir ajan koşusunun yaşam döngüsü durumu."""

    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"


class AgentEventKind(StrEnum):
    """Koşu içindeki bir olayın türü."""

    start = "start"
    step = "step"
    info = "info"
    output = "output"
    warning = "warning"
    error = "error"
    finish = "finish"


class AgentSpec(BaseModel):
    """``automation_manifest.yaml`` içindeki tek bir runtime-agent tanımı.

    Alanlar denetimde (audit) çıkarılan gerçek davranışı yansıtır; bu bir
    BELGE + KEŞİF kaydıdır, çalışma zamanında davranışı zorlamaz (Phase 1).
    """

    agent_id: str
    name: str
    file: str
    entrypoint: str
    trigger: str = ""
    autonomy: AgentAutonomy = AgentAutonomy.manual
    dangerous: bool = False
    default_enabled: bool = False
    writes: list[str] = Field(default_factory=list)
    reads: list[str] = Field(default_factory=list)
    safety_gates: list[str] = Field(default_factory=list)
    approval_required: bool = False
    stop_method: str = ""
    status_location: str = ""
    known_failure_modes: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    """Bir koşu içinde kaydedilen tek bir olay."""

    event_id: str
    run_id: str
    ts: str
    kind: AgentEventKind = AgentEventKind.info
    level: str = "info"
    message: str | None = None
    payload: dict[str, Any] | None = None


class AgentRun(BaseModel):
    """Tek bir ajan koşusunun (run) tam kaydı."""

    run_id: str
    agent_id: str
    task_id: str | None = None
    status: AgentRunStatus = AgentRunStatus.running
    trigger_type: str = "manual"
    trigger_payload: dict[str, Any] | None = None
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None
    outputs: list[Any] | None = None
