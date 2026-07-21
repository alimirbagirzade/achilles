"""Orkestrasyon web uçları — dayanıklı eğitim hattı (tek-tık + canlı izleme).

`server.py`'ye TEK satır (`include_router`) ile bağlanır → sıcak dosya minimal dokunulur.
Uçlar `TrainingOrchestrator`'ı sürer: salt-okuma aşamaları gözetimsiz yürür; insan
kapılarında (deep-hunt, approval) DURUR. Gerçek eğitim ASLA gözetimsiz başlamaz (Kural 8) —
tehlikeli train/eval/registry aşamaları varsayılan HANDOFF'tur.

Kimlik doğrulama: `require_auth` (token boşsa lokal-açık, mevcut davranışla aynı).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.web.security import require_auth, require_human

router = APIRouter(
    prefix="/api/orchestration", tags=["orchestration"], dependencies=[Depends(require_auth)]
)


class OrchestrationStartRequest(BaseModel):
    model: str = Field(default="", max_length=128)  # boş → ayardan (peft_base_model)
    # profile de adapter_name ile aynı disiplinde kalıplı: dry-run komut dizesine gömülür,
    # serbest-metin (boşluk/shell metakarakteri) yaniltici/kopyalaninca zararli olmasin.
    profile: str = Field(default="discipline_safe_local", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    # adapter_name detached_launch._ADAPTER_RE ile aynı kalıp (yol-geçişi savunması, erken ret)
    adapter_name: str = Field(default="achilles_lora", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    iters: int = Field(default=300, ge=1, le=100000)  # üst sınır: anlamsız dev değerleri ele
    hunt_ack: bool = False  # Kademe-2 derin av tamamlandı mı (ZORUNLU gate)
    auto_run: bool = True  # başlattıktan sonra blocked olana dek ilerlet (tek-tık)


class OrchestrationResumeRequest(BaseModel):
    hunt_ack: bool = False


class OrchestrationRecoverRequest(BaseModel):
    timeout_min: float = Field(default=30.0, ge=1.0, le=100000.0)


def _orchestrator() -> Any:
    from app.orchestration.orchestrator import TrainingOrchestrator

    return TrainingOrchestrator()


@router.post("/start")
def orchestration_start(req: OrchestrationStartRequest, request: Request) -> dict[str, Any]:
    """Dayanıklı eğitim orkestrasyonunu BAŞLAT (tek-tık).

    `auto_run=true` (varsayılan): salt-okuma aşamalarını yürütür, insan kapısında durur.
    Gerçek eğitim için `hunt_ack=true` + ayrı taze onay (Kural 8) gerekir.

    `hunt_ack=true` bir İNSAN yetki beyanıdır ("Kademe-2 derin avı yaptım") ve
    doğrulanmadan kabul edilir → sürücü scope'una KAPALI. Aksi halde motor, zorunlu
    eğitim-öncesi avı basitçe `{"hunt_ack": true}` göndererek atlayabilirdi (v5
    regresyonunun kök nedeni tam olarak buydu). Başlatmanın kendisi serbesttir.
    """
    from app.config import get_settings

    if req.hunt_ack:
        require_human(request)

    orch = _orchestrator()
    model = req.model or getattr(get_settings(), "peft_base_model", "")
    run_id = orch.start(
        model=model,
        profile=req.profile,
        adapter_name=req.adapter_name,
        params={"iters": req.iters, "hunt_ack": req.hunt_ack},
    )
    snap = orch.run_until_blocked(run_id) if req.auto_run else orch.status(run_id)
    return {"run_id": run_id, **snap}


@router.get("/status/{run_id}")
def orchestration_status(run_id: str) -> dict[str, Any]:
    """Koşunun aşama durumunu döndür (dashboard polling)."""
    orch = _orchestrator()
    snap = orch.status(run_id)
    if snap.get("run") is None:
        raise HTTPException(status_code=404, detail=f"Koşu bulunamadı: {run_id}")
    return snap


@router.get("/timeline/{run_id}")
def orchestration_timeline(run_id: str, limit: int = 200) -> dict[str, Any]:
    """Koşunun olay zaman çizelgesini döndür."""
    orch = _orchestrator()
    if orch.store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Koşu bulunamadı: {run_id}")
    return {"run_id": run_id, "events": orch.timeline(run_id, limit=limit)}


@router.post("/resume/{run_id}")
def orchestration_resume(
    run_id: str, req: OrchestrationResumeRequest, request: Request
) -> dict[str, Any]:
    """Bloke/başarısız koşuyu sürdür — tamamlanan aşamalar atlanır (checkpoint).

    `hunt_ack=true` insan yetki beyanıdır → sürücüye kapalı (bkz. `orchestration_start`).
    """
    import json

    if req.hunt_ack:
        require_human(request)

    orch = _orchestrator()
    run = orch.store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Koşu bulunamadı: {run_id}")
    if req.hunt_ack:
        params = dict(run.get("params") or {})
        params["hunt_ack"] = True
        orch.store.update_run(run_id, params_json=json.dumps(params, ensure_ascii=False))
    return orch.run_until_blocked(run_id)


@router.get("/runs")
def orchestration_runs(limit: int = 20) -> dict[str, Any]:
    """Son orkestrasyon koşularını listele."""
    orch = _orchestrator()
    return {"runs": orch.list_runs(limit=limit)}


@router.post("/recover")
def orchestration_recover(req: OrchestrationRecoverRequest) -> dict[str, Any]:
    """Panic recovery — kalp atışı durmuş 'running' aşamaları failed'a çevir."""
    orch = _orchestrator()
    return {"recovered": orch.recover_stale(timeout_min=req.timeout_min)}


class OrchestrationAutodriveRequest(BaseModel):
    execute: bool = False  # True → gerçek `claude -p` spawn (abonelik); False → dry-run komut


def _run_autodrive_bg(run_id: str) -> None:
    """Arka plan: gerçek otonom sürüş (uzun sürer). Olaylar timeline'a yazılır."""
    from app.orchestration.driver import AutoDriver

    AutoDriver().drive(run_id, execute=True)


@router.post("/autodrive/{run_id}")
def orchestration_autodrive(
    run_id: str, req: OrchestrationAutodriveRequest, background: BackgroundTasks
) -> dict[str, Any]:
    """deep-hunt'ı headless `claude -p` (abonelik) ile OTONOM sür → onay kapısına ilerlet.

    `execute=false` (varsayılan): DRY-RUN — çalıştırılacak komutu döner, spawn YOK.
    `execute=true`: gerçek sürüş ARKA PLANDA başlar (timeline'dan izlenir); yanıt hemen döner.
    Gerçek eğitim yine TAZE insan onayı bekler (Kural 8 — onayda durur).
    """
    from app.orchestration.driver import AutoDriver, claude_available

    orch = _orchestrator()
    if orch.store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Koşu bulunamadı: {run_id}")

    if not req.execute:
        return AutoDriver(orchestrator=orch).drive(run_id, execute=False)

    if not claude_available():
        raise HTTPException(
            status_code=503,
            detail="`claude` CLI bulunamadı — abonelikli Claude Code kurulu olmalı.",
        )
    background.add_task(_run_autodrive_bg, run_id)
    return {
        "ok": True,
        "status": "autodrive_started",
        "message": "Otonom sürüş arka planda başladı; ilerlemeyi timeline'dan izle.",
        "run_id": run_id,
    }
