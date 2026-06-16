# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-16 · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_

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

### Mevcut durum (2026-06-16 SON) — 🧠 ANLAMA DOĞRULAMA SİSTEMİ İNŞA EDİLDİ ✅

> Bu seans (06-16 akşam/gece): RAG vs LoRA netleşti + **"Anlama Doğrulama" merdiveni —
> _anlama yüzdeyle değil SINAVLA kanıtlanır_ — hem belgelendi hem KOD olarak inşa edildi.**
> Çekirdek fikir: "anladı" = bilgiyi DOĞRU KULLANIP ondan TEST EDİLEBİLİR yeni bir şey ÜRETEBİLDİ.

**İNŞA EDİLEN (hepsi push'lu · ~60 sınav testi + tüm offline paket yeşil · ruff+mypy temiz):**
- `app/verification/exams/` paketi:
  - `safe_eval.py` (whitelist AST — eval/exec YOK, Kural 5), `reference_oracle.py`, `registry.py`
  - `l3_application.py` — **L3:** formül + tutulan sayı → model hesapla → `np.allclose` referansla
  - `l4_counterfactual.py` — **L4:** parametre yön değişimi KODDAN türetilir, model puanlanır
  - `l5_composition.py` — **L5:** yeni-formül 3 kapı (math + novelty + maliyet-dahil backtest/OOS) → aday/red
  - `understanding_score.py` — objektif geçme-oranı (skipped/no_data paydaya GİRMEZ) +
    `rag_answers_to_results` (mevcut RAG sınavını Taban/L1/L2 olarak merdivene bağlar)
- **CLI:** `achilles exam-l3 / exam-l4 / exam-l5 / understanding-score`
- **ENTROPY göstergesi** (`indicators.py` + registry) — yönsel ikili Shannon entropisi [0,1],
  look-ahead'siz; entropi vizyonunun ilk indikatörü, L5 Markov+entropi yapı taşı.
- Belgeler: README "🧠 Achilles okuduğunu *anladı* mı?" + `docs/PROTOKOL_RAG_LORA_ZINCIR.md`
  "ANA FİKİR" + `docs/examples/raft_discipline_seed.jsonl` (RAFT disiplin seed örneği).
- Hafıza: `memory/anlama-dogrulama-ana-fikir.md`, `memory/arastirma-makale-kaynagi.md`.
- **Makaleler indirildi** → `C:\Users\sevinc\Desktop\RAG Kaynak\Gerekli kaynaklar`:
  RAFT(2403.10131), HMM Intraday(2006.08307), Transfer Entropy(2507.09554),
  Entropy Analysis(1807.09423) + `00_NEDEN_ONEMLI_oku_once.md`. **Kullanıcı inceleyip web'den
  RAG'a yükleyecek.** Bu indirme LOOP — yeni makaleler aynı klasöre eklenecek.

**BEKLEYEN BACKLOG (yeni seans buradan devam — kullanıcı: "loop olarak çözene kadar"):**
1. ✅ **L5 → synthesis_engine bağlandı** (`18cabd4`) — orchestrator her iterasyonda L5
   CompositionGate koşar (math+novelty+backtest); sonuç IterationResult + session + web API.
2. **Registry'yi genişlet** — ✅ permütasyon entropi (Bandt-Pompe, `PERMENTROPY`) eklendi
   (indicators + exams registry + L5 _REGISTRY + query_expander); KALAN: daha çok Markov/entropi
   göstergesi (ör. transfer entropi, rejim/HMM tabanlı) + yeni makale indir.
3. ✅ **Web objektif anlama skoru** — kaba "anlama %" dürüstçe "öz-değ. %" diye yeniden
   adlandırıldı; header'a tıklanabilir "obj. anlama" rozeti + `GET /api/understanding-score`
   (L3/L4 sınav geçme oranı; LLM yoksa insufficient_data). Ortak `score_indicator_exams`
   helper (CLI + web). KALAN: web'de L5 kompozisyon sonucunu da göstermek (opsiyonel).
4. **RAFT reçetesini düzelt** (seed'i yüzlerce örneğe ölçekle) → SONRA eğit (körlemesine 47h retrain YOK).
5. Eğitim: reçete düzeltilince → eğit → eval → koşullu terfi → bug-fix loop.

**🎯 EĞİTİM LOOP KARARI (2026-06-16, kullanıcı):** Donanım = **Bulut GPU (Kaggle T4×2)**
(önceki bulut-reddi geri alındı; ~30 dk/koşu → loop fizibıl). Otonomi = **tam otonom loop**
(reçete→dataset→eğit→eval→koşullu terfi→düzelt→tekrar; sonuçlar raporlanır).
**Sıralama:** önce dokümanlar → #4 reçete → #3 dataset'i OFFLINE sınavdan geçir (L3/L4/L5 +
understanding-score, eğitMEDEN kalite kanıtı) → Kaggle eğit → eval → koşullu terfi.
**Caveat:** Kaggle "Run All" manuel (headless değil) — çevresi otomatik, sadece o tık kullanıcıda.

**Eğitim kararı:** detached tek-tık eğitim TEKNİK olarak hazır AMA başlatma — önce reçete düzelt
(v5 aynı sebepten battı). Kullanıcı onayı: **"önce bitir, sonra eğit."**

**Komut notu:** testleri `--basetemp=.pytest_tmp` ile çalıştır (stale `pytest-of-sevinc` izin
sorunu = WinError 5). Push döngüsü: `git fetch + rebase origin/main` sonra push (eşzamanlı makine).

**Son commit:** `d54ab68` (ENTROPY). Bu seans zinciri: `5820ab5 → 1c5f349 → da98e6e →
135cc66`(L3)`→ 8c721c9`(L4)`→ 65feac1`(L5)`→ 0ec5854`(CLI)`→ d0e139f`(L1/L2)`→ d54ab68`(ENTROPY).

**Otonom nöbet:** bu seansta ScheduleWakeup loop aktifti (sağlık + backlog ilerletme + makale indirme).
Yeni seansta kendiliğinden devam ETMEZ — istenirse `/loop` ile yeniden kur.

---

### Önceki durum (2026-06-16 erken) — LOKAL EĞİTİM BİTTİ, ADAPTER REJECT

> Kullanıcı Kaggle/bulut REDDETTİ → eğitim **lokal CPU**'da yapıldı (kendi imkanlarıyla;
> ileride uzaktan kiralık CPU). Bu seans gece+gündüz otonom yürüdü (eğitim nöbeti + post-training).

- **🔴 achilles_lora_v5 EĞİTİLDİ ama REJECT:** lokal CPU PEFT, 1203 adım, **46.75 saat**,
  loss 2.66→0.60. Adapter: `models/adapters/achilles_lora_v5/`. **AMA base-vs-adapter
  karşılaştırması (gerçek PEFT yükleme) gösterdi: adapter base'den DAHA KÖTÜ** — tekrar
  döngüsü (overfit), "pasaja göre" uydurma, maliyetsiz rakam uydurma. **TERFİ EDİLMEDİ**
  (Kural 2). RAG hâlâ base modelle çalışıyor. Detay: `memory/v5-adapter-regression.md`,
  `reports/evals/adapter_smoke_compare.json`.
- **KÖK SEBEP:** sentetik-QA recipe ("pasaja göre cevapla" + adversarial disiplin örneği yok).
- **🔧 EVAL HARNESS FIX (push'lu):** `app/training/adapter_eval.py` + `achilles lora-eval
  <adapter> --eval-set <jsonl> --n <k>` — adapter'ı transformers/PEFT ile GERÇEKTEN yükler,
  base ile kıyaslar (eski `ModelEvaluator` base Ollama'yı ölçüyordu, adapter'ı YÜKLEMİYORDU).
  UYARI: red-flag sezgisi negasyon-kör → otomatik verdict güvenilmez; LLM-judge gerekli.
- **▶️ ÖĞRENME DÖNGÜSÜ ÇALIŞIYOR** (2026-06-16 restart, 72h, `continuous-learning.sh`):
  48 kartsız makaleyi işliyor (kart/anlama/synth-qa). **AYRI OS SÜRECİ — yeni seansta da sürer.**
  `keep_alive=5m` (eğitim bitti). Yeni LoRA eğitimi başlatınca `.env: ACHILLES_OLLAMA_KEEP_ALIVE=0` yap.
- **Veri:** `data/lora_sft/lora_sft.jsonl` ~1266 örnek · `lora-split` → `data/training/jsonl/train.jsonl`
  (1203 train+63 valid). **DİKKAT:** `DatasetBuilder.build()` train.jsonl'i ezer (clobber) —
  `detached_launch.launch()` her başlatmada lora_sft'den yeniden böler. Detay: `memory/training-data-pipeline.md`.
- **RAG:** Ollama qwen3:4b + nomic-embed-text · **109 makale / 11341 parça** · kart kapsamı %56 (artıyor).
- **Bu seansta push'lananlar:** detached tek-tık eğitim + "EĞİTİME HAZIR" rozeti · CVD-safe renkler ·
  web bug avı fix'leri (XSS/auth/hata yönetimi) · çekirdek denetim fix'leri (backtester metrik:
  Sortino+trade-bazlı win-rate/PF, RAG retrieval) · güvenlik sertleştirme (TrustedHost/HSTS/pip-audit/
  gitleaks) · `update.sh` (Mac/Linux) + `update.ps1` sağlamlaştırma · Ollama `keep_alive` OOM fix.
- **🔒 BEKLEYEN (kullanıcı yönü):** (1) eğitim-veri reçetesini düzelt — adversarial disiplin
  örnekleri ekle, "pasaja göre" sızıntısını gider — SONRA yeniden eğit (körlemesine 47h retrain YOK).
  (2) eval judge'ı iyileştir (negasyon-farkında / LLM-judge).
- **Base model:** `Qwen/Qwen3-4B-Instruct-2507` (Ollama qwen3:4b ile birebir).
- **754 cybersecurity skill** `~/.claude/skills/`'e (global) kuruldu (kullanıcı isteği, alimirbagirzade
  fork) — savunma+ofansif spektrum; her oturuma yüklenir (context maliyeti); plugin'e çevrilebilir.
- **Otonom nöbet (ScheduleWakeup loop):** yeni seansta KENDİLİĞİNDEN devam ETMEZ — istenirse
  `/loop` ile yeniden kur. Öğrenme döngüsü (OS süreci) bağımsız sürer.
- **(O günkü commit:** `9115fd5` — güncel durum yukarıdaki "SON" bloğunda, `d54ab68`.)

---

## ✅ Bu Seansta Tamamlananlar (2026-06-13 → 06-14) — BÜYÜK PİVOT

**Tema:** "RAG eğitiminin sağlamlığını araştır, yeniden yaz, push." → 4-ajan
araştırma → dürüst teşhis → RAG-first robust + aşamalı (lokal-veri → bulut-GPU) eğitim.

### Commit'ler (sırayla)
- `2422c5d` RAG: Reranker'ı canlı yola bağla (over-fetch + rerank) — A2
- `ab1220b` Sentetik QA motoru (`synthetic_qa_builder.py`) + sürekli CPU-eğitimi durdur
- `ca39070` Aşamalı eğitim protokolü (Stage 1/2 doc + skill + `cloud_notebook.py`)
- `5d31657` **fix:** 4B base-model 1.5B hardcode (şema/sunucu/UI/CLI 5 katman)
- `96e55b7` RAG: hybrid BM25 (A3) + prompt birleştirme (A4)
- `ae2b998` RAG: cross-encoder reranker (A8, opt-in)
- `ec2fd4c` RAG: contextual retrieval (P2, opt-in + `reindex-contextual`)
- `4212b30` LoRA: near-duplicate dedup (A7)
- `85d61de` LoRA: `synth-qa-bulk` (checkpoint'li bulk üretim)
- `383860c` fix: upload limiti 100 MB tutarlı
- `e24cd80` feat: paper-düzeyi dedup (başlık-normalize)
- `61df8dd` fix: gece döngüsü `lora-dataset` clobber'ı kaldır (Stage 2 dataset korunsun)

### Önemli bilgiler
- **Gerçek 4B eğitimi CPU'da YAPILMAZ** (haftalar + overfit). Yalnız bulut-GPU.
- Sentetik veri synthetic_qa.jsonl'de **birikir**; birleşik Stage 2 dataset'i
  `lora-cloud-prep` üretir (lora_sft.jsonl). Döngü artık bu dosyayı ezmiyor.
- `.env`: `ACHILLES_MAX_UPLOAD_MB=100` · Fable 5 erişimi YOK (hesap/plan).

### ▶️ SABAH SIRADAKİ İŞ: Stage 2 gerçek eğitim (~30 dk, bulut-GPU)
1. `huggingface-cli upload <kullanıcı>/achilles-lora-sft data/lora_sft/lora_sft.jsonl lora_sft.jsonl --repo-type dataset`
2. HF READ token → Kaggle Secrets (ad: `HF_TOKEN`)
3. Kaggle T4×2 + Internet ON → `notebooks/achilles_lora_stage2.ipynb` → `HF_DATASET_REPO`'ya kullanıcı adı → Run All
4. İndir GGUF + Modelfile → `ollama create achilles -f Modelfile`
5. Eval: `$env:ACHILLES_LLM_MODEL='achilles'; uv run achilles evaluate evals/discipline_core.jsonl`
Detay: `docs/PROTOKOL_BULUT_EGITIM.md` · skill: `/bulut-egitim-protokolu`

### Opsiyonel (kullanıcı tetikler)
- `reindex-contextual` → P2 aktive (korpusu yeniden-embed, sonra `.env` `ACHILLES_RAG_CONTEXTUAL_EMBED=true`)
- Cross-encoder: `uv pip install sentence-transformers` + `ACHILLES_RAG_CROSS_ENCODER=true`

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

### 4. Genel Sağlık Kontrolü + Bug Fix'leri — `1aef7eb` `572b605` `47ffd4c`

**Tespit edilen ve düzeltilen hatalar:**

| Dosya | Hata | Düzeltme |
|-------|------|----------|
| `server.py:17` | `HTTPException` import eksik → runtime `NameError` | Import eklendi |
| `server.py:455` | `PaperComprehension.total` yok → 500 error | → `total_score` |
| `comprehension_scorer.py:47` | `list_knowledge_cards` yok | → `get_latest_knowledge_card` |
| `comprehension_scorer.py:117` | `llm.is_available()` yok | → `llm.available()` |
| `formula_extractor.py` | `available()` guard eksik → test isolation bug | LLM çağrısından önce `available()` kontrolü |
| `comprehension_scorer.py` | unused `json` import | ruff auto-fix |
| `sqlite_store.py` | quoted type annotations | ruff auto-fix |

**Sonuç:** 405 test PASS · ruff CLEAN · mypy CLEAN (app/ üzerinde)

### Önceki Seans Detayları (2026-06-11 akşam)

#### Batch Comprehension Skor Butonu
- `GET /api/papers/comprehension/all` — tüm skorları tek çağrıda döner (N+1 fix)
- `POST /api/papers/comprehension/batch` — kartı olan tüm makaleler için skor hesapla
- Frontend: `🧪 TÜM SKORLARI HESAPLA` butonu, client-side cache reset

#### Math-Aware Chunker + Formül Pipeline
- `app/ingestion/chunker.py` → `_MATH_BLOCK_RE` ile `$...$` / `\[...\]` / `\begin{equation}` bloklarını korur
- `app/memory/paper_indexer.py` → ingestion sonrası otomatik: formül çıkarma → kavram grafiği → çapraz sentez
- `app/research/cross_paper_synthesizer.py` → 8 kategori kombinasyonu, SHA256 idempotency, 8 fallback template

#### 27 Makale Yeniden İndekslendi
- 4194 chunk · 142 formül (7 kategori) · 19 çapraz sentez örneği · 121 toplam eğitim örneği
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

## 🏛️ Mimari Kararlar (değişmez)

- **API key entegrasyonu planlanmıyor.** OpenAI/Anthropic/Google key desteği kodda mevcut ama aktif olarak geliştirilmeyecek. Sistem tamamen lokal-öncelikli.
- **Uzun vadeli hedef: lokal 120B OSS model.** (ör. Llama 3.1 405B, Qwen2.5 72B+) Ollama üzerinden çalışacak. Geçiş için tek değişiklik: `.env` dosyasında `ACHILLES_LLM_MODEL` ve `ACHILLES_OLLAMA_HOST`. Kod değişikliği gerekmez.
- **Ollama host:** `127.0.0.1:11434` (localhost değil — Windows IPv6 sorunundan dolayı).

---

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
