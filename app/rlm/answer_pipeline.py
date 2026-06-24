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
import re
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
    grounding_score = (len(supported) / len(claims)) if claims else 0.0

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
    support_levels = _chunk_support_levels(claims)

    # §13.14: alexzhang yolu da run kaydı + trajektori yazsın (rlm_store + JSON) →
    # rlm-runs / /api/rlm/runs / /trajectory alexzhang cevaplarını da gösterir.
    # Best-effort: DB/dosya hatası cevabı BOZMAZ ama SESSİZ YUTULMAZ (log.warning).
    run_id = _log_alexzhang_run(
        query,
        answer_text,
        status,
        cit_score,
        grounding_score,
        supported,
        unsupported,
        chunks=chunks,
        engine_meta=resp.metadata,
        engine_draft=resp.answer,
        cfg=cfg,
    )

    return {
        "run_id": run_id,
        "answer": answer_text,
        "sources": [
            {
                "paper_id": c.paper_id,
                "chunk_id": c.chunk_id,
                "section": c.section_name,
                "support_level": support_levels.get(c.chunk_id, "weak"),
            }
            for c in chunks
        ],
        "unsupported_claims_removed": unsupported,
        "limitations": [] if status == "grounded" else ["Doğrulama tam değil."],
        "confidence": round(cit_score, 4),
        "adapter": "alexzhang_rlm",
        "status": status,
    }


def _chunk_support_levels(claims: list[Any]) -> dict[str, str]:
    """Her chunk için en güçlü dayanak seviyesini hesapla (§13: strong|partial|weak).

    Bir chunk 'supported' bir iddiayı destekliyorsa strong; yalnız 'partially_supported'
    iddiada geçiyorsa partial; hiçbir desteklenen iddiada geçmiyorsa weak.
    """
    rank = {"strong": 2, "partial": 1, "weak": 0}
    levels: dict[str, str] = {}
    for c in claims:
        if c.support_status == "supported":
            lvl = "strong"
        elif c.support_status == "partially_supported":
            lvl = "partial"
        else:
            continue  # speculative/unsupported chunk'a güç katmaz
        for cid in c.supporting_chunks:
            if rank[lvl] > rank.get(levels.get(cid, "weak"), 0):
                levels[cid] = lvl
    return levels


def _log_alexzhang_run(
    query: str,
    final_answer: str,
    status: str,
    cit_score: float,
    grounding_score: float,
    supported: list[str],
    unsupported: list[str],
    *,
    chunks: list[Any],
    engine_meta: dict[str, Any],
    engine_draft: str,
    cfg: dict[str, Any],
) -> str | None:
    """alexzhang cevabını rlm_store'a (run + adım + kanıt) ve trajektoriyi JSON'a kaydet.

    Best-effort: DB/dosya hatası cevabı BOZMAZ ama SESSİZ YUTULMAZ — log.warning ile
    görünür kılınır (CLAUDE.md: sessiz kesme yok)."""
    import contextlib

    from app.rlm.rlm_store import RlmStore

    run_id: str | None = None
    try:
        from app.rlm.task_classifier import TaskClassifier

        store = RlmStore()
        task_type = TaskClassifier().classify(query)
        run_id = store.create_run(query, task_type, model_name="alexzhang_rlm")
        # Pipeline aşamalarını trajektori adımı olarak kaydet (audit/görselleştirme).
        store.add_step(
            run_id, 1, "retrieval", input_text=query, output_text=f"{len(chunks)} chunk getirildi"
        )
        store.add_step(
            run_id, 2, "engine_draft", output_text=engine_draft, tool_used="alexzhang_rlm"
        )
        store.add_step(
            run_id,
            3,
            "verification",
            output_text=(
                f"supported={len(supported)} unsupported={len(unsupported)} "
                f"citation={round(cit_score, 4)} grounding={round(grounding_score, 4)}"
            ),
        )
        store.add_step(run_id, 4, "final", output_text=final_answer)
        used = {cid for cid in (getattr(c, "chunk_id", None) for c in chunks) if cid}
        for c in chunks:
            # relevance_score [0,1]'e sıkıştırılır (native rlm_controller ile tutarlı):
            # Chroma cosine mesafesi >1 olabilir → 1.0-d negatif olmasın.
            rel = min(1.0, max(0.0, 1.0 - (c.distance or 0.0)))
            store.add_evidence(run_id, c.paper_id, c.chunk_id, rel, c.chunk_id in used)
        store.set_verification(
            run_id,
            supported_claims=supported,
            unsupported_claims=unsupported,
            contradictions=[],
            citation_score=round(cit_score, 4),
            grounding_score=round(grounding_score, 4),
            context_sufficiency_score=round(grounding_score, 4),
            final_decision=status,
        )
        store.finish_run(
            run_id,
            status=status,
            final_answer=final_answer,
            final_confidence=round(cit_score, 4),
            evidence_score=round(grounding_score, 4),
        )
        if cfg.get("alexzhang", {}).get("log_trajectories", True):
            _write_trajectory_file(
                cfg, run_id, query, task_type, status, chunks, engine_meta, supported, unsupported
            )
        return run_id
    except Exception as exc:  # DB/import hatası → run_id=None ama cevap döner; görünür logla
        log.warning(
            "alexzhang run kaydı başarısız (cevap etkilenmedi): %s: %s",
            type(exc).__name__,
            exc,
        )
        # create_run sonrası yarıda kaldıysa run 'running' asılı kalmasın → hemen 'failed'
        # (60dk reaper'ı bekleme; /api/rlm/runs tutarlı olsun). Best-effort.
        if run_id is not None:
            with contextlib.suppress(Exception):
                RlmStore().finish_run(
                    run_id,
                    status="failed",
                    final_answer="[alexzhang run-log yarıda kaldı]",
                    final_confidence=0.0,
                    evidence_score=0.0,
                )
        return None


# Trajektori dosya adı: yalnız güvenli karakterler (path traversal / yanlış-yol önle).
# Nokta DE yasak: run_id'ler nokta içermez (rlm_<hex>); böylece '..' segmenti imkânsız.
_TRAJ_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")
# Trajektori okuma tavanı (OOM savunması): normal trajektori KB; bunu aşan dosya okunmaz.
_TRAJ_MAX_BYTES = 50_000_000


def _write_trajectory_file(
    cfg: dict[str, Any],
    run_id: str,
    query: str,
    task_type: str,
    status: str,
    chunks: list[Any],
    engine_meta: dict[str, Any],
    supported: list[str],
    unsupported: list[str],
) -> None:
    """alexzhang koşu trajektorisini `trajectory_log_dir/{run_id}.json` olarak yaz.

    Dizin `.gitignore`'da (runtime + olası hassas içerik). run_id dosya adı sanitize
    edilir (path traversal yok). engine_meta = motorun kendi recursive-çağrı izi (varsa).
    """
    import json
    from pathlib import Path

    log_dir = str(cfg.get("alexzhang", {}).get("trajectory_log_dir", "reports/rlm/trajectories"))
    safe_id = _TRAJ_SAFE_RE.sub("_", run_id) or "run"
    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "run_id": run_id,
        "task_type": task_type,
        "status": status,
        "query": query,
        "adapter": "alexzhang_rlm",
        "evidence": [
            {"paper_id": c.paper_id, "chunk_id": c.chunk_id, "section": c.section_name}
            for c in chunks
        ],
        "supported_claims": supported,
        "unsupported_claims": unsupported,
        # Motorun kendi metadata'sı (recursive alt-çağrı izi vb.) — paket varsa dolu olur.
        "engine_metadata": engine_meta or {},
    }
    (out_dir / f"{safe_id}.json").write_text(
        json.dumps(trajectory, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_trajectory_file(run_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """`trajectory_log_dir/{run_id}.json` trajektorisini oku (yoksa None).

    run_id sanitize edilir (path traversal yok). Bozuk/eksik dosya → None (çökme yok).
    """
    import json
    from pathlib import Path

    cfg = cfg or build_engine_config()
    log_dir = str(cfg.get("alexzhang", {}).get("trajectory_log_dir", "reports/rlm/trajectories"))
    safe_id = _TRAJ_SAFE_RE.sub("_", run_id) or "run"
    path = Path(log_dir) / f"{safe_id}.json"
    if not path.is_file():
        return None
    # OOM savunması: anormal büyük dosyayı belleğe ALMA (50MB tavanı). Trajektori normalde KB.
    try:
        if path.stat().st_size > _TRAJ_MAX_BYTES:
            log.warning(
                "trajektori dosyası çok büyük (>%d B), atlanıyor: %s", _TRAJ_MAX_BYTES, path
            )
            return None
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        log.warning("trajektori okunamadı (%s): %s", path, exc)
        return None


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
