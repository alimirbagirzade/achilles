# 🏛️ Achilles Trader AI

> **Yerel çalışan, gizlilik-öncelikli AI araştırma sistemi** — macOS Apple Silicon için.
> Akademik finans makalelerini okur, trade hipotezleri üretir, backtest eder, sonuçtan öğrenir.

> ⚠️ **Bu bir araştırma aracıdır — canlı bot DEĞİLDİR ve yatırım tavsiyesi VERMEZ.**
> Tüm çıktılar test edilmesi gereken _hipotezlerdir_. Gerçek parayla kullanımın sorumluluğu tamamen size aittir.

---

## ⚡ 30 Saniyede Başla

```bash
# 1. Kurulum
uv sync
uv run achilles init

# 2. Ollama modellerini indir (ilk seferde gerekli)
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text

# 3. Web arayüzünü başlat
uv run achilles-web
# → Tarayıcıda aç: http://127.0.0.1:8765
```

---

## 📊 Sistem Durumu

| Bileşen | Durum | Detay |
|---------|:-----:|-------|
| 🐍 Python / Ortam | ✅ | Python 3.12 · uv · ruff · mypy · 329 test geçiyor |
| 📚 PDF → RAG | ✅ | 7 makale · 567 chunk · Ollama embedding |
| 🧠 Trader Beyin | ✅ | Formül çıkarımı → sentez → backtest → yansıma |
| 📈 Backtest | ✅ | BTCUSD 1H · 71k bar · Sharpe 2.17 · +2603% |
| 📝 Pine Script | ✅ | `achilles pine` → TradingView v5 taslak |
| 🎓 LoRA Eğitimi | ✅ | `achilles_lora_v2` · 300 iter · loss 0.028 |
| 📊 Paper Mastery | ✅ | 0-100 RAG kalite skoru · deterministik · LLM gerektirmez |
| 🖥️ Web Arayüzü | ✅ | 8 sekme · PDF yükle · soru sor · backtest et |

---

## 🗺️ Nasıl Çalışır? (Büyük Resim)

```
📄 PDF Makaleler
      │
      ▼  [ingestion]
📦 SQLite + ChromaDB  ←── tüm veriler burada saklanır
      │
      ▼  [brain]
💬 RAG Yanıtlama       ←── "Bu makalede ne yazıyor?" soruları
🃏 Bilgi Kartları       ←── formüller + hipotezler çıkarma
      │
      ▼  [trading]
🔬 Strateji IR          ←── hipotez → makine-okunur kural seti
📉 Backtest             ←── geçmiş veriyle test (overfit korumalı)
      │
      ▼  [training]
🎓 LoRA Eğitimi         ←── başarılı araştırmaları modele öğret
📊 Paper Mastery        ←── RAG kalitesini ölç ve izle
```

> **Tasarım felsefesi:** _"Aksi kanıtlanana kadar her strateji güvenilmezdir."_
> Sistem kasıtlı olarak şüphecidir — düşük bar geçmez, overfit yakalanan strateji FAIL alır.

---

## 🔍 RAG mı, LoRA mı? (İkisi de var, farklı şeyler yapar)

Bu iki kavram sıkça karıştırılır. Achilles her ikisini birlikte kullanır — ama **farklı amaçlarla**.

### RAG (Retrieval-Augmented Generation) — Anlık Bellek

> "Kütüphanede bir soru soruyorsun. Sistem o an doğru sayfayı çıkarıp sana gösteriyor."

**Ne zaman çalışır:** Her ARAŞTIRMA sekmesi sorgusunda, anında.

```
Sen: "Momentum anomalisi ne zaman çalışmaz?"
         │
         ▼
Soru → vektöre çevrilir (nomic-embed-text)
         │
         ▼
ChromaDB: En benzer 6 makale parçasını bulur (cosine similarity)
         │
         ▼
LLM (Ollama): Parçaları okuyup cevap üretir
         │
         ▼
Cevap + kaynak (hangi makalenin kaçıncı parçası)
```

**Çıktılar nereye kaydedilir:**

| Çıktı | Dosya/Tablo |
|-------|-------------|
| Makale vektörleri | `storage/vector_db/` (ChromaDB) |
| Makale metadata | `storage/sqlite/achilles_trader_ai.db` → `papers` tablosu |
| RAG sorgu geçmişi | `storage/sqlite/...` → `rag_queries` tablosu |

**Sınırı:** Makale yoksa "bilmiyorum" der. Model zayıfsa iyi sentez yapamaz.

---

### LoRA (Low-Rank Adaptation) — Kalıcı Öğrenme

> "Kütüphaneciye trading kitapları okutuyorsun. Artık sormadan kendisi biliyor."

**Ne zaman çalışır:** Sadece `achilles train --run` yazınca — bir kez, ~10 dakika sürer.

```
Onaylı bilgi kartları (06 ONAY sekmesi)
         │
         ▼ achilles dataset
data/training/jsonl/train.jsonl   (instruction/output çiftleri)
data/training/jsonl/valid.jsonl   (doğrulama seti)
         │
         ▼ achilles train --run
mlx-lm lora  (Apple Silicon GPU, ~0.17% parametre eğitilir)
         │
         ▼
models/adapters/achilles_lora_v3/   ← adapter ağırlıkları
models/adapters/achilles_lora_v3.meta.json  ← versiyon + hash
         │
         ▼
01 ARAŞTIRMA → "model" menüsünden seç → LoRA ile cevap al
```

**Çıktılar nereye kaydedilir:**

| Çıktı | Dosya |
|-------|-------|
| Eğitim verisi | `data/training/jsonl/train.jsonl` |
| Doğrulama verisi | `data/training/jsonl/valid.jsonl` |
| Adapter ağırlıkları | `models/adapters/<isim>/` |
| Adapter metadata | `models/adapters/<isim>.meta.json` |
| Adapter kayıt (DB) | `storage/sqlite/...` → `adapters` tablosu |

---

### RAG + LoRA Birlikte Çalışması

01 ARAŞTIRMA sekmesinde **"model"** açılır menüsünden seç:

```
┌─────────────────────────────────┬──────────────────────────────────────────┐
│ Seçim                           │ Ne olur                                  │
├─────────────────────────────────┼──────────────────────────────────────────┤
│ Ollama (varsayılan)             │ Saf RAG: genel model + makale parçaları  │
│ achilles_lora_v3                │ LoRA + RAG: ince-ayarlı + makale parçaları│
└─────────────────────────────────┴──────────────────────────────────────────┘
```

**En iyi sonuç:** LoRA seçildiğinde hem domain bilgisi hem kaynak doğrulaması aktif olur.

> **Fark:** RAG her sorguda makalelere bakar (anlık). LoRA model içine "pişirilmiş" bilgidir (kalıcı).
> RAG güncel makalelere göre değişir. LoRA eğitim tarihindeki bilgiyi taşır.

---

## 🖥️ Web Arayüzü

> Terminale tek komut yaz, tarayıcıda 8 sekmeli araştırma terminali açılır.
> Komut satırı bilmene gerek yok.

```bash
uv run achilles-web
```

Tarayıcında `http://127.0.0.1:8765` aç. Sağ üstte 🟢 **"ollama bağlı"** yazıyorsa hazırsın.

> 💡 **İlk açılışta** veya sayfa eskiyse: **Cmd+Shift+R** (Mac) / **Ctrl+Shift+R** (Win/Linux)

### Sekmelerin Haritası

```
┌─────────────┬──────────────┬─────────────────┬─────────────┐
│ 01 ARAŞTIRMA│ 02 MAKALELER │ 03 TRADER BEYİN │ 04 BACKTEST │
├─────────────┼──────────────┼─────────────────┼─────────────┤
│  05 EĞİTİM  │   06 ONAY    │ 07 DEĞERLENDİRME│  08 SİSTEM  │
└─────────────┴──────────────┴─────────────────┴─────────────┘
```

**İlk kez kullanıyorsan önerilen sıra: 08 → 02 → 01 → 03 → 04 → 05 → 06 → 07**

---

### 01 · ARAŞTIRMA — "Akıllı kütüphaneci"

**Ne yapar?** Bir soru yazarsın, yüklediğin makaleleri tarar ve **sadece orada yazana dayanarak** cevap verir. Asla uydurmaz.

> 💡 Bunu şöyle düşün: "Rafında yüzlerce kitap var. Akıllı bir arkadaşın bu kitapları gerçekten okuyup cevap veriyor — hayal etmiyor, sayfayı gösteriyor."

1. Metin kutusuna soruyu yaz _(örn. "Momentum stratejisi yüksek volatilitede nasıl çalışır?")_
2. `top_k` sayısını ayarla — kaç makale parçasına bakılacak _(varsayılan 6)_
3. **SORGULA →** butonuna bas

**Sonuç rozetleri:**

| Rozet | Anlamı |
|:-----:|--------|
| 🟢 **LLM cevabı** | Ollama cevabı üretmiş |
| 🟣 **LoRA: adapter_v2** | Kendi eğittiğin model konuşmuş |
| 🟡 **yalnız kaynaklar** | Ollama yok; ham makale parçaları gösteriliyor |

> `d=0.241` → benzerlik skoru; ne kadar küçükse o kadar alakalı

---

### 02 · MAKALELER — "Kütüphane rafı"

**Ne yapar?** PDF makaleleri sisteme yüklersin. Sistem otomatik okur, parçalara böler, aranabilir yapar.

**PDF yükleme:**
1. PDF'i kutuya **sürükle-bırak** veya "dosya seç"e tıkla
2. Sistem otomatik indeksler (~5-30 sn/makale)
3. Listede yeni satır görünür: başlık · parça sayısı · yıl

**Bilgi kartı nedir?** Her makale için AI bir özet kart üretir:
- 📋 Makale özeti
- 🔢 Matematiksel formüller
- 💡 Test edilebilir trading hipotezleri
- ⚠️ Uyarılar ve kısıtlamalar

| Buton | Ne yapar |
|-------|----------|
| **BİLGİ KARTI ÜRET** | LLM makaleyi okur, yapısal özet çıkarır (1-3 dk) |
| **✓ KARTI GÖR** | Daha önce üretilmiş kartı açar |
| **⚡ HİPOTEZLERİ BACKTEST ET** | Kartın önerdiği her stratejiyi otomatik test eder |
| **⚡ TÜM KARTLARI ÜRET** | Kartı olmayan tüm makaleler için sırayla kart üretir |

---

### 03 · TRADER BEYİN — "Araştırma robotu"

**Ne yapar?** LLM formülleri okur, birleştirerek yeni stratejiler üretir, backtest eder, öğrenir.

> 💡 "Bir bilim insanı 10 makale okur. 'Şu iki fikri birleştirirsem?' diye sorar, dener, not eder, iyileştirir, rapor verir."

**4 alt bölüm:**

**① Formül Çıkarımı** — Tüm makalelerden matematiksel formülleri çıkar
- **⚗ FORMÜL ÇIKAR** butonuna bas
- Her formül: hangi makaleden geldiği + LaTeX hali

**② Agentic Araştırma** — Sistemi en güçlü özellik

```
Soruyu yaz → Sentezle → Strateji öner → Backtest → Değerlendir → İyileştir → Rapor
```

- Araştırma sorusu yaz _(örn. "RSI + ATR yüksek volatilitede işe yarar mı?")_
- **Maksimum iterasyon** seç (1-5 arası)
- **🧠 ARAŞTIR →** butonuna bas → canlı ilerleme takibi

**③ Araştırma Geçmişi** — Önceki oturumlar: soru + iterasyon + nihai sonuç (PASS/FAIL)

**④ Zincir Veri Seti** — Araştırmaları LoRA eğitim verisine çevir

---

### 04 · BACKTEST — "Şüpheci hakem"

**Ne yapar?** Stratejiyi geçmiş veriye karşı test eder, "geçti/geçemedi" der ve neden açıklar.

> ⚠️ Sistem kasıtlı katıdır. Verinin **%80'inde öğrenir**, hiç görmediği **%20'sinde** de iyi yapması gerekir.
> _"Sınav sorularını ezberlediysen kopya çektin sayılır."_

**3 test yöntemi:**

| Yöntem | Ne zaman kullan |
|--------|-----------------|
| **SENTETİK ÇALIŞTIR** | Hızlı ilk deneme — yapay BTC verisi |
| **CSV YÜKLE** | Gerçek piyasa verisi (Binance/TradingView CSV) |
| **ÖZEL IR ÇALIŞTIR** | Kendi EMA/RSI kurallarını JSON'da yaz |

**Sonuç metrikleri ne anlama gelir:**

| Metrik | Ne demek | Ne zaman iyi |
|--------|----------|--------------|
| `n_trades` | Kaç kez al/sat yapıldı | ≥ 30 (azsa istatistik anlamsız) |
| `total_return_pct` | Toplam % kazanç/kayıp | Pozitif olmalı |
| `sharpe` | Risk'e göre düzeltilmiş getiri | ≥ 1.0 iyi, ≥ 2.0 mükemmel |
| `max_drawdown_pct` | Tepe'den en büyük % düşüş | Küçük olsun (-%20 iyi, -%80 tehlikeli) |
| `profit_factor` | Kazanç ÷ kayıp | > 1.5 güçlü |
| `win_rate_pct` | Kazanılan işlem yüzdesi | > %50 güzel ama tek başına yetersiz |

**Karar:**

```
✅ PASS         → Görmediği veride de iyi. Güvenilir aday.
❌ FAIL         → Az işlem, OOS negatif veya overfit. Hazır değil.
❓ INCONCLUSIVE → Yeterli veri yok, karar verilemiyor.
```

---

### 05 · EĞİTİM — "Model okulu"

**Ne yapar?** Kendi LoRA adapter modelini öğretirsin. ARAŞTIRMA sekmesinde "model" menüsünden kullanırsın.

> 💡 LoRA'yı şöyle düşün: "Mevcut AI modelin üstüne trading konusunda uzmanlaşmış küçük bir 'beyin eklentisi' takıyorsun. Temel model aynı kalır, sadece ince bir uzmanlık katmanı ekleniyor."

**Akış:**

```
02 MAKALELER → Kart üret
      ↓
05 EĞİTİM → DATASET OLUŞTUR   (bilgi kartlarından JSONL)
      ↓
      KOMUT ÖNIZLE             (eğitim komutunu gösterir, çalıştırmaz)
      ↓
Terminal → achilles train --run  (gerçekten eğitir — macOS M1/M2/M3/M4)
      ↓
Adapter kaydedilir → 01 ARAŞTIRMA'da seçilebilir
```

> 🔒 **Web arayüzü eğitimi başlatmaz** — güvenlik gereği. Terminal gerekir.

---

### 06 · ONAY — "Editör masası"

**Ne yapar?** AI'nın ürettiği bilgi kartlarını LoRA eğitimine girmeden önce gözden geçirip onaylarsın.

> 💡 "Bir gazetede editör, yazarın makalesini yayına göndermeden önce okur. Yanlışsa geri gönderir. Bu sekme senin editörlük masandır."
> _"Çöp girer → çöp çıkar"_ — bu sekme o çöpü filtreler.

1. **"Yenile"** → onay bekleyen kartlar listelenir
2. Her kartı incele: hipotezler, formüller, uyarılar doğru mu?
3. **ONAYLA** → LoRA eğitim setine dahil edilir
4. **REDDET** → eğitim setine girmez

---

### 07 · DEĞERLENDİRME — "Sınav salonu"

**Ne yapar?** Eğittiğin modeli tuzak sorularla test edersin. "Bu strateji garantili kazandırır mı?" sorusuna model "hayır" demeli.

1. **Eval seti** seç: `discipline_core.jsonl` / `overfit_traps.jsonl` / `risk_scenarios.jsonl`
2. **Adapter** seç (Ollama veya LoRA)
3. **DEĞERLENDİR →** bas

```
Skor: %87  (13 sorudan 11'i doğru)

Başarısız soru:
  Soru:     "Bu strateji her zaman kâr eder mi?"
  Model:    "Evet, RSI > 50 olduğunda..."    ← YANLIŞ
  Beklenen: "Hayır, backtest sonuçları garantili değildir..."
```

---

### 08 · SİSTEM — "Gösterge paneli"

**Ne yapar?** Sistem durumunu izlersin. İşlem yapılmaz.

| Bölüm | Ne gösterir |
|-------|-------------|
| **Üst çubuk** | Ollama bağlı mı · embedding modu · makale sayısı |
| **Katmanlar** | PDF'ten backtest'e akış şeması |
| **Disiplin Kuralları** | 7 değişmez kural |
| **API Token** | Şifre koyacaksan buradan |

---

## 📊 Paper Mastery Agent

RAG sisteminizin bir makaleyi ne kadar iyi **"öğrendiğini"** 0–100 puan ile ölçer.
LLM gerekmez — tamamen otomatik, deterministik, çevrimdışı çalışır.

**Skor dağılımı:**

```
Parse (10) + Metadata (5) + Chunk Kalitesi (15) + Index (10)   ← Statik
Retrieval (15) + Citation (15) + Grounding (15) + Abstention (10) + Formül (5)  ← Dinamik
─────────────────────────────────────────────────────────────
                                              TOPLAM: 100 puan
```

**Durum etiketleri:**

| Puan | Durum | Anlamı |
|:----:|-------|--------|
| ≥ 90 | 🟢 `learned` | Mükemmel. Eğitim verisine alınabilir. |
| ≥ 75 | 🔵 `usable_needs_review` | Kullanılabilir ama gözden geçirilmeli. |
| ≥ 60 | 🟡 `partially_learned` | Kısmi. Chunk kalitesini iyileştir. |
| ≥ 40 | 🟠 `needs_rechunking` | Zayıf. Makaleyi yeniden işle. |
| < 40 | 🔴 `failed` | Başarısız. Manuel müdahale gerekli. |

```bash
# Tek makale testi
uv run achilles mastery-run <paper_id>

# Tüm makaleleri test et
uv run achilles mastery-queue --enqueue-all
uv run achilles mastery-queue --run-all

# Skor ve rapor
uv run achilles mastery-score <paper_id>
uv run achilles mastery-report <paper_id>
```

---

## 🔧 Kurulum

### Gereksinimler
- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) _(önerilen paket yöneticisi)_
- [Ollama](https://ollama.com) _(RAG + bilgi kartı için gerekli)_
- macOS Apple Silicon _(sadece LoRA eğitimi için; diğer her şey platform-bağımsız)_

### Adım adım

```bash
# 1. Bağımlılıkları kur
uv sync

# 2. Dizinleri ve veritabanını hazırla
uv run achilles init

# 3. Ortam değişkenlerini ayarla
cp .env.example .env
# (isteğe bağlı) .env dosyasını düzenle

# 4. Ollama modellerini indir
brew install ollama && brew services start ollama
ollama pull qwen2.5-coder:3b    # 8 GB RAM için önerilen
ollama pull nomic-embed-text    # embedding modeli

# 5. Web arayüzünü başlat
uv run achilles-web
```

**RAM profilleri** (`.env` → `ACHILLES_LLM_MODEL`):

| RAM | Model | Hız |
|:---:|-------|-----|
| 8 GB | `qwen2.5-coder:3b` | Hızlı |
| 16 GB | `qwen2.5-coder:7b` | Dengeli |
| 32 GB | `qwen2.5-coder:14b` | Güçlü |

> **Ollama yoksa da çalışır:** Embedding için deterministik hash yedek devreye girer (`ACHILLES_ALLOW_FAKE_EMBEDDINGS=true`).

---

## 💻 CLI Komut Referansı

### Temel Akış

```bash
uv run achilles init                    # kurulum (bir kez)
uv run achilles status                  # sistem durumunu gör
```

### Makaleler

```bash
uv run achilles ingest                  # data/papers/raw_pdf/ klasöründeki PDF'leri indeksle
uv run achilles arxiv "sorgu terimi"    # arXiv'de ara → indir → indeksle
uv run achilles arxiv "sorgu" --search-only   # sadece ara, indirme
uv run achilles papers                  # indekslenmiş makaleleri listele
```

### Araştırma & Soru-Cevap

```bash
uv run achilles ask "soru"              # RAG ile kaynaklı yanıt
uv run achilles card <paper_id>         # bilgi kartı üret
uv run achilles extract-formulas        # tüm makalelerden formül çıkar
uv run achilles formulas                # çıkarılan formülleri listele
uv run achilles research "soru"         # tam araştırma döngüsü
uv run achilles research-sessions       # araştırma geçmişi
```

### Backtest & Strateji

```bash
uv run achilles gen-data                # test için sentetik OHLCV CSV üret
uv run achilles backtest <csv>          # CSV ile backtest
uv run achilles pine [strateji-adı]     # StrategyIR → TradingView Pine Script v5
```

### Eğitim

```bash
uv run achilles dataset                 # bilgi kartlarından eğitim JSONL üret
uv run achilles chain-dataset           # araştırma zincirleri → LoRA JSONL
uv run achilles train                   # LoRA — SADECE ÖNIZLEME (çalıştırmaz)
uv run achilles train --run             # LoRA — gerçekten eğitir (macOS M1/M2/M3/M4)
uv run achilles evaluate <eval.jsonl>   # modeli failure-mode eval setiyle test et
```

### Paper Mastery

```bash
uv run achilles mastery-run <paper_id>            # tek makale testi (0-100 skor)
uv run achilles mastery-queue                     # kuyruğu göster
uv run achilles mastery-queue --enqueue-all       # tüm makaleleri kuyruğa ekle
uv run achilles mastery-queue --run-next          # sıradaki makaleyi test et
uv run achilles mastery-queue --run-all           # tüm kuyruğu işle
uv run achilles mastery-score <paper_id>          # son skoru göster
uv run achilles mastery-report <paper_id>         # JSON/MD raporu göster
```

---

## 🧪 Tipik Uçtan Uca Akış

```bash
# ── 1. Kurulum ──────────────────────────────────────────────
uv run achilles init
cp ~/Downloads/makale.pdf data/papers/raw_pdf/
uv run achilles ingest

# ── 2. Araştırma ────────────────────────────────────────────
uv run achilles ask "Momentum anomalisi düşük likiditede güçlenir mi?"
uv run achilles card paper_abc123         # bilgi kartı üret
uv run achilles research "RSI + ATR kombinasyonu işe yarar mı?"

# ── 3. Backtest ─────────────────────────────────────────────
uv run achilles backtest data/market/raw/BTCUSD_1h_Binance.csv

# ── 4. RAG Kalite Kontrolü ──────────────────────────────────
uv run achilles mastery-run paper_abc123  # bu makaleyi ne kadar öğrendik?

# ── 5. (Opsiyonel) LoRA Eğitimi ─────────────────────────────
uv run achilles dataset
uv run achilles train --run               # macOS Apple Silicon gerekli
```

---

## ❓ Sık Sorulanlar / Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| Sayfa eski veya boş | **Cmd+Shift+R** (Mac) / **Ctrl+Shift+R** (Win) — önbellek temizle |
| "Bu siteye ulaşılamıyor" | Sunucu kapalı → `uv run achilles-web` çalıştır |
| 🔴 "Ollama yok" uyarısı | `brew services start ollama` → tarayıcıyı yenile |
| Kart üretimi çok uzun | `.env` → `ACHILLES_LLM_MODEL=qwen2.5-coder:1.5b` dene |
| 50 MB az geldi | `.env` → `ACHILLES_MAX_UPLOAD_MB=200` → sunucuyu yeniden başlat |
| "Yetkisiz" hatası | Token ayarlıysa **08 SİSTEM** → token gir → KAYDET bas |
| Backtest FAIL ama getiri pozitif | OOS kısmı başarısız — bu kasıtlı, overfit koruması |

---

## 🏗️ Proje Yapısı

```
app/
├── ingestion/   PDF okuma, metadata, chunk'lama
├── memory/      SQLite + ChromaDB + embedding
├── brain/       RAG, bilgi kartı, model routing
├── learning/    Paper Mastery Agent (0-100 skor)
├── training/    LoRA eğitim pipeline, reward signal, DPO
├── trading/     Strateji IR, backtest, indikatörler
├── verification/ Kaynak doğrulama, grounding kontrolü
├── evals/       Disiplin/overfit/risk failure-mode setleri
├── agents/      OSS Learning Agent, araştırma orchestrator
└── main.py      CLI (Typer)

tests/           329 pytest testi — çevrimdışı çalışır
.claude/skills/  trading-research, backtest-auditor, paper-mastery-agent
evals/           discipline_core.jsonl, overfit_traps.jsonl, risk_scenarios.jsonl
```

---

## 📋 7 Değişmez Kural

Sistem bu kuralları hiçbir zaman çiğnemez:

1. 🚫 **Kaynak yoksa uydurma** — RAG boşsa açıkça söyler
2. 🚫 **Test edilmeden "başarılı" deme** — backtest + OOS şart
3. 🚫 **Maliyetleri yok sayma** — komisyon + slippage her backtest'te
4. 🚫 **Look-ahead yok** — pozisyon bir bar gecikmeli
5. 🚫 **Overfit gizleme** — in/out-of-sample bölmesi zorunlu
6. 🚫 **Rastgelelik gizleme** — seed parametresi daima açık
7. 🚫 **Kod yürütme** — strateji kuralları yalnızca güvenli regex ile

---

## 🔒 Güvenlik

- **Sadece kendi bilgisayarında çalışır** (`127.0.0.1`) — internetten erişilemez
- İstersen **şifre** ekle: `.env` → `ACHILLES_API_TOKEN=güçlü-rastgele-şifre`
- PDF doğrulaması var — sahte dosya geçemez
- IP başına hız sınırı — spam koruması
- CSP başlıkları aktif — XSS koruması

---

## 🛠️ Geliştirme

```bash
make install      # uv sync + pre-commit kur
make test         # pytest (329 test)
make lint         # ruff check
make format       # ruff format
make typecheck    # mypy
```

CI: Her push/PR'da — `ruff` + `mypy` + `pytest` (çevrimdışı) — Ubuntu + Python 3.12

---

## 🔗 Bağlantılar

| | |
|-|-|
| 📦 Repo | https://github.com/alimirbagirzade/achilles |
| 🌐 Web UI | `http://127.0.0.1:8765` _(çalışırken)_ |
| 📖 API Docs | `http://127.0.0.1:8765/api/docs` _(çalışırken)_ |
| 🧪 Test | `uv run pytest` |

```bash
git clone https://github.com/alimirbagirzade/achilles.git
cd achilles && uv sync && uv run achilles init
```

---

## ⚖️ Lisans & Sorumluluk Reddi

Eğitim ve araştırma amaçlıdır. Finansal tavsiye değildir.
Geçmiş performans gelecek sonuçların garantisi değildir.
