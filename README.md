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

## 🧪 Web Arayüzü — Adım Adım Test Kılavuzu

> Çok basit anlatım. Her adımda **ne yapacağın** ve **ne görmen gerektiği** (✔) yazıyor.

### 0) Sunucuyu aç
1. **Terminal** uygulamasını aç.
2. Şunu yaz ve Enter'a bas:
   ```bash
   cd ~/Development/Achilles
   uv run achilles-web
   ```
3. Tarayıcıda şu adresi aç: **http://127.0.0.1:8765**
4. ✔ Sağ üstte küçük bir **nokta + "ollama bağlı"** yazısı görmelisin. (Karanlık görünüyorsa **Cmd+Shift+R** ile yenile.)

### 1) SİSTEM sekmesi (ısınma turu)
1. Üstte **"04 · SİSTEM"**e tıkla.
2. ✔ Kutular açılır, hata yok. (Token kutusunu boş bırak — yerelde gerekmez.)

### 2) MAKALELER — bir PDF yükle
1. **"02 · MAKALELER"**e tıkla.
2. Bir akademik **.pdf**'i kutunun içine **sürükle-bırak** ya da **"dosya seç"**e tıkla.
3. ✔ Birkaç saniye sonra altta makale satırı + **"… chunk"** yazısı belirir.
4. **Yaramazlık testi:** bir **.txt** dosyası sürükle → ✔ *"Yalnız .pdf kabul edilir"* uyarısı çıkar (reddetmesi **iyi**).

### 3) MAKALELER — Bilgi Kartı üret
1. Makale satırındaki **"BİLGİ KARTI"** düğmesine tıkla.
2. ✔ ~1 dakika sonra **"Bilgi kartı üretildi"** bildirimi gelir. (Yerel model düşünüyor, sabırlı ol 🙂)

### 4) ARAŞTIRMA — soru sor (RAG)
1. **"01 · ARAŞTIRMA"**ya tıkla.
2. Kutuya soru yaz (örn: *"Bu makalenin ana bulgusu nedir?"*), **"SORGULA →"**.
3. ✔ Kaynaklı bir cevap + altta **"kaynaklar"** listesi gelir.
4. Hiç makale yoksa ✔ *"Kaynak bulunamadı"* der — **uydurmaz** (bu **iyi**).

### 5) BACKTEST — sentetik (uydurma) veri
1. **"03 · BACKTEST"**e tıkla → **"SENTETİK ÇALIŞTIR →"**.
2. ✔ Metrik tablosu + büyük **YARGI** kutusu çıkar: **✓ GEÇTİ / ✕ BAŞARISIZ / ≈ SONUÇSUZ**.
3. Zayıf strateji **✕ BAŞARISIZ** alır — bu **normal ve doğru** (sistem şüpheci).

### 6) BACKTEST — gerçek veri (CSV)
1. Aynı sekmede aşağıda **"veya gerçek veri"** bölümüne bir **OHLCV .csv** bırak.
   (Hazır örnek: `data/market/raw/BTCUSD_1d.csv` — varsa onu kullan.)
2. ✔ Gerçek veriyle metrikler + yargı + **"veri: dosya.csv (… bar)"** görünür.
3. **Yaramazlık testi:** kolonları yanlış bir csv → ✔ *"open/high/low/close bulunamadı"* reddi.

### 7) Renk körü göz testi 👓
- Yargı ve metriklerde **renge ek ikon** var mı bak: **✓ / ✕ / ≈** ve **▲ / ▼**.
- ✔ Anlam sadece renkle değil, ikon+şekille de verilmeli.

### Sık sorulanlar
- **"50 MB az geldi"** → `.env` dosyasına `ACHILLES_MAX_UPLOAD_MB=200` yaz, sunucuyu yeniden başlat. Arayüz limiti **otomatik** günceller.
- **"Yetkisiz" hatası** → yalnız token ayarlıysa olur; SİSTEM sekmesinden token gir.
- **Sayfa karanlık** → tarayıcı eski stili önbelleğe almış: **Cmd+Shift+R**.

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
