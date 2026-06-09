# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-09 (öğleden sonra) · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

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

### Mevcut durum (2026-06-09 öğleden sonra)
- **405 test** geçiyor (2 deselected: ollama+slow) · ruff temiz · Python 3.12
- **8 sekme** web UI: Araştırma · Makaleler · Trader Beyin · Backtest · Eğitim · Onay · Değerlendirme · Sistem
- **Ollama:** qwen3:8b (Windows) / qwen2.5-coder:3b (macOS) + nomic-embed-text
- **19 makale** · 2497 chunk
- **19 onaylı knowledge card**
- **LoRA adapter:** `models/adapters/achilles_lora_v1/` — 300 iter tamamlandı, train loss 0.012
- **macOS:** LaunchAgent aktif (`com.achilles.web.plist`) — login'de otomatik başlar
- **Windows:** Task Scheduler (`AchillesWeb`) — login'de Ollama + web server birlikte başlar
- **Son commit:** `9861ab6`

---

## ✅ Bu Seansta Tamamlananlar (2026-06-09 öğleden sonra)

### Windows Kalıcı Kurulum — `install.ps1`
- Tek satır kurulum: `irm .../install.ps1 | iex` — her zaman `$USERPROFILE\achilles`'e kurar
- system32 dizininde çalıştırılsa bile doğru konuma yönlendirir
- Git otomatik kurulumu (winget), clone/update, setup, servis kaydı hepsi otomatik

### Windows Servis Kalıcılığı — `scripts/start-server.ps1`
- PowerShell kapandığında web server duruyordu → Task Scheduler ile çözüldü
- Script kendisini Task olarak kaydediyor; login'de `Start-OllamaIfNeeded` + `Start-AchillesServer`
- Ayrı log dosyaları: `logs/achilles-web.log` + `logs/achilles-web-err.log`
- `$pid` built-in çakışması → `$webPid` ile düzeltildi

### macOS LaunchAgent
- `~/Library/LaunchAgents/com.achilles.web.plist` oluşturuldu ve yüklendi
- `KeepAlive: true`, `RunAtLoad: true` — login'de otomatik başlar

### Test Fix
- `pyproject.toml` addopts: `-m 'not ollama and not slow'` eklendi
- qwen3:4b thinking mode 600s timeout'a neden oluyordu → artık varsayılan çalışmada atlanıyor
- 405 test geçiyor

### PEFT / PyTorch Install Fix
- `--index-url` PyPI'ı tamamen değiştiriyordu → `transformers` bulunamıyordu
- İki ayrı komuta bölündü: `torch` PyTorch index'ten, `transformers peft datasets accelerate` PyPI'dan

### `update.ps1` Encoding Fix
- em dash (`—`) ve curly apostrophe (`'`) → ASCII'ye dönüştürüldü
- Windows-1252 sistemlerde string terminator hatası artık yok

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
