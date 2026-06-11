# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-11 (akşam) · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

Yerel-öncelikli (local-first) AI **trading araştırma** sistemi (macOS Apple Silicon + Windows).
**Canlı bot değil, yatırım tavsiyesi değil.**

---

## 🚨 YENİ SEANS BAŞLANGICI — BUNU OKU

### Proje amacı
LLM'i "trader gibi düşünen" bir araştırma motoru yapmak:
1. Makalelerden formül ve kavramları hafızaya al
2. Bunları birleştirip daha önce denenmemiş indikatör/algoritma öner
3. Otomatik backtest et → sonuçtan öğren → LoRA eğitim verisi üret
4. 3B modeli test eder; gerçek çıktı için 120B kullanılacak

### Mevcut durum (2026-06-11 akşam)
- **405 test** geçiyor (2 deselected: ollama+slow) · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **Ollama:** qwen3:8b (Windows) / qwen2.5-coder:3b (macOS) + nomic-embed-text
- **26 onaylı knowledge card** (8 içeriksiz kart reject edildi)
- **103 training example** — `training_examples` tablosunda, 83 train + 14 valid
- **LoRA adapter'lar:** `models/adapters/achilles_lora_v1..v4` — macOS'ta eğitildi
- **Auto-LoRA pipeline:** `ready_to_train` — 9/9 gate PASS, Windows'ta eğitime hazır
- **macOS:** LaunchAgent aktif (`com.achilles.web.plist`) — login'de otomatik başlar
- **Windows:** Task Scheduler (`AchillesWeb`) — login'de Ollama + web server birlikte başlar
- **Son commit:** `1f5ca50`

---

## ✅ Bu Seansta Tamamlananlar (2026-06-11)

### 1. LoRA Gate Pipeline Düzeltmesi — `cf66c63`
**Sorun:** Windows'ta yüklenen 8 knowledge card, içeriksiz (title=None, main_claim boş) halde onaylanmıştı.
Bu kartlar Gate 0/3/4'ü blokluyordu → auto-LoRA pipeline gate_failed durumunda kalıyordu.

**Çözüm:**
- `app/lora/control_plane.py` → `_run_card_gates`: gate'lerden önce `_card_text()==""` kartları filtrele
- DB'deki 8 içeriksiz kart `rejected` yapıldı (`lora_eligible=0`)
- `storage/auto_lora_state.json` → `ready_to_train`'e getirildi
- **Sonuç:** 9/9 gate PASS, 26 temiz kart pipeline'da

### 2. Windows PEFT Backend Düzeltmesi — `c2205d2`
**Sorun:** `auto_pipeline.start_training()` her platformda `python -m mlx_lm.lora` çalıştırıyordu.
MLX macOS'a özel olduğundan Windows'ta eğitim anında çöküyordu.

**Çözüm:** `app/lora/auto_pipeline.py` → `detect_lora_backend()` ile platform tespiti:
- macOS ARM64 → `mlx_lm.lora` (değişiklik yok)
- Windows/Linux → `app.training.peft_lora_train --run`

**Windows eğitim ön koşulu:**
```
uv pip install torch transformers peft datasets accelerate
```

### 3. Eğitim UI — Açıklamalar + Auto-LoRA Konfig — `1f5ca50`
- Her eğitim ayarına (model, adapter, iterasyon, batch, katman) Türkçe açıklama eklendi
- Auto-LoRA bölümüne kendi adapter adı + iterasyon inputları eklendi (`#autoLoraAdapterName`, `#autoLoraIters`)
- JS validation: boş ad ve 50–5000 dışı iter engellendi
- CSS: `.setting-group`, `.setting-desc` sınıfları eklendi

---

## 📁 Kritik Dosyalar

| Dosya | Görev |
|-------|-------|
| `app/lora/auto_pipeline.py` | Otomatik pipeline + platform tespiti (MLX vs PEFT) |
| `app/lora/control_plane.py` | Gate 0-8 orkestrasyonu, boş kart filtresi |
| `app/lora/gates.py` | 9 kalite kapısı (source/schema/domain/quality/math/…) |
| `app/training/peft_lora_train.py` | Windows/Linux PEFT eğitimi (CLI: `--run`) |
| `app/training/mlx_lora_train.py` | macOS MLX eğitimi |
| `app/training/backend.py` | Platform tespiti: `detect_lora_backend()` |
| `app/training/dataset_builder.py` | `training_examples` tablosundan JSONL üretir |
| `app/memory/sqlite_store.py` | Ana DB (kartlar, örnekler, adapter'lar) |
| `storage/auto_lora_state.json` | Pipeline anlık durumu (stage, gate_summary, …) |

## ⚠️ Bilinen Sınırlamalar / Dikkat Noktaları

- **Dataset builder vs LoRA dataset builder:** `app/training/dataset_builder.py` → `training_examples` tablosunu okur. `app/lora/dataset_builder.py` → `knowledge_cards` tablosunu okur. İkisi farklı sistem.
- **Windows'ta CPU eğitimi yavaş** (~2-4 saat). Hızlı eğitim için Eğitim sekmesindeki "Colab Notebook İndir" butonunu kullan.
- **Gate tekrar çalıştırılırsa** `auto_lora_state.json` `checking` → `ready_to_train` veya `gate_failed`'a geçer.
- **İçeriksiz kart oluşursa:** ingestion sırasında LLM cevabı boş gelirse kart DB'ye boş kaydedilir. Gate pipeline bunu filtreler ama kart DB'de `approved` olarak kalabilir — `control_plane` bunu tolere eder.

## 🔧 Sonraki Olası Görevler

- [ ] Windows'ta PEFT eğitim progress'ini web UI'da SSE ile yayınla
- [ ] Boş kart oluşmasını önlemek için ingestion'a `title` validasyonu ekle
- [ ] Gate özet raporunu web UI'da göster (hangi kartlar reddedildi, neden)
- [ ] Eğitim süresi tahmini: iterasyon × batch × donanım → dakika bilgisi

---

## 🗂 Önceki Seanslar (referans)

### 2026-06-09 (öğleden sonra)
- Windows kalıcı kurulum (`install.ps1`), Task Scheduler entegrasyonu
- macOS LaunchAgent (`com.achilles.web.plist`)
- PEFT/PyTorch install fix, `update.ps1` encoding düzeltmesi
- Qwen3 thinking-mode response fix, test suite (405 test)

### 2026-06-10
- PDF yükleme event loop blocking fix (BackgroundTasks)
- Makale başlığı fallback (dosya adından)
- UI CSS fix: Risk modal, Pine Script, Backtest grid, Training light mode

---

## 🔴 Sıradaki Görevler (öncelik sırasıyla)

### 1. Windows'ta Son Güncellemeyi Al (5 dakika)
```powershell
cd "$env:USERPROFILE\achilles"
git pull
.\scripts\start-server.ps1 -Install
.\scripts\start-server.ps1 -Status
```
Ollama + web server'ın birlikte başladığını doğrula.

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
