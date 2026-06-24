# HANDOFF — Achilles Trader AI

_Son güncelleme: 2026-06-24 · Branch: `main` · Repo: https://github.com/alimirbagirzade/achilles_
_Açık PR: yok — RLM iş PR'ları #43/44/45/46 hepsi MERGED._

Yerel-öncelikli (local-first) AI **trading araştırma** sistemi (macOS Apple Silicon + Windows).
**Canlı bot değil, yatırım tavsiyesi değil.**

---

## 🚨 YENİ SEANS BAŞLANGICI — BUNU OKU

### ⛔ KALICI KISIT (2026-06-24) — API ASLA KULLANILMAZ
Kullanıcı direktifi: **pay-per-token API hiçbir zaman kullanılmayacak.** Çalışma-zamanı LLM
hattı YEREL (Ollama / native RLM Controller + RAG). Geliştirme/AI yardımı aylık **abonelikli**
araçlarla (Claude Code, Codex vb.) — API anahtarı/faturalı endpoint DEĞİL. Sonuç: alexzhang
RLM `backend="anthropic"` (API) yolu OPSİYONEL + KAPALI kalır (`rlm_alexzhang_enabled=False`,
`provider=native`); varsayılan/zorunlu YAPILMAZ. Yeni özelliklerde bulut API'sini varsayılan
bağımlılık yapma → opt-in + native fallback şart. Bkz memory [[no-api-local-subscription-only]].

### 🆕 EN SON İŞ (2026-06-24) — alexzhang13/rlm OPSİYONEL motor-adapter (4 PR MERGED)
`Desktop\RAG Kaynak\RLM\achilles_alexzhang_rlm_claude_integration_prompt` (1051 satır) uçtan uca
entegre edildi — additive, **native VARSAYILAN korundu**, OpenAI default değil, RAG/Mastery/LoRA
DOKUNULMADI. Hepsi izole-worktree→PR→auto-merge (paylaşılan tree çakışması yok).
- **PR #43** entegrasyon: `app/rlm/adapters/` (base/native/alexzhang/security), `engine_config`,
  `tool_registry`+`safe_tools` (deny-by-default allowlist), `answer_pipeline`; CLI `rlm-engine`/
  `rlm-test-adapter`. rlm-security-reviewer KENDİ kodumda 4 fix buldu (HIGH ipython-bypass→allow-list).
  GOTCHA: `.gitignore` `adapters/` (LoRA) → `app/rlm/adapters/` kaynağını sessizce yutuyordu → `*.py` negasyonu.
- **PR #44** wiring: `rlm-answer --engine`, web `/api/rlm/config`+`/test-adapter`, `rlm-tools` CLI
  (ölü-kod allowlist'i canlı bağladı), alexzhang run-log, source `support_level`.
- **PR #45** lock: pyproject `rlm` extra ↔ `uv.lock` drift kapandı (openai yalnız opsiyonel-transitive).
- **PR #46** Level 3 + observability: trajektori logging (rlm_store+JSON, `/runs/{id}/trajectory`,
  `rlm-trajectory`), docker preflight (CLI+daemon probe), web motor dashboard paneli (preview-verified),
  GERÇEK `rlms` kurulum doğrulaması. Bug-avı 5 fix (orphan-run→failed, determinizm temperature=0,
  daemon-probe, relevance clamp, traj 50MB+OOM).
- **Doğrulama:** her PR ruff+format+mypy+pytest yeşil (main CI success); dashboard preview_eval ile.
- **AÇIK KARAR (kullanıcı):** gerçek Claude-destekli alexzhang inference API+key+docker ister → API
  YOK direktifi gereği KOŞTURULMAZ; sistem native (Ollama) ile tam çalışır. Memory [[rlm-alexzhang-adapter-2026-06-24]].
- **NOT:** `rlms` paketi dev `.venv`'de kurulu kaldı (#46 doğrulaması; eşzamanlı achilles-web.exe
  `uv sync`'i kilitledi). Zararsız; temizlemek için web sunucusunu kapat + `uv sync`.

### 🆕 EN SON İŞ (2026-06-23) — Kademe-2 derin av (8 finder) → 5 fix push, 2 devir
Kullanıcı "tüm projeyi tara + pushla". 8-finder Kademe-2 workflow + adversarial doğrulama; hedef
`f14fd33` (sabah Kademe-1'den sonra geldiği için kapsanmamıştı). **Rapor: `reports/bug-scan/scan-2026-06-23_0030.md`.**
**DÜZELTİLDİ + PUSH (her biri kapı yeşil: ruff+mypy+pytest tümü):**
- **A** `b99c4a0` (HIGH): `is_detached_training_running(root)` log-tazeliği yedeği `root`'u yok sayıp
  gerçek makine logunu okuyordu → ölü-pid testi yanlış `True`. ("Windows pid bug" sanılan = izolasyon
  sızıntısı.) `root` verilince yedek de yalnız o root'u sorgular.
- **E** `ed44bb5` (BLOCKER-sınıf): `gates._card_text` `limitations`/`datasets`/`risk_warnings` alanlarını
  toplamıyordu → bu alanlardaki sır/PII Gate 7 (BLOCKER) taramasını atlıyordu. 3 alan eklendi + 2 test.
- **C-kısmi** `9453a5a` (kural 6): `concept_graph._extract_links` seedsiz LLM → graf kararsız; seed=42.
- **B** `a672ce0` (kural 3): `risk_manager._extract_trade_returns` blokları HAM position'la sınırlıyordu
  → çıkış maliyeti + son tutuş-barı bloğun dışında → Kelly şişiyordu (headline doğru). Bloklar eff_pos'tan
  sınırlanır + çıkış-maliyeti barı dahil; +5 test.
- **D** `e4fb9fa` (kural 2): `aggregate()` min-graded korumasızdı → çevrimdışı graded=1 (yalnız L5) →
  pass_rate=%100 'scored' → `auto_pipeline` TERFİ kapısını şişirir. `_MIN_GRADED_FOR_SCORE=3` guard; +3 test.

**DENETİMLİ SEANSA DEVİR (gözetimsiz fix YOK):**
- **C-cross_paper**: `cross_paper_synthesizer` sentez yolu seed — YARATICI yolda determinizm-vs-yaratıcılık
  tasarım kararı (per-input türetilmiş seed seçeneği). Backtest/eval/terfi'yi etkilemez (LOW).
- **safety FN×2**: `safety_scanner.py` eş zamanlı oturumun aktif WIP'i → çakışmamak için bırakıldı.

**GOTCHA'lar:** (1) Büyük çok-ajan av 03:00 (Istanbul) **session-limit** reset'ine takıldı → `synthesize`
+3 verify düştü; bulgular ana-döngüde elle sentez/doğrulandı. (2) Eş zamanlı oturum (RLM/PR #12) çok aktifti;
collision 2× (Fix A süpürüldü → b99c4a0; LORA_log benim B commit'ime süpürüldü). ÇÖZÜM: `git reset`+dar-add.
Bkz memory [[kademe2-hunt-2026-06-23]].

### 🆕 EN SON İŞ (2026-06-22) — İki-hat train.jsonl drifti kökten kapatıldı (Kademe-2)
**Bulgu:** İki ayrı veri hattı aynı `data/training/jsonl/train.jsonl`'i yarışıp habersiz
ezerdi. **A (zengin):** `assemble_sft`/`lora-cloud-prep` → `lora_sft.jsonl` (~2020, `{messages}`)
→ `ensure_train_split` → ~1919/101. **B (cılız):** web uçları `DatasetBuilder.build()` →
`training_examples` SQLite → ~29/4 satır, `{prompt,completion}`. `train --run`/`launch()`
eğitimden hemen önce `ensure_train_split` çağırıp onarıyordu; AMA çağırmayan bir yol (doğrudan
backend/harici) 29 satırlık bayat/yanlış-formatlı veriyle eğitebilirdi.
**Fix (bu seans):**
- `app/training/detached_launch.py` → yeni KANONİK yardımcı `build_training_split()`
  (lora_sft.jsonl → ensure_train_split; kaynak yok/boşsa `assemble_sft_lines` ile bir kez
  üret, boşsa dokunma=clobber guard). `DatasetResult`-uyumlu `TrainingSplit` döner.
- `app/web/server.py` → 3 uç (`/api/training/dataset`, `/dry-run`, `/colab-notebook`) artık
  `DatasetBuilder` yerine `build_training_split()` çağırıyor → format `{messages}`, sayı kanonik
  kaynakla AYNI. `DatasetBuilder` yalnız manuel `achilles dataset` (SQLite inceleme) için kaldı.
- Regresyon testi: `tests/test_web_api.py::test_dataset_endpoint_uses_canonical_lora_sft`
  (hermetik, monkeypatch settings → SQLite'a dokunmaz; train+valid sayı=kaynak, format={messages},
  valid⊥train).
- Doğrulama: format+lint+typecheck (179 dosya)+test (tümü yeşil).
**Not:** CLI `achilles dataset` ve `/api/training/run`→`launch()` zaten kanonik yolu kullanıyordu;
yalnız 3 web "veri oluştur/dry-run/colab" ucu cılız hatta düşüyordu. Branch/commit: bekliyor
(insan onayı ile). Memory: `training-data-pipeline` + `kademe2-pretrain-hunt-2026-06-22` güncellendi.

### 🆕 EN SON İŞ (2026-06-21) — Web upload "bir kısım gelmedi" düzeltildi
**Şikâyet:** Başka bilgisayarda çok sayıda PDF yüklenince web arayüzünde ~10 dosya görünmemiş.
**Kök neden:** Upload uçunda kayan-60sn hız sınırı (`upload_rate_limit_per_min`) **20/dk** idi;
sürükle-bırak ile >20 dosya gelince fazlası **429** yiyor, frontend bunu sessizce "hata" sayıp
dosyayı **diske bile kaydetmeden** düşürüyordu (429 middleware'de handler'dan ÖNCE).
**Fix (PR [#10](https://github.com/alimirbagirzade/achilles/pull/10), branch `fix/upload-rate-limit-retry`, oto-merge):**
- `app/web/static/assets/app.js` → toplu yükleme artık 429'da dosyayı düşürmüyor; bekleyip aynı
  dosyayı yeniden deniyor (≤40 deneme, 3.5sn ara). Kök çözüm.
- `app/config/settings.py` → `upload_rate_limit_per_min` 20→**60** (env: `ACHILLES_UPLOAD_RATE_LIMIT_PER_MIN`).
- Doğrulama: format+lint+typecheck+test **yeşil**.
**Not (kullanıcıya söylenenler):** (a) JS değişikliği için web **yeniden başlatılmalı**/sayfa yenilenmeli;
(b) zaten diske inmiş ama indekslenememiş dosyalar için **"⟳ TÜMÜNÜ İNDEKSLE"** / `uv run achilles ingest`
(idempotent kurtarma); (c) makineler arası senkron YOK — A'da yükleyip B'ye bakmak boş gelir.
**Henüz YAPILMADI (aday):** arka-plan indeksleme sessiz hatası hâlâ kullanıcıya yüzeye çıkmıyor
(Ollama kapalı/parse hatası → log'a yazılır, UI'da "alındı, indeksleniyor…" der). İleride bir
indeksleme-durumu/hata rozeti eklenebilir. Memory: yok (bu işten yeni).
**Gotcha (test):** Bash tool alt-kabuğu `PYTEST_DEBUG_TEMPROOT` user env var'ını miras almıyor →
pytest `PermissionError` verir. Çözüm: `PYTEST_DEBUG_TEMPROOT="C:/Users/sevinc/pytest-tmp" uv run pytest -q`.

### Proje amacı
LLM'i "trader gibi düşünen" bir araştırma motoru yapmak:
1. Makalelerden formül ve kavramları hafızaya al
2. Bunları birleştirip daha önce denenmemiş indikatör/algoritma öner
3. Otomatik backtest et → sonuçtan öğren → LoRA eğitim verisi üret
4. 3B modeli test eder; gerçek çıktı için 120B kullanılacak

### Mevcut durum (2026-06-21) — ✅ TOPARLAMA + TAŞINABİLİRLİK + OTOMATİK PR + YEŞİL CI

> Seans hedefi (kullanıcı): repoyu topla, pull/push çöz, kullanım kılavuzu yaz, sistemi
> **kiralık CPU / daha güçlü makineye taşımaya hazırla** ("kur-çalıştır, orada geliştirme YOK"),
> PR'ları **otomatikleştir**. Hepsi LANDED + doğrulandı. **main YEŞİL + senkron** (`dd46378`).

**1) Git toparlama (pull/push çözüldü):** 15→2 worktree, 18→5 branch (main + korunan 4:
`fix/rag-scoring-approval-cas`, `feat/web-training-gate-fix`, `feat/local-claude-operator-dry-run`,
`salvage/system32-cpu-lora`), ~780MB çöp silindi + `.gitignore` sertleşti (`.pytest_tmp_*`/`*.pid`/
`logs/`/`*.bak`/`vector_db/chroma.corrupt-*`/`storage/_*.py`/`scripts/*-autostart.vbs`). Commit `d940bdb`.
İş kaybı YOK (her dal/worktree önce denetlendi). Memory: `git-repo-durumu`.

**2) Taşınabilirlik katmanı (commit `72f4de4`):** çekirdek zaten CPU-first/taşınabilirdi; otomasyon
katmanı eklendi: `scripts/verify-install.sh` (offline kurulum kapısı, ps1'in bash portu, GECTI doğrulandı),
`scripts/install-autostart.sh` (Linux systemd/cron autostart), `setup.sh` +yerel/uzaktan erişim sorusu
(uzaktan→`0.0.0.0`+otomatik API token)+verify kapısı+opsiyonel autostart, `continuous-learning.sh` HIGH
blocker fix (gömülü powershell→`pgrep`). **KARAR:** RAG+LoRA her makinede SIFIRDAN (vector_db/sqlite/
adapter KOPYALANMAZ; sadece PDF→`ingest`→Kaggle). Memory: `bulut-tasima-protokolu`.

**3) Kullanım kılavuzu (kullanıcı için, Desktop):** `Desktop\RAG Kaynak\Kulanım talimatı\` →
`00_GENEL_BAKIS` / `01_KURULUM_ve_CALISTIRMA` / `02_PUSH_PULL_GIT` / `03_BULUT_TASIMA_PROTOKOLU`.
`README.md` eskimiş bilgileri yenilendi (`d4338b7`: bulut/9-sekme/vektör-yolu/eğitim-süresi/uzaktan-mod).

**4) OTOMATİK PR akışı CANLI + UÇTAN UCA KANITLANDI:** `gh auth login` (kullanıcı yaptı) →
`scripts/setup-pr-automation.sh` çalıştırıldı (repo PUBLIC+ADMIN → `allow_auto_merge` + main branch
koruması, required ctx=`lint · types · tests (offline)`, `enforce_admins=false` → **owner doğrudan
`git push origin main` yapabilir**, loop'lar kırılmaz). `scripts/open-pr.{sh,ps1}` = push+PR+CI-yeşilse
oto squash-merge (varsayılan; `--no-merge`/`-NoMerge` ile kapat). **PR #9 PowerShell'den oto-merge oldu
(kanıt).** `.github/pull_request_template.md` eklendi. Commit'ler `5603c74`,`dd46378`.

**5) main CI RED→YEŞİL:** seans öncesinden kırmızıydı (kimse fark etmemişti). İki arıza: format drift
(`72f4de4`'te `ruff format .`) + `test_flashrank_reranker` opsiyonel `flashrank` paketsiz FAIL (`5d3eee4`
SimpleNamespace shim). + `open-pr.ps1` PS 5.1 native-stderr bug (`dd46378`, sadece ÇALIŞTIRINCA çıktı).

**KALAN (sonraki seans — hiçbiri bloke değil):**
- **Node.js 20 deprecation** CI uyarısı (`actions/checkout@v4`, `setup-uv@v5` Node24'e zorlanıyor) →
  ileride aksiyon sürümlerini bump et. CI'ı bozmuyor.
- **GOTCHA:** açık PR'a yeni commit push'u (synchronize) CI'ı tetiklemeyebilir (PR BLOCKED kalır);
  TAZE PR sorunsuz. Tekrarsa: PR'ı close/reopen.
- **Eşzamanlı oturum `rag-chains-work`** worktree'si AKTİF (RAG "Zincir" işi: keyword-eval/router/
  CRAG-lite/FlashRank) — DOKUNMA. Not: ben `scripts/rag_keyword_eval.py`'yi main'e (eski kopya)
  commit'ledim; o oturum merge ederken küçük çakışma çıkabilir (onların çözeceği).
- Proje backlog'u (bu toparlamanın DIŞINDA): RAG turları sonrası backtest/eval ölçümü, sıradaki RAG
  adayları — bkz. memory `session-devir-2026-06-21`, `hiz-kalite-makale-uygulama`.

---

### Mevcut durum (2026-06-20) — ✅ OTONOM BAŞLANGIÇ ZİNCİRİ (branch `feat/otonom-baslangic-zinciri` · PR #5)

> Hedef: "yeni makinede git clone sonrası tertipli bir SIRALAMA ZİNCİRİ olarak otonom ayağa kalksın."
> 5 alt-sistem repo-taramasıyla tasarlandı (ayrıntı: memory `otonom-baslangic-zinciri`); sistemin %80'i
> zaten taşınabilir çıktı → eksik halkalar eklendi. **Kararlar:** tetikleyici = mevcut hibrit (HKCU Run +
> Task Scheduler yedek), otonomi = **varsayılan KAPALI**, executor = hibrit ince. Kural 8 korunur
> (gerçek eğitim/terfi yine tek-kullanımlık taze onay; executor o kapıyı zayıflatmaz).

**LANDED — 6 commit (hepsi ruff+mypy temiz · tüm offline suite YEŞİL · CLI duman-testi exit 0):**
- `verify-install.ps1` — autostart ÖNCESİ çevrimdışı duman testi kapısı (`start-server.ps1 -Install` artık önce doğrular; kalırsa autostart kurmaz; `-SkipVerify` kaçış).
- hibrit **executor** (`app/agents/runtime/executor.py`) — allow-list handler (bilinmeyen agent çalışmaz), `run_task`/`run_pending(--retry-blocked)`, STOP_ALL + taze-onay kapısını korur; + `task_queue.requeue_task` + CLI `tasks-run`. (9 test)
- `synth_qa_chain.ps1` taşınabilir (`$PSScriptRoot`+`Find-Uv`) + UTF-8 BOM (PS 5.1 parse fix).
- **runtime-init** ön-uçuş (`app/agents/runtime/preflight.py`) — manifest + 4 Phase-2 tablosu + STOP_ALL doğrula; CLI kapı. (2 test)
- **chain** (`automation_manifest.yaml` 'chain' bölümü + `app/agents/runtime/chain.py` Kahn topo-sort, döngü/eksik-step doğrulama) + CLI `chain-status [--live]`. (8 test)
- README ajan-runtime/otomasyon komut bölümü.

**KALAN (sonraki seans):**
- **PR #5** → `main` merge: github.com/alimirbagirzade/achilles/pull/5 (branch eşzamanlı oturum commit'leri `06e048b`/`3de5082`/`c420d3b`'yi de içeriyor — collision; main'e ayrı yoldan girerlerse düşer).
- **`.claude/settings.json`** SessionStart hook'unda yabancı macOS yolu (`/Users/mirbagirzade`) → **self-modification guardrail** otomatik düzeltmeyi engelliyor. Kullanıcı AÇIKÇA "o hook'u düzelt" demeli. Fix: `cd "${CLAUDE_PROJECT_DIR:-.}"`.
- Executor **per-agent handler**'ları kayıtlı değil (allow-list bilinçli boş) → `tasks-run`/`chain-status` altyapısı hazır ama henüz ajan çalıştırmaz; her ajan için handler eklemek doğal sonraki adım (tehlikeli zincir dikkatli).
- ✅ **ÇÖZÜLDÜ (`52d305c`, 2026-06-20):** `app/main.py` `__main__` bloğu (line ~1327, komutların yarısından önce) dosya SONUNA taşındı → `python -m app.main chain-status / tasks-list` artık çalışıyor (önce "no such command" veriyordu). Saf yer-değiştirme (4+/4-); ruff+mypy temiz, offline pytest yeşil. Console-script entry-point zaten etkilenmiyordu.
- **gh ipucu:** `gh auth login` interaktif; ama GCM'deki `gho_` token `git credential fill` → `GH_TOKEN` ile `gh.exe`'ye verilerek PR açılabilir (token yazdırmadan).

---

### Mevcut durum (2026-06-20 · web anlama rozeti) — ✅ CACHE-BUST + OBJ.ANLAMA 500 FIX

> Kullanıcı: "RAG anladı: %54 (63/116) · anlama %32 (114 makale) — web'te canlı mı? değilse çöz+fix+push."

**Teşhis:** Rozet SAYILARI canlıydı (`/api/rag-mastery` her 30sn DB'den, poll'lu), ama kullanıcı
DONMUŞ/önbellekten eski sayfayı görüyordu. Kök neden: `index.html` `app.js?v=2` SABİT etiketiyle
yükleniyordu; app.js değişince etiket elle bump edilmemiş (CSS ?v=4'e çıkmış, JS ?v=2'de kalmış) +
asset'lerde Cache-Control yok → tarayıcı eski JS'i süresiz önbellekten servis ediyordu (eski "anlama %"
etiketi = kullanıcının gördüğü; güncel kod "öz-değ. %").

**LANDED (2 commit — origin/main + `feat/agent-runtime-phase2` (PR #3); `feat/agent-runtime-observer`'da da var):**
- `38ed997` **cache-bust**: `index()` dinamikleşti → `/assets/app.(js|css)?v=` içerik sha256 hash'iyle
  servis + HTML `no-cache`. app.js/app.css değişince URL otomatik değişir → manuel `?v=` bump bir daha
  gerekmez. (+`test_index_cache_busting`)
- `3b67ed1` **exam timeout**: `/api/understanding-score` 500 veriyordu (yavaş CPU'da `httpx.ReadTimeout`
  yalnız `LLMUnavailable` yakalandığı için sızıyordu). `local_llm` httpx hataları→`LLMUnavailable`;
  `score_indicator_exams` try/except + fail-fast. (+`tests/test_local_llm.py`, +2 understanding_score testi)
  - NOT: eşzamanlı oturum `e359aa6` ile DAHA RAFİNE etti (bayat-skor recompute + 2-ardışık-fail bail +
    timeout 60→**240sn**). İkisi uyumlu; **e359aa6 nihai**.

**Doğrulama (canlı, restart sonrası):** index hashed URL + `no-cache` ✓; rag-mastery canlı & hareketli
(kart 237→239, içerikli makale 63→64); obj.anlama **HTTP 200** (önceden 500), ~102sn'de dürüst skor
(1 graded, pass_rate 0.0). ~590 offline test yeşil; ruff+mypy temiz.

**Araştırma sonucu (KAPANDI — bu konu için harici loop GEREKMEDİ):** obj.anlama düşük (~%0–15) çünkü
qwen3:4b held-out indikatör hesaplama sınavlarını CPU'da ya geçemiyor ya zaman aşımına uğruyor. Projenin
tezini DOĞRULUYOR: kaba öz-değ. %32 iyimser; objektif sınav geçme oranı çok düşük. Sorun model-kapasitesi
+ CPU, kod değil → makale/LoRA dış araştırma rutinleri (ayrı/zamanlanmış) bu konuya çözüm değil.

**KALAN (sonraki seans):**
- obj.anlama'yı e359aa6'nın 240sn timeout'uyla TEKRAR ölç → gerçek pass-rate (kaç sınav graded). Running
  server bayatsa web RESTART (rotalar/kod başlangıçta yüklenir; statik diskten canlı).
- Kullanıcı tarayıcısında bir kez `Ctrl+Shift+R` (eski cached index.html kırılsın) — sonrası kalıcı.
- gh CLI bu makinede kurulu DEĞİL → PR'lar GCM token (`git credential fill`) + GitHub API/`GH_TOKEN` ile
  açılıyor (token yazdırmadan; bkz. yukarıdaki "gh ipucu").

---

### Mevcut durum (2026-06-19) — ✅ KAD-2 TAMAMLANDI + 🔄 SYNTH-QA ÜRETİMİ DEVAM EDİYOR

> **Kademe-2 derin bug-avı TAMAMLANDI** (Sprint 1-5, toplam 18 onaylanan fix, commit `ceae006`).
> Şu an kritik tek bekleyen: `synthetic_qa.jsonl` → 362'den 1300'e (seed=100 CPU'da sürüyor).
> 1300'e ulaşınca: `achilles lora-split` yenile → Kaggle "Run All" tıkla (tek manuel adım).

**KAD-2 SPRINT FİX ÖZETİ (hepsi committer ve test edildi):**
- Sprint-1: rag_exam_runner sahte-geçme, bollinger registry, entropy bar-0 NaN, adapter peft_base_model, rag_answerer seed, significant_numbers binlik ayraç
- Sprint-2: BM25 tie-break (determinizm), citation_score gerçek parse, dataset_quality false-positive (192→6), entropy warmup=period (7 test yeşil)
- Sprint-3: paper_indexer embedded erken yazım (BUG-M6), sqlite_store mark_chunks_embedded, auto_pipeline eval_pass_threshold (BUG-M9)
- Sprint-4: peft_llm_shim.py (PEFT adapter → LocalLLM), auto_pipeline anlama-merdiveni kıyası (v5 savunma dikişi)
- Sprint-5: server.py BUG-H3 (komisyon+slippage eksikti), agents/runtime Phase 2 (approvals/supervisor/task_queue), overfit_checks BUG-M7 IS+OOS

**SYNTH-QA DURUMU:**
- Mevcut: 362/1300 (`data/lora_sft/synthetic_qa.jsonl`)
- Aktif: `logs/synth_qa_seed100.log` — PID 8044 çalışıyor (~3 dk/chunk, CPU-only)
- Hedef ulaşmazsa: `powershell scripts/synth_qa_chain.ps1 -Target 1300 -StartSeed 200`
- **1300'e ulaşınca:** `uv run achilles lora-split` → Kaggle "Run All"

**KALAN (KAD-2 sonrası):**
- grounding_verifier markdown sentence splitter (BUG-M8, ertelendi — büyük refactor)
- PR: `feat/agent-runtime-phase2` → `main` merge (Kad-2 tamamlanınca)

---

### Mevcut durum (2026-06-17) — 🔒 ANLAMA MERDİVENİ KALICI + 📚 MAKALE LOOP + 🐛 `\r` BUG

> Kullanıcı: "L2/L3/L4/L5'i kalıcı yap + push; bug'ları loop'la çöz; faydalı makaleleri
> sürekli indir; sonra eğitime devam." Eğitim kararı DEĞİŞMEDİ: **önce bitir, sonra bulut-GPU**
> (lokal CPU = v5 çıkmazı; veri kapısı temiz-regen bitince GO → manuel Kaggle "Run All").

**KALICILIK (L2-L5) ✅ — bu seansta inşa edildi:**
- `understanding_snapshots` SQLite tablosu + `SqliteStore.save_/list_/latest_understanding_snapshot`.
- `app/verification/exams/understanding_record.py`: `record_understanding` (DB + zaman-damgalı
  `reports/evals/understanding/*.json`), `load_understanding_history`.
- `understanding_score.py`: `score_full_ladder` (L5 deterministik—**çevrimdışı bile notlanır**
  + L3/L4 LLM + opsiyonel RAG Taban/L1/L2), `l5_example_result`, `run_rag_ladder_answers`;
  `score_indicator_exams` geri-uyumlu (refactor → `_indicator_exam_results`).
- CLI: `understanding-score --full --with-rag --record` + yeni `understanding-history`.
- Web: `/api/understanding-score`'a `full/with_rag/record` query (**VARSAYILAN DAVRANIŞ DEĞİŞMEDİ**)
  + yeni `/api/understanding-score/history`; "obj. anlama" rozeti tıklayınca tam merdiven + KALICI kayıt.
- **6 yeni test + tüm offline paket yeşil · ruff+mypy temiz.** Uçtan uca denendi (snapshot DB + CLI history).

**🔬 GENİŞ DENETİM SONRASI SAĞLAMLAŞTIRMA (2026-06-18) — kullanıcı "acele etmeden geniş bakalım ve çözelim":**
Çok-ajan denetim (5 boyut, 24 doğrulanmış bulgu) → 11 "now" çözüldü, hepsi offline test edildi:
1. **L5 yanlış-negatif BUG fix** — `composition_to_result`: backtest YALNIZ "çok az işlem/veri yok/belirsiz"
   yüzünden düştüyse artık `failed` değil `skipped` (test edilemedi). Sahte ~%0 sinyali bitti.
2. **L5 gerçek sinyal** — `l5_results_from_sessions`: `score_full_ladder` sabit `example_ir` yerine sistemin
   KENDİ ürettiği kompozisyonların (`research_sessions.verdict`) gerçek sonucunu okur (`use_sessions_l5`).
3. **Bağlam otomatik kaydı** — snapshot context'ine `llm_model`/`model_kind`/`n_papers`/`n_carded` otomatik
   yazılır (zaman serisi yorumlanabilir; base vs adapter ayrımı için temel).
4. **Merdiven sırası** — `Taban→L1..L5` sabit sıra (alfabetik sort Taban'ı sona atıyordu); CLI + web ortak.
5. **Regresyon kıyası** — `compare_understanding(prev,curr)` (yalnız aynı `llm_model` → `regressed` bayrağı) +
   CLI `understanding-history --compare` + "Bağlam" sütunu. v5-tipi gerilemeyi yakalamanın temeli.
6. **Web görünürlük** — Öğrenme paneline "Objektif Anlama Geçmişi" kartı (sparkline + tablo, `/history`
   tüketilir, XSS-güvenli esc) + açılışta son skor rozette pasif gösterilir. **Canlı sunucuda doğrulandı (HTTP 200).**
7. **Adapter-ölçüm dikişi** — `score_full_ladder(llm=...)` + `_indicator_exam_results(llm=...)` → base yerine
   ADAPTER ölçülebilir (sahte-LLM ile offline test edildi). v5-savunmasının altyapısı.
- **12 yeni test (toplam) + tüm offline paket yeşil (exit 0) · ruff+mypy temiz.** 145/145 makale artık kartlı.

**🔴 "NEXT" (eğitilmiş adapter gerektirir / daha büyük — denetim doğruladı, henüz YAPILMADI):**
- **Adapter promosyonunu anlama-merdivenine BAĞLA (en kritik):** `auto_pipeline._run_eval` base-vs-adapter
  `score_full_ladder` koşsun; adapter pass_rate base'in altındaysa promosyonu BLOKLA. (#7 dikişi hazır; PEFT
  LLM shim + eğitilmiş adapter gerekir — v6 daha yok, o yüzden offline doğrulanamaz.)
- **Disiplin/dürüstlük sınav basamağı:** merdiven "maliyetsiz getiri / garanti / pasaja-göre" v5 patolojilerine
  KÖR (onlar adapter_eval + pretrain-gate'te). `discipline_core` red-flag'lerini bir ExamResult'a sar.
- **pretrain-gate → auto_pipeline zinciri:** `dataset_quality.audit_dataset` Gate 0-8 sonrası çağrılmalı (NO-GO → bloke).

**🐛 `\r` BUG (kart üretimi OSError 22):** Windows Python stdout CRLF → bash `for pid` döngüsüne `\r`
sızıyor → `paper_xxx\r_card.json`. Kök sebep doğrulandı (DB id'leri TEMİZ: 138 makale, 0 bozuk).
`continuous-learning.sh` (satır 71/101) **eşzamanlı oturum/makine** tarafından düzeltildi; `auto-chain.sh`
de düzeltiliyor → scriptlere DOKUNMADIM (çakışmamak için). `continuous-learning` loop synth-yazma
yarışı için duraklatıldı (`storage/STOP_LEARNING`); bulk-regen bağımsız sürüyor. **KALAN:** mac-loop.sh
aynı `\r` desenine sahip (macOS'ta zararsız ama robustluk için bir gün düzeltilebilir).

**Synth temiz yeniden-üretim (AKTİF):** `synth-qa-bulk → 1300` arka planda; yeni veride "pasaja göre"
oranı **%0** (eski %68 = v5'i batıran). 1300'e ulaşınca kapı GO beklenir.

**📚 Makale loop:** 6 yeni gerçek arXiv makalesi `Desktop\RAG Kaynak\Gerekli kaynaklar\` köküne indi
(1905.05023 backtest-OVF, 2512.12924 walk-forward, 2309.15217 RAGAS, 2401.15884 CRAG, 2601.05716
Kalman-Markov, 2605.17117 geometrik rejim) + `00_NEDEN_ONEMLI_oku_once.md` güncellendi. DSR/PBO arXiv'de
yok (uydurulmadı, Kural 7). Yeni `lora-arastirma` ajanı da mevcut (LoRA tekniği araştırması için).

---

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
   - 🔬 **TEŞHİS (v5 batış kök sebebi, koddan doğrulandı):** (1) `synthetic_qa_builder._ONESHOT_EXAMPLE`
     her cevaba "Pasaja gore" öneki → model koşulsuz açılış ezberledi (bağlamsız evalde de). (2) Üretici
     yalnız "pasajdan cevapla" örneği üretiyor; adversarial disiplin örneği YOK (`raft_discipline_seed.jsonl`'de
     6 var ama ölçeklenip karıştırılmamış). (3) overfit/tekrar. → adapter maliyetsiz %20 getiri uydurdu (REJECT).
   - ✅ **Fix A yapıldı:** `_ONESHOT_EXAMPLE` açılışı çeşitlendi, "Pasaja gore" sızıntı öneki kaldırıldı + test.
   - ✅ **Fix B yapıldı (ASIL):** `app/training/discipline_dataset.py` — 9 tuzak (garanti/backtest'siz/
     maliyetsiz/kaynak-yok/bağlam-uyumsuz/look-ahead/overfit/kaldıraç/grounded-belirsizlik) × 16 strateji
     × 3 varyant = **432 deterministik adversarial örnek**. `lora-cloud-prep` bunları DEDUP'TAN SONRA
     ~%25 karıştırır (`--discipline-ratio` / `--no-discipline`); CLI `discipline-dataset` önizleme/export.
     v5 dersleri kodlandı: açılışlar çeşitli (sabitleme yok), 1/3 örnek system-prompt'suz (eval öyle
     çağırır), cevaplar naif `check_flags`'i geçer (yasak yüzey token'ı yok + maliyet token'ı var).
     12 yeni test + tüm offline paket yeşil · ruff+mypy temiz.
   - ✅ **Fix C yapıldı:** `dataset_quality.recommend_epochs(n)` (boyuta göre 1-3); mix oranı zaten flag.
   - ✅ **#3 OFFLINE KAPI yapıldı:** `app/training/dataset_quality.py` + `achilles pretrain-gate` —
     birleşik SFT setini LLM'siz tarar, **GO/NO-GO** verir (garanti-vaadi zehiri / açılış-ezberi → blok).
     `app/training/sft_assembly.py` ortak birleştirme (lora-cloud-prep + gate DRY). 11 yeni test yeşil.
   - 🔴 **KAPI İLK KOŞUDA NO-GO VERDİ (2026-06-17, beklenen):** mevcut `synthetic_qa.jsonl` (1289 satır)
     Fix A'dan ÖNCE üretildi → cevapların **%68'i "pasaja gore" ile açılıyor** (v5'i batıran tam mekanizma).
     Disiplin karışımı (432/432) ve garanti-zehiri (0) temiz; sorun ESKİ synth verisi. **ÇÖZÜM = synth-qa'yı
     temiz üreticiyle YENİDEN ÜRET** (gece loop'u bunu yapıyor). Rapor: `reports/evals/pretrain_gate.json`.
5. **Gece otonom loop (2026-06-17, AKTİF):** synth-qa'yı temiz yeniden-üret → `pretrain-gate` GO olana kadar
   → `lora-cloud-prep` paketi tazele → raporla. Eğitim: kapı GO + kullanıcı sabah Kaggle "Run All" (manuel tık).

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

> [bug-scan 2026-06-22_0900] Weekly Tier-1 scan done -> reports/bug-scan/scan-2026-06-22_0900.md
