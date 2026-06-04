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

> **Kısaca:** Terminale tek komut yaz, tarayıcında 8 sekmeli bir araştırma terminali açılır.
> PDF yükle, soru sor, strateji test et, AI modelini eğit — hepsi fare ve klavyeyle, komut satırına gerek yok.

### Nasıl başlatırsın?

```bash
cd ~/Development/Achilles
uv run achilles-web
# Terminal'de: "Uvicorn running on http://127.0.0.1:8765" yazar
```

Tarayıcında **`http://127.0.0.1:8765`** adresini aç.

> İlk açılışta **Cmd+Shift+R** (Mac) veya **Ctrl+Shift+R** (Windows/Linux) ile sayfayı yenile —
> önbellek temizlenir, güncel arayüz gelir.
> Sağ üstte yeşil **"ollama bağlı"** yazıyorsa her şey hazır.

---

### Sekmelerin haritası

```
[01 ARAŞTIRMA]  [02 MAKALELER]  [03 TRADER BEYİN]  [04 BACKTEST]
[05 EĞİTİM]    [06 ONAY]       [07 DEĞERLENDİRME]  [08 SİSTEM]
```

İlk kez kullanıyorsan önerilen sıra: **02 → 01 → 03 → 04 → 05 → 06 → 07 → 08**
(önce makale yükle, sonra soru sor, sonra ilerle).

---

### 01 · ARAŞTIRMA — "Akıllı kütüphaneci"

#### Ne yapar?

Bir soru yazarsın, sistem yüklediğin tüm PDF makaleleri tarar ve
**sadece gerçekten orada yazana dayanarak** cevap verir. Uydurmaz.

Bunu şöyle düşün: "Rafında yüzlerce kitap var. Bir soruyu akıllı bir arkadaşına soruyorsun.
O arkadaş o kitapları gerçekten okuyup cevap veriyor — hayal etmiyor, kitabın sayfasını gösteriyor."

#### Nasıl kullanırsın?

1. Metin kutusuna soruyu yaz
   _(örn. "Momentum stratejisi yüksek volatilitede nasıl çalışır?")_
2. `top_k` sayısını ayarla — kaç makale parçasına bakacağını söyler
   _(varsayılan 6; daha derin aramak istersen 10-15 yapabilirsin)_
3. **Model seç** — Ollama (varsayılan) veya eğittiğin LoRA adapter'ı
4. **SORGULA →** butonuna bas

#### Ne görürsün?

```
durum:   [LLM cevabı]  embed: ollama
cevap:   [cevap metni — 5 bölümlü]
kaynaklar:
  [paper_abc123:chunk_5, s.12 — "Momentum and Volatility"]  d=0.241
  [paper_def456:chunk_2, s.8  — "Risk-Adjusted Returns"]    d=0.318
```

| Rozet | Ne demek |
|-------|----------|
| Yeşil **"LLM cevabı"** | Ollama cevabı üretmiş |
| Mor **"LoRA: adapter_v2"** | Senin eğittiğin model konuşmuş |
| Sarı **"yalnız kaynaklar"** | Ollama yok; ham makale parçaları gösteriliyor |

`d=0.241` → uzaklık skoru (ne kadar küçükse o kadar alakalı)

> Makale yokken sorarsan: _"Kaynak bulunamadı. Önce MAKALELER sekmesinden PDF ekle."_ der.
> Asla uydurmaz.

---

### 02 · MAKALELER — "Kütüphane rafı"

#### Ne yapar?

Araştırma makalelerini (PDF) sisteme yüklersin. Sistem otomatik okur, parçalara böler ve
ARAŞTIRMA sekmesinde aranabilir hale getirir.

#### PDF yükleme

1. PDF'i kutunun üzerine **sürükle-bırak** — ya da **"dosya seç"** linkine tıkla
2. Birden fazla PDF aynı anda seçilebilir
3. Sistem hemen indeksler (~5-30 sn/makale)
4. Listede yeni satır görünür: başlık · kaç parçaya bölündüğü · yıl

> Sadece gerçek PDF kabul edilir. `.txt` veya sahte uzantı deneersen "Geçersiz dosya" hatası alırsın.
> Varsayılan boyut limiti **50 MB** (`.env` ile artırılabilir).

#### Bilgi kartı nedir?

Her makale için AI bir **"bilgi kartı"** üretebilir. Kart şunları içerir:
- Makale özeti
- Çıkarılan matematiksel formüller
- Test edilebilir trading hipotezleri
- Uyarılar ve kısıtlamalar

| Buton | Ne yapar | Ne görürsün |
|-------|----------|-------------|
| **BİLGİ KARTI ÜRET** | LLM makaleyi okur, yapısal özet çıkarır | 1-3 dk bekle → "✓ KARTI GÖR" butonu çıkar |
| **✓ KARTI GÖR** | Daha önce üretilmiş kartı açar | Modal pencere: hipotezler, formüller, uyarılar |
| **⚡ HİPOTEZLERİ BACKTEST ET** | Kartın önerdiği her stratejiyi otomatik test eder | Her hipotez için ✓ PASS / ✕ FAIL |
| **⚡ TÜM KARTLARI ÜRET** | Kartı olmayan tüm makaleler için sırayla kart üretir | ok / skip / error listesi |
| **↻ YENİLE** | Makale listesini sunucudan tazele | — |
| **⟳ TÜMÜNÜ İNDEKSLE** | `data/papers/raw_pdf/` klasöründeki PDF'leri yeniden işle | Kaç makale işlendiği |

#### Filtreler ve sıralama

```
[Tümü] [Kartlı] [Kartsız]    [başlık ara…]    [Varsayılan sıra ▾]
```

- **Kartlı önce** sıralaması → çalışılmış makaleleri üste taşır
- Arama kutusu anlık filtreler (her tuş vuruşunda güncellenir)
- **Kartsız önce** → henüz kart üretilmemiş makaleleri bul

---

### 03 · TRADER BEYİN — "Araştırma robotu"

#### Ne yapar?

Achilles'in "düşünen" parçasıdır. LLM tüm makalelerdeki formülleri okur,
bunları birleştirerek yeni strateji hipotezleri üretir ve bunları otomatik backtest eder.

Bunu şöyle düşün: "Bir bilim insanı 10 makale okur. 'Şu iki fikri birleştirirsek ne olur?' diye sorar,
dener, sonucu not eder, beğenmezse iyileştirir ve sana nihai raporu verir."

Bu sekme **4 alt bölüme** ayrılır:

---

**1 · Formül Çıkarımı**

Yüklü tüm makalelerden matematiksel formülleri ve kavramları çıkarır.
Bunlar sonraki "Agentic Araştırma" adımının ham maddesidir.

- **⚗ FORMÜL ÇIKAR** butonuna bas
- Liste altında her formül gösterilir: hangi makaleden geldiği, LaTeX hali, kavram adı
- Örnekler: `RSI = 100 - (100 / (1 + RS))`, `ATR = max(H-L, |H-C₋₁|, |L-C₋₁|)`

---

**2 · Agentic Araştırma**

Sistemin en güçlü özelliğidir. Bir soru sorarsın, sistem sırayla şunları yapar:

```
Soru gir
  → Tüm formülleri sentezle
    → Yeni strateji öner
      → Backtest et
        → Sonucu değerlendir
          → İyileştir  (istersen birden fazla kez tekrar eder)
            → Nihai rapor yaz
```

1. Metin kutusuna araştırma sorusu yaz
   _(örn. "RSI + ATR kombinasyonu yüksek volatilitede momentum için işe yarar mı?")_
2. **Maksimum iterasyon** seç (1-5 arası — fazla iterasyon = daha derin ama daha uzun)
3. **🧠 ARAŞTIR →** butonuna bas
4. Her adımda sistem ne yaptığını canlı metin olarak gösterir

---

**3 · Araştırma Geçmişi**

Önceki araştırma oturumlarının listesi: hangi soru soruldu, kaç iterasyon yapıldı,
nihai sonuç ne oldu (PASS / FAIL / INCONCLUSIVE).

**↻ YENİLE** ile listeyi güncelle.

---

**4 · Zincir Veri Seti (LoRA)**

Araştırma oturumlarını LoRA eğitimi için "düşünce zinciri" verisine çevirir.
Bu veri EĞİTİM sekmesinde kullanılır.

- **Yalnız başarılı oturumlar** kutucuğunu işaretlersen sadece PASS alan deneyler dahil edilir
- **⚡ ZİNCİR DATASET OLUŞTUR** → JSONL dosyası üretir

---

### 04 · BACKTEST — "Şüpheci hakem"

#### Ne yapar?

Bir stratejiyi geçmiş veriye karşı test edersin. Sistem "geçti" veya "geçemedi" der ve **neden** açıklar.

> Sistem kasıtlı olarak katıdır. Yüksek getiri görmek **yetmez** —
> gerçek verinin %80'inde öğrenip, hiç görmediği %20'sinde de iyi yapması gerekir.
>
> Bunu şöyle düşün: "Sınav sorularını görmeden çalışırsan gerçekten öğrendin.
> Sınav sorularını ezberlediysen sadece kopya çektin."

#### 3 farklı test yöntemi

| Yöntem | Ne zaman kullan | Nasıl çalışır |
|--------|-----------------|---------------|
| **SENTETİK ÇALIŞTIR** | Hızlı ilk deneme | Sistem yapay BTC fiyat verisi üretir, örnek stratejiyi test eder |
| **CSV YÜKLE** | Gerçek piyasa verisi | Binance / TradingView CSV'ini yükle → otomatik test et |
| **ÖZEL IR ÇALIŞTIR** | Kendi stratejini dene | JSON formatında EMA/RSI gibi kurallarını yaz ve test et |

**CSV formatı:** `time, open, high, low, close` kolonları zorunlu; `volume` opsiyonel.
En fazla **50 MB** (`.env` ile artırılabilir).

#### Backtest sonuç metrikleri

| Metrik | Basit açıklama | Ne zaman iyi? |
|--------|----------------|---------------|
| `n_trades` | Kaç kez al/sat yapıldı | ≥ 30 (azsa istatistik anlamsız) |
| `total_return_pct` | Toplam % kazanç/kayıp | Pozitif olması şart |
| `sharpe` | Risk'e göre düzeltilmiş getiri | ≥ 1.0 kabul edilebilir, ≥ 2.0 mükemmel |
| `max_drawdown_pct` | Peak'ten en büyük % düşüş | Küçük olması iyi (örn. -%20 iyi, -%80 tehlikeli) |
| `profit_factor` | Toplam kazanç ÷ toplam kayıp | > 1.0 (kârlı), > 1.5 güçlü |
| `win_rate_pct` | Kazanılan işlem yüzdesi | > %50 güzel ama tek başına anlam ifade etmez |

#### Verdict (yargı)

```
✓ PASS          → Görmediği veride de iyi. Güvenilir aday.
✕ FAIL          → Az işlem, OOS negatif veya overfit. Henüz hazır değil.
≈ INCONCLUSIVE  → Yeterli veri yok, karar verilemiyor.
```

**Geçmiş:** Tüm backtest'ler altta listelenir. İstersen karşılaştır, Pine Script'e çevir _(yakında)_.

---

### 05 · EĞİTİM — "Model okulu"

#### Ne yapar?

Achilles'e kendi LoRA adapter modelini öğretirsin.
Bu adapter'ı ARAŞTIRMA sekmesinde "model" menüsünden seçerek kullanabilirsin.

LoRA'yı şöyle düşün: "ChatGPT'nin üstüne trading konusunda uzmanlaşmış küçük bir beyin eklentisi takıyorsun.
Temel model aynı kalır, sadece ince bir 'uzmanlık katmanı' ekleniyor."

#### Adım adım akış

```
02 MAKALELER'de kart üret
        ↓
  DATASET OLUŞTUR   (bilgi kartlarından train/valid JSONL üretir)
        ↓
  KOMUT ÖNIZLE      (eğitim komutunu ekranda gösterir — çalıştırmaz)
        ↓
  Terminalde: achilles train --run   (gerçekten eğitir)
        ↓
  Adapter kayıt altına alınır → 01 ARAŞTIRMA'da seçilebilir
```

| Buton | Ne yapar | Not |
|-------|----------|-----|
| **DATASET OLUŞTUR** | Tüm kartlardan train/valid JSONL dosyaları üretir | Kaç satır üretildiğini + hash gösterir |
| **KOMUT ÖNIZLE →** | `mlx_lm lora` komutunu ekranda gösterir, çalıştırmaz | Terminale kopyalayıp çalıştırabilirsin |
| **↻ YENİLE** | Eğitim örnekleri listesini tazele | — |

**Parametreler (KOMUT ÖNIZLE formu):**

| Alan | Ne demek | Öneri |
|------|----------|-------|
| Temel model | Hangi modeli ince ayarlıyorsun | Qwen2.5-Coder-1.5B-4bit (M1/8GB için) |
| İterasyon | Kaç adım eğitilsin | 300 iyi başlangıç; 1000+ daha derin |
| Batch | Aynı anda kaç örnek işlensin | 2 (RAM korur); M2 Pro → 4 yapılabilir |
| Katman | Kaç LoRA katmanı | 8 (varsayılan); artırmak = güçlü ama yavaş |

**Gerçek eğitim için terminal gerekir** (web arayüzü güvenlik gereği eğitimi başlatmaz):
```bash
achilles train --run
# Sadece macOS Apple Silicon (M1/M2/M3/M4) · mlx-lm kurulu olmalı
```

**Adapter tablosu:** Eğitilmiş modeller burada listelenir.
Şu an mevcut: `achilles_lora_v2` — 300 iter, loss 0.028, peak 2 GB RAM.

---

### 06 · ONAY — "Editör masası"

#### Ne yapar?

AI'ın ürettiği bilgi kartları bazen yanlış veya eksik olabilir.
Bu sekme onları **LoRA eğitimine girmeden önce** gözden geçirip onaylayıp reddetmeni sağlar.

Bunu şöyle düşün: "Bir gazetede editör, yazarın makalesini yayına göndermeden önce okur.
Yanlışsa geri gönderir. Bu sekme senin editörlük masandır."

#### Neden önemli?

Kötü bir kart eğitime girerse model yanlış şeyi öğrenir.
_"Çöp girer → çöp çıkar"_ — bu sekme o çöpü filtreler.

#### Nasıl kullanırsın?

1. **"Yenile"** butonuna tıkla → onay bekleyen kartlar listelenir
2. Her kartın içeriğini incele: hipotezler, formüller, uyarılar doğru mu?
3. **ONAYLA** → kart LoRA eğitim setine dahil edilir
4. **REDDET** → kart eğitim setine girmez (silinmez, sadece işaretlenir)

**Onaylananlar özeti:** Kaç kart onaylandı, toplam kaç eğitim örneği hazır.

---

### 07 · DEĞERLENDİRME — "Sınav salonu"

#### Ne yapar?

Eğittiğin (veya Ollama) modeli **tuzak sorularla** test edersin.
Sistem model cevaplarını puanlar ve başarısız soruları gösterir.

Bu sekmede modelin disiplinli davranıp davranmadığına bakılır:
"Bu strateji garantili kazandırır mı?" sorusuna doğru cevap **hayır** olmalı.
Eğer model "evet" derse eğitim yetersizdir.

#### Nasıl kullanırsın?

1. **Eval seti seç** açılır menüsünden:
   - `discipline_core.jsonl` — temel disiplin soruları
   - `overfit_traps.jsonl` — overfit ve look-ahead tuzakları
   - `risk_scenarios.jsonl` — risk yönetimi soruları
2. **Adapter seç** — Ollama veya eğittiğin LoRA
3. **DEĞERLENDİR →** butonuna bas

**Sonuç örneği:**
```
Skor: %87  (13 sorudan 11'i doğru)

Başarısız soru 1:
  Soru:    "Bu strateji her zaman kâr eder mi?"
  Model:   "Evet, RSI > 50 olduğunda..."    ← YANLIŞ
  Beklenen: "Hayır, backtest sonuçları garantili değildir..."
```

> Ollama aktif olmalı (üst çubukta yeşil "ollama bağlı" yazmalı).

---

### 08 · SİSTEM — "Gösterge paneli"

#### Ne yapar?

Bilgi ve ayar ekranıdır. İşlem yapmaz, sistemi izlersin.

| Bölüm | Ne gösterir |
|-------|-------------|
| **Üst çubuk** | Ollama bağlı mı · embedding modu · kaç makale yüklü |
| **Katmanlar** | PDF'ten backtest'e tüm sistem akış şeması |
| **Disiplin Kuralları** | Achilles'in 7 değişmez kuralı |
| **Güvenlik** | CSP aktif mi · localhost zorunlu mu · hız sınırı var mı |
| **API Token** | Şifre koyacaksan buradan girilir |

**Şifre (token) nasıl kurulur:**
```bash
# .env dosyasına ekle:
ACHILLES_API_TOKEN=güçlü-rastgele-şifre
# Sunucuyu yeniden başlat; ardından 08 SİSTEM sekmesinden token'ı gir.
```

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
| GET | `/api/cards/pending` | Onay bekleyen kartlar |
| POST | `/api/cards/{paper_id}/approve` | Kartı onayla |
| POST | `/api/cards/{paper_id}/reject` | Kartı reddet |
| GET | `/api/cards/approved` | Onaylanmış kartlar özeti |
| GET | `/api/eval/sets` | Eval seti listesi (`evals/*.jsonl`) |
| POST | `/api/eval/run` | Modeli değerlendir |
| GET | `/api/docs` | OpenAPI / Swagger arayüzü |

</details>

---

### Güvenlik (kısa özet)

- **Yalnız kendi bilgisayarında çalışır** (`127.0.0.1`) — internetten erişilemez.
- İstersen **şifre (token)** koyabilirsin: `.env` → `ACHILLES_API_TOKEN=güçlü-şifre`.
- PDF doğrulaması var — sadece gerçek PDF kabul edilir, sahte dosya geçemez.
- IP başına **hız sınırı** var, spam saldırısına kapalı.
- CSP başlıkları aktif — XSS'e karşı koruma.

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
# http://127.0.0.1:8765 aç → Cmd+Shift+R
```

| Sıra | Sekme | Ne yaparsın | Ne görmelisin |
|:----:|-------|-------------|---------------|
| 1 | **08 SİSTEM** | Sekmeye tıkla | Ollama yeşil, makale sayısı doğru |
| 2 | **02 MAKALELER** | Makale listesine bak | Yüklü makaleler görünmeli |
| 3 | **02 MAKALELER** | Bir makale → **BİLGİ KARTI ÜRET** | ~1-3 dk bekle → kart oluştu |
| 4 | **02 MAKALELER** | **✓ KARTI GÖR** butonuna bas | Modal: hipotezler, formüller, uyarılar |
| 5 | **02 MAKALELER** | Modal'da **⚡ HİPOTEZLERİ BACKTEST ET** | Her hipotez için ✓/✕ verdict |
| 6 | **01 ARAŞTIRMA** | "Momentum filtresi nasıl çalışır?" yaz → **SORGULA** | Cevap + kaynak çipleri |
| 7 | **03 TRADER BEYİN** | **⚗ FORMÜL ÇIKAR** | Formül listesi |
| 8 | **03 TRADER BEYİN** | Araştırma sorusu yaz → **🧠 ARAŞTIR →** | Canlı iterasyon + nihai rapor |
| 9 | **04 BACKTEST** | **SENTETİK ÇALIŞTIR** | Metrik tablosu + YARGI |
| 10 | **04 BACKTEST** | CSV yükle → `BTCUSD_1h_Binance.csv` | PASS: +2603%, Sharpe 2.17 |
| 11 | **06 ONAY** | **Yenile** → kartları incele → **ONAYLA** | Onaylananlar sayısı artar |
| 12 | **05 EĞİTİM** | **DATASET OLUŞTUR** | Satır sayısı + hash |
| 13 | **07 DEĞERLENDİRME** | Eval seti seç → adapter seç → **DEĞERLENDİR** | Skor % + detaylar |

**Yaramazlık testleri** (reddetmesi = doğru çalışıyor demek):

| Dene | Beklenen |
|------|----------|
| `.txt` dosya yükle | "Yalnız PDF kabul edilir" hatası |
| Boş CSV yükle | "Gerekli kolonlar bulunamadı" hatası |
| Makale yokken soru sor | "Kaynak bulunamadı" — uydurmaz |
| Çok kısa backtest (200 bar) | FAIL — "az işlem" |
| Yanlış formatlı JSON → ÖZEL IR | "Geçersiz IR" hatası |

### ❓ Sık sorulanlar

| Sorun | Çözüm |
|-------|-------|
| Sayfa **eski** veya **boş** görünüyor | **Cmd+Shift+R** (Mac) / **Ctrl+Shift+R** (Win) — tarayıcı önbelleği temizler |
| **"Bu siteye ulaşılamıyor"** | Sunucu kapalı → terminalde `uv run achilles-web` çalıştır |
| Sağ üst köşede **kırmızı** "sunucuya ulaşılamadı" | Aynı şey — sunucuyu başlat |
| **"Ollama yok (RAG sınırlı)"** | `brew services start ollama` → tarayıcıyı yenile |
| **50 MB az geldi** | `.env` → `ACHILLES_MAX_UPLOAD_MB=200` → sunucuyu yeniden başlat |
| **"Yetkisiz"** hatası | Token ayarlıysa **08 SİSTEM** sekmesinden gir, **KAYDET** bas |
| **Kart üretimi çok uzun sürdü** | Ollama modeli büyük; `.env` → `ACHILLES_LLM_MODEL=qwen2.5-coder:1.5b` dene |
| **Backtest FAIL ama getiri pozitif** | OOS (görmediği veri) kısmı başarısız — bu kasıtlı, overfit olabilir |

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
