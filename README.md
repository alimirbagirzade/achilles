# Achilles Trader AI

> **Yerel-öncelikli AI trading _araştırma_ sistemi** — macOS Apple Silicon için.
> RAG + bilgi kartları + (opsiyonel) LoRA + disiplinli backtest.

> ⚠️ **ÖNEMLİ:** Bu bir **araştırma aracıdır**, canlı trading botu **değildir**
> ve **yatırım tavsiyesi vermez**. Tüm çıktılar test edilmesi gereken
> _hipotezlerdir_. Gerçek parayla kullanımın tüm sorumluluğu kullanıcıya aittir.

---

## 📊 Proje Durumu — _canlı_ (2026-06-02, branch `main`)

> Repo: https://github.com/alimirbagirzade/achilles · Test: **43 geçti** (offline) + 2 ollama-entegrasyon · Kalite: ruff+mypy temiz

- [x] **Ortam**: uv (Python 3.13) · Ollama (servis) · `nomic-embed-text` · `qwen2.5-coder:3b`+`7b` · `mlx-lm 0.31.3`
- [x] **İsim**: tüm repo `Achilles` (sıfır "ares" kalıntısı)
- [x] **Ingestion**: gerçek arXiv PDF → SQLite + ChromaDB (69 chunk, gerçek embedding)
- [x] **RAG canlı**: `ask` kaynaklı 5-bölümlü cevap (3b aktif, 8GB profili)
- [x] **LoRA `train --run`**: uçtan uca (loss 1.21→0.029, adapter + registry, öğrenilmiş davranış)
- [x] **Gerçek veri backtest**: BTC-USD 1g (5 yıl) → evaluator overfit'i **FAIL** ile yakaladı
- [x] **Web arayüzü**: güvenlik-sertleştirilmiş FastAPI + **açık (light), renk-körü-dostu** temiz arayüz (`app/web/`, `SECURITY.md`)
- [x] **8GB'da güvenilir LLM bilgi-kartı** — Ollama `format:"json"` + kısa girdi + num_predict cap + retry + esnek parse → 3b artık dolu/doğru kart üretiyor (~56s); card→dataset→LoRA döngüsü otomatik
- [ ] intraday (15m/1h) OHLCV kaynağı · çok-makaleli LoRA dataseti · CI (GitHub Actions)
- [ ] 32GB makineye geçince `ACHILLES_LLM_MODEL=qwen2.5-coder:14b` (profil `.env.example`'da hazır)

---

## Ne işe yarar?

Akademik finans/trading literatürünü (PDF) sindirir, kaynağa dayalı yanıtlar
üretir, bulguları **test edilebilir strateji hipotezlerine** çevirir ve bu
hipotezleri **look-ahead'siz, maliyetli, örneklem-dışı (OOS) doğrulamalı** bir
backtest motorunda şüpheci bir denetçi gibi sınar.

Tasarım felsefesi: **"Aksi kanıtlanana kadar her strateji güvenilmezdir."**

---

## Mimari (katmanlar)

```
PDF makaleler
   │  (ingestion)  pdf_parser → metadata → chunker
   ▼
SQLite (yapısal kayıt)  +  ChromaDB (vektör arama)
   │  (memory)  embedding_service → paper_indexer → retrieval_service
   ▼
RAG yanıtlama / özet / bilgi kartı / eğitim verisi
   │  (brain)  rag_answerer · paper_summarizer · knowledge_card_builder
   ▼                                            training_data_builder
(opsiyonel) LoRA eğitimi — MLX, varsayılan DRY-RUN
   │  (training)  dataset_builder → mlx_lora_train → evaluate_model
   ▼
Strateji IR → Backtest → Overfit kontrolü → Evaluator (pass/fail/inconclusive)
      (trading)  strategy_ir · indicators · backtester · overfit_checks · evaluator
```

### Çevrimdışı çalışma (önemli)
Ollama kurulu değilse:
- **Embedding**: deterministik hash-tabanlı yedek embedder devreye girer
  (`ACHILLES_ALLOW_FAKE_EMBEDDINGS=true`), böylece pipeline uçtan uca çalışır.
- **LLM**: RAG, kaynak parçalarını ham gösterir (graceful degradation).

---

## Kurulum

### Gereksinimler
- Python ≥ 3.12
- (Önerilen) [uv](https://docs.astral.sh/uv/) paket yöneticisi
- (Opsiyonel) [Ollama](https://ollama.com) — yerel LLM + embedding için
- (Opsiyonel, sadece macOS arm64) `mlx-lm` — LoRA eğitimi için

### uv ile (önerilen)
```bash
uv sync                      # bağımlılıkları kur
uv run achilles init             # dizinleri + DB'yi hazırla
```

### pip ile
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
achilles init
```

### Ortam değişkenleri
```bash
cp .env.example .env
# ACHILLES_OLLAMA_HOST, ACHILLES_LLM_MODEL, ACHILLES_EMBED_MODEL, ACHILLES_RAG_TOP_K ...
```

### Ollama (RAG/kart için gerekli)
```bash
brew install ollama && brew services start ollama
ollama pull qwen2.5-coder:3b   # 8GB profili (aktif). 16GB->7b, 32GB->14b
ollama pull nomic-embed-text   # embedding modeli
```
> RAM profilleri `.env.example`'da belgeli; `ACHILLES_LLM_MODEL` ile seçilir.

---

## Kullanım (CLI: `achilles`)

| Komut | Açıklama |
|-------|----------|
| `achilles init` | Dizinleri ve SQLite şemasını oluşturur |
| `achilles status` | Sistem durumu (Ollama, embedding modu, sayımlar) |
| `achilles ingest` | `data/papers/raw_pdf/` içindeki PDF'leri indeksler (idempotent) |
| `achilles papers` | İndekslenmiş makaleleri listeler |
| `achilles ask "soru"` | RAG ile kaynaklı yanıt (5 bölümlü disiplinli format) |
| `achilles card <paper_id>` | Yapılandırılmış bilgi kartı üretir |
| `achilles dataset` | Bilgi kartlarından eğitim JSONL'i üretir |
| `achilles train` | LoRA eğitimi — **varsayılan dry-run**; gerçek için `--run` |
| `achilles evaluate <eval.jsonl>` | Modeli failure-mode eval setiyle dener |
| `achilles gen-data` | Test için sentetik OHLCV CSV üretir |
| `achilles backtest <csv>` | Strateji IR'i backtest eder + yargılar + kaydeder |

### Tipik uçtan uca akış
```bash
# 1) Araştırma
achilles init
cp ~/Downloads/*.pdf data/papers/raw_pdf/
achilles ingest
achilles ask "Momentum anomalisi düşük likiditede güçlenir mi?"
achilles card paper_abc123
achilles dataset

# 2) (Opsiyonel) Eğitim — varsayılan dry-run
achilles train                      # sadece komutu gösterir
achilles train --run                # gerçekten eğitir (macOS arm64 + mlx-lm)
achilles evaluate evals/discipline_core.jsonl

# 3) Backtest (gerçek veri yoksa sentetik üret)
achilles gen-data
achilles backtest data/market/raw/synthetic.csv
```

---

## Web arayüzü 🖥️

Açık (light), temiz ve **renk-körü-dostu**, **güvenlik-sertleştirilmiş** yerel web arayüzü.

```bash
pip install -e ".[web]"      # veya: uv sync --extra web
achilles-web                 # http://127.0.0.1:8765 (yalnız localhost)
# alternatif: uvicorn app.web.server:app
```

Tarayıcıda `http://127.0.0.1:8765` aç. Sekmeler: **Araştırma** (RAG soru-cevap),
**Makaleler** (PDF yükle/indeksle, bilgi kartı), **Backtest** (sentetik veri +
örnek strateji + yargı), **Sistem** (durum + token).

### API uçları
| Yöntem | Uç | Açıklama |
|--------|-----|----------|
| GET | `/api/status` | Sistem durumu |
| GET | `/api/papers` | İndekslenmiş makaleler |
| POST | `/api/papers/upload` | PDF yükle (doğrulanır) → indeksle |
| POST | `/api/ingest` | Tüm PDF'leri yeniden indeksle |
| POST | `/api/ask` | RAG sorusu (kaynaklı) |
| POST | `/api/card/{paper_id}` | Bilgi kartı üret |
| POST | `/api/backtest` | Sentetik veri üzerinde backtest |
| POST | `/api/backtest/csv` | **Gerçek OHLCV CSV** yükle → backtest (doğrulanır) |
| GET | `/api/docs` | OpenAPI (Swagger) arayüzü |

### Güvenlik (özet — tamamı `SECURITY.md`)
- **Yalnız localhost'a bağlanır** (`127.0.0.1`); ağa açmak için token zorunlu.
- İsteğe bağlı **bearer token** (`ACHILLES_API_TOKEN`), sabit-zamanlı karşılaştırma.
- **CSP + güvenlik başlıkları** her yanıtta; frontend'de inline script yok.
- **Katı PDF doğrulama** (uzantı + sihirli bayt + 50 MB limit) + path-traversal koruması.
- IP başına **hız sınırı**. Kullanıcı girdisi asla çalıştırılmaz.

> Sunucuyu internete açacaksan **mutlaka** `ACHILLES_API_TOKEN` ata ve TLS'li bir
> reverse proxy arkasına koy. Ayrıntılar: [`SECURITY.md`](./SECURITY.md).

---

## ⚙️ Sekmeler Nasıl Çalışır? (motorun içi)

### 🔎 RAG Araştırma — _soru-cevap_

```
Soru ─▶ embedding ─▶ ChromaDB'de EN YAKIN 6 parça (top_k)
                              │  (senin yüklediğin makalelerin metni)
                              ▼
        Model: "SADECE bu kaynaklara dayan, uydurma"
                              ▼
   Cevap = kısa cevap · kaynaklar · akademik bulgu · trading hipotezi · test noktaları
```

- **Ne yapar:** sorunla **en alakalı bölümleri bulur**, onları **okuyup dayanarak** cevaplar.
- **Ne yapmaz:** tüm makaleyi baştan sona özetlemez · kendi kafasından serbest yorum üretmez · kaynak yoksa **"Kaynak bulunamadı"** der (uydurmaz).
- **Ayar:** geniş cevap için `top_k`'yı artır (6 → 12–20). Tüm makale özeti için **Bilgi Kartı**'nı kullan.

### 📈 Strateji Backtest — _şüpheci denetçi_

```
Veri (sentetik VEYA gerçek CSV) ─▶ indikatörler (EMA/RSI/ATR) ─▶ Strateji IR (kurallar)
   ─▶ Backtest motoru (look-ahead-safe + komisyon/slippage dahil)
   ─▶ metrikler ─▶ in/out-of-sample bölme + overfit kontrolü
   ─▶ EVALUATOR → ✓ GEÇTİ / ✕ BAŞARISIZ / ≈ SONUÇSUZ ─▶ SQLite'a kayıt
```

- Strateji **test edilmeden "başarılı" sayılmaz**; örneklem-dışı (OOS) pozitif değilse **FAIL**.
- Maliyetler her zaman dahil, pozisyon **bir bar gecikmeli** (look-ahead yok), az işlemde "istatistiksel anlam zayıf".
- Yüksek getiri görünse bile overfit varsa sistem **reddeder** — bu sistemin kalbidir.

### 🛡️ Sistem & Disiplin — _kontrol paneli_

İşlem yapılmaz; sistemin **nasıl düşündüğünü ve sınırlarını** gösterir: katman mimarisi,
değişmez disiplin kuralları, güvenlik özeti ve (gerekiyorsa) **API token** girişi.
"Sağlık tablosu" gibi düşün — model bağlı mı, embedding modu ne, kaç makale var.

### 📚 Makaleler — _hafıza_

PDF yükle → otomatik **ingestion** (metin çıkar → parçala → SQLite + ChromaDB).
Buradaki makaleler RAG'in "okuduğu" kaynaklardır. Her makaleden **Bilgi Kartı** üretilebilir.

---

## 🧪 Web Arayüzü — Adım Adım Test Kılavuzu

> Sunucuyu aç, sonra tabloyu **yukarıdan aşağı** uygula. Her satırda **ne yaparsın** ve **✅ ne görmelisin** var.

### ▶️ Başlat
```bash
cd ~/Development/Achilles
uv run achilles-web        # → http://127.0.0.1:8765
```
Tarayıcıda aç → **Cmd+Shift+R** (yenile). Sağ üstte **🟢 yeşil "ollama bağlı"** görmelisin.

### ✅ Ana akış (sırayla)

| # | Sekme | Ne yaparsın | ✅ Ne görmelisin |
|:-:|-------|-------------|------------------|
| 1 | **SİSTEM** | sekmeye tıkla | katman / disiplin / güvenlik kutuları, hata yok |
| 2 | **MAKALELER** | PDF sürükle-bırak _(birden çok olur)_ | "Yükleniyor 1/N…" → makale satırı + **"… chunk"** |
| 3 | **MAKALELER** | satırda **BİLGİ KARTI**'na bas | **◌ ÜRETİLİYOR** → ~1 dk → yeşil **✓ KART HAZIR** |
| 4 | **ARAŞTIRMA** | soru yaz → **SORGULA →** | kaynaklı cevap + altta **kaynaklar** listesi |
| 5 | **BACKTEST** | **SENTETİK ÇALIŞTIR →** | metrik tablosu + **YARGI** kutusu (✓ / ✕ / ≈) |
| 6 | **BACKTEST** | "veya gerçek veri"ye **CSV** bırak | metrikler + **"veri: dosya.csv (… bar)"** |

### 🧨 "Yaramazlık" testleri — _reddetmesi = İYİ_

| Dene | ✅ Beklenen (güvenli davranış) |
|------|-------------------------------|
| `.txt` dosya yükle | *"Yalnız .pdf kabul edilir"* |
| kolonları bozuk CSV | *"open/high/low/close bulunamadı"* |
| hiç makale yokken soru sor | *"Kaynak bulunamadı"* — **uydurmaz** |
| zayıf stratejiyi backtest et | **✕ BAŞARISIZ** (overfit / OOS) |

### 👓 Renk körü göz testi
Yargı ve metriklerde **renge ek ikon** olmalı: **✓ / ✕ / ≈** ve **▲ / ▼** — anlam sadece renkle verilmez.

### ❓ Sık sorulanlar

| Sorun | Çözüm |
|-------|-------|
| Sayfa **karanlık** görünüyor | **Cmd+Shift+R** (tarayıcı önbelleği) |
| **"Bu siteye ulaşılamıyor"** | sunucu kapalı → `uv run achilles-web` ile başlat |
| **50 MB az geldi** | `.env` → `ACHILLES_MAX_UPLOAD_MB=200` → yeniden başlat (arayüz otomatik güncellenir) |
| **"Yetkisiz"** hatası | yalnız token ayarlıysa; **SİSTEM** sekmesinden token gir |

---

## Geliştirme

```bash
make install      # uv sync + pre-commit
make test         # pytest
make lint         # ruff check
make format       # ruff format
make typecheck    # mypy
```

CI (`.github/workflows/ci.yml`): her push/PR'da `uv sync` + `ruff` + `pytest`.

---

## Disiplin kuralları (sistemin kalbi)

1. **Kaynak yoksa uydurma** — RAG, retrieval boşsa açıkça söyler.
2. **Test edilmeden "başarılı" deme** — backtest + OOS olmadan yasak kelime.
3. **Maliyetleri yok sayma** — komisyon + slippage her backtest'te.
4. **Look-ahead yok** — pozisyon bir bar gecikmeli uygulanır.
5. **Overfit'e karşı** — in/out-of-sample bölmesi + statik bayraklar.
6. **Determinizm** — rastgelelik daima `seed` ile.
7. **Kod yürütme yok** — strateji kuralları yalnızca güvenli regex ile.

---

## GitHub

Repo: **https://github.com/alimirbagirzade/achilles** (`main`). Klonlama:

```bash
git clone https://github.com/alimirbagirzade/achilles.git
cd achilles && uv sync --extra dev --extra web && uv run achilles init
```

---

## Proje yapısı

```
app/
  config/      ayarlar (pydantic-settings), logging
  ingestion/   pdf_parser, paper_loader, metadata, chunker
  memory/      sqlite_store, embedding_service, chroma_store,
               paper_indexer, retrieval_service
  brain/       local_llm, prompt_loader, rag_answerer, paper_summarizer,
               knowledge_card_builder, training_data_builder, model_router
  training/    dataset_builder, mlx_lora_train, adapter_registry, evaluate_model
  trading/     strategy_ir, indicators, backtester, overfit_checks,
               evaluator, strategy_generator, market_data_loader
  prompts/     *.md (Türkçe sistem/RAG/özet/kart/hipotez/kritik şablonları)
  main.py      Typer CLI
.claude/skills/  trading-research, backtest-auditor, codegen-review
evals/         disiplin/overfit/risk failure-mode JSONL setleri
tests/         pytest (çevrimdışı, fake-embedding ile çalışır)
```

---

## Lisans & sorumluluk reddi

Eğitim ve araştırma amaçlıdır. Finansal tavsiye değildir. Geçmiş performans
gelecek sonuçların garantisi değildir.
