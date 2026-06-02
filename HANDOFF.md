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
4. **Ollama kuruldu** — `brew install ollama`, `brew services start ollama` (servis ayakta, `http://localhost:11434`). Modeller arka planda çekiliyor: `nomic-embed-text` + `qwen2.5-coder:7b`.
5. **Testler** — `uv run pytest` → **21/21 geçti** (çevrimdışı, fake embedding).
6. **Uçtan uca duman testi** — `achilles init` + `gen-data` + `backtest` çalıştı; EMA/RSI stratejisi metrik üretti, evaluator **FAIL** yargısı verdi (out-of-sample + min işlem şartı), SQLite'a `bt_…` olarak kaydedildi.
7. **GitHub'a push edildi** — `alimirbagirzade/achilles` `main`: `Initial commit → feat: Achilles Trader AI MVP skeleton` (temiz lineer tarih, force yok).

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

- [ ] **Model indirme** bitince `uv run achilles status` ile Ollama erişimini ve embedding modunun `ollama` olduğunu doğrula (artık `fake` değil).
- [ ] **Python sürümü:** ortam **3.13** kuruldu; spec **3.12** diyor. Testler 3.13'te geçiyor; istenirse `uv python pin 3.12 && uv sync` ile sabitlenebilir.
- [ ] **`uv.lock` `.gitignore`'da** — uygulamalarda tekrarlanabilirlik için lock dosyasını commit etmek tercih edilir; gözden geçir.
- [ ] **Gerçek PDF ile ingestion** test edilmedi (henüz `data/papers/raw_pdf/` boş). Bir akademik PDF koyup `achilles ingest` → `ask` akışını uçtan uca dene.
- [ ] **RAG / knowledge card / dataset / eval** komutları Ollama'sız çalışmadı (kod hazır, model bekliyor).
- [ ] **MLX-LM LoRA**: `train` komutu varsayılan dry-run; gerçek eğitim `--run` ile (Apple Silicon + `uv sync --extra train`).

## Yapılmayacaklar (sabit sınırlar)

Canlı emir/işlem yok · maliyetsiz backtest yok · look-ahead bias yok · `eval`/`exec` yok · test edilmeden "başarılı" denmez · sır/credential commit edilmez.
