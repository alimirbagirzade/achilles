# Achilles — Eğitim Protokolü (Windows / yerel)

_Bu makineye özel ölçülmüş değerlerle. Son güncelleme: 2026-06-12._

Bu belge **bu bilgisayarda** Achilles LoRA eğitiminin nasıl çalıştığını,
donanım/model özelliklerini ve **ölçülmüş eğitim sürelerini** içerir.

> İlke (CLAUDE.md): Gerçek ağır eğitim yalnızca açık `--run` ile başlar.
> Çıktı `verdict != pass` ise "aday"dır, "hazır" değildir.

---

## 1. Bilgisayar özellikleri (bu makine)

| Bileşen | Değer |
|---|---|
| CPU | Intel Core **i7-1165G7** (11. nesil, Tiger Lake) |
| Çekirdek | **4 fiziksel / 8 mantıksal**, ~2.8 GHz baz |
| SIMD | AVX-512 (CPU çıkarım/eğitimi hızlandırır) |
| GPU | **YOK** — Intel Iris Xe (entegre); CUDA yok → her şey CPU'da |
| RAM | **31.7 GB** |
| Disk (C:) | ~209 GB boş |
| OS | Windows 10 Pro 19045 |
| Python / torch | 3.12 · **torch 2.12.0+cpu** · transformers 5.12.0 |

**Sonuç:** Bu bir laptop CPU'su. Çıkarım rahat; **eğitim CPU'da yavaştır**
(adım başına ~dakika). GPU olmadığı için 4B üstü model lokal eğitilemez.

---

## 2. Model — tek beyin: **Qwen3-4B**

RAG çıkarımı ve LoRA eğitimi **aynı** modeldir (tek beyin mimarisi).

| Kullanım | Model | Kaynak | Boyut |
|---|---|---|---|
| RAG / çıkarım | `qwen3:4b` | Ollama (GGUF) | ~2.5 GB |
| LoRA eğitim base | `Qwen/Qwen3-4B` | HuggingFace (safetensors) | ~8 GB |

- LoRA adapter **base-model'e özeldir** → eğitim ve çıkarım aynı model olmalı.
- Daha büyük beyin (9B / 30B / 120B) → **Colab/GPU**'da eğitilir, aynı pipeline.
- Ayar: `.env → ACHILLES_LLM_MODEL=qwen3:4b`, `ACHILLES_PEFT_BASE_MODEL=Qwen/Qwen3-4B`.

### LoRA hiperparametreleri (varsayılan)
`r=8`, `alpha=16`, `dropout=0.05`, `lr=2e-4`, `max_seq_length=512`, `batch_size=1`.
Eğitilebilir parametre: **~2.95M / 4.03B (%0.073)**.

---

## 3. Eğitim süreçleri (pipeline)

```
Onaylı kartlar → Gate 0-8 denetim → dataset + train/valid split
   → LoRA eğitim (PEFT/CPU) → eval → adapter registry → (onayla) promote
```

| Gate | Ad | Kontrol |
|---|---|---|
| 0 | source | onaylı RAG verisi mi |
| 1 | schema | JSONL format |
| 2 | curriculum | seviye atanmış mı |
| 3 | domain | en az bir alan |
| 4 | quality | kısa/tekrar/duplicate |
| 5 | math | hesap doğruluğu |
| 6 | philosophy | mantık tutarlılığı |
| 7 | safety | gizli veri (BLOCKER) |
| 8 | split | train/valid/test sızıntısı |

**Backend otomatik seçilir** (`detect_lora_backend`): macOS ARM64 → MLX,
Windows/Linux → **PEFT** (torch+peft).

---

## 4. Ölçülmüş eğitim süreleri (bu makine)

Gerçek koşudan ölçülen **adım başına süre** (CPU fp32, batch=1, seq=512):

| Config | Qwen3-4B adım başına | Tam koşu (6 adım) |
|---|---|---|
| İlk (pad→512, eval açık) | ~85 sn/adım | 513.7 sn |
| **Optimize (dinamik padding, eval kapalı)** | **~40.6 sn/adım** | **243.6 sn** |

Hız optimizasyonları (CPU): **dinamik padding** (512'ye doldurma yok → her adım yalnız
gerçek token; batch=1 ile sıfır padding), **eval kapalı** (epoch başına ~35 sn tasarruf),
tek checkpoint, `pin_memory=False`. Sonuç: **~2× hızlanma**.
(Qwen2.5-1.5B referans: ~29 sn/adım.)

**Toplam süre formülü:** `süre ≈ iterations × adım_süresi`
(çünkü toplam adım ≈ `iterations`).

### Qwen3-4B — iterasyona göre tahmini süre (optimize config, ~40 sn/adım)

| `--iterations` | Süre | Not |
|---|---|---|
| 30 | **~20 dk** | hızlı deneme |
| 60 | **~40 dk** | döngü başına önerilen |
| 100 | **~67 dk** | |
| 300 (varsayılan) | **~3.3 saat** | tam koşu |

> **Maksimum pratik süre:** varsayılan `iters=300` → **~3.3 saat** (optimize). Daha büyük
> `iters` orantılı artar ama küçük veri setinde anlamsızdır (overfit). 1.5B ~%30 daha hızlı.
>
> **24 saatlik döngü:** `scripts/train-loop.ps1` (iters=40, 2 dk cooldown) → ~24 saatte
> ~30+ döngü. NOT: veri tavanı (5 örnek) nedeniyle her döngü aynı sonuca yakınsar —
> hız öğrenmeyi artırmaz, sadece overfit'i hızlandırır. Asıl çözüm: veri setini büyütmek.

---

## 5. Periyodik / sürekli eğitim

Sabit "her saat" yerine **makine kapasitesine** göre:

```
[eğitim döngüsü] → [2-3 dk dinlenme] → [eğitim döngüsü] → ...
```

- CPU sürekli %100'de kalmasın diye döngüler arası **2-3 dk cooldown**.
- Yeni onaylı kart geldikçe dataset büyür → her döngü daha anlamlı.
- Auto-pipeline: `.env → ACHILLES_AUTO_LORA_*` (varsayılan kapalı, güvenli).

---

## 6. Komutlar

```bash
uv run achilles lora-status          # genel durum
uv run achilles lora-audit           # Gate 0-7
uv run achilles lora-dataset         # JSONL + train/valid split üret
uv run achilles train --run --backend peft \
    --adapter-name <ad> --iterations <n>   # gerçek eğitim (CPU)
uv run achilles lora-registry        # adapter listesi
```

Onay gerektirenler: smoke test (200+ örnek), adapter promote, GGUF export,
production adapter değişimi.

---

## 7. SÜREKLİ ÖĞRENME PROTOKOLÜ — "Trader Uzmanı" döngüsü

> Amaç: model yalnız eğitilmez; **sürekli yeni kaynak okur, kavrar, sentezler ve
> eğitilir** — her turda biraz daha "trader gibi düşünen" bir uzmana yaklaşır.
> Çalıştır: `bash scripts/continuous-learning.sh [saat]` · Durdur: `storage/STOP_LEARNING`

```
┌────────────────────────────────────────────────────────────────────┐
│  1) ZENGİNLEŞTİR   arXiv'den 3 makale (dönüşümlü konu kuyruğu)     │
│  2) KAVRA          kart üret (LLM) → içerikli onayla → anlama %    │
│  3) SENTEZLE       (her 3 turda) hipotez + backtest + sentez       │
│                    makalesi → web'den indirilebilir                │
│  4) EĞİT           dataset tazele → LoRA 2×40 iter                 │
│  └─→ tekrar (RAM disiplini: LLM fazı ↔ eğitim fazı asla çakışmaz)  │
└────────────────────────────────────────────────────────────────────┘
```

### Neden bu alanlar? (konu kuyruğu: `scripts/enrichment-topics.txt`)
Trader uzmanlığı yalnız formül değildir; kuyruk bilinçli olarak şu eksenlerde
zengindir:
- **Psikoloji / davranışsal finans** — aşırı güven, kayıp kaçınma, sürü
  davranışı, disposition etkisi → modelin "neden yanılırız"ı öğrenmesi.
- **Belirsizlik** — Knightian belirsizlik, belirsizlik nicemleme, kuyruk riski,
  black swan → emin görünmek yerine belirsizliği DOĞRU ifade etme davranışı.
- **Felsefe / karar kuramı** — olasılık felsefesi, Bayesçi karar, tümevarım
  problemi, sınırlı akılcılık → muhakeme disiplini (LoRA'nın asıl hedefi).
- **Trading / risk** — rejim değişimi (Markov), Kelly, drawdown kontrolü,
  momentum-ortalamaya dönüş etkileşimi.

Kuyruk düz metin dosyasıdır: satır ekle/çıkar, döngü kaldığı yerden devam eder
(`storage/learning_topic_index`).

### Protokol ilkeleri
1. **Kavramadan eğitme yok** — yeni makale önce kart + anlama skoru alır;
   içeriksiz kart asla onaylanmaz/eğitime girmez.
2. **Sentez = yeni bilgi** — hipotezler mevcut kartların ÜZERİNE üretilir,
   backtest edilir (geçemeyen FAIL olarak raporlanır) ve sentez makalesi
   olarak hem insana (web) hem RAG'a geri beslenebilir.
3. **Dürüst metrik** — `rag-mastery` her tur sonunda loglanır; ilerleme
   kapsam/anlama/eğitim bileşenleriyle izlenir.
4. **RAM disiplini** — LLM fazları ve eğitim fazı sıralıdır; düşük RAM'li
   makinede asla çakışmaz.

### RAG + LoRA tek beyin entegrasyonu
Eğitilen adapter'ın RAG ile AYNI modelde çalışması için GGUF dönüşümü ve
RAFT-tarzı veri reçetesi: bkz. **docs/RAG_LORA_ENTEGRASYON.md** (Ollama
ADAPTER yolu, base eşleşme kuralı, ≥1000 örnek hedefi, kaynak-yok reddi
örnekleri, müfredat sırası).

## 8. Güçlü makineye taşıma (ölçekleme rehberi)

Protokol makineden bağımsızdır — yalnız şu düğmeler değişir:

| Düğme | Bu laptop (CPU) | Mac M-serisi | Tek GPU (24GB) | Colab A100 |
|---|---|---|---|---|
| Base model | Qwen3-4B-Instruct-2507 | aynı / 9B | 9B / 14B | 30B+ |
| Backend | PEFT (CPU) | MLX | PEFT (CUDA) | PEFT (CUDA) |
| iters/koşu | 40 | 200+ | 300+ | 300+ |
| max_seq | 1024 | 2048 | 2048 (RAFT) | 4096 |
| batch_size | 1 | 4 | 8+ | 16+ |
| Tur süresi | ~1.5-2 sa | ~20-30 dk | ~10 dk | ~5 dk |
| Anlama skoru | seçili makale | tüm korpus | tüm korpus | tüm korpus + judge kalibrasyon |

Taşıma adımları: repo'yu klonla → `.env`'de `ACHILLES_PEFT_BASE_MODEL` +
`ACHILLES_LLM_MODEL`'i makineye göre seç (base ↔ Ollama tag EŞLEŞMELİ) →
`bash scripts/continuous-learning.sh 72`. Hepsi bu.

## 9. Sınırlar ve uyarılar

- **Veri darboğazı:** şu an yalnızca **5 eğitim örneği** (3 train / 1 valid).
  LoRA için çok az — asıl performans kaldıracı **veri miktarı + kalitesi**.
- **CPU yavaşlığı:** ciddi/uzun eğitim için **Colab/GPU** önerilir
  (`peft_lora_train.generate_colab_notebook` notebook üretir).
- **Bellek:** 4B eğitimi ~16 GB RAM kullanır; aynı anda büyük Ollama modeli
  (30B = 18 GB) açık olmasın → OOM riski.
- "Yüksek performans" 4B ile sınırlıdır; üst kalite için 9B/30B (Colab) + RAG.
