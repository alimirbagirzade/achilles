"""Sızıntısız chunk-düzeyi golden-set üreticisi (Zincir 1 — derin araştırma).

Mevcut "self-retrieval" metriği SIZINTILI: sorgu, karttan (kart makaleden) türediği için
dense'i trivially şişiriyor (query-from-source leakage, arXiv 2504.14175). Adil ölçüm için:
chunk'tan LLM ile Q üret → **DECONTAMINATE** (sorunun chunk'tan uzun n-gram KOPYALAMASINI
ele → paraphrase zorla → lexical değil ANLAM ölçülür) → chunk-düzeyi golden (expected_chunk_id).

`has_excessive_overlap` DETERMİNİSTİK (LLM'siz) → birim test edilebilir. `generate_golden_questions`
LLM kullanır (yavaş, döngü-sonrası temiz ortamda koşulur). Sonuç `GoldenDataset` ile kaydedilir,
mevcut `RetrievalEvaluator` (recall@k/MRR/nDCG, chunk-düzeyi) ile skorlanır. (CLAUDE.md Kural 2/6)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.evals.golden_dataset import GoldenQuestion

if TYPE_CHECKING:
    from app.memory.retrieval_service import RetrievedChunk

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD_RE.findall(text.lower())
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def has_excessive_overlap(question: str, source: str, n: int = 5, max_hits: int = 1) -> bool:
    """Soru kaynaktan ≥n-kelimelik n-gram KOPYALIYOR mu (sızıntılı → reject)?

    Deterministik. Sorunun n-gram'larından `max_hits`'ten fazlası kaynakta birebir geçiyorsa
    sızıntılı sayılır (soru pasajı ezberlemiş → retrieval'ı trivially kolaylaştırır). Çok kısa
    soruda (n-gram yok) eleme yapmaz (False). Amaç paraphrase'i zorlamak.
    """
    qg = _ngrams(question, n)
    if not qg:
        return False
    overlap = len(qg & _ngrams(source, n))
    return overlap > max_hits


def _clean_question(raw: str) -> str:
    """LLM çıktısından tek-satır soruyu çıkar (ön-ek/numaralandırma/tırnak temizle)."""
    line = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    line = re.sub(r"^\s*(soru|question|q)\s*[:\-.]\s*", "", line, flags=re.IGNORECASE)
    return line.strip().strip('"').strip()


def generate_golden_questions(
    chunks: list[RetrievedChunk],
    llm: object,
    *,
    seed: int = 42,
    n: int = 5,
    max_hits: int = 1,
    domain: str = "trading",
) -> list[GoldenQuestion]:
    """Chunk'lardan sızıntısız golden soru üret (LLM; yavaş — döngü-sonrası koş).

    Her chunk için LLM "pasajdan cevaplanabilir, kelimelerini kopyalamayan" bir soru yazar;
    `has_excessive_overlap` ile sızıntılılar ELENİR. Boş/sızıntılı → atlanır. Çıktı
    GoldenQuestion (expected_chunk_ids=[chunk_id], expected_source_ids=[paper_id]).
    """
    out: list[GoldenQuestion] = []
    for idx, ch in enumerate(chunks):
        src = (ch.text or "").strip()
        if len(src) < 80:  # çok kısa pasaj → soru üretme
            continue
        prompt = (
            "Aşağıdaki PASAJDAN cevaplanabilecek TEK bir soru yaz. Soru, pasajın cümlelerini "
            "KOPYALAMASIN — paraphrase et, anlamı/kavramı sor. Yalnız soruyu yaz (tek satır).\n\n"
            f"PASAJ:\n{src[:1500]}"
        )
        try:
            raw = llm.generate(prompt, temperature=0.3, seed=seed + idx)  # type: ignore[attr-defined]
        except Exception:
            continue
        q = _clean_question(str(raw or ""))
        if not q or "?" not in q or has_excessive_overlap(q, src, n=n, max_hits=max_hits):
            continue
        out.append(
            GoldenQuestion(
                question_id=f"gq_{ch.chunk_id}",
                question_text=q,
                domain=domain,
                expected_answer="",
                expected_source_ids=[ch.paper_id],
                expected_chunk_ids=[ch.chunk_id],
                answer_type="factual",
                difficulty="medium",
            )
        )
    return out
