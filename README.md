# Achilles Trader AI

> **Yerel-öncelikli AI trading _araştırma_ sistemi** — macOS Apple Silicon için.
> RAG + bilgi kartları + (opsiyonel) LoRA + disiplinli backtest.

> ⚠️ **ÖNEMLİ:** Bu bir **araştırma aracıdır**, canlı trading botu **değildir**
> ve **yatırım tavsiyesi vermez**. Tüm çıktılar test edilmesi gereken
> _hipotezlerdir_. Gerçek parayla kullanımın tüm sorumluluğu kullanıcıya aittir.

---

## 📊 Proje Durumu — _canlı_ (2026-06-03, branch `main`)

> Repo: https://github.com/alimirbagirzade/achilles · Test: **140 geçti** (offline) · Kalite: ruff+mypy temiz

| Bileşen | Durum | Detay |
|---------|-------|-------|
| **Ortam** | ✅ | Python 3.12 · uv · Ollama · `qwen2.5-coder:3b` · `mlx-lm 0.31.3` |
| **Ingestion** | ✅ | 7 arXiv PDF · 567 chunk · Ollama embedding |
| **RAG** | ✅ | `ask` 5-bölümlü cevap; MLX adapter bypass destekli |
| **LoRA eğitimi** | ✅ | `achilles_lora_v2` — 300 iter, loss 0.028, 2GB peak |
| **Trader Beyin** | ✅ | Formül çıkarımı → kavram grafiği → sentez → backtest → yansıma |
| **BTCUSD 1H backtest** | ✅ | **PASS** — 71k bar, 2017-2025, +2603%, Sharpe 2.17, DD -63.9% |
| **Pine Script export** | ✅ | `achilles pine` → TradingView v5 taslak |
| **Web arayüzü** | ✅ | 7 sekme · toplu kart · kart→backtest · eval UI |
| **Araştırma döngüsü** | 🔄 | Çalışıyor; az-işlem sorunu üzerinde iterasyon yapılıyor |
| **arXiv otomatik çekme** | 📋 | Planlandı (arxiv-research skili) |
| **Pine→TradingView push** | 📋 | Planlandı (TradingView MCP entegrasyonu) |

### Son 3 aktivite
- `2026-06-03` — BTCUSD 1H backtest: **PASS** (71k bar Binance, 2017-2025)
- `2026-06-03` — Pine Script export (`strategy_ir.to_pine()` + CLI `achilles pine`)
- `2026-06-03` — Seans protokolü + 3 proje skili + tam HANDOFF güncellendi

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
| `achilles extract-formulas` | Tüm makalelerden formülleri çıkar |
| `achilles formulas` | Çıkarılan formülleri listele |
| `achilles research "soru"` | Tam araştırma döngüsü (sentez→backtest→yansıma) |
| `achilles research-sessions` | Araştırma oturumlarını listele |
| `achilles chain-dataset` | Araştırma zincirleri → LoRA JSONL |
| `achilles pine [strateji]` | StrategyIR → TradingView Pine Script v5 |

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

Tarayıcıda `http://127.0.0.1:8765` aç. Altı sekme:

| Sekme | İçerik |
|-------|--------|
| **01 · Araştırma** | RAG soru-cevap; model seçici (Ollama / MLX adapter) |
| **02 · Makaleler** | PDF yükle/indeksle; bilgi kartı üret/gör; toplu kart; arama/filtre/sıralama |
| **03 · Backtest** | Sentetik + gerçek CSV + özel strateji IR; backtest geçmişi |
| **04 · Eğitim** | Dataset oluştur; dry-run komutu; eğitim örnekleri yönet; adapter listesi |
| **05 · Değerlendirme** | Eval seti seç, adapter seç, çalıştır; skor + bayrak + yanıt detayı |
| **06 · Sistem** | Durum, disiplin kuralları, API token |

### API uçları
| Yöntem | Uç | Açıklama |
|--------|-----|----------|
| GET | `/api/status` | Sistem durumu |
| GET | `/api/papers` | İndekslenmiş makaleler |
| POST | `/api/papers/upload` | PDF yükle (doğrulanır) → indeksle |
| POST | `/api/ingest` | Tüm PDF'leri yeniden indeksle |
| POST | `/api/ask` | RAG sorusu; `adapter_version` ile MLX inference |
| GET | `/api/card/{paper_id}` | Kaydedilmiş kartı getir (LLM gerektirmez) |
| POST | `/api/card/{paper_id}` | Bilgi kartı üret (LLM gerekli) |
| POST | `/api/cards/batch` | Kartı olmayan tüm makaleleri sırayla işle |
| POST | `/api/card/{paper_id}/backtest` | Kart hipotezlerini sentetik veride test et |
| GET | `/api/backtests` | Geçmiş backtest kayıtları |
| POST | `/api/backtest` | Sentetik / özel IR backtest |
| POST | `/api/backtest/csv` | Gerçek OHLCV CSV yükle → backtest |
| GET | `/api/training/status` | Eğitim örnek sayısı + adapter listesi |
| POST | `/api/training/dataset` | Train/valid JSONL oluştur |
| POST | `/api/training/dry-run` | mlx_lm komutu önizle |
| GET | `/api/training/examples` | Eğitim örneklerini listele |
| DELETE | `/api/training/examples/{id}` | Örnek sil |
| GET | `/api/eval/sets` | Eval seti listesi |
| POST | `/api/eval/run` | Eval çalıştır (Ollama gerekli) |
| GET | `/api/docs` | OpenAPI (Swagger) arayüzü |

### Güvenlik (özet — tamamı `SECURITY.md`)
- **Yalnız localhost'a bağlanır** (`127.0.0.1`); ağa açmak için token zorunlu.
- İsteğe bağlı **bearer token** (`ACHILLES_API_TOKEN`), sabit-zamanlı karşılaştırma.
- **CSP + güvenlik başlıkları** her yanıtta; frontend'de inline script yok.
- **Katı PDF doğrulama** (uzantı + sihirli bayt + 50 MB limit) + path-traversal koruması.
- IP başına **hız sınırı**. Kullanıcı girdisi asla çalıştırılmaz.

> Sunucuyu internete açacaksan **mutlaka** `ACHILLES_API_TOKEN` ata ve TLS'li bir
> reverse proxy arkasına koy. Ayrıntılar: [`SECURITY.md`](./SECURITY.md).

### 🌐 Arkadaşların bağlanabilir mi? (paylaşım)

Varsayılan: **yalnız senin makinende** (`127.0.0.1`) — başkası bağlanamaz (güvenli). Paylaşmak için:

**A) Aynı Wi-Fi / yerel ağ:**
```bash
echo 'ACHILLES_API_TOKEN=uzun-gizli-bir-parola' >> .env   # ZORUNLU (ağa açıyorsun)
echo 'ACHILLES_WEB_HOST=0.0.0.0' >> .env
uv run achilles-web
```
- IP'ni öğren: `ipconfig getifaddr en0` → arkadaşların `http://<o-IP>:8765` açar.
- **SİSTEM** sekmesinden token'ı girerler. macOS güvenlik duvarı sorarsa **İzin Ver**.

**B) İnternet üzerinden (geçici tünel):**
```bash
ngrok http 8765        # veya: cloudflared tunnel --url http://localhost:8765
```
Sana `https://…` bir adres verir; arkadaşların oradan (token ile) girer.

> ⚠️ Açınca kendi makinendeki modele + dosya yükleme/backtest'e erişim verirsin.
> **Güçlü token şart**, işin bitince kapat. Detay: [`SECURITY.md`](./SECURITY.md).

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
| 1 | **SİSTEM** | sekmeye tıkla | katman / disiplin / güvenlik kutuları |
| 2 | **MAKALELER** | PDF sürükle-bırak | makale satırı + chunk sayısı |
| 3 | **MAKALELER** | **BİLGİ KARTI ÜRET** → kart oluştuktan sonra **KARTI GÖR** | kart modalı (başlık, hipotezler, uyarılar…) |
| 4 | **MAKALELER** | kart modalında **⚡ HİPOTEZLERİ BACKTEST ET** | her hipotez için metrikler + verdict |
| 5 | **MAKALELER** | **⚡ TÜM KARTLARI ÜRET** (tüm PDF'ler için) | ok/skip/error listesi |
| 6 | **ARAŞTIRMA** | soru yaz → model seç (Ollama / adapter) → **SORGULA →** | kaynaklı cevap + adapter badge |
| 7 | **BACKTEST** | **SENTETİK ÇALIŞTIR →** | metrik tablosu + YARGI (✓/✕/≈) + geçmişe eklendi |
| 8 | **BACKTEST** | "Özel strateji IR" aç → JSON yapıştır → **ÖZEL IR ÇALIŞTIR →** | özel strateji adıyla sonuç |
| 9 | **EĞİTİM** | **DATASET OLUŞTUR** | train/valid satır sayısı + hash |
| 10 | **EĞİTİM** | **KOMUT ÖNIZLE →** | `python -m mlx_lm lora …` komutu |
| 11 | **DEĞERLENDİRME** | eval seti + model seç → **DEĞERLENDİR →** | skor % + bayrak sayısı + soru/cevap listesi |

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

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): her push/PR'da
`uv sync` + `ruff check` + `ruff format --check` + `mypy` + `pytest` (offline,
ollama-işaretli testler hariç). Ubuntu + Python 3.12; `mlx-lm` (Apple-Silicon) kurulmaz.

---

## 🗺️ Yol Haritası (açık işler)

**Veri & Araştırma**
- [ ] Intraday (15m/1h) OHLCV kaynağı + `market_data_loader`'a fetch fonksiyonu
- [ ] arXiv/SSRN'den otomatik makale çekme (şu an elle yükleme)
- [ ] Web: "tüm makaleyi özetle" düğmesi + ayarlanabilir `top_k`

**Eğitim (LoRA)**
- [ ] Çok-makaleli gerçek LoRA dataseti (kartlar artık otomatik) + daha fazla iter
- [ ] `evaluate` (eval setleri) akışını web'e bağla
- [ ] DPO / preference tuning (ileride, yeterli veri birikince)

**Web / UX**
- [ ] Bilgi kartını/makale detayını arayüzde görüntüleme
- [ ] Kütüphane yönetimi (makale silme)
- [ ] Strateji IR'i web'den düzenleyip backtest etme

**Çıktı & Altyapı**
- [x] ~~Pine Script / MQL5 strateji çıktısı~~ — **eklendi** (`achilles pine`)
- [x] CI (GitHub Actions) — kuruldu
- [ ] TradingView MCP entegrasyonu (doğrudan Pine yükle)
- [ ] arXiv otomatik makale çekme skili
- [ ] Araştırma döngüsünde az-işlem sorunu çözümü (reflection_agent iyileştirme)
- [ ] 32GB makineye geçince `ACHILLES_LLM_MODEL=qwen2.5-coder:14b` (profil hazır)

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
