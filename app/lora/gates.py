"""Doğrulama kapıları (Gate 0-8) — LoRA dataset denetim hattı.

Her kapı bir saf fonksiyondur ve bir `GateResult` döndürür. Kapılar
sıralı çalışır; bir kapının çıktısı sonrakine girdi olabilir. Kapılar
veri reddeder veya inceleme işaretler; ağır eğitim başlatmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.lora.dataset_splitter import DatasetSplit, check_leakage, split_dataset
from app.lora.domain_classifier import classify_domains
from app.lora.math_verifier import verify_math_content
from app.lora.quality_filter import QualityFilter
from app.lora.safety_scanner import scan_for_secrets

# Felsefe/mantık tutarsızlık işaretleri (Gate 6).
CONTRADICTION_MARKERS: list[str] = [
    "çelişki",
    "contradiction",
    "tutarsız",
    "inconsistent",
    "hem doğru hem yanlış",
    "both true and false",
]
# Korelasyon-nedensellik karışımı işareti.
CAUSALITY_MARKERS: list[str] = [
    "korelasyon nedenselliktir",
    "correlation implies causation",
    "korelasyon = nedensellik",
]


@dataclass
class GateResult:
    """Tek bir kapının sonucu."""

    gate_id: int
    name: str
    passed: bool
    skipped_count: int = 0
    rejected_count: int = 0
    review_count: int = 0
    details: list[str] = field(default_factory=list)


def _card_text(card: dict) -> str:
    """Bir karttan denetlenebilir serbest metni topla."""
    card_json = card.get("card_json")
    if isinstance(card_json, dict):
        parts = [
            str(card_json.get("title") or ""),
            str(card_json.get("summary") or ""),
            str(card_json.get("main_claim") or ""),
            str(card_json.get("trading_relevance") or ""),
            str(card_json.get("domain") or ""),
        ]
        for field in ("methods", "possible_strategy_hypotheses", "implementation_notes"):
            items = card_json.get(field) or []
            if isinstance(items, list):
                parts.extend(str(x) for x in items if x)
        formulas = card_json.get("formulas") or []
        if isinstance(formulas, list):
            for f in formulas:
                if isinstance(f, dict):
                    parts.append(str(f.get("description") or ""))
                    parts.append(str(f.get("plain") or ""))
        return "\n".join(p for p in parts if p)
    # düz örnek (messages) durumunda
    msgs = card.get("messages")
    if isinstance(msgs, list):
        return "\n".join(str(m.get("content") or "") for m in msgs)
    return ""


def gate_0_source(cards: list[dict]) -> GateResult:
    """Kaynak bütünlüğü: approved + domain + created_at var mı?"""
    rejected = 0
    details: list[str] = []
    for card in cards:
        if card.get("review_status") != "approved":
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: review_status != approved")
            continue
        text = _card_text(card)
        if not classify_domains(text):
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: domain atanamadı")
            continue
        if not card.get("created_at"):
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: created_at yok")
    return GateResult(
        gate_id=0,
        name="source",
        passed=rejected == 0,
        rejected_count=rejected,
        details=details[:20],
    )


def gate_1_schema(examples: list[dict]) -> GateResult:
    """Şema: messages formatı (system→user→assistant) ve metadata varlığı."""
    rejected = 0
    details: list[str] = []
    for i, ex in enumerate(examples):
        messages = ex.get("messages")
        if not isinstance(messages, list) or len(messages) < 3:
            rejected += 1
            details.append(f"#{i}: messages eksik veya < 3")
            continue
        roles = [m.get("role") for m in messages]
        if roles[:3] != ["system", "user", "assistant"]:
            rejected += 1
            details.append(f"#{i}: rol sırası system→user→assistant değil")
            continue
        if "metadata" not in ex:
            rejected += 1
            details.append(f"#{i}: metadata yok")
    return GateResult(
        gate_id=1,
        name="schema",
        passed=rejected == 0,
        rejected_count=rejected,
        details=details[:20],
    )


def gate_2_curriculum(cards: list[dict]) -> GateResult:
    """Müfredat: difficulty 0.0-1.0 arasında atanmış mı?"""
    rejected = 0
    details: list[str] = []
    for card in cards:
        difficulty = card.get("difficulty")
        if difficulty is None or not (0.0 <= float(difficulty) <= 1.0):
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: geçersiz difficulty={difficulty}")
    return GateResult(
        gate_id=2,
        name="curriculum",
        passed=rejected == 0,
        rejected_count=rejected,
        details=details[:20],
    )


def gate_3_domain(cards: list[dict]) -> GateResult:
    """Domain: her kart en az bir domaine ait mi?"""
    rejected = 0
    details: list[str] = []
    for card in cards:
        if not classify_domains(_card_text(card)):
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: domain bulunamadı")
    return GateResult(
        gate_id=3,
        name="domain",
        passed=rejected == 0,
        rejected_count=rejected,
        details=details[:20],
    )


def gate_4_quality(cards: list[dict]) -> tuple[GateResult, list[dict]]:
    """Kalite: kısa/tekrarlı/duplicate içerikleri ele; temiz listeyi döndür."""
    quality_inputs = []
    for card in cards:
        card_json = card.get("card_json")
        question = ""
        answer = ""
        if isinstance(card_json, dict):
            question = f"{card_json.get('title', '')} konusunu açıkla."
            answer_parts = [
                str(card_json.get("main_claim") or ""),
                str(card_json.get("summary") or ""),
                str(card_json.get("trading_relevance") or ""),
            ]
            hypotheses = card_json.get("possible_strategy_hypotheses") or []
            if isinstance(hypotheses, list):
                answer_parts.extend(str(h) for h in hypotheses if h)
            answer = " ".join(p for p in answer_parts if p)
        quality_inputs.append({**card, "question": question, "answer": answer})

    passed, rejected = QualityFilter().filter_batch(quality_inputs)
    details = [f"{c.get('card_id', '?')}: {c.get('_quality_reason')}" for c in rejected]
    # Temiz çıktı: orijinal kart alanlarını koru (eklenen question/answer'ı at).
    clean = [{k: v for k, v in c.items() if k not in ("question", "answer")} for c in passed]
    result = GateResult(
        gate_id=4,
        name="quality",
        passed=len(rejected) == 0,
        rejected_count=len(rejected),
        details=details[:20],
    )
    return result, clean


def gate_5_math(cards: list[dict]) -> GateResult:
    """Matematik/istatistik: hesap tutarlılığı ve kırmızı bayraklar."""
    rejected = 0
    review = 0
    details: list[str] = []
    for card in cards:
        result = verify_math_content(_card_text(card))
        card_json = card.get("card_json")
        requires_check = isinstance(card_json, dict) and bool(card_json.get("requires_math_check"))
        if not result.passed:
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: {'; '.join(result.issues)}")
        elif result.requires_review or requires_check:
            review += 1
            reason = "; ".join(result.issues) or "requires_math_check"
            details.append(f"{card.get('card_id', '?')}: inceleme — {reason}")
    return GateResult(
        gate_id=5,
        name="math",
        passed=rejected == 0,
        rejected_count=rejected,
        review_count=review,
        details=details[:20],
    )


def gate_6_philosophy(cards: list[dict]) -> GateResult:
    """Mantık/felsefe: çelişki ve korelasyon-nedensellik karışımı işaretle."""
    from app.lora.safety_scanner import tr_fold

    review = 0
    details: list[str] = []
    for card in cards:
        # tr_fold: büyük harf/aksanlı Türkçe işaretler (ÇELİŞKİ, TUTARSIZ) str.lower()
        # ile (İ→i+nokta) kaçıyordu — safety_scanner/math_verifier ile aynı desen.
        folded = tr_fold(_card_text(card))
        flags = [m for m in CONTRADICTION_MARKERS + CAUSALITY_MARKERS if tr_fold(m) in folded]
        if flags:
            review += 1
            details.append(f"{card.get('card_id', '?')}: {', '.join(flags)}")
    return GateResult(
        gate_id=6,
        name="philosophy",
        passed=True,  # işaretler bloklamaz; insan incelemesine yönlendirir
        review_count=review,
        details=details[:20],
    )


def gate_7_safety(cards: list[dict]) -> GateResult:
    """Güvenlik (BLOCKER): sır, kişisel veri, finansal yönlendirme."""
    rejected = 0
    details: list[str] = []
    for card in cards:
        result = scan_for_secrets(_card_text(card))
        if not result.passed:
            rejected += 1
            details.append(f"{card.get('card_id', '?')}: {'; '.join(result.violations)}")
    return GateResult(
        gate_id=7,
        name="safety",
        passed=rejected == 0,
        rejected_count=rejected,
        details=details[:20],
    )


def gate_8_split(examples: list[dict]) -> tuple[GateResult, DatasetSplit]:
    """Dataset bölme ve sızıntı denetimi."""
    split = split_dataset(examples)
    leaks = check_leakage(split)
    details = list(leaks)
    details.append(f"train={len(split.train)} valid={len(split.valid)} test={len(split.test)}")
    result = GateResult(
        gate_id=8,
        name="split",
        passed=len(leaks) == 0,
        rejected_count=len(leaks),
        details=details[:20],
    )
    return result, split
