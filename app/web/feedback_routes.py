"""Echo feedback web uçları — kullanıcı düzeltmesi → sentetik SFT adayı.

`server.py`'ye TEK satır (`include_router`) ile bağlanır. Düzeltme submit'te Kural-1
güvenlik kontrolünden geçer (garanti/kesinlik dili → reddedilir). Export AYRI aday dosyaya
yazar; kanonik `lora_sft.jsonl`'e dokunmaz ve **eğitim BAŞLATMAZ** (Kural 8).

Kimlik doğrulama: `require_auth` (token boşsa lokal-açık, mevcut davranışla aynı).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.web.security import require_auth

router = APIRouter(prefix="/api/feedback", tags=["feedback"], dependencies=[Depends(require_auth)])


class FeedbackSubmitRequest(BaseModel):
    correction: str = Field(..., min_length=1, max_length=8000)
    question: str = Field(default="", max_length=8000)
    bad_answer: str = Field(default="", max_length=8000)
    source: str = Field(default="manual", max_length=64)
    correction_type: str = Field(default="other", max_length=40)


def _echo() -> Any:
    from app.feedback import EchoCollector

    return EchoCollector()


@router.post("/submit")
def feedback_submit(req: FeedbackSubmitRequest) -> dict[str, Any]:
    """Bir düzeltmeyi kaydet. Kural-1 zehiri → status=rejected döner (eğitim başlatmaz)."""
    return _echo().record(
        source=req.source,
        question=req.question,
        bad_answer=req.bad_answer,
        correction=req.correction,
        correction_type=req.correction_type,
    )


@router.get("/list")
def feedback_list(status: str = "", limit: int = 50) -> dict[str, Any]:
    """Düzeltmeleri listele (status filtresi opsiyonel)."""
    items = _echo().store.list(status=status or None, limit=limit)
    return {"items": items}


@router.get("/summary")
def feedback_summary() -> dict[str, Any]:
    """Özet sayılar (pending/approved/rejected/exported)."""
    return _echo().summary()


@router.post("/approve/{correction_id}")
def feedback_approve(correction_id: str) -> dict[str, Any]:
    """Bir düzeltmeyi onayla (export'a aday). Güvenlik onay anında tekrar kontrol edilir."""
    echo = _echo()
    ok = echo.approve(correction_id)
    if not ok:
        cur = echo.store.get(correction_id)
        if cur is None:
            raise HTTPException(status_code=404, detail=f"Düzeltme bulunamadı: {correction_id}")
        return {"ok": False, "reason": cur.get("reject_reason") or "Onaylanamadı.", "item": cur}
    return {"ok": True, "item": echo.store.get(correction_id)}


@router.post("/reject/{correction_id}")
def feedback_reject(correction_id: str) -> dict[str, Any]:
    """Bir düzeltmeyi reddet."""
    echo = _echo()
    if echo.store.get(correction_id) is None:
        raise HTTPException(status_code=404, detail=f"Düzeltme bulunamadı: {correction_id}")
    echo.reject(correction_id, "Web'den reddedildi.")
    return {"ok": True, "item": echo.store.get(correction_id)}


@router.post("/export")
def feedback_export() -> dict[str, Any]:
    """Onaylananları AYRI aday SFT dosyasına yaz (eğitim başlatmaz, Kural 8)."""
    return _echo().export_approved()
