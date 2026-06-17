# RAG İzleme Listesi (Watchlist)

> Ucuz **tarama** turlarının çıktısı: güncel literatürde görülen ama henüz entegre
> edilmemiş RAG teknikleri burada biriktirilir. **Entegrasyon** turu buradan başlar
> (≥1 güçlü aday birikince tam tur koşar). Kod/sürüm/PDF değişmez; bu dosya push edilir.
>
> Durum etiketleri: `aday` (incelenecek) · `entegre` (kodda, dokümanda) · `ertelendi` (gerekçeli) · `red` (uygun değil/hype).
> Aynı teknik tekrar görülürse satırı GÜNCELLE (yeni kaynak/yeni durum), tekrar EKLEME.

| Eklendi | Teknik | Kaynak (URL) | Durum | Not / gerekçe |
|---|---|---|---|---|
| 2026-06-17 | Reciprocal Rank Fusion (RRF) | github.com/Raudaschl/rag-fusion | entegre (v1.2) | `rank_fusion.py` + MultiQuery + opt-in `rag_rrf` |
| 2026-06-17 | bge-reranker-v2-m3 (çok-dilli reranker) | huggingface.co/BAAI/bge-reranker-v2-m3 | entegre (v1.2, kısmi) | model yapılandırılabilir; varsayılan base kaldı (modest CPU) |
| 2026-06-17 | Late chunking (Jina) | arxiv.org/abs/2409.04701 | ertelendi | uzun-bağlam embedding + tutarlı yeniden-embed gerektirir |
| 2026-06-17 | Corrective RAG (CRAG) | arxiv.org/abs/2401.15884 | ertelendi | hafif offline retrieval-evaluator ileride; web-arama kademesi offline değil |
| 2026-06-17 | HyDE | — | ertelendi | LLM + latency/halüsinasyon; opsiyonel graceful HyDE ileride |
| 2026-06-17 | GraphRAG / LightRAG / HippoRAG | arxiv.org/abs/2507.03226 | ertelendi | token-pahalı; LightRAG/HippoRAG hafif varyant olarak ileride |
| 2026-06-17 | RAGAS offline metrikleri | docs.ragas.io | aday | deterministik alt-küme (context precision via overlap) "sınavla kanıt" çizgisine uygun — sonraki entegrasyon turunda aday |
| 2026-06-17 | RbFT / ALoFTRAG (RAFT varyantları) | arxiv.org/abs/2403.10131 | ertelendi | LoRA reçetesi notu; `discipline_dataset` RbFT ruhunda |
| 2026-06-17 | Matryoshka / nomic-embed v2 (MoE) | nomic.ai | ertelendi | Ollama embedding modeli değişince yükseltme yolu |
