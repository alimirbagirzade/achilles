# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-07 (gece geç) · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

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

### Mevcut durum (2026-06-07 gece geç)
- **407 test** geçiyor · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **Ollama:** qwen2.5-coder:3b + nomic-embed-text
- **19 makale** · 2497 chunk (11 alakasız arXiv silindi, 8 alakalı + 11 kullanıcı makalesi kaldı)
- **19 onaylı knowledge card**
- **LoRA adapter:** `models/adapters/achilles_lora_v1/` — 300 iter tamamlandı, train loss 0.012
- **Son commit:** `af5222d`

---

## ✅ Bu Seansta Tamamlananlar (2026-06-07 gece geç)

### RAGsetup Doğrulaması
`/Users/mirbagirzade/Development/RAGsetup/` içindeki 3 belge okundu ve projeyle karşılaştırıldı.
Belgelerde istenen tüm RAG/verification/mastery modülleri zaten projeye uygulanmış bulundu.
5 Claude skill dosyası `.claude/skills/` altında aktif.

### LoRA 300-iter Eğitimi Tamamlandı
- Adapter: `models/adapters/achilles_lora_v1/adapters.safetensors`
- Train loss: 4.48 → 0.012 · Val loss: 4.48 → 1.70
- 16 train / 3 valid örnek; pipeline uçtan uca doğrulandı.

### Makale Temizliği
- 11 alakasız arXiv makalesi silindi (SQLite + ChromaDB + filesystem)
- 19 makale · 2497 chunk kaldı

### Gate Fix'leri (önceki seans devamı, bu seansta onaylandı)
- `gates.py` `_card_text()` ve `gate_4_quality()` — boş cevap hatası giderildi
- `domain_classifier.py` — TRADING keyword seti genişletildi
- `dataset_builder.py` — `_build_answer()` multi-source okuma

### Web UI Bug Tespit
- **Trader Beyin → Formül Çıkar** butonu "Hata: Not Found" döndürüyor
- Sebep: PID 25825 eski server; route sonradan eklendi, process restart almadı
- Çözüm: `kill $(lsof -ti:8765) && uv run achilles web`

---

## 🔴 Sıradaki Görevler (öncelik sırasıyla)

### 1. Server Restart (2 dakika)
```bash
kill $(lsof -ti:8765) && uv run achilles web
```
"Trader Beyin → Formül Çıkar" test et.

### 2. Daha Fazla Makale + Kart → LoRA
```bash
uv run achilles arxiv "momentum volatility regime" --max 10
uv run achilles lora-audit && uv run achilles lora-dataset
```
Hedef: 50+ onaylı kart.

### 3. 500-iter LoRA Eğitimi
```bash
uv run achilles train --run --iters 500
```

### 4. Paper Mastery Testi
```bash
uv run achilles mastery-queue --enqueue-all && uv run achilles mastery-queue --run-all
```

### 5. DPO Hazırlığı (uzun vadeli)
500+ onaylı kart gerekiyor.

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

# LoRA Control Plane
uv run achilles lora-status       # pipeline genel durumu
uv run achilles lora-audit        # Gate 0-8 denetle
uv run achilles lora-dataset      # dataset oluştur (--dry-run varsayılan)
uv run achilles lora-registry     # adapter kayıtları listele

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
├── lora/         LoRA Control Plane — Gate 0-8 + adapter registry
├── training/     Dataset builder, LoRA, reward, DPO, unified
├── trading/      StrategyIR, backtest, indikatörler, evaluator
├── verification/ Citation, grounding, context sufficiency
├── evals/        Eval framework, metrics
├── agents/       OSS Learning Agent, research orchestrator
└── main.py       CLI (Typer)

.claude/agents/
├── lora-control-orchestrator.md
├── lora-dataset-auditor.md
├── lora-curriculum-classifier.md
├── lora-domain-verifier.md
├── lora-math-physics-statistics-verifier.md
├── lora-logic-philosophy-reviewer.md
├── lora-safety-secret-scanner.md   ← BLOCKER gate
├── lora-trainer-configurator.md
├── lora-evaluation-reviewer.md
└── lora-adapter-registry-manager.md
```

---

## 🧪 Test Komutu

```bash
uv run pytest                    # 407 test
uv run pytest -x -q              # hızlı, ilk hatada dur
make format && make lint && make typecheck && make test
```

---

## 🔑 Önemli Dosyalar

| Dosya | Ne içerir |
|-------|-----------|
| `TRAINING_ROADMAP.md` | Eğitim stratejisi + tamamlanan/bekleyen |
| `app/main.py` | Tüm CLI komutları |
| `app/lora/control_plane.py` | LoRA Gate 0-8 orchestrator |
| `app/lora/safety_scanner.py` | Blocker gate — secrets/PII/finansal tavsiye |
| `app/lora/adapter_registry.py` | Adapter yaşam döngüsü yönetimi |
| `app/learning/paper_mastery_agent.py` | Ana mastery pipeline |
| `app/training/unified_dataset.py` | Faz 2 dataset birleştirici |
| `configs/lora/lora_profiles.yaml` | 3 LoRA eğitim profili |
| `configs/eval/lora_eval_questions.yaml` | 50 eval sorusu |
| `.env.example` | Tüm ayar değişkenleri |
