"""Sızıntısız chunk-düzeyi golden-set ÜRET + dense vs router'ı SKORLA (Zincir 1).

İki aşama (döngü-sonrası TEMİZ ortamda, TEK başına koş — Chroma çekişmesi get_all'ı düşürür):
  1. BUILD: korpustan makale-başı örnek chunk → LLM ile sızıntısız soru → decontaminate →
     data/eval/golden_chunk_qa.json (GoldenDataset). LLM YAVAŞ (qwen3:4b CPU) → dakikalar.
  2. SCORE: GoldenQuestion'ları mevcut RetrievalEvaluator ile dense_only vs router(lexical→
     konveks-hibrit) için chunk-düzeyi recall@5/10 + MRR + nDCG ölç → adil karşılaştırma.

Mevcut golden varsa BUILD atlanır (yeniden üretme — Evidently: test setini DONDUR). Force:
RAG_GOLDEN_FORCE=1. Örnek sayısı: RAG_GOLDEN_PAPERS (varsayılan 60 makale × 1 chunk).

Kullanım: RAG_GOLDEN_PAPERS=60 uv run --no-sync python scripts/build_golden_eval.py
"""

from __future__ import annotations

import os
import statistics


def main() -> None:
    from app.brain.local_llm import LocalLLM
    from app.config import get_settings
    from app.evals.golden_dataset import GoldenDataset
    from app.evals.golden_generator import generate_golden_questions
    from app.evals.retrieval_eval import RetrievalEvaluator
    from app.memory.bm25_corpus import get_corpus_bm25
    from app.memory.reranking_retriever import RerankingRetriever

    n_papers = int(os.environ.get("RAG_GOLDEN_PAPERS", "60"))
    force = os.environ.get("RAG_GOLDEN_FORCE") == "1"
    out_path = get_settings().root / "data" / "eval" / "golden_chunk_qa.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- BUILD (varsa atla; LLM yavaş) ---
    if out_path.exists() and not force:
        questions = GoldenDataset.load_from_json(out_path)
        print(f"# golden mevcut: {len(questions)} soru ({out_path})", flush=True)
    else:
        _bm25, chunk_map = get_corpus_bm25()
        if not chunk_map:
            print("# HATA: korpus boş (Chroma kilidi — TEK başına koş)", flush=True)
            return
        # makale-başı İLK uygun chunk (stratified; determinizm için sıralı)
        by_paper: dict[str, object] = {}
        for cid in sorted(chunk_map):
            ch = chunk_map[cid]
            if ch.paper_id not in by_paper and len((ch.text or "").strip()) >= 200:
                by_paper[ch.paper_id] = ch
        sample = [by_paper[p] for p in sorted(by_paper)][:n_papers]
        print(f"# {len(sample)} makaleden chunk seçildi → LLM soru üretiyor (yavaş)…", flush=True)
        questions = generate_golden_questions(sample, LocalLLM())  # type: ignore[arg-type]
        GoldenDataset.save_to_json(questions, out_path)
        print(
            f"# golden üretildi: {len(questions)}/{len(sample)} (sızıntılı/boş elendi)",
            flush=True,
        )

    if not questions:
        print("# soru yok — çık", flush=True)
        return

    # --- SCORE (dense vs router) ---
    def agg(retr: object) -> dict:
        results = RetrievalEvaluator(retr).evaluate(questions)  # type: ignore[arg-type]
        if not results:
            return {}
        return {
            "recall@5": round(statistics.mean(r.recall_5 for r in results), 4),
            "recall@10": round(statistics.mean(r.recall_10 for r in results), 4),
            "mrr": round(statistics.mean(r.mrr for r in results), 4),
            "ndcg": round(statistics.mean(r.ndcg for r in results), 4),
        }

    print("# scoring dense_only…", flush=True)
    dense = agg(RerankingRetriever(enabled=False))
    print("# scoring router…", flush=True)
    router = agg(RerankingRetriever(enabled=True, router=True))

    def _row(label: str, d: dict) -> str:
        keys = ("recall@5", "recall@10", "mrr", "ndcg")
        return f"# {label:<7} " + " ".join(str(d.get(k)) for k in keys)

    print(f"DENSE : {dense}", flush=True)
    print(f"ROUTER: {router}", flush=True)
    print("\n# config recall@5 recall@10 mrr nDCG", flush=True)
    print(_row("dense", dense), flush=True)
    print(_row("router", router), flush=True)


if __name__ == "__main__":
    main()
