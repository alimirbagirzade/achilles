# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-02 · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

Yerel-öncelikli (local-first) AI **trading araştırma** sistemi (macOS Apple Silicon).
**Canlı bot değil, yatırım tavsiyesi değil.** Akış:
`PDF → metin → chunk → SQLite + ChromaDB → RAG → knowledge card → training JSONL → MLX-LM LoRA hazırlık → backtest`

---

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
- [ ] **Python sürümü:** ortam **3.13** kuruldu; spec **3.12** diyor. Testler 3.13'te geçiyor; istenirse `uv python pin 3.12 && uv sync` ile sabitlenebilir.
- [ ] **`uv.lock` `.gitignore`'da** — uygulamalarda tekrarlanabilirlik için lock dosyasını commit etmek tercih edilir; gözden geçir.
- [ ] **Gerçek PDF ile ingestion** test edilmedi (henüz `data/papers/raw_pdf/` boş). Bir akademik PDF koyup `achilles ingest` → `ask` akışını uçtan uca dene.
- [ ] **RAG / knowledge card / dataset / eval** komutları Ollama'sız çalışmadı (kod hazır, model bekliyor).
- [ ] **MLX-LM LoRA**: `train` komutu varsayılan dry-run; gerçek eğitim `--run` ile (Apple Silicon + `uv sync --extra train`).

- [x] **Gerçek OHLCV backtest YAPILDI** — BTC-USD günlük (Yahoo Finance, 1827 bar / 5 yıl; Binance+CryptoCompare+Kraken Türkiye'de bloklu, Stooq apikey istiyor). EMA/RSI: getiri +%52 / Sharpe 4.0 / DD -%52 ama evaluator **FAIL** (`bt_e22fbfde4b`): örneklem-dışı negatif (overfit) + az işlem. Gerçek veride disiplin doğrulandı. CSV: `data/market/raw/BTCUSD_1d.csv` (gitignored).
- [x] **Güvenlikli web arayüzü eklendi** (`app/web/`) — FastAPI ince katman: status/papers/upload/ingest/ask/card/backtest + `/api/docs`; `security.py` (token auth `secrets.compare_digest`, IP rate-limit, CSP+güvenlik başlıkları, PDF magic-byte+boyut doğrulama, path-traversal koruması); terminal-estetik static UI (CSP-uyumlu); `SECURITY.md`. `pip install -e ".[web]"` → `achilles-web` (yalnız localhost). Denetim: 2 "ares" regresyonu (`achilles_lora_v1`, `achilles_test`) düzeltildi, `_consteq`→`secrets.compare_digest`, README canlı-durum+github+model bölümleri geri getirildi. **43 offline test geçiyor, ruff+mypy temiz.**

- [x] **8GB'da güvenilir bilgi-kartı ÇÖZÜLDÜ** — `knowledge_card_builder`: Ollama `format:"json"` (geçerli JSON garanti) + kısa girdi (14000→6000 krk) + `num_predict` cap + boşsa kısa retry + esnek `_extract_json` (akıllı tırnak/sondaki virgül onarımı); `local_llm.generate` artık `fmt`/`timeout` alıyor. 3b ile gerçek makaleden dolu+doğru kart (methods: polyhedral lemma, James-Stein shrinkage…) ~56s. Card→TrainingDataBuilder→dataset artık otomatik (elle seed gerekmez). 49 offline test geçiyor.

## Yapılmayacaklar (sabit sınırlar)

Canlı emir/işlem yok · maliyetsiz backtest yok · look-ahead bias yok · `eval`/`exec` yok · test edilmeden "başarılı" denmez · sır/credential commit edilmez.
