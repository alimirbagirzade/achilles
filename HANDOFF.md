# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-07 · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

Yerel-öncelikli (local-first) AI **trading araştırma** sistemi (macOS Apple Silicon).
**Canlı bot değil, yatırım tavsiyesi değil.** Tam akış:
`PDF → metin → chunk → SQLite + ChromaDB → RAG → knowledge card → formül çıkarımı → kavram grafiği → sentez → agentic döngü → backtest → reasoning zinciri → LoRA eğitimi → MLX inference`

---

## 🚨 YENİ SEANS BAŞLANGICI — BUNU OKU

### Proje amacı (asıl hedef)
LLM'i **"trader gibi düşünen"** bir araştırma motoru yapmak:
1. Makalelerden formül ve kavramları hafızaya al
2. Bunları birleştirip **daha önce denenmemiş** indikatör/algoritma öner
3. Otomatik backtest et
4. Sonuçtan öğren (yansıt → iyileştir → tekrar)
5. Tüm zinciri **LoRA eğitim verisi** olarak kullan
6. 3B model mimiriyi test eder; gerçek çıktı için 120B kullanılacak

### Mevcut durum (2026-06-07 — son commit: d24cb1a)
- **233 test** geçiyor · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **`app/research/`** modülü TAMAMLANDI
- **Advanced RAG katmanı** EKLENDI — 37 yeni dosya (verification, evals, reliability)
- **OSS Learning Agent MVP** EKLENDI — 6 yeni modül (profiler, advisor, installer, benchmark, memory, registry)
- **LoRA:** `achilles_lora_v2` eğitildi (300 iter, loss 0.028, 2GB peak)
- **Ollama aktif:** qwen2.5-coder:3b + nomic-embed-text · 7 PDF · 567 chunk

### Bu seansta TAMAMLANANLAR ✅

1. **✅ BTCUSD 1H CSV → backtest bağlandı**
   - `market_data_loader.py`: Binance `Open time` kolonunu tanır, 71.328 bar
   - `uv run achilles backtest data/market/raw/BTCUSD_1h_Binance.csv`
   - Sonuç: **PASS** — 588 işlem, +2603% getiri, Sharpe 2.17, DD -%63.9

2. **✅ `extract-formulas` çalıştırıldı** — 5 formül (ATR, EMA, RSI x2, Stochastic)

3. **✅ Araştırma döngüsü çalıştırıldı**
   - "Momentum göstergeleri yüksek volatilitede nasıl filtrelenir?"
   - VolumeAdjustedMomentum x3 → FAIL (az işlem — beklenen sonuç, döngü disiplinli)
   - Düzeltmeler: backtester eksik kolonu auto-compute eder, LLM string indicator'ı dict'e çevirir

4. **✅ Pine Script export eklendi**
   - `StrategyIR.to_pine()` → Pine v5 taslak kod
   - CLI: `uv run achilles pine [strateji-adı] [--output dosya.pine]`

### Bu seansta TAMAMLANANLAR ✅ (2026-06-04 — oturum 2)

9. **✅ Görev 9 — `achilles status` onay kart sayısı**
   - `status` komutu artık "X bekliyor / Y onaylı" satırı gösteriyor

10. **✅ Görev 10 — `export-package` backtest verdict otomatik**
    - SQLite'tan en son backtest çekilip pakete ekleniyor (verdict + sharpe + return + n_trades)
    - CLI çıktısında `[green]pass[/green]` / `[red]fail[/red]` rengi

11. **✅ Görev 11 — `.achpkg` TypeScript tip tanımı**
    - `achilles_package.d.ts` oluşturuldu (kök dizin)
    - `AchillesPackage`, `CodeBundle`, `BacktestMetrics`, `IndicatorSpec`, `CostSpec` interface'leri

12. **✅ Advanced RAG entegrasyonu (RAGsetup dokümantasyonundan)**
    - 37 yeni modül: `app/brain/`, `app/memory/`, `app/ingestion/`, `app/verification/`, `app/evals/`, `app/reliability/`
    - 4 yeni Claude skill: `scientific-rag-reasoning`, `advanced-rag-optimizer`, `formula-and-argument-integrity`, `rag-reliability-engineer`
    - `rag_answerer.py`: cevaplar artık **hem İngilizce hem Türkçe** (9 başlık)
    - RAG modülleri **İngilizce** docstring
    - 9 yeni SQLite tablosu + 10 test

13. **✅ Synthesis engine "az işlem" düzeltmesi**
    - `prev_failures` parametresi eklendi → önceki FAIL bilgisi prompt'a giriyor
    - `_parse_result`: RSI eşiği > 53 ise otomatik > 50'ye indir; entry rule > 2 ise 1'e kısalt
    - `_build_failure_hint`: "az işlem" tespitinde prompt'a açık uyarı ekle
    - Orchestrator `prev_failures` listesini doldurarak synthesis'e iletiyor

14. **✅ Pine Script: Stochastic, VWAP, Supertrend eklendi**
    - `strategy_ir.py` `to_pine()` → 3 yeni indikatör (Pine v5 `ta.*` syntax)
    - `package_exporter.py` `_ir_to_python()` → pandas implementasyonları

15. **✅ Pine Script commission fix**
    - `commission_value=0.0500` → `0.05` (trailing zero temizlendi)
    - `commission_type=strategy.commission.percent` açıkça belirtildi

### Bu seansta TAMAMLANANLAR ✅ (2026-06-04)

5. **✅ Faz 1 — Bilgi Mimarisi + Sınıflandırma Backend**
   - `knowledge_cards` tablosuna 5 yeni kolon: `trust_level`, `review_status`, `lora_eligible`, `difficulty`, `stage`
   - DB migration: idempotent ALTER TABLE (`_migrate()`)
   - `KnowledgeCardBuilder._classify_card()`: kural tabanlı otomatik sınıflandırma
   - Yeni store metodları: `approve_card`, `reject_card`, `list_pending_cards`, `list_approved_cards`
   - CLI: `achilles cards pending | approve <id> | reject <id>`

6. **✅ Faz 1 — Web UI Onay Ekranı**
   - `GET /api/cards/pending` → bekleyen kartlar
   - `POST /api/card/{id}/approve` / `reject` → onay/red
   - `GET /api/cards/approved` → onaylı kartlar (difficulty filtresi)
   - Web UI: **06 · ONAY** sekmesi (Onayla/Reddet butonları)

7. **✅ Faz 2 — Curriculum-Aware Dataset Builder**
   - `DatasetBuilder.collect(phase=1-4, lora_eligible_only=True)`
   - Curriculum pacing: %60 mevcut + %30 alt + %10 üst faz
   - CLI: `achilles dataset --phase 1` / `--all`

8. **✅ Faz 3 — Structured LoRA Training**
   - `TrainConfig.lora_phase` + `from_phase`
   - Faz-tabanlı adlandırma: `achilles_lora_v3_phase1` → `_phase2`
   - `--resume-adapter-file` ile kademeli eğitim desteği

9. **✅ Achilles Package (Entropia export)**
   - `app/trading/package_exporter.py`: StrategyIR → `.achpkg` (JSON)
   - İçerik: Pine Script v5 + Python `compute_signals()` modülü
   - CLI: `achilles export-package [strateji-adı] [--output dosya.achpkg]`
   - API: `GET /api/strategy/{name}/export` + `POST /api/package/export`
   - **176 test** — hepsi yeşil · ruff+mypy sıfır hata

### Bu seansta TAMAMLANANLAR ✅ (2026-06-07 — oturum 5)

20. **✅ TradingView MCP Köprüsü — Canlı Test**
    - TV CDP modu manuel başlatma (`--remote-debugging-port=9222`) çözüldü
    - BTCUSD 1H · Pine v6 derleme · Strategy Tester aktif
    - Kritik bulgu: `ema_rsi_trend_filter_v1` → Achilles: +2603%/Sharpe 2.17 (2017–2025 Binance) vs TV: -4%/Sharpe -0.641 (2025–2026 Bitstamp) → **overfit konfirme edildi**, OOS denetiminin önemi doğrulandı
    - TV bridge tamamen işlevsel: Pine yükleme ✅, derleme ✅, metrik okuma ✅, ekran görüntüsü ✅

21. **✅ OSS Learning Agent MVP**
    - `app/agents/system_profiler/profiler.py` — hardware tara (Windows/macOS/Linux, psutil-free fallback)
    - `app/registry/model_registry.yaml` — 9 model (tiny 1.5B → very_large 70B)
    - `app/agents/model_advisor/advisor.py` — RAM/VRAM/görev bazlı skor motoru + red listesi
    - `app/agents/installer/ollama_installer.py` — whitelist güvenlik katmanı (rm -rf, sudo, curl|sh bloklu)
    - `app/agents/benchmark/runner.py` — 4 prompt (json/code/reasoning/translation) · tokens/sec · kalite
    - `app/agents/learning/memory.py` — SQLite: `system_profiles`, `model_trials`, `error_patterns`, `rule_suggestions`
    - 16 yeni test → **233 toplam test** · ruff CLEAN
    - Yeni CLI: `achilles profile`, `achilles recommend --task`, `achilles install --auto-safe`, `achilles benchmark`
    - 8 GB Apple Silicon'da test: qwen2.5-coder:1.5b + qwen3:4b önerildi, 7B+ reddedildi ✅

### Bu seansta TAMAMLANANLAR ✅ (2026-06-04 — oturum 3)

16. **✅ README web kılavuzu tam güncelleme**
    - 8 sekme (03·TRADER BEYİN + 06·ONAY eklendi), numaralar düzeltildi
    - 12 yaş seviyesinde analoji+tablo formatı

17. **✅ TradingView MCP köprüsü**
    - `GET /api/backtest/{id}/pine` endpoint'i → Pine Script v5 döndürür
    - `PineExportResponse` şeması
    - Web UI: backtest geçmişinde **🌲 Pine Kopyala** butonu + modal
    - `.claude/skills/tv-bridge/skill.md` → `/tv-bridge` skill'i

18. **✅ arXiv otomatik makale çekme**
    - `app/ingestion/arxiv_fetcher.py` (search + fetch, httpx, idempotent)
    - CLI: `achilles arxiv "sorgu" --max 5 --search-only`
    - API: `GET /api/arxiv/search` + `POST /api/arxiv/fetch`
    - Web UI: MAKALELER sekmesinde "arXiv'den Makale Çek" bölümü

19. **✅ Risk manager modülü**
    - `app/trading/risk_manager.py`: Kelly kriteri, drawdown ölçekleme, sabit risk
    - CLI: `achilles risk <backtest_id> [--equity 10000 --max-dd -20]`
    - API: `GET /api/backtest/{id}/risk`
    - Web UI: backtest geçmişinde **⚖ Risk Analizi** butonu + modal (Kelly grid)

### ⚡ YENİ SEANS BAŞLANGICI — KULLANICIYA SOR

> **Claude: Bir sonraki seansta aşağıdaki listeden kullanıcıya seçim yaptır. Hemen koda girme.**

---

## 🗺️ DEVAM SEÇENEKLERİ (kullanıcıya sor)

### 🔴 Kalite borcu — düzeltilmemiş şeyler

| # | Sorun | Durum |
|----|-------|-------|
| ~~1~~ | Araştırma döngüsü — az işlem FAIL döngüsü | ✅ |
| ~~2~~ | Pine Script — Stochastic, VWAP, Supertrend eksik | ✅ |
| ~~3~~ | Package exporter — commission_value yüzde | ✅ |

### 🟡 Kalan planlanmış özellikler

| # | Özellik | Neden önemli |
|---|---------|--------------|
| ~~4~~ | ~~TradingView MCP köprüsü~~ | ✅ **TAMAMLANDI** |
| ~~5~~ | ~~arXiv otomatik çekme~~ | ✅ **TAMAMLANDI** |
| ~~6~~ | ~~Web UI pine export butonu~~ | ✅ **TAMAMLANDI** |
| ~~7~~ | ~~Risk manager modülü~~ | ✅ **TAMAMLANDI** |
| ~~A~~ | ~~TV köprüsü canlı test~~ | ✅ **TAMAMLANDI** — overfit bulgusu önemli |
| ~~OSS~~ | ~~OSS Learning Agent MVP~~ | ✅ **TAMAMLANDI** — profiler + advisor + installer + benchmark + memory |
| 8 | **Faz 4 DPO altyapısı** | 500+ onaylı not gerekiyor; önce kart biriktirmek lazım |

### 🟢 Bekleyen görevler (öncelik sırasıyla)

| # | Görev | Süre | Not |
|---|-------|------|-----|
| **B** | **Risk raporu → SQLite persist** | ~1 saat | `analyze_risk()` sonucunu `risk_reports` tablosuna kaydet, web UI'da göster |
| **C** | **Web UI: .achpkg İndir butonu** | ~30 dk | Backtest kartında `GET /api/strategy/{name}/export` tetikle |
| **D** | **arXiv sorgu kütüphanesi** | ~45 dk | Önerilen sorguları kaydet, scheduled/otomatik çalıştır |
| **E** | **SessionStart hook** | ~10 dk | `.claude/settings.json` oluştur (otomatik HANDOFF yükleme) — kullanıcı onayı gerekli |
| **F** | **OSS Agent: rules_updater.py** | ~1 saat | Başarısız trial → kural önerisi pipeline |
| **G** | **OSS Agent: psutil opsiyonel bağımlılık** | ~15 dk | `pyproject.toml`'a `[dev,oss]` extra ekle |

### 🔵 Büyük / ileriki — şimdi yapılmaz

| | Neden bekler |
|--|-------------|
| Faz 4 DPO + GraphRAG | 500+ onaylı not gerekiyor (şu an 0) |
| 120B model | Donanım hazır değil |
| CCXT/Binance canlı veri | Türkiye'de bloklu |
| OSS Agent Phase 2 | llama.cpp + MLX backend, GGUF downloader, HF metadata |
| OSS Agent Phase 3 | RAG memory (logs/benchmark indexing) |

---

**Önerilen sıra (sonraki seans):**
- **B)** Risk raporu SQLite persist (küçük, bağımsız)
- **C)** .achpkg İndir butonu (web UI tamamlama)
- **D)** arXiv sorgu kütüphanesi (otomatik literatür tarama)
- **E)** SessionStart hook — `.claude/settings.json` oluşturma (kullanıcı onayıyla)

---

## Tam modül haritası (güncel)

```
app/
├── brain/
│   ├── knowledge_card_builder.py  # PDF → yapısal bilgi kartı (Ollama JSON mode)
│   ├── local_llm.py               # Ollama HTTP client (fmt/timeout/max_tokens)
│   ├── mlx_llm.py                 # MLX adapter inference (subprocess, LoRA)
│   ├── model_router.py            # görev→model/adapter yönlendirme
│   ├── paper_summarizer.py        # makale özeti
│   ├── prompt_loader.py           # prompts/ dizininden şablon yükle
│   ├── rag_answerer.py            # RAG + 5-bölümlü disiplinli cevap
│   └── training_data_builder.py   # kart → training_examples tablosu
├── config/settings.py             # pydantic-settings, tüm path'ler buradan
├── ingestion/
│   ├── chunker.py                 # metin → chunk (overlap)
│   ├── metadata_extractor.py      # başlık/yıl/yazar çıkarımı
│   ├── paper_loader.py            # ham PDF yükle
│   └── pdf_parser.py              # pymupdf/pdfplumber
├── memory/
│   ├── chroma_store.py            # ChromaDB vektör deposu
│   ├── embedding_service.py       # Ollama embed + fake fallback
│   ├── paper_indexer.py           # PDF → SQLite + ChromaDB pipeline
│   ├── retrieval_service.py       # semantic search → RetrievedChunk
│   └── sqlite_store.py            # SQLAlchemy 2.0 (tüm tablolar + metotlar)
├── research/                      # 🆕 TRADER BEYİN
│   ├── formula_extractor.py       # chunk → formül JSON (LLM + kural yedek)
│   ├── concept_graph.py           # kavram bağlantıları (extends/measures/limits)
│   ├── synthesis_engine.py        # ★ tüm formüller → yeni indikatör öneri
│   ├── reflection_agent.py        # backtest sonucu → iyileştirilmiş IR
│   ├── orchestrator.py            # ★ tam döngü: sentezle→test→yansıt→iyileştir
│   └── chain_data_builder.py      # araştırma zincirleri → LoRA JSONL
├── trading/
│   ├── backtester.py              # look-ahead-safe backtest + persist
│   ├── evaluator.py               # OOS split → pass/fail/inconclusive
│   ├── indicators.py              # EMA/SMA/RSI/ATR/MACD/Bollinger registry
│   ├── market_data_loader.py      # CSV yükle + sentetik üret
│   ├── overfit_checks.py          # static checks + in/out-of-sample
│   ├── strategy_generator.py      # hipotez keyword → StrategyIR template
│   └── strategy_ir.py             # Pydantic StrategyIR (güvenli regex parse)
├── agents/                        # 🆕 OSS Learning Agent MVP
│   ├── system_profiler/profiler.py  # hardware tara (win/mac/linux)
│   ├── model_advisor/advisor.py     # RAM/VRAM/görev bazlı öneri motoru
│   ├── installer/ollama_installer.py # güvenli whitelist Ollama wrapper
│   ├── benchmark/runner.py          # tokens/sec + 4-prompt kalite testi
│   └── learning/memory.py           # SQLite: profiles/trials/errors/rules
├── registry/
│   └── model_registry.yaml        # 9 OSS model (1.5B–70B, tiny→very_large)
├── training/
│   ├── adapter_registry.py        # LoRA adapter versiyonları SQLite+JSON
│   ├── dataset_builder.py         # training_examples → train/valid JSONL
│   ├── evaluate_model.py          # red-flag eval (guardrail testleri)
│   └── mlx_lora_train.py          # mlx_lm lora launcher (dry-run default)
└── web/
    ├── schemas.py                 # Pydantic request/response modelleri
    ├── security.py                # token auth, rate-limit, CSP, PDF doğrulama
    └── server.py                  # FastAPI: 20+ endpoint

SQLite tabloları:
  papers, chunks, summaries, knowledge_cards, training_examples,
  strategies, backtests, model_evaluations, adapters,
  formulas, concept_links, research_sessions   ← 🆕

CLI komutları (achilles --help):
  init, status, ingest, papers, ask, card, dataset, train, evaluate,
  gen-data, backtest, extract-formulas, formulas, research,
  research-sessions, chain-dataset, pine, export-package, risk, arxiv,
  profile, recommend, install, benchmark          ← 🆕 OSS Agent

Web API endpoint'leri (/api/...):
  status, papers, papers/upload, ingest, ask,
  card/{id} (GET/POST), cards/batch, card/{id}/backtest,
  backtests, backtest (POST), backtest/csv,
  training/status, training/dataset, training/dry-run,
  training/examples (GET/DELETE),
  research/formulas, research/graph, research/extract,
  research/run, research/sessions, research/chain-dataset,  ← 🆕
  eval/sets, eval/run
```

## Bu oturumda yapılanlar

1. **Proje doğrulandı** — ~40 modül / 3235+ satır kod (ingestion, memory, brain, training, trading, CLI, testler) tutarlı ve çalışır durumda.
2. **İsim tutarlılığı** — repo genelindeki tüm `Ares` / `ares` ibareleri **`Achilles` / `achilles`** olarak değiştirildi (kod, env prefix `ACHILLES_`, db `achilles_trader_ai.db`, CLI komutu `achilles`, scriptler, şartname `.txt`). Kalan "ares" yok.
3. **Ortam kuruldu** — `uv sync --extra dev` → **Python 3.13** + 267 paket (chromadb, pymupdf, sqlalchemy, typer, backtesting…).
4. **Ollama kuruldu** — `brew install ollama`, `brew services start ollama` (servis ayakta, `http://localhost:11434`). `nomic-embed-text` ✅ indi; `qwen2.5-coder:7b` ⏳ iniyor.
5. **mlx-lm kuruldu** — `uv sync --extra dev --extra train` → `mlx-lm 0.31.3` (Apple Silicon, LoRA eğitim hazır).
6. **Testler** — `uv run pytest` → **21/21 geçti** (çevrimdışı, fake embedding).
7. **Kalite kapıları (ruflo `quality` ajanı)** — `ruff format` (43 dosya temiz), `ruff check` (0 ihlal), `mypy` (37 dosya, 0 hata).
8. **Uçtan uca duman testi** — `achilles init` + `gen-data` + `backtest` çalıştı; EMA/RSI metrik üretti, evaluator **FAIL** yargısı verdi (out-of-sample + min işlem), SQLite'a `bt_…` kaydedildi.
9. **GERÇEK PDF ingestion doğrulandı (ruflo `ingestion` ajanı)** — arXiv `2606.01650` "Post-Selection Estimation of Sharpe Ratios" indirildi → **1 makale, 69 chunk** SQLite + ChromaDB, **gerçek ollama embedding** (63.459 karakter). Hatasız.
10. **GitHub'a push edildi** — `alimirbagirzade/achilles` `main`: `Initial commit → feat: MVP skeleton → docs(handoff)` (temiz lineer tarih, force yok).
11. **ruflo devrede** — hierarchical swarm `swarm-1780379731927-98lit9`, oturum durumu `patterns` namespace'inde (HNSW, 384-dim). İki uzman ajan (`code-analyzer`, `backend-dev`) görevleri tamamladı.

---

## Nasıl çalıştırılır

```bash
cd ~/Development/Achilles
uv sync --extra dev          # ortam + bağımlılıklar
uv run achilles --help       # tüm komutlar
uv run achilles init         # dizinler + SQLite şeması
uv run achilles status       # model / embedding modu / kayıt sayıları
uv run achilles gen-data --n 1500
uv run achilles backtest data/market/raw/synthetic.csv
uv run pytest                # 21 test (çevrimdışı)
# Makefile kısayolları: make test | lint | format | typecheck | ci
```

RAG / knowledge card / dataset komutları için Ollama + modeller gerekir:
```bash
ollama list                                  # modeller indi mi?
# PDF'leri data/papers/raw_pdf/ içine koy:
uv run achilles ingest
uv run achilles ask "Bu literatürdeki ana trading bulgusu nedir?"
uv run achilles card <paper_id>
uv run achilles dataset
```

---

## Mimari (katmanlar)

| Katman | Dosyalar |
|--------|----------|
| **ingestion** | `pdf_parser`, `paper_loader`, `metadata_extractor`, `chunker` |
| **memory** | `sqlite_store` (SQLAlchemy 2.0), `chroma_store`, `embedding_service` (Ollama + fake fallback), `paper_indexer`, `retrieval_service` |
| **brain** | `local_llm`, `rag_answerer`, `paper_summarizer`, `knowledge_card_builder`, `training_data_builder`, `model_router`, `prompt_loader` |
| **training** | `dataset_builder`, `mlx_lora_train` (dry-run default), `evaluate_model`, `adapter_registry` |
| **trading** | `market_data_loader`, `indicators` (vektörize), `strategy_ir`, `strategy_generator`, `backtester` (look-ahead-safe), `evaluator`, `overfit_checks` |
| **cli** | `app/main.py` — Typer (`achilles`) |

Sözleşmeler: `paper_id` içerik hash'inden türer (idempotent ingestion). Strateji yaşam döngüsü: `hipotez → StrategyIR → backtest → evaluate → verdict`; `verdict != pass` ise çıktı "aday"dır.

---

## Açık konular / sonraki adımlar

- [x] **RAG canlı doğrulandı** — `achilles ask` hem 7B hem 3b ile kaynaklı 5-bölümlü cevap üretti; `pytest -m ollama` (RAG + knowledge card) 3b'de **2 passed**.
- [x] **8GB RAM kararı** — 7B 8GB'da ağır (model+embed birlikte sığmıyor, RAG ~3dk). Aktif model **`qwen2.5-coder:3b`** (`.env`). 32GB'a geçince `ACHILLES_LLM_MODEL=qwen2.5-coder:14b` (profil `.env.example`'da kayıtlı).
- [x] **`dataset` → `train --run` LoRA denemesi YAPILDI** — kart→10 örnek→`mlx_lm.lora` (base `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit`); train loss 1.21→0.029, peak 3.8GB, `models/adapters/achilles_lora_smoke/adapters.safetensors` + registry; adapter çıkarımda öğrenilmiş "hipotez+test planı" formatını üretti. NOT: kart 3b/7b ile 8GB'da üretilemedi (3b geçersiz JSON, 7b 300s timeout) → kart makaleye uygun şekilde elle seed edildi; deterministik training_data_builder + dataset + mlx zinciri gerçektir. NOT: mlx_lm ollama GGUF değil HF/MLX modeli ister (`achilles train --base-model <hf-mlx-id>`).
- [x] **Python 3.12 pin** — `.python-version` → 3.12, `.gitignore`'dan çıkarıldı, 64 test geçiyor.
- [x] **`uv.lock`** — commit edildi (önceki oturumda). `.gitignore`'da değil, tracked.
- [x] **Gerçek PDF ingestion** — 7 PDF (`data/papers/raw_pdf/`), 567 chunk, Ollama embed. `achilles ingest` → `ask` uçtan uca doğrulandı.
- [x] **RAG / knowledge card / dataset** — Ollama qwen2.5-coder:3b ile canlı; `achilles ask` LLM cevabı + kaynaklar; `achilles card paper_d1cfbf08c065` tam kart üretti; `dataset` 15+4 JSONL.
- [x] **MLX-LM LoRA gerçek eğitim** — `achilles train --run` ile `achilles_lora_v2` eğitildi (300 iter, loss 2.47→0.028, val 1.108, peak **1.995 GB**). Komut formatı `mlx_lm lora`; `--save-every/--steps-per-eval 300` OOM düzeltmesi; `batch_size=2, num_layers=8` 8GB varsayılanı. `models/adapters/achilles_lora_v2/adapters.safetensors` + registry'e kayıtlı.

- [x] **Test kapsamı genişletildi (2026-06-03)** — 64 → 114 test (+50). Yeni dosyalar: `test_indicators` (14 test: EMA/SMA/RSI/ATR/MACD/Bollinger/compute_indicator), `test_evaluator` (10 test: static_checks/OOS/verdict), `test_strategy_generator` (11 test: trend/mean-reversion/keyword/defaults), `test_dataset_builder` (8 test: split/bootstrap/dedup/hash), `test_sqlite_store_extended` (9 test: list_backtests/list_training_examples/delete).

- [x] **Toplu kart üretimi** — `POST /api/cards/batch` endpoint'i; "⚡ TÜM KARTLARI ÜRET" butonu (Makaleler sekmesi); kart olmayan tüm makaleleri sırayla işler, skip/ok/error raporlar.

- [x] **MLX adapter inference + model eval UI (2026-06-03)** —
  - `app/brain/mlx_llm.py`: `MlxLLM` sınıfı — subprocess ile `mlx_lm generate`, adapter_path desteği, timeout/hata yönetimi
  - `AskRequest.adapter_version` — belirtilirse MLX adapter ile yanıt, Ollama bypass
  - `AskResponse.adapter_used` — hangi adapter kullanıldı badge olarak gösterilir
  - `GET /api/eval/sets` — `evals/` dizinindeki `.jsonl` eval setleri
  - `POST /api/eval/run` — `ModelEvaluator` çalıştır, skor + bayrak + yanıt listesi
  - 05 · DEĞERLENDİRME sekmesi — eval seti + adapter seçimi + sonuç render
  - ARAŞTIRMA sekmesinde model seçici dropdown (Ollama / adapter versiyonları)
  - `test_mlx_llm` (10 test) + `test_eval_api` (5 test) → **128 toplam test**

- [x] **BTCUSD 1H Binance backtest YAPILDI (2026-06-03)** — 71.328 bar, 2017-2025; EMA/RSI: +2603%/Sharpe 2.17/DD -%63.9; evaluator **PASS** (`bt_cd00c55600`). `market_data_loader` Binance `Open time` formatını destekler.
- [x] **Pine Script export eklendi (2026-06-03)** — `StrategyIR.to_pine()` → Pine v5 taslak; CLI `achilles pine [strateji] [--output]`.
- [x] **Backtester auto-column fix (2026-06-03)** — rule'larda referans edilen ama `indicators` listesinde olmayan kolonlar (ör. `ema_50`) otomatik hesaplanır.
- [x] **Synthesis engine string indicator fix (2026-06-03)** — LLM `"RSI_20"` string döndürünce `IndicatorSpec`'e dönüştürülür.
- [x] **Oturum protokolü + skill sistemi kuruldu (2026-06-03)** — CLAUDE.md seans başlangıç protokolü; 3 proje skili dolduruldu; HANDOFF'a tam skill haritası eklendi.
- [x] **Gerçek OHLCV backtest YAPILDI** — BTC-USD günlük (Yahoo Finance, 1827 bar / 5 yıl; Binance+CryptoCompare+Kraken Türkiye'de bloklu, Stooq apikey istiyor). EMA/RSI: getiri +%52 / Sharpe 4.0 / DD -%52 ama evaluator **FAIL** (`bt_e22fbfde4b`): örneklem-dışı negatif (overfit) + az işlem. Gerçek veride disiplin doğrulandı. CSV: `data/market/raw/BTCUSD_1d.csv` (gitignored).
- [x] **Güvenlikli web arayüzü eklendi** (`app/web/`) — FastAPI ince katman: status/papers/upload/ingest/ask/card/backtest + `/api/docs`; `security.py` (token auth `secrets.compare_digest`, IP rate-limit, CSP+güvenlik başlıkları, PDF magic-byte+boyut doğrulama, path-traversal koruması); terminal-estetik static UI (CSP-uyumlu); `SECURITY.md`. `pip install -e ".[web]"` → `achilles-web` (yalnız localhost). Denetim: 2 "ares" regresyonu (`achilles_lora_v1`, `achilles_test`) düzeltildi, `_consteq`→`secrets.compare_digest`, README canlı-durum+github+model bölümleri geri getirildi. **43 offline test geçiyor, ruff+mypy temiz.**

- [x] **8GB'da güvenilir bilgi-kartı ÇÖZÜLDÜ** — `knowledge_card_builder`: Ollama `format:"json"` (geçerli JSON garanti) + kısa girdi (14000→6000 krk) + `num_predict` cap + boşsa kısa retry + esnek `_extract_json` (akıllı tırnak/sondaki virgül onarımı); `local_llm.generate` artık `fmt`/`timeout` alıyor. 3b ile gerçek makaleden dolu+doğru kart (methods: polyhedral lemma, James-Stein shrinkage…) ~56s. Card→TrainingDataBuilder→dataset artık otomatik (elle seed gerekmez). 49 offline test geçiyor.

- [x] **Bilgi kartı görüntüleme (2026-06-03)** — `GET /api/card/{paper_id}` endpoint'i (LLM gerektirmez); `SqliteStore.get_latest_knowledge_card()`; "KART VAR" butonu → tıklanabilir "KARTI GÖR"; kart içeriğini modal'da render eden UI (başlık, meta, tüm alanlar). 53 offline test.

- [x] **LoRA Web UI + Kart→Backtest + Arama/Filtre (2026-06-03)** — Üç bağımsız özellik:
  1. **04 · EĞİTİM sekmesi**: `GET /api/training/status` (örnek sayısı + adapter listesi), `POST /api/training/dataset` (DatasetBuilder), `POST /api/training/dry-run` (mlx_lm komutu önizle; çalıştırmaz). UI: dataset oluştur, dry-run formu, adapter tablosu.
  2. **Kart→Backtest** (`POST /api/card/{paper_id}/backtest`): her `possible_strategy_hypotheses` için `generate_from_hypothesis` → `run_backtest` (sentetik 2000 bar) → `evaluate`; kart modalında "⚡ HİPOTEZLERİ BACKTEST ET" butonu + sonuç render.
  3. **Makale arama/filtre/sıralama**: başlık arama inputu, Tümü/Kartlı/Kartsız filtresi, A→Z/Z→A/kartlı önce sıralama (client-side). **59 offline test, ruff+mypy temiz.**

---

## SEANS BAŞLANGIÇ PROTOKOLÜ

### /login neden gerekiyor?
`/login` yalnızca **claude.ai OAuth MCP sunucuları** (Figma, Gmail, Google Calendar, Notion) için gereklidir. Bu sunucuların token'ları periyodik olarak sona erer. Bu proje **lokal-öncelikli** olduğundan o sunuculara ihtiyaç yoktur. `/login` atlansa da olur; ancak Notion/Gmail entegrasyonu kullanılacaksa ilk komut olarak çalıştır.

### Ruflo — Otomatik Başlatma
Her seansta Claude, ruflo araçlarını (ToolSearch ile yükleyerek) başlatmalı:
```
ToolSearch → "ruflo memory_search" → son `patterns` namespace'ini yükle
```
Ruflo swarm'ı yoksa: `swarm_init` → `code-analyzer` + `backend-dev` ajanlarını başlat.

---

## LOKAL SKİLLLER — TAM LİSTE

### Proje Skiller (`.claude/skills/` bu repoda)

| Skill | Amaç | Ne zaman çalıştır |
|-------|------|-------------------|
| `/trading-research` | Araştırma döngüsü: formül çıkar → sentez → backtest → yansıt | Yeni hipotez test edilecekse |
| `/backtest-auditor` | Look-ahead bias, OOS split, overfit, komisyon denetimi | Her backtest sonrasında |
| `/codegen-review` | Yeni indikatör/strateji kodu kalite denetimi | Kod commit öncesi |

### Global Skiller (`~/.claude/skills/`) — Bu projede kullanılanlar

| Skill | Amaç |
|-------|------|
| `/health` | Ruff+mypy+test özet raporu |
| `/investigate` | Hata kök neden analizi |
| `/code-review` | PR diff denetimi (--fix ile otomatik düzelt) |
| `/security-review` | Güvenlik açığı taraması |
| `/deep-research` | Çok kaynaklı web araştırması → sentez raporu |
| `/qa` | Uygulama QA testi ve hata düzeltme |
| `/ship` | Test→lint→commit→push→PR otomasyonu |
| `/spec` | Belirsiz isteği → çalıştırılabilir spesifikasyon |
| `/claude-mem:make-plan` | Çok adımlı plan oluştur |
| `/claude-mem:do` | Planı ajanlarla çalıştır |
| `/claude-mem:mem-search` | Geçmiş seansları ara |
| `/claude-mem:learn-codebase` | Repoyu belleğe tam al (yeni seans) |
| `/claude-mem:timeline-report` | Proje geçmişi özet raporu |

### Geliştirme Roadmap Skilleri (kurulacak)

Bu projeyi ilerletmek için eklenmesi planlanan skiller:

| Skill (hedef) | Amaç | Öncelik |
|---------------|------|---------|
| `arxiv-research` | arXiv'den makale ara/indir/ingest et | YÜKSEK |
| `pine-export` | StrategyIR → TradingView Pine Script | YÜKSEK |
| `factor-analysis` | Çok faktörlü strateji analizi (Fama-French vb.) | ORTA |
| `risk-manager` | Pozisyon büyüklüğü + Kelly + max-drawdown hesabı | ORTA |
| `data-fetch` | Binance/CCXT ile canlı OHLCV çekme | DÜŞÜK |

---

---

## LoRA EĞİTİM DÜZLEMİ — Sıradaki Büyük Görev

> Araştırma: `~/Development/LoRAsetup/` — tüm detaylar orada
> Yöntem: Claude ile otomatik, aşamalı curriculum eğitimi

### Ana İlke (değişmez)
```
Önce sınıflandır → RAG'e koy → insan onayla → sonra LoRA.
Ters sıra = çöp kalıcılaşır.
```

### Verim Tablosu (araştırmadan)
| Yol | Uyum % |
|-----|--------|
| Kürasyon + sınıflandırma + RAG + geç LoRA | **93%** ← bu |
| GraphRAG + önkoşul grafı (Faz 2) | 87% |
| Ham web → doğrudan LoRA | 12% ← istenmeyen |

### Seviye Sistemi ("küçük→büyük çocuk")
```
Seviye 0 → "RSI nedir?" (temel tanım)           → LoRA Faz 1
Seviye 1 → "RSI nasıl hesaplanır?" (formül)     → LoRA Faz 1
Seviye 2 → "RSI 70'te ne yapmalı?" (yorum)      → LoRA Faz 2
Seviye 3 → "RSI+EMA nasıl backtest edilir?"     → LoRA Faz 3
Seviye 4 → araştırma/sentez (PASS alan zincir)  → LoRA Faz 4
```

### Faz 1'de Yapılacaklar (ilk açılışta)
1. `knowledge_cards` tablosuna ekle:
   `trust_level`, `review_status`, `lora_eligible`, `difficulty`, `stage`
2. Web UI'ya "Onay Bekleyen Notlar" listesi ekle
3. `training_examples` → sadece `lora_eligible=1` alanlar girebilir
4. `achilles_lora_v3` = ilk sınıflandırılmış, onaylı, seviyeli eğitim

### Eğitim Politikası (özet)
- Ham internet içeriği **asla** LoRA'ya girmez
- `review_status = approved` olmadan **girmez**
- Backtest FAIL olanlar **girmez**
- LoRA davranış/format öğretir; bilgi RAG'den gelir

### Referans Dosyalar
```
~/Development/LoRAsetup/
  README.md              ← verim tablosu + özet
  curriculum/levels.md   ← 5 seviye sistemi detayı
  curriculum/note-schema.yaml ← metadata şeması
  data-quality/classification.md ← sınıflandırma sistemi
  data-quality/routing-rules.md  ← nereye gider kararı
  methods/comparison.md  ← SFT/DPO/RAG/CPT karşılaştırma
  impl/phase-plan.md     ← Achilles faz planı
  impl/training-policy.md ← eğitim politikası kuralları
  deep-research-report.md ← ham araştırma raporu (kaynaklı)
```

---

## Yapılmayacaklar (sabit sınırlar)

Canlı emir/işlem yok · maliyetsiz backtest yok · look-ahead bias yok · `eval`/`exec` yok · test edilmeden "başarılı" denmez · sır/credential commit edilmez.
