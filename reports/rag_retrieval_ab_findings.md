# RAG Retrieval A/B Bulguları — 2026-06-20

Ölçüm araçları: `scripts/rag_retrieval_ab.py`, `scripts/rag_ab_multi.py`,
`scripts/rag_ab_crossenc.py`. Metrik: **makale-düzeyi self-retrieval** (bilgi
kartından türetilen sorgu o kartın makalesini geri getiriyor mu, hangi sırada) —
recall@1/3/5/10 + MRR + sorgu başına gecikme. Korpus: 153 makale / ~91.705 chunk.
Donanım: i7-1165G7, **GPU yok**. Çevrimdışı, deterministik (Kural 2/6).

## 1. KRİTİK BUG (düzeltildi) — canlı RAG ~18s/sorgu + BM25 hibrit ölü

- `ChromaStore.get_all()` tüm 91.705 chunk id'sini TEK SQL `get()`'ine koyuyordu →
  SQLite **"too many SQL variables"** → get_all KOMPLE BAŞARISIZ → BM25 korpusu hiç
  kurulamıyordu (hibrit sessizce dense-only'e düşüyordu).
- `get_corpus_bm25()` her çağrıda YENİ `ChromaStore()` yaratıyordu → her sorgu SOĞUK
  koleksiyon yükleme + `count()` (~10-18s) ödüyordu; get_all hatası cache'i
  doldurmadığından her sorgu yeniden deniyordu.
- **Fix:** `get_all()` sayfalama (limit/offset, page=5000) + modül-düzeyi paylaşılan
  ChromaStore. Ölçülen: `retrieve()` **~18s → ~150-650ms (~30-100×)**, BM25 hibrit
  artık çalışıyor.

## 2. Config A/B (BM25 fix sonrası, 70 sorgu)

| config | recall@1 | recall@5 | MRR | gecikme p50 |
|---|---|---|---|---|
| **dense_only** | **68.6%** | 72.9% | **0.702** | **234 ms** |
| hybrid+rerank | 64.3% | 71.4% | 0.665 | 2216 ms |
| rrf | 67.1% | 72.9% | 0.689 | 2286 ms |
| dense + cross-encoder (bge-reranker-base) | — | — | — | **>15.000 ms** (CPU'da kullanılamaz) |
| dense + FlashRank (ms-marco-MiniLM-L-12, ONNX-int8) | 67.5% | 70.0% | 0.688 | **12.388 ms** |

> **FlashRank (Zincir 3, derin araştırma sonrası ölçüldü):** Web-araştırma FlashRank'i CPU'da
> ~30-100ms olarak veriyordu (M-serisi Mac / kısa pasaj). Bu GPU'suz i7-1165G7'de 40 GERÇEK
> akademik aday (≤1200 char) ile **TEMİZ koşulda bile ~12,4 s/sorgu** VE recall@1 dense'den
> DÜŞÜK (67.5 < 70.0). Sonuç KESİN: **bu donanımda hiçbir cross-encoder reranking (bge >15s,
> FlashRank ~12s) kullanılamaz** — dense-only kazanır. FlashRank opt-in olarak KODDA (GPU
> gelirse / kısa chunk'larda işe yarayabilir) ama KAPALI. `ACHILLES_RAG_FLASHRANK`.

## 3. Sonuç ve karar

Bu korpus + GPU'suz donanımda **dense-only hem en hızlı hem en doğru**:
- hibrit/rerank/RRF kaliteyi düşürüp ~2.2s ekliyor (uzun sorgularda BM25 araması yavaş).
- cross-encoder CPU'da sorgu başına >15s → kullanılamaz (kalite kazancı olsa bile hız ihlali).

**Karar:** canlı sistemde `ACHILLES_RAG_RERANK=false` + `ACHILLES_RAG_HYBRID=false`
(dense-only). Her sorgu ~234ms, BM25 soğuk-başlatma yok. **Geri alınabilir** (.env satırlarını kaldır).
BM25 sayfalama fix'i kodda kalıcı (hibrit ileride açılırsa veya başka kullananlar için doğru).

**Uyarı:** metrik semantik (kart-türevi) sorguları kayırır; keyword-ağırlıklı kullanıcı
sorularında BM25 hibrit teorik olarak yardımcı olabilir → ileride keyword golden-set ile
yeniden değerlendirilebilir. Cevap-üretimi (LLM, qwen3:4b) gecikmesi retrieval'dan AYRI ve
CPU/model-bağlı (mimari kısıt; bu çalışmanın kapsamı dışı).
