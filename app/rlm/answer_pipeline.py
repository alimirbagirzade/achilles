"""RLM cevap pipeline — motor seçimi + (alexzhang yolunda) doğrulama (talimat §13).

provider='native' (VARSAYILAN): mevcut RlmController tüm grounded akışı yapar.
provider='alexzhang' + enabled + paket kurulu + güvenli: recursive motor taslağı üretir;
taslak mevcut verifier'larla (grounding + citation) doğrulanır, desteklenmeyen iddialar
çıkarılır. Motor yoksa/başarısızsa/güvensizse → NATIVE'E DÜŞER (sistem bozulmaz).

RAG evidence olmadan kaynaklı cevap üretilmez; require_citations True iken kaynak yoksa
status='insufficient_evidence'.
"""

from __future__ import annotations

import logging
from typing import Any

from app.rlm.adapters.alexzhang_rlm import AlexZhangRLMAdapter
from app.rlm.adapters.base import RLMRequest
from app.rlm.adapters.native import NativeRLMAdapter
from app.rlm.adapters.security import RLMUnsafeRuntimeError
from app.rlm.engine_config import build_engine_config

log = logging.getLogger(__name__)


def run_rlm_answer(
    query: str,
    *,
    adapter: str | None = None,
    top_k: int | None = None,
    paper_ids: list[str] | None = None,
    max_rounds: int | None = None,
    require_citations: bool = True,
    write_report: bool = True,
) -> dict[str, Any]:
    """Soruyu seçilen motorla (native varsayılan) kaynaklı/doğrulanmış cevapla."""
    cfg = build_engine_config()
    provider = (adapter or cfg.get("provider") or "native").lower()

    if provider == "alexzhang" and cfg.get("alexzhang", {}).get("enabled"):
        result = _try_alexzhang(query, cfg, top_k, paper_ids, require_citations)
        if result is not None:
            return result
        log.warning("alexzhang motoru kullanılamadı/başarısız → native'e düşülüyor.")

    return _native(
        query, top_k=top_k, paper_ids=paper_ids, max_rounds=max_rounds, write_report=write_report
    )


def _native(
    query: str,
    *,
    top_k: int | None,
    paper_ids: list[str] | None,
    max_rounds: int | None,
    write_report: bool = True,
) -> dict[str, Any]:
    resp = NativeRLMAdapter().complete(
        RLMRequest(
            query=query,
            run_config={
                "top_k": top_k,
                "paper_ids": paper_ids,
                "max_rounds": max_rounds,
                "write_report": write_report,
            },
        )
    )
    m = resp.metadata
    status_map = {
        "answered": "grounded",
        "answered_with_limitation": "grounded",
        "abstained": "insufficient_evidence",
        "no_llm": "needs_review",
        "failed": "needs_review",
    }
    return {
        "answer": resp.answer,
        "sources": m.get("sources", []),
        "unsupported_claims_removed": m.get("unsupported_claims", []),
        "limitations": [],
        "confidence": m.get("confidence", 0.0),
        "adapter": resp.used_adapter,
        "status": status_map.get(str(m.get("status")), "needs_review"),
    }


def _try_alexzhang(
    query: str,
    cfg: dict[str, Any],
    top_k: int | None,
    paper_ids: list[str] | None,
    require_citations: bool,
) -> dict[str, Any] | None:
    """alexzhang motorunu dene. Kullanılamaz/güvensiz/başarısız → None (native fallback)."""
    from app.memory.reranking_retriever import RerankingRetriever

    chunks = RerankingRetriever().retrieve(query, top_k=top_k)
    if paper_ids:  # native ile aynı: yalnız istenen makalelerle sınırla (sessiz yok-sayma değil)
        wanted = set(paper_ids)
        chunks = [c for c in chunks if c.paper_id in wanted]
    if not chunks:
        if require_citations:
            return {
                "answer": "Bu makalelere göre bu soruya yeterli kanıt yok.",
                "sources": [],
                "unsupported_claims_removed": [],
                "limitations": ["Kaynak bulunamadı."],
                "confidence": 0.0,
                "adapter": "alexzhang_rlm",
                "status": "insufficient_evidence",
            }
        return None

    evidence_pack = {
        "chunks": [
            {
                "paper_id": c.paper_id,
                "chunk_id": c.chunk_id,
                "section": c.section_name,
                "page": c.page_number,
                "text": c.text,
            }
            for c in chunks
        ]
    }
    adapter = AlexZhangRLMAdapter(cfg)
    try:
        resp = adapter.complete(RLMRequest(query=query, evidence_pack=evidence_pack))
    except RLMUnsafeRuntimeError as exc:
        log.warning("alexzhang güvenlik kapısı reddetti: %s", exc)
        return None
    except Exception as exc:  # SDK/ağ/API hatası → native'e düş (sistem bozulmaz; sessiz değil)
        log.warning("alexzhang motoru beklenmeyen hata: %s: %s", type(exc).__name__, exc)
        return None
    if not resp.success or not resp.answer.strip():
        return None

    # Taslağı mevcut verifier'larla doğrula + desteklenmeyen iddiaları çıkar (kural 4/7).
    from app.rlm.claim_extractor import extract_claims
    from app.verification.citation_verifier import CitationVerifier
    from app.verification.grounding_verifier import GroundingVerifier

    groundings = GroundingVerifier().verify(resp.answer, chunks)
    citations = CitationVerifier().verify(resp.answer, chunks)
    claims = extract_claims(groundings)
    supported = [c.claim for c in claims if c.is_supported]
    unsupported = [c.claim for c in claims if not c.is_supported]
    cit_valid = sum(1 for c in citations if c.exists)
    cit_score = (cit_valid / len(citations)) if citations else 1.0

    if require_citations and not supported:
        status = "insufficient_evidence"
    elif cit_score < 0.5 or not supported:
        status = "needs_review"
    else:
        status = "grounded"

    # FIX (kural 4/7): nihai cevabı YALNIZ desteklenen iddialardan yeniden kur — motorun
    # ham taslağını (resp.answer) GÖVDEYE koyma. Aksi halde desteklenmeyen/uydurma iddialar
    # 'unsupported_claims_removed' içine yazılsa da gövdede kalır (native bunu yapmaz).
    answer_text = _rebuild_from_supported(supported, chunks, status)

    return {
        "answer": answer_text,
        "sources": [
            {"paper_id": c.paper_id, "chunk_id": c.chunk_id, "section": c.section_name}
            for c in chunks
        ],
        "unsupported_claims_removed": unsupported,
        "limitations": [] if status == "grounded" else ["Doğrulama tam değil."],
        "confidence": round(cit_score, 4),
        "adapter": "alexzhang_rlm",
        "status": status,
    }


def _rebuild_from_supported(supported: list[str], chunks: list[Any], status: str) -> str:
    """Cevap gövdesini yalnız desteklenen iddialardan kur (native _build_envelope ile aynı ruh).

    Gövdeye giren cümlelerdeki uydurma satır-içi atıflar (getirilen sette olmayan
    [paper:chunk]) çıkarılır (kural 7). Desteklenen iddia yoksa çekimser metin döner.
    """
    from app.rlm.rlm_controller import _sanitize_citations

    valid_ids = {c.chunk_id for c in chunks}
    # Uydurma atıf çıkarıldıktan SONRA boşalan iddialar (yalnız sahte atıftan ibaret olanlar)
    # gerçek dayanak içermez → tamamen elenir (gövde 'Kısa cevap: .'a çökmesin).
    safe = [s for s in (_sanitize_citations(c, valid_ids) for c in supported) if s.strip()]
    if not safe:
        return (
            "Kısa cevap:\n"
            "Bu makalelere göre soruya kaynaklarla desteklenen güvenilir bir cevap üretilemedi.\n\n"
            "Güven seviyesi: Low"
        )
    gerekce = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(safe))
    kaynaklar = "\n".join(
        f"- {c.citation} | {c.section_name or '—'} | {c.title or '—'}" for c in chunks
    )
    level = "High" if status == "grounded" else "Low"
    return (
        f"Kısa cevap:\n{safe[0]}\n\n"
        f"Makalelere göre gerekçe:\n{gerekce}\n\n"
        f"Kaynak dayanakları:\n{kaynaklar}\n\n"
        f"Güven seviyesi: {level}"
    )


def _main() -> None:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Achilles RLM answer pipeline")
    ap.add_argument("--query", required=True)
    ap.add_argument("--adapter", default=None, choices=[None, "native", "alexzhang"])
    ap.add_argument("--top-k", type=int, default=None)
    args = ap.parse_args()
    out = run_rlm_answer(args.query, adapter=args.adapter, top_k=args.top_k)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
