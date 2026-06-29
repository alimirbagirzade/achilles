"""echo.py — Echo: kullanıcı düzeltmelerini sentetik SFT adayına çevirir (feedback döngüsü).

Akış: kullanıcı "bu cevap yanlıştı, doğrusu X" der → Echo kaydeder + Kural-1 güvenlik
kontrolü (düzeltme metni garanti/kesinlik dili içeriyorsa ANINDA reddedilir, zehir girmesin)
→ insan onayı → onaylananlar lora_sft FORMATINDA AYRI bir aday dosyaya export edilir.

GÜVENLİK (Kural 8): export edilen aday `data/feedback/feedback_sft.jsonl`'e yazılır;
kanonik `lora_sft.jsonl`'e OTO-MERGE YOK. Eğitim ASLA tetiklenmez; aday yine pretrain-gate
+ dataset audit'ten geçmelidir. Çıktı determinist (Kural 6).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.feedback.store import FeedbackStore

log = logging.getLogger(__name__)

# Geçerli düzeltme türleri (serbest metin yerine sınırlı küme → tutarlı metadata).
VALID_CORRECTION_TYPES: frozenset[str] = frozenset(
    {
        "claim_correction",  # yanlış iddia düzeltildi
        "missing_caveat",  # eksik uyarı/çekince eklendi
        "wrong_number",  # hatalı sayı/metrik düzeltildi
        "advice_language_removed",  # tavsiye/kesinlik dili giderildi
        "other",
    }
)

# Durum sabitleri.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXPORTED = "exported"


def correction_safety_reason(*texts: str) -> str | None:
    """Verilen metinlerden BİRİ Kural-1 zehiri (garanti/kesinlik vaadi) içeriyorsa gerekçe.

    KRİTİK: SFT satırına giren TÜM alanlar (soru=user-turn + düzeltme=assistant-turn) ve
    saklanan bad_answer denetlenmeli. Yalnız 'correction' denetlenseydi zehir 'question'
    alanından eğitim verisine SIZABİLİRDİ (adversarial review bulgusu). Diğer kalite
    denetimi export sonrası pretrain-gate + dataset audit'te yapılır (burada yalnız zehir)."""
    from app.training.evaluate_model import RED_FLAGS

    rx = RED_FLAGS["guaranteed_profit"]
    for t in texts:
        if rx.search(t or ""):
            return "Girdi garanti/kesinlik dili içeriyor (Kural 1 zehiri) — reddedildi."
    return None


def _ensure_within(path: Path, roots: tuple[Path, ...]) -> Path:
    """Export yolunu izinli köklerin İÇİNE kısıtla (yol-geçişi savunması).

    Adversarial review bulgusu: out_path ileride güvensiz bir girdiye bağlanırsa
    '../../etc/passwd' gibi keyfi konuma yazmayı engeller. İzinli kökler proje kökü +
    deponun kendi dizinidir (üretimde sqlite kök altında; testte tmp_path) → kırılgan
    OS-temp varsayımı yok. Web ucu out_path'i HİÇ ifşa etmez; bu ek savunma katmanıdır."""
    resolved = path.resolve()
    if not any(resolved.is_relative_to(r.resolve()) for r in roots):
        raise ValueError(f"Export yolu izinli kök dışında reddedildi: {resolved}")
    return resolved


class EchoCollector:
    """Feedback toplama + onay + SFT-aday export'u (eğitim başlatmaz)."""

    def __init__(self, store: FeedbackStore | None = None) -> None:
        self.store = store or FeedbackStore()

    # ── kayıt ────────────────────────────────────────────────────────────────

    def record(
        self,
        *,
        source: str,
        question: str,
        bad_answer: str,
        correction: str,
        correction_type: str = "other",
    ) -> dict[str, Any]:
        """Bir düzeltmeyi kaydet. Boş/zehirli düzeltme ANINDA reddedilir (dürüstlük)."""
        ct = correction_type if correction_type in VALID_CORRECTION_TYPES else "other"

        if not (correction or "").strip():
            cid = self.store.add(
                source=source,
                question=question,
                bad_answer=bad_answer,
                correction=correction,
                correction_type=ct,
                status=REJECTED,
                reject_reason="Boş düzeltme.",
            )
            return self.store.get(cid)  # type: ignore[return-value]

        reason = correction_safety_reason(correction, question, bad_answer)
        status = REJECTED if reason else PENDING
        cid = self.store.add(
            source=source,
            question=question,
            bad_answer=bad_answer,
            correction=correction,
            correction_type=ct,
            status=status,
            reject_reason=reason or "",
        )
        return self.store.get(cid)  # type: ignore[return-value]

    # ── onay/ret ──────────────────────────────────────────────────────────────

    def approve(self, correction_id: str) -> bool:
        """Bir düzeltmeyi onayla. Onay anında güvenlik tekrar kontrol edilir (Kural 1)."""
        c = self.store.get(correction_id)
        if c is None:
            return False
        reason = correction_safety_reason(c["correction"], c["question"], c["bad_answer"])
        if reason:
            self.store.set_status(correction_id, REJECTED, reason)
            return False
        if not (c["question"] or "").strip() or not (c["correction"] or "").strip():
            self.store.set_status(correction_id, REJECTED, "Boş soru veya düzeltme.")
            return False
        return self.store.set_status(correction_id, APPROVED)

    def reject(self, correction_id: str, reason: str = "") -> bool:
        return self.store.set_status(correction_id, REJECTED, reason or "Elle reddedildi.")

    # ── SFT export ────────────────────────────────────────────────────────────

    def to_sft_line(self, correction: dict[str, Any]) -> str:
        """Bir düzeltmeyi lora_sft uyumlu JSONL satırına çevir (system→user→assistant)."""
        from app.lora.dataset_builder import SYSTEM_PROMPT, LoRAExample

        ex = LoRAExample(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": correction["question"]},
                {"role": "assistant", "content": correction["correction"]},
            ],
            metadata={
                "source": "feedback",
                "correction_type": correction["correction_type"],
                "feedback_id": correction["correction_id"],
            },
        )
        return ex.to_jsonl_line()

    def export_approved(self, out_path: str | Path | None = None) -> dict[str, Any]:
        """Onaylanan (ve daha önce export edilen) düzeltmeleri AYRI aday dosyaya yaz.

        Kanonik `lora_sft.jsonl`'e DOKUNMAZ (Kural 8). İdempotent: approved ∪ exported
        kümesini yazar, approved → exported işaretler → tekrar çağrı aynı dosyayı üretir
        (export sonrası 'approved' boşalıp dosyanın silinmesi bug'ına karşı)."""
        approved = self.store.list(status=APPROVED, limit=1_000_000)
        already = self.store.list(status=EXPORTED, limit=1_000_000)
        # id'ye göre birleştir + dedup, kronolojik (created_at artan) sırada determinist yaz.
        by_id: dict[str, dict[str, Any]] = {c["correction_id"]: c for c in already + approved}
        usable = [
            c
            for c in sorted(by_id.values(), key=lambda c: c["created_at"])
            if (c["question"] or "").strip() and (c["correction"] or "").strip()
        ]

        path = (
            Path(out_path)
            if out_path
            else get_settings().root / "data" / "feedback" / "feedback_sft.jsonl"
        )
        # yol-geçişi savunması: proje kökü + deponun kendi dizini izinli (kırılgan değil)
        path = _ensure_within(path, (get_settings().root, self.store.db_path.parent))
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [self.to_sft_line(c) for c in usable]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        # Race savunması: işaretlemeden hemen ÖNCE durumu TEKRAR oku; arada REJECTED olduysa
        # EXPORTED'a geçirme (rejected→exported state bozulması — adversarial review bulgusu).
        marked = 0
        for c in (c for c in approved if c["status"] == APPROVED):
            cur = self.store.get(c["correction_id"])
            if cur and cur["status"] == APPROVED:
                self.store.set_status(c["correction_id"], EXPORTED)
                marked += 1

        return {"n_exported": len(usable), "newly_marked": marked, "path": str(path)}

    # ── özet ──────────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        counts = self.store.counts()
        return {
            "counts": counts,
            "pending": counts.get(PENDING, 0),
            "approved": counts.get(APPROVED, 0),
            "rejected": counts.get(REJECTED, 0),
            "exported": counts.get(EXPORTED, 0),
        }
