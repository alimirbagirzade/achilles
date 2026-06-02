# Achilles Trader AI

> **Yerel-öncelikli AI trading _araştırma_ sistemi** — macOS Apple Silicon için.
> RAG + bilgi kartları + (opsiyonel) LoRA + disiplinli backtest.

> ⚠️ **ÖNEMLİ:** Bu bir **araştırma aracıdır**, canlı trading botu **değildir**
> ve **yatırım tavsiyesi vermez**. Tüm çıktılar test edilmesi gereken
> _hipotezlerdir_. Gerçek parayla kullanımın tüm sorumluluğu kullanıcıya aittir.

---

## 📊 Proje Durumu — _canlı_ (son güncelleme: 2026-06-02, branch `main`)

> Repo: https://github.com/alimirbagirzade/achilles · Test: **30 passed, 2 skipped** · Kalite: ruff+mypy temiz

**Kurulum & Ortam**
- [x] uv ortamı (Python 3.13) + bağımlılıklar (`uv sync --extra dev --extra train`)
- [x] Ollama kurulu + servis ayakta
- [x] `nomic-embed-text` (embedding modeli) indirildi
- [x] `qwen2.5-coder:7b` (LLM) indirildi — RAG ile **canlı doğrulandı** (ama 8GB için ağır, ~3dk/sorgu)
- [x] `mlx-lm 0.31.3` (LoRA eğitim extra'sı, Apple Silicon)
- [x] `qwen2.5-coder:3b` (8GB profili, **aktif model**) — indirildi + RAG ile canlı çalışıyor (~60s/sorgu)

> **RAM profilleri** (`.env` / `.env.example`): **8GB → `qwen2.5-coder:3b`** (aktif) · 16GB → `7b` · **32GB → `qwen2.5-coder:14b`** (gelecekte makine değişince). Bilgisayar yükseltilince `.env`'de `ACHILLES_LLM_MODEL`'i 14b yapıp `ollama pull qwen2.5-coder:14b` yeterli.

**Çekirdek pipeline**
- [x] PDF ingestion → SQLite + ChromaDB — **gerçek PDF ile doğrulandı** (arXiv `2606.01650`, 1 makale / 69 chunk / gerçek ollama embedding)
- [x] Embedding servisi (ollama + deterministik fake fallback)
- [x] RAG yanıtlama — mantık **çevrimdışı** test edildi (stub LLM/retriever)
- [x] RAG **canlı LLM** doğrulandı — `achilles ask` qwen 7B ile kaynaklı, 5-bölümlü cevap üretti (`llm_used=True`, 3 kaynak, doğru citation)
- [x] Backtest + evaluator — EMA/RSI çalıştı, **FAIL** yargısı SQLite'a yazıldı
- [x] LoRA `train` dry-run — `mlx_lm.lora` komut kurulumu doğrulandı
- [x] Knowledge card **canlı** üretimi — `pytest -m ollama` ile 3b'de doğrulandı (kart üretildi + kaydedildi)

**Kalite & Test**
- [x] **32/32 test** (model varken): 30 çevrimdışı + 2 `@pytest.mark.ollama` canlı entegrasyon (RAG + card, 3b ile geçti)
- [x] ruff format + lint: 0 ihlal · mypy: 0 hata (37 dosya)
- [x] Şartname bölüm-7'nin **8 test dosyası da mevcut**

**Yapılacaklar (sıradaki)**
- [ ] `dataset` → LoRA `train --run` uçtan uca (3b ile küçük deneme)
- [ ] Gerçek OHLCV verisiyle backtest (sentetik yerine)
- [ ] `uv.lock`'u versiyonlamaya alma kararı (tekrarlanabilirlik)
- [ ] CI'da ollama-işaretli testleri ayır (`pytest -m "not ollama"`)
- [ ] 32GB makineye geçince `ACHILLES_LLM_MODEL=qwen2.5-coder:14b` (profil hazır)

---

## Ne işe yarar?

Akademik finans/trading literatürünü (PDF) sindirir, kaynağa dayalı yanıtlar
üretir, bulguları **test edilebilir strateji hipotezlerine** çevirir ve bu
hipotezleri **look-ahead'siz, maliyetli, örneklem-dışı (OOS) doğrulamalı** bir
backtest motorunda şüpheci bir denetçi gibi sınar.

Tasarım felsefesi: **"Aksi kanıtlanana kadar her strateji güvenilmezdir."**

---

## Mimari (katmanlar)

```
PDF makaleler
   │  (ingestion)  pdf_parser → metadata → chunker
   ▼
SQLite (yapısal kayıt)  +  ChromaDB (vektör arama)
   │  (memory)  embedding_service → paper_indexer → retrieval_service
   ▼
RAG yanıtlama / özet / bilgi kartı / eğitim verisi
   │  (brain)  rag_answerer · paper_summarizer · knowledge_card_builder
   ▼                                            training_data_builder
(opsiyonel) LoRA eğitimi — MLX, varsayılan DRY-RUN
   │  (training)  dataset_builder → mlx_lora_train → evaluate_model
   ▼
Strateji IR → Backtest → Overfit kontrolü → Evaluator (pass/fail/inconclusive)
      (trading)  strategy_ir · indicators · backtester · overfit_checks · evaluator
```

### Çevrimdışı çalışma (önemli)
Ollama kurulu değilse:
- **Embedding**: deterministik hash-tabanlı yedek embedder devreye girer
  (`ACHILLES_ALLOW_FAKE_EMBEDDINGS=true`), böylece pipeline uçtan uca çalışır.
- **LLM**: RAG, kaynak parçalarını ham gösterir (graceful degradation).

---

## Kurulum

### Gereksinimler
- Python ≥ 3.12
- (Önerilen) [uv](https://docs.astral.sh/uv/) paket yöneticisi
- (Opsiyonel) [Ollama](https://ollama.com) — yerel LLM + embedding için
- (Opsiyonel, sadece macOS arm64) `mlx-lm` — LoRA eğitimi için

### uv ile (önerilen)
```bash
uv sync                      # bağımlılıkları kur
uv run achilles init             # dizinleri + DB'yi hazırla
```

### pip ile
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
achilles init
```

### Ortam değişkenleri
```bash
cp .env.example .env
# ACHILLES_OLLAMA_HOST, ACHILLES_LLM_MODEL, ACHILLES_EMBED_MODEL, ACHILLES_RAG_TOP_K ...
```

### Ollama (opsiyonel ama RAG/kart için gerekli)
```bash
brew install ollama && brew services start ollama
ollama pull qwen2.5-coder:7b   # LLM (varsayılan, ~4.7GB)
ollama pull nomic-embed-text   # embedding modeli (~274MB)
```

---

## Kullanım (CLI: `achilles`)

| Komut | Açıklama |
|-------|----------|
| `achilles init` | Dizinleri ve SQLite şemasını oluşturur |
| `achilles status` | Sistem durumu (Ollama, embedding modu, sayımlar) |
| `achilles ingest` | `data/papers/raw_pdf/` içindeki PDF'leri indeksler (idempotent) |
| `achilles papers` | İndekslenmiş makaleleri listeler |
| `achilles ask "soru"` | RAG ile kaynaklı yanıt (5 bölümlü disiplinli format) |
| `achilles card <paper_id>` | Yapılandırılmış bilgi kartı üretir |
| `achilles dataset` | Bilgi kartlarından eğitim JSONL'i üretir |
| `achilles train` | LoRA eğitimi — **varsayılan dry-run**; gerçek için `--run` |
| `achilles evaluate <eval.jsonl>` | Modeli failure-mode eval setiyle dener |
| `achilles gen-data` | Test için sentetik OHLCV CSV üretir |
| `achilles backtest <csv>` | Strateji IR'i backtest eder + yargılar + kaydeder |

### Tipik uçtan uca akış
```bash
# 1) Araştırma
achilles init
cp ~/Downloads/*.pdf data/papers/raw_pdf/
achilles ingest
achilles ask "Momentum anomalisi düşük likiditede güçlenir mi?"
achilles card paper_abc123
achilles dataset

# 2) (Opsiyonel) Eğitim — varsayılan dry-run
achilles train                      # sadece komutu gösterir
achilles train --run                # gerçekten eğitir (macOS arm64 + mlx-lm)
achilles evaluate evals/discipline_core.jsonl

# 3) Backtest (gerçek veri yoksa sentetik üret)
achilles gen-data
achilles backtest data/market/raw/synthetic.csv
```

---

## Geliştirme

```bash
make install      # uv sync + pre-commit
make test         # pytest
make lint         # ruff check
make format       # ruff format
make typecheck    # mypy
```

CI (`.github/workflows/ci.yml`): her push/PR'da `uv sync` + `ruff` + `pytest`.

---

## Disiplin kuralları (sistemin kalbi)

1. **Kaynak yoksa uydurma** — RAG, retrieval boşsa açıkça söyler.
2. **Test edilmeden "başarılı" deme** — backtest + OOS olmadan yasak kelime.
3. **Maliyetleri yok sayma** — komisyon + slippage her backtest'te.
4. **Look-ahead yok** — pozisyon bir bar gecikmeli uygulanır.
5. **Overfit'e karşı** — in/out-of-sample bölmesi + statik bayraklar.
6. **Determinizm** — rastgelelik daima `seed` ile.
7. **Kod yürütme yok** — strateji kuralları yalnızca güvenli regex ile.

---

## GitHub

Repo: **https://github.com/alimirbagirzade/achilles** (`main`). Klonlama:

```bash
git clone https://github.com/alimirbagirzade/achilles.git
cd achilles && uv sync --extra dev && uv run achilles init
```

---

## Proje yapısı

```
app/
  config/      ayarlar (pydantic-settings), logging
  ingestion/   pdf_parser, paper_loader, metadata, chunker
  memory/      sqlite_store, embedding_service, chroma_store,
               paper_indexer, retrieval_service
  brain/       local_llm, prompt_loader, rag_answerer, paper_summarizer,
               knowledge_card_builder, training_data_builder, model_router
  training/    dataset_builder, mlx_lora_train, adapter_registry, evaluate_model
  trading/     strategy_ir, indicators, backtester, overfit_checks,
               evaluator, strategy_generator, market_data_loader
  prompts/     *.md (Türkçe sistem/RAG/özet/kart/hipotez/kritik şablonları)
  main.py      Typer CLI
.claude/skills/  trading-research, backtest-auditor, codegen-review
evals/         disiplin/overfit/risk failure-mode JSONL setleri
tests/         pytest (çevrimdışı, fake-embedding ile çalışır)
```

---

## Lisans & sorumluluk reddi

Eğitim ve araştırma amaçlıdır. Finansal tavsiye değildir. Geçmiş performans
gelecek sonuçların garantisi değildir.
