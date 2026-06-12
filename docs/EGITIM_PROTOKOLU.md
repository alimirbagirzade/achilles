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

| Model | Adım başına | Tam koşu (6 adım, 2 epoch) | eval_loss |
|---|---|---|---|
| Qwen2.5-1.5B | **~29 sn/adım** | 174 sn | 2.769 |
| **Qwen3-4B** | **~74 sn/adım** (saf) | **513.7 sn** (eval dahil ~85 sn/adım) | **2.588** |

> Not: `eval_strategy=epoch` her epoch sonunda ~35 sn eval ekler; çok epoch'lu
> uzun koşularda toplam süreye bu da eklenir.

**Toplam süre formülü:** `süre ≈ iterations × adım_süresi`
(çünkü toplam adım ≈ `iterations`).

### Qwen3-4B — iterasyona göre tahmini süre

| `--iterations` | Süre (~74 sn/adım) | Not |
|---|---|---|
| 30 | **~37 dk** | hızlı deneme |
| 60 | **~74 dk** | |
| 100 | **~2 saat** | |
| 300 (varsayılan) | **~6.2 saat** | tam koşu |

> **Maksimum pratik süre:** varsayılan `iters=300` → **~6.2 saat**.
> Daha büyük `iters` orantılı artar (1000 ≈ ~20 saat) ama küçük veri setinde
> anlamsızdır (overfit). 1.5B kullanılırsa süreler ~2.5× kısalır.

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

## 7. Sınırlar ve uyarılar

- **Veri darboğazı:** şu an yalnızca **5 eğitim örneği** (3 train / 1 valid).
  LoRA için çok az — asıl performans kaldıracı **veri miktarı + kalitesi**.
- **CPU yavaşlığı:** ciddi/uzun eğitim için **Colab/GPU** önerilir
  (`peft_lora_train.generate_colab_notebook` notebook üretir).
- **Bellek:** 4B eğitimi ~16 GB RAM kullanır; aynı anda büyük Ollama modeli
  (30B = 18 GB) açık olmasın → OOM riski.
- "Yüksek performans" 4B ile sınırlıdır; üst kalite için 9B/30B (Colab) + RAG.
