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
| **Araştırma döngüsü** | 🔄 | Gerçek 71k bar · 2400+ işlem üretiyor · drawdown optimizasyonu devam ediyor |
| **arXiv otomatik çekme** | 📋 | Planlandı (arxiv-research skili) |
| **Pine→TradingView push** | 📋 | Planlandı (TradingView MCP entegrasyonu) |

### Son aktiviteler
- `2026-06-03` — Araştırma döngüsü gerçek 71k bar ile çalışıyor; 2400+ işlem/iterasyon
- `2026-06-03` — Web arayüzü kullanım kılavuzu 12 yaş seviyesinde yeniden yazıldı
- `2026-06-03` — BTCUSD 1H backtest: **PASS** (71k bar Binance, 2017-2025, Sharpe 2.17)
- `2026-06-03` — Pine Script export (`strategy_ir.to_pine()` + CLI `achilles pine`)

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

## Web Arayüzü 🖥️

> **Kısaca:** Tarayıcından Achilles'e bağlanıp soru sorabilir, makale yükleyebilir,
> strateji test edebilir ve modeli eğitebilirsin — komut satırına gerek yok.

### Nasıl başlatırsın?

```bash
cd ~/Development/Achilles
uv run achilles-web
# Terminal'de "Uvicorn running on http://127.0.0.1:8765" yazar
```

Tarayıcında `http://127.0.0.1:8765` aç. **Cmd+Shift+R** ile yenile.
Sağ üstte yeşil **"ollama bağlı"** yazıyorsa her şey hazır.

---

### Sekmeler — ne işe yarar?

#### 01 · ARAŞTIRMA — "Akıllı kütüphaneci"

Buraya bir soru yazarsın, sistem yüklediğin tüm PDF makaleleri tarar ve
**sadece gerçekten orada yazana dayanarak** cevap verir. Uydurmaz.

```
Sen: "Momentum stratejisi yüksek volatilitede nasıl çalışır?"
Achilles: [makale bölümlerini okur] → 5 bölümlü cevap
  1. Kısa cevap
  2. Kaynaklar (hangi makalenin kaçıncı sayfası)
  3. Akademik bulgu
  4. Trading hipotezi
  5. Test etmek için ne yapmalı
```

**Model seçici:** Sağ üstte Ollama (varsayılan) veya eğittiğin LoRA adapter'ı seçebilirsin.
LoRA adapter seçersen cevap eğitilmiş modelden gelir + üstünde badge çıkar.

**Durum:** ✅ Tam çalışıyor · 7 PDF · 567 chunk taranıyor

---

#### 02 · MAKALELER — "Kütüphane rafı"

Araştırma makalelerini buraya yüklersin. Sistem otomatik okur, parçalar ve arar hale getirir.

**Yapabileceklerin:**

| Buton | Ne yapar | Ne görürsün |
|-------|----------|-------------|
| PDF sürükle-bırak | Makaleyi sisteme yükler ve indeksler | Makale satırı + kaç parçaya bölündüğü |
| **BİLGİ KARTI ÜRET** | LLM tüm makaleyi okur, yapısal özet çıkarır | ~1-3 dk bekle (3b model) |
| **KARTI GÖR** | Daha önce üretilmiş kartı açar | Modal pencere: hipotezler, formüller, uyarılar |
| **⚡ HİPOTEZLERİ BACKTEST ET** | Kartın önerdiği her stratejiyi otomatik test eder | Her hipotez için ✓/✕ verdict |
| **⚡ TÜM KARTLARI ÜRET** | Kartı olmayan tüm makaleler için sırayla kart üretir | ok/skip/error listesi |
| Arama kutusu | Makale başlığında filtrele | Anlık filtreleme |
| Filtre: Tümü/Kartlı/Kartsız | Kartı olan/olmayan makaleleri ayır | — |

**Durum:** ✅ Tam çalışıyor · 7 makale yüklü · kartlı olanlar mevcut

---

#### 03 · BACKTEST — "Şüpheci hakem"

Bir stratejiyi test edersin. Sistem sana "geçti" veya "geçemedi" der ve **neden** açıklar.

> Önemli: Sistem kasıtlı olarak katıdır. Yüksek getiri görmek yetmez —
> gerçek verinin %80'inde öğrenip %20'sinde (görmediği veri) de iyi yapması lazım.

**3 farklı test yöntemi:**

| Yöntem | Kullanım | Açıklama |
|--------|----------|----------|
| **SENTETİK ÇALIŞTIR** | "Hızlı deneme" için | Sistem yapay BTC verisi üretir, mevcut stratejiyi test eder |
| **CSV YÜKLE → TEST ET** | Gerçek piyasa verisi için | Binance/Coinbase CSV dosyanı yükle, test et |
| **ÖZEL IR ÇALIŞTIR** | Kendi stratejini dene | JSON formatında kendi kurallarını yaz |

**Backtest sonuç metrikleri:**

| Metrik | Ne demek |
|--------|----------|
| `n_trades` | Kaç kez alım/satım yapıldı (30'dan az → istatistik zayıf) |
| `total_return_pct` | Toplam kazanç/kayıp yüzdesi |
| `sharpe` | Risk'e göre düzeltilmiş getiri (2+ iyi, 1+ kabul edilebilir) |
| `max_drawdown_pct` | En kötü düşüş (örn. -63% = peak'ten -63% düştü) |
| `profit_factor` | Kazanç/kayıp oranı (1+ = kârlı) |
| `win_rate_pct` | Kazanılan işlem yüzdesi |

**Verdict (yargı):**
- ✓ **PASS** — Gerçek verinin görmediği kısımda da iyi. Güvenilir aday.
- ✕ **FAIL** — Az işlem, OOS negatif veya overfit. Henüz hazır değil.
- ≈ **INCONCLUSIVE** — Yeterli veri yok, karar verilemiyor.

**Geçmiş:** Tüm backtest'ler listede kalır, karşılaştırabilirsin.

**Durum:** ✅ Çalışıyor · 14 backtest kayıtlı · 2 PASS (BTCUSD 1H Binance) · 12 FAIL

**Yakında:** Pine Script export butonu (stratejiyi TradingView'e gönder)

---

#### 04 · EĞİTİM — "Model okulu"

Achilles'in kendi LoRA modelini eğitirsin. Bu modeli sonraki sorularda kullanabilirsin.

**Nasıl çalışır (adım adım):**

```
1. Bilgi kartları (makalelerden) → otomatik eğitim örnekleri üretir
2. "DATASET OLUŞTUR" → train + validation JSONL dosyaları
3. "KOMUT ÖNIZLE" → mlx_lm lora komutunu gösterir (çalıştırmaz)
4. Terminalde: achilles train --run  (gerçekten eğitir, macOS Apple Silicon gerekli)
5. Adapter registry'e kaydedilir → ARAŞTIRMA sekmesinde seçilebilir
```

| Buton | Ne yapar |
|-------|----------|
| **DATASET OLUŞTUR** | Tüm kartlardan train/valid JSONL üretir |
| **KOMUT ÖNIZLE** | Eğitim komutunu gösterir (çalıştırmaz — önce görmek için) |
| Eğitim örnekleri listesi | Hangi örnek var, hangisini silmek istiyorsun |
| Adapter tablosu | Kaç adapter var, ne zaman eğitildi, hangi base model |

**Şu anki eğitilmiş model:** `achilles_lora_v2` — 300 iterasyon, loss 0.028, peak 2GB RAM

**Durum:** ✅ Çalışıyor · achilles_lora_v2 mevcut · Apple Silicon MLX

---

#### 05 · DEĞERLENDİRME — "Sınav salonu"

Eğittiğin modeli "tuzak sorularla" test edersin. Sistem cevapları puanlar.

**Eval setleri** (`evals/` klasöründe):
- `discipline_core.jsonl` — "Garanti kazandırır mı?" gibi tuzak sorular (hayır demeli)
- `overfit_traps.jsonl` — Overfit, look-ahead gibi yasaklara dair sorular
- `risk_scenarios.jsonl` — Risk yönetimi soruları

```
Adapter seç + Eval seti seç → DEĞERLENDİR →
  Skor: %87 (13 sorudan 11'i doğru)
  2 bayrak: [soru göster] [modelin cevabı göster] [doğru cevap göster]
```

**Durum:** ✅ Çalışıyor

---

#### 06 · SİSTEM — "Gösterge paneli"

Bilgi amaçlı — işlem yapmazsın.

| Kutu | Ne gösterir |
|------|-------------|
| Bağlantı durumu | Ollama bağlı mı, embedding modu ne, kaç makale var |
| Mimari diyagramı | PDF'ten backtest'e kadar tüm katmanlar |
| Disiplin kuralları | Sistemin değişmez 7 kuralı (kaynak uydurma yok, look-ahead yok…) |
| Güvenlik özeti | Token zorunlu mu, CSP aktif mi |
| API token girişi | Token gerektiriyorsa buradan girilir |

**Durum:** ✅ Çalışıyor

---

### API Uçları (tam liste)

<details>
<summary>Geliştiriciler için — tıkla aç</summary>

| Yöntem | Uç | Açıklama |
|--------|-----|----------|
| GET | `/api/status` | Sistem durumu (Ollama, model, sayımlar) |
| GET | `/api/papers` | İndekslenmiş makaleler |
| POST | `/api/papers/upload` | PDF yükle (sihirli bayt + boyut doğrulama) → indeksle |
| POST | `/api/ingest` | Tüm PDF'leri yeniden indeksle |
| POST | `/api/ask` | RAG sorusu; `adapter_version` ile MLX inference |
| GET | `/api/card/{paper_id}` | Kaydedilmiş kartı getir (LLM gerektirmez) |
| POST | `/api/card/{paper_id}` | Bilgi kartı üret (Ollama gerekli) |
| POST | `/api/cards/batch` | Kartı olmayan tüm makaleleri sırayla işle |
| POST | `/api/card/{paper_id}/backtest` | Kart hipotezlerini sentetik veride test et |
| GET | `/api/backtests` | Geçmiş backtest kayıtları |
| POST | `/api/backtest` | Sentetik / özel IR backtest |
| POST | `/api/backtest/csv` | Gerçek OHLCV CSV yükle → backtest |
| POST | `/api/backtest/{id}/pine` | *(yakında)* Backtest'i Pine Script'e çevir |
| GET | `/api/research/formulas` | Çıkarılan formüller |
| GET | `/api/research/graph` | Kavram grafiği |
| POST | `/api/research/extract` | Formül çıkarımı çalıştır |
| POST | `/api/research/run` | Araştırma döngüsü çalıştır |
| GET | `/api/research/sessions` | Araştırma oturumları + öğrenme geçmişi |
| POST | `/api/research/chain-dataset` | Zincir → LoRA eğitim verisi |
| GET | `/api/training/status` | Eğitim örnek sayısı + adapter listesi |
| POST | `/api/training/dataset` | Train/valid JSONL oluştur |
| POST | `/api/training/dry-run` | mlx_lm komutunu önizle (çalıştırmaz) |
| GET | `/api/training/examples` | Eğitim örneklerini listele |
| DELETE | `/api/training/examples/{id}` | Örnek sil |
| GET | `/api/eval/sets` | Eval seti listesi (`evals/*.jsonl`) |
| POST | `/api/eval/run` | Modeli değerlendir |
| GET | `/api/docs` | OpenAPI / Swagger arayüzü |

</details>

---

### Güvenlik (kısa özet)

- **Yalnız kendi bilgisayarında çalışır** (`127.0.0.1`) — internetten erişilemez.
- İstersen **şifre (token)** koyabilirsin: `.env` dosyasına `ACHILLES_API_TOKEN=güçlü-şifre`.
- PDF doğrulaması var — sadece gerçek PDF kabul edilir, sahte dosya geçemez.
- IP başına **hız sınırı** var.

**Arkadaşına açmak istersen:**
```bash
# .env dosyasına ekle:
ACHILLES_API_TOKEN=uzun-rastgele-bir-sifre
ACHILLES_WEB_HOST=0.0.0.0
# Kendi IP'ni bul:
ipconfig getifaddr en0
# Arkadaşın: http://<o-IP>:8765 (token gerekli)
```

---

### Adım Adım Test Rehberi (ilk açılışta uygula)

```bash
cd ~/Development/Achilles
uv run achilles-web
# http://127.0.0.1:8765 aç, Cmd+Shift+R
```

| Sıra | Sekme | Ne yaparsın | Ne görmelisin |
|:----:|-------|-------------|---------------|
| 1 | **SİSTEM** | Sekmeye tıkla | Ollama yeşil, makale sayısı doğru |
| 2 | **MAKALELER** | Makale listesine bak | 7 makale görünmeli |
| 3 | **MAKALELER** | Bir makale → **BİLGİ KARTI ÜRET** | ~1-3 dk, kart oluştu mesajı |
| 4 | **MAKALELER** | **KARTI GÖR** butonuna bas | Modal açılır: hipotezler, formüller |
| 5 | **MAKALELER** | Modal içinde **⚡ HİPOTEZLERİ BACKTEST ET** | Her hipotez için ✓/✕ |
| 6 | **ARAŞTIRMA** | "Momentum filtresi nasıl çalışır?" yaz → **SORGULA** | 5 bölümlü cevap + kaynak |
| 7 | **BACKTEST** | **SENTETİK ÇALIŞTIR** | Metrik tablosu + YARGI |
| 8 | **BACKTEST** | CSV yükle butonu → `BTCUSD_1h_Binance.csv` → test | PASS: +2603%, Sharpe 2.17 |
| 9 | **EĞİTİM** | **DATASET OLUŞTUR** | Satır sayısı + hash |
| 10 | **DEĞERLENDİRME** | Eval seti seç → adapter seç → **DEĞERLENDİR** | Skor % + detaylar |

**Yaramazlık testleri (reddetmesi = iyi çalışıyor demek):**

| Dene | Beklenen |
|------|---------|
| `.txt` dosya yükle | "Yalnız PDF kabul edilir" hatası |
| Boş CSV yükle | "Gerekli kolonlar bulunamadı" hatası |
| Makale yokken soru sor | "Kaynak bulunamadı" — uydurmaz |
| Çok kısa backtest | FAIL — "az işlem" |

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
