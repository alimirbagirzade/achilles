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

## Otomatik tarama adayları (rag-scan)

> `rag-scan` ajanının otomatik eklediği arXiv adayları (heuristik skorlu).
> Entegrasyon turu bunları değerlendirip yukarıdaki ana tabloya taşır.

| Eklendi | arXiv | Skor | Başlık | Sorgu |
|---|---|---|---|---|
| 2026-06-17 | 2602.16974 | 6 | Beyond Chunk-Then-Embed: A Comprehensive Taxonomy and Evaluation of Document Chunking Stra | RAG chunking late chunking contextual retrieval |
| 2026-06-17 | 2601.15518 | 6 | DS@GT at TREC TOT 2025: Bridging Vague Recollection with Fusion Retrieval and Learned Rera | dense retrieval embedding cross-encoder reranker |
| 2026-06-17 | 2504.19754 | 5 | Reconstructing Context: Evaluating Advanced Chunking Strategies for Retrieval-Augmented Ge | RAG chunking late chunking contextual retrieval |
| 2026-06-17 | 2606.01070 | 4 | Test-Time Training for Zero-Resource Dense Retrieval Reranking | dense retrieval embedding cross-encoder reranker |
| 2026-06-17 | 2603.25333 | 4 | Adaptive Chunking: Optimizing Chunking-Method Selection for RAG | RAG chunking late chunking contextual retrieval |
| 2026-06-17 | 2603.14828 | 4 | Toward Robust GraphRAG: Mitigating Retrieval Drift and Hallucination from Imperfect Knowle | GraphRAG knowledge graph retrieval |
| 2026-06-17 | 2511.22858 | 4 | RAG System for Supporting Japanese Litigation Procedures: Faithful Response Generation Com | RAG evaluation faithfulness groundedness hallucination |
| 2026-06-17 | 2511.11017 | 4 | AI Agent-Driven Framework for Automated Product Knowledge Graph Construction in E-Commerce | GraphRAG knowledge graph retrieval |
| 2026-06-17 | 2510.22344 | 4 | FAIR-RAG: Faithful Adaptive Iterative Refinement for Retrieval-Augmented Generation | corrective RAG self-RAG adaptive retrieval |
| 2026-06-17 | 2505.21439 | 4 | Towards Better Instruction Following Retrieval Models | dense retrieval embedding cross-encoder reranker |
| 2026-06-17 | 2501.00309 | 4 | Retrieval-Augmented Generation with Graphs (GraphRAG) | GraphRAG knowledge graph retrieval |
| 2026-06-17 | 1811.08772 | 4 | Overcoming low-utility facets for complex answer retrieval | dense retrieval embedding cross-encoder reranker |
| 2026-06-17 | 2601.05264 | 3 | Engineering the RAG Stack: A Comprehensive Review of the Architecture and Trust Frameworks | corrective RAG self-RAG adaptive retrieval |
| 2026-06-17 | 2510.25621 | 3 | FARSIQA: Faithful and Advanced RAG System for Islamic Question Answering | corrective RAG self-RAG adaptive retrieval |
| 2026-06-17 | 2506.09886 | 3 | Probabilistic distances-based hallucination detection in LLMs with RAG | RAG evaluation faithfulness groundedness hallucination |
| 2026-06-17 | 2506.06962 | 3 | AR-RAG: Autoregressive Retrieval Augmentation for Image Generation | retrieval augmented generation reranking |
