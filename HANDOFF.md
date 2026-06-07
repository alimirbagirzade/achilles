# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-07 (gece) · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

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

### Mevcut durum (2026-06-07 gece)
- **407 test** geçiyor · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **Ollama:** qwen2.5-coder:3b + nomic-embed-text · 12 PDF · ~2000 chunk
- **Son commit:** `1adcd6b` — tam sistem denetimi + 5 kritik bug düzeltildi

---

## ✅ Bu Seansta Tamamlananlar (2026-06-07 gece)

### LoRA Training Control Plane (commit `1d8688a`)
- `app/lora/` — 9 modül: curriculum, domain_classifier, quality_filter, math_verifier,
  safety_scanner, dataset_builder, dataset_splitter, adapter_registry, control_plane, gates
- Gate 0–8 pipeline: source → schema → curriculum → domain → quality → math → logic → safety[BLOCKER] → split
- **Safety Gate (Gate 7) BLOCKER:** API key / finansal tavsiye / PII → tüm batch reddedilir
- Adapter registry: candidate → smoke_passed → eval_passed → approved → production
  (production'a geçiş `user_approved=True` zorunlu)
- 10 Claude agent: `.claude/agents/lora-*.md`
- 3 LoRA config profili: `configs/lora/lora_profiles.yaml`
- 50 eval sorusu: `configs/eval/lora_eval_questions.yaml`
- 4 yeni CLI komutu: `lora-status`, `lora-audit`, `lora-dataset`, `lora-registry`

### Tam Sistem Denetimi (commit `1adcd6b`)
- `tool_use_trainer.py` — 5 kritik runtime bug düzeltildi (mock testlerin arkasında gizliydi):
  - `eval_strategy(bt)` → `evaluate(df, ir)` yanlış imza
  - `bt.metrics.get()` → `bt.metrics.to_dict().get()` dataclass erişimi
  - `synthesize()` None dönüşü kontrolsüz → AttributeError
  - `reflect()` eksik argümanlar
  - `sharpe_ratio` → `sharpe` yanlış metrik anahtarı
- `mastery_store.py` — `sqlite_db` → `sqlite_file` AttributeError
- `arxiv_fetcher.py` — ağ/PDF hataları artık `FetchResult(skipped=True, error=...)` dönüyor;
  UI "1 atlandı/hata" gösterebilir, log'a yazılıyor (PDF yükleme bug'ının kök nedeni)
- 33+ dosyada ruff lint temizlendi (I001, F541, SIM110 vb.)

---

## 🔴 Sıradaki Görevler (öncelik sırasıyla)

### 1. Knowledge Card Onayı + LoRA Pipeline Besleme
- 12 kart onay bekliyor (web UI → **06 ONAY** sekmesi)
- Onaydan sonra:
```bash
uv run achilles lora-audit        # Gate durumu kontrol
uv run achilles unified-dataset   # veri seti oluştur
uv run achilles train --run       # gerçek eğitim
```

### 2. LoRA Pipeline Aktivasyonu
- Şu an `lora_eligible=1` kart yok — mastery onayından geçmiş kart gerekiyor
- Pipeline hazır, veri bekliyor

### 3. Bilgi Kartı Onay Akışı (ertelendi)
- Kullanıcı "ona döneriz" dedi — bu seansta atlandı

### 4. OSS Agent Phase 2
- llama.cpp ve MLX'i alternatif backend olarak bağlamak
- `TRAINING_ROADMAP.md` → `[ ] OSS Agent Phase 2`

### 5. DPO Hazırlığı
- Engel: 500+ onaylı kart → önce onay akışını işlet

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
