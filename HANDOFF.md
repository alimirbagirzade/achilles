# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-07 · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

Yerel-öncelikli (local-first) AI **trading araştırma** sistemi (macOS Apple Silicon).
**Canlı bot değil, yatırım tavsiyesi değil.**

---

## 🚨 YENİ SEANS BAŞLANGICI — BUNU OKU

### Proje amacı
LLM'i "trader gibi düşünen" bir araştırma motoru yapmak:
1. Makalelerden formül ve kavramları hafızaya al
2. Bunları birleştirip daha önce denenmemiş indikatör/algoritma öner
3. Otomatik backtest et → sonuçtan öğren → LoRA eğitim verisi üret
4. 3B modeli test eder; gerçek çıktı için 120B kullanılacak

### Mevcut durum (2026-06-07)
- **338 test** geçiyor · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **Ollama aktif:** qwen2.5-coder:3b + nomic-embed-text · 7 PDF · 567 chunk
- **LoRA:** `achilles_lora_v2` eğitildi (300 iter, loss 0.028)

---

## ✅ Bu Seansta Tamamlananlar (2026-06-07)

### Paper Mastery Agent (YENİ)
- `app/learning/` — 8 modül (inspector, question_gen, rag_exam, scorer, status, report, agent)
- `app/memory/mastery_store.py` — 6 ORM tablo (learning_queue, tests, questions, answers, scores, history)
- 0–100 deterministik RAG kalite skoru (LLM gerekmez)
- Durum makinas: uploaded → learned (5 eşik)
- CLI: `achilles mastery-run / mastery-queue / mastery-score / mastery-report`

### arXiv Otomatik Senkronizasyon (Görev D ✅)
- `achilles arxiv-sync` — kayıtlı arXiv sorgularını otomatik yeniden çalıştırır
- `--dry-run`, `--force` seçenekleri

### Mastery → SFT Pipeline
- `app/training/mastery_sft_builder.py`
- `achilles mastery-to-sft` — mastery cevapları → LoRA eğitim JSONL

### Unified SFT Dataset (LoRA Faz 2)
- `app/training/unified_dataset.py` — 3 kaynağı birleştirir: kart + mastery + tool-use
- `achilles unified-dataset` — tek komutla faz 2 veri seti

### README Yeniden Yazıldı
- Emoji · ASCII mimari diyagramı · 30 saniyede başla · renk kodlu tablolar

---

## 🔴 Sıradaki Görevler (öncelik sırasıyla)

### 1. LoRA Faz 2 Eğitimi — Hemen Başlatılabilir
```bash
# Önce kartları onayla (06 ONAY sekmesi — 12 kart bekliyor)
# Sonra:
uv run achilles unified-dataset
uv run achilles train --run
```

### 2. Knowledge Card Onayı
- 12 kart onay bekliyor, 0 onaylı
- DPO için 500+ onaylı kart hedefi
- **06 ONAY** sekmesinden web UI'da yapılır

### 3. OSS Agent Phase 2
- `TRAINING_ROADMAP.md` → Bekleyen: `[ ] OSS Agent Phase 2 (llama.cpp + MLX backend)`
- llama.cpp ve MLX'i alternatif backend olarak bağlamak

### 4. DPO Hazırlığı
- Engel: 500+ onaylı kart → önce onay akışını işlet
- `DPODatasetBuilder` sonra devreye girer

---

## 📋 CLI Komut Referansı (tam liste)

```bash
# Sistem
uv run achilles init / status

# Makaleler
uv run achilles ingest / arxiv "sorgu" / arxiv-sync / papers

# Araştırma
uv run achilles ask "soru" / card <id> / extract-formulas / research "soru"

# Backtest
uv run achilles backtest <csv> / pine [strateji]

# Eğitim
uv run achilles dataset / chain-dataset / unified-dataset
uv run achilles mastery-to-sft
uv run achilles train / train --run
uv run achilles tool-use-train / tool-use-dataset
uv run achilles reward-analyze / auto-research

# Paper Mastery
uv run achilles mastery-run <paper_id>
uv run achilles mastery-queue [--enqueue-all|--run-next|--run-all]
uv run achilles mastery-score <paper_id>
uv run achilles mastery-report <paper_id>

# Web UI
uv run achilles-web   →  http://127.0.0.1:8765
```

---

## 🏗️ Mimari Özeti

```
app/
├── ingestion/    PDF okuma, metadata, chunklama, arXiv fetcher
├── memory/       SQLite + ChromaDB + embedding + MasteryStore
├── brain/        RAG, bilgi kartı, model routing
├── learning/     Paper Mastery Agent (0-100 skor)
├── training/     Dataset builder, LoRA, reward, DPO, unified
├── trading/      StrategyIR, backtest, indikatörler, evaluator
├── verification/ Citation, grounding, context sufficiency
├── evals/        Eval framework, metrics
├── agents/       OSS Learning Agent, research orchestrator
└── main.py       CLI (Typer) — ~1250 satır
```

---

## 🧪 Test Komutu

```bash
uv run pytest                    # 338 test, ~100 sn
uv run pytest -x -q              # hızlı, ilk hatada dur
make format && make lint && make typecheck && make test
```

---

## 🔑 Önemli Dosyalar

| Dosya | Ne içerir |
|-------|-----------|
| `TRAINING_ROADMAP.md` | Eğitim stratejisi + tamamlanan/bekleyen |
| `app/main.py` | Tüm CLI komutları |
| `app/learning/paper_mastery_agent.py` | Ana mastery pipeline |
| `app/training/unified_dataset.py` | Faz 2 dataset birleştirici |
| `.env.example` | Tüm ayar değişkenleri |
