# Achilles LoRA — Araştırma Logu & Tarama Defteri

Bu dosya **iki işlevi** birden görür:

1. **İnsan-okur araştırma logu:** Her araştırma turunda ne tarandı, ne bulundu, ne
   entegre edildi.
2. **Dedup defteri (machine-readable):** Tekrarlı tarama (günlük/haftalık) bu dosyaya
   karşı diff alır — "Kapsanan teknikler" ve "Kapsanan kaynaklar" listelerinde geçen
   bir teknik/arXiv-ID **yeniden derin-araştırılmaz** (boş tur gürültüsünü önler).

> Tekrarlı tarama tasarımı (kullanıcı kararı, 2026-06-17):
> - **Günlük hafif tarama:** arXiv/HF/Unsloth/PEFT'te *bu defterde olmayan* yeni öğe var mı?
>   Yoksa no-op (commit yok). Varsa → bu loga aday satırı + (doküman-değişikliğiyse) auto-push.
> - **Haftalık derin tur:** tam çok-ajanlı sweep + adversarial doğrulama + sentez + entegrasyon.
> - **Kapı:** kod/reçete değişikliği doğrudan `main`'e push EDİLMEZ → PR / inceleme chip'i
>   (doğrulanmamış reçete riski; CLAUDE.md Kural 2/8). Doküman-yalnız güncelleme auto-push olabilir.
> - **Mekanizma:** bulut zamanlı routine (bkz. `.claude/` scheduled routine).

---

## Kapsanan teknikler (dedup anahtarı — yeniden derin-araştırma YOK)

`rsLoRA` · `DoRA` · `LoRA+` · `PiSSA` · `OLoRA` · `EVA` · `LoftQ` · `CorDA` ·
`orthogonal-init` · `NEFTune` · `gaussian-init` · `QLoRA` · `train_on_responses_only` ·
`cosine-warmup` · `weight-decay` · `gradient-clipping` · `replay/rehearsal` ·
`n-gram-repetition-detection` · `assistant_only_loss`

## Elenen adaylar (dedup anahtarı — yeniden derin-araştırma YOK)

`LoRA-GA` (PEFT-native değil — ⚠️ 2026-07-02'de PEFT docs'ta `lora_ga_config` görüldü → weekly-deep'te
native-durum YENİDEN doğrulanacak) · `VeRA` · `MiLoRA` · `LoRA-FA` (param-azaltma, v5-ilgisiz) ·
`O-LoRA/orthogonal-subspace-CL` · `CLoRA` · `EWCLoRA` · `FIP` (continual-learning, native değil) ·
`DFT loss_type=dft` · `OPLoRA` · `SC-LoRA` · `AILoRA` · `D²LoRA` · `all-linear` (zaten hizalı) ·
`OFT/BEFT/Lily` (image-gen odaklı, disiplin/v5-ilgisiz) · `aLoRA/alora_invocation_tokens` ·
`MonteCLoRA` · `QALoRA` · `BDLoRA` · `VeLoRA` · `Arrow-routing` (2026-07-02 günlük; v5-ilgisiz)

## Kapsanan kaynaklar (arXiv ID / URL)

- arXiv 2312.03732 (rsLoRA) · arXiv 2402.09353 (DoRA) · arXiv 2310.05914 (NEFTune) ·
  arXiv 1904.09751 (neural text degeneration)
- unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide
- unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune
- huggingface.co/docs/peft/main/en/developer_guides/lora (rsLoRA/DoRA/init/LoRA+)
- huggingface.co/docs/trl/sft_trainer (NEFTune/response-only/packing/assistant_only_loss)
- github.com/NVlabs/DoRA · github.com/neelsjain/NEFTune · github.com/yxli2123/LoftQ
- huggingface.co/docs/peft/main/en/developer_guides/lora (orthogonal/eva/gaussian init listesi)
- arXiv 2407.05000 (LoRA-GA) · github.com/huggingface/peft/issues/2927 (LoRA-GA PEFT'e EKLENMEDİ)
- huggingface.co/docs/peft/main/package_reference/lora (`ensure_weight_tying` + yeni init/config alanları) ·
  huggingface.co/blog/peft-beyond-lora (2026-06-18 "Beyond LoRA": OFT/BEFT/Lily) ·
  unsloth.ai/docs/models/qwen3.5/fine-tune (Qwen3.5 + alpha=r default ablasyonu)

---

## Günlük tarama — 2026-07-02 (daily-light — zamanlı görev)

**Tetikleyici:** Zamanlı görev `lora-arastirma-gunluk-tarama` (daily-light). `lora-arastirma`
alt-ajan tipi bu ortamda YOK → protokol (`docs/PROTOKOL_LORA_ARASTIRMA.md`, daily-light) doğrudan
uygulandı. Hafif tarama (tam sweep YOK): arXiv (LoRA/PEFT/forgetting), HF PEFT docs/blog, Unsloth
Qwen3. CLAUDE.md Kural 2/7/8'e uyuldu; eğitim BAŞLATILMADI.

**Sonuç: YENİ, doğrulanmış, PEFT-native, v5-ilgili ENTEGRE edilebilir teknik BULUNAMADI → PR YOK.**
Yalnız dedup defteri güncellendi (bu doküman) + 1 durum-değişikliği bayrağı (LoRA-GA) weekly-deep'e
devredildi. Doküman-yalnız değişiklik → `main`'e push (kod/reçete dokunulmadı).

**Taranan ve elenen/ertelenen adaylar:**

| Aday / gözlem | Karar | Gerekçe |
|---------------|-------|---------|
| Forgetting makaleleri: arXiv 2603.09684 (survey), 2606.06920 (sub-1B math), 2503.02659 (init) | ⏭️ İLGİSİZ | Survey/analiz veya PEFT-native-DEĞİL yöntemler (LoRETTA tensör-ayrışım, WeGeFT). Entegre edilebilir aday değil. |
| EWCLoRA / FIP / Hierarchical (arXiv 2501.13669) | ✅ ZATEN ELENDİ | Dedup defterinde mevcut; yeniden derin-araştırılmadı. |
| Instruction-data karışımı %5–20 (forgetting azaltma) | ✅ ZATEN VAR | `replay/rehearsal` olarak kapsanan teknikte. |
| **"Beyond LoRA" (HF blog, 2026-06-18): OFT / BEFT / Lily** | ❌ ELE | PEFT-native ama blog açıkça **image-generation** odaklı (OFT "strictly dominates on image metrics"); disiplin/forgetting için üstünlük gösterilmemiş. v5-ilgisiz. |
| **PEFT `ensure_weight_tying=True`** (LoraConfig, native) | 🟡 FARKINDALIK | GERÇEK + Achilles GGUF-güvenlik tasarımıyla doğrudan ilgili: bağlı `embed_tokens`/`lm_head` katmanlarında adapter'ların da bağlı kalmasını garanti eder. Achilles bu katmanları `target_modules`'e KOYMADIĞINDAN şu an **no-op** → entegrasyon gerekmez. Ancak ileride embed/lm_head eğitilirse native mekanizma budur. Log'a farkındalık notu. |
| **PEFT `lora_ga_config`** (docs'ta görüldü) | ⚠️ DURUM-DEĞİŞİKLİĞİ | Defter LoRA-GA'yı "PEFT-native değil" (issue #2927) kaydetmişti; artık docs/API'de gradient-tahminli init callback'i görünüyor. Kesin merge PR'ı bu turda doğrulanamadı (Kural 7 → overclaim yok) → **weekly-deep'te native-durum yeniden doğrulanacak**. |
| Yeni native config alanları: `alora_invocation_tokens`, `monteclora_config`, `use_qalora`, `use_bdlora`, `velora_config`, `arrow_config` | ⏭️ ERTELENDİ | Daily-light kapsamında derin-değerlendirme YOK; "Elenen adaylar"a işlendi (çoğu param-verimlilik/routing, v5-forgetting-ilgisiz). Gerekirse weekly-deep bakar. |
| Unsloth 2026 ablasyonu: `alpha=r` "temiz varsayılan" | 🟡 NOT | Reçete önerisi; Kural 2 gereği bulut eğitim + `adapter_eval` gate'i olmadan "daha iyi" DENMEZ. Yalnız not; reçete değişmedi. |

**NOT (Kural 2):** Hiçbir reçete/kod değişikliği yapılmadı; yukarıdakiler hipotez/gözlem.
Bulut eğitim koşusu + `adapter_eval` gate'i ile doğrulanmadan "daha iyi" denmez.

### Kaynaklar (Günlük tarama 2026-07-02)

| Teknik / Konu | Kaynak |
|---------------|--------|
| PEFT `ensure_weight_tying` + yeni config alanları | <https://huggingface.co/docs/peft/main/package_reference/lora> |
| "Beyond LoRA" (OFT/BEFT/Lily) | <https://huggingface.co/blog/peft-beyond-lora> |
| Forgetting survey / sub-1B / init | arXiv 2603.09684 · arXiv 2606.06920 · arXiv 2503.02659 |
| Unsloth Qwen3.5 (alpha=r default) | <https://unsloth.ai/docs/models/qwen3.5/fine-tune> |

---

## Tur 2 — 2026-06-22 (derin tur — haftalık zamanlı görev)

**Tetikleyici:** Zamanlı görev `lora-arastirma-haftalik-derin` (weekly-deep). `lora-arastirma`
alt-ajan tipi bu ortamda yoktu → protokol (`docs/PROTOKOL_LORA_ARASTIRMA.md`, weekly-deep) doğrudan
uygulandı. CLAUDE.md Kural 2/7/8'e uyuldu; eğitim BAŞLATILMADI.

**Yöntem:** 7 açılı paralel WebSearch sweep — (a) yeni LoRA varyantları, (b) init yöntemleri,
(c) küçük-LLM catastrophic forgetting/refusal koruma, (d) SFT regularizasyon, (e) Unsloth/Qwen3
güncel, (f) SFT veri kalitesi, (g) LoRA-GA özel doğrulama. Her aday adversarial süzgeçten geçti:
*gerçek mi? PEFT 0.19+/Unsloth native mi? Achilles'e uygun mu? GGUF-güvenli mi? v5'e yardım eder mi?*

**Sonuç: YENİ, doğrulanmış, PEFT-native, v5-ilgili teknik BULUNAMADI → kod PR'ı YOK.**

**Adaylar ve eleme gerekçeleri:**

| Aday | Karar | Gerekçe |
|------|-------|---------|
| **LoRA-GA** (arXiv 2407.05000) | ❌ ELE | PEFT'e EKLENMEDİ — issue #2927 native merge olmadan kapandı; harici `Outsider565/LoRA-GA` reposu gerekir. Kural 7: native-değil entegre edilmez. |
| `orthogonal` init | ✅ ZATEN VAR | `peft_lora_train.py:_INIT_STRATEGIES` içinde mevcut (kod kapsıyor) ama dedup defterinde eksikti → log'a eklendi (doküman düzeltmesi). |
| `assistant_only_loss` (2026-06-22 günlük adayı) | ⚠️ GEREKSİZ | Bulut notebook şablonu (Hücre 10) ZATEN `train_on_responses_only` ile asistan-dışı turları maskeliyor — TRL `assistant_only_loss` ile işlevsel olarak AYNI. Ayrı entegrasyon mükerrer; veri-format dönüşümü riski de cabası. Günlük aday bu mevcut entegrasyonla **karşılanmış** sayılır. |
| VeRA / MiLoRA / LoRA-FA | ❌ ELE | Parametre-azaltma odaklı; v5 disiplin-gerilemesiyle ilgisiz (sorun param sayısı değil, forgetting/degenerasyon). |
| O-LoRA / CLoRA / EWCLoRA / FIP | ❌ ELE | Continual-learning; PEFT-native değil + çok-görev orthogonality makinesi gerektirir (tek-adapter Achilles akışına uymaz). CLoRA/EWCLoRA zaten 2026-06-22 günlükte elenmişti. |
| DFT `loss_type="dft"` (ICLR 2026) | ❌ ELE | 2026-06-22 günlükte elendi; yalnız math/reasoning'de test, 4B/disiplin doğrulanmadı. Tekrar araştırılmadı. |
| `target_modules="all-linear"` (Unsloth 2026) | ✅ ZATEN HİZALI | Achilles `TARGET_MODULES` zaten tüm linear projeksiyonları (q/k/v/o + gate/up/down) hedefliyor; embed/lm_head bilinçli dışarıda (Qwen3 tied-embeddings / GGUF güvenliği). Değişiklik yok. |

**Doküman/sürüm:** Anlamlı (entegre edilebilir) yeni bulgu olmadığından `LORA_EGITIM_DETAYLI_ANLATIM.md`
sürümü ARTIRILMADI; PDF yeniden üretilmedi (protokol §6: yalnız anlamlı bulguda). Yalnız bu defter
güncellendi (dedup listesine `orthogonal` + elenen-adaylar bloğu + kaynaklar).

**Takip (gözetimli seansa not):** `configs/lora/lora_profiles.yaml` yorum satırı (init seçenekleri)
`orthogonal`/`corda`'yı listelemiyor — saf yorum düzeltmesi ama reçete dosyası olduğu için Kural 5
gereği PR ister; bu otonom turda dokunulmadı.

### Kaynaklar (Tur 2 — 2026-06-22)

| Teknik / Konu | Kaynak |
|---------------|--------|
| LoRA-GA (PEFT-native değil — issue) | <https://github.com/huggingface/peft/issues/2927> · arXiv 2407.05000 |
| PEFT init listesi (orthogonal/eva/gaussian) | <https://huggingface.co/docs/peft/main/en/developer_guides/lora> |
| Unsloth Qwen3 2026 (all-linear öneri) | <https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune> |
| TRL SFT (assistant_only_loss ↔ response-only) | <https://huggingface.co/docs/trl/sft_trainer> |

> Kural 7 notu: VeRA/MiLoRA/LoRA-FA/O-LoRA/CLoRA/AILoRA/D²LoRA için atıf gören arXiv'ler var ama
> Achilles'e uygun + PEFT-native + v5-ilgili kriterini geçmediklerinden entegre edilmedi; yeniden
> derin-araştırma yapılmaması için "Elenen adaylar" defterine işlendi.

---

## Günlük tarama — 2026-06-22 (yönlü tarama, kullanıcı isteği)

**Tetikleyici:** Kullanıcı isteği — "v5 disiplin gerilemesine yönelik güncel SFT/LoRA tekniği
ara; kodu değiştirme, yalnız öner."

**Yöntem:** Çok açılı WebSearch (catastrophic forgetting / küçük model / disiplin koruma /
eval-aware / TRL/PEFT yeni özellikler) + adversarial doğrulama.

**Taranan ve elenen adaylar:**

| Aday | Eleme gerekçesi |
|------|-----------------|
| OPLoRA (arXiv 2510.13003) | PEFT native desteği yok; custom trainer gerekir |
| SC-LoRA (arXiv 2505.23724) | PEFT native desteği yok; research prototype |
| EWCLoRA / Hierarchical Layer-wise (arXiv 2501.13669) | Kod henüz yayımlanmadı |
| DFT `loss_type="dft"` (arXiv 2508.05629) | Yalnız math/reasoning'de test edilmiş; disiplin etkisi belirsiz; 4B doğrulanmamış |

**Onaylanan aday: `assistant_only_loss=True` (TRL SFTConfig)**

- **Kaynak:** TRL v1.6.0 resmi docs + sft_config.py main branch
  (https://huggingface.co/docs/trl/sft_trainer)
- **Ne yapar:** SFTConfig'e `assistant_only_loss=True` eklendiğinde kayıp yalnız asistan
  yanıtı tokenlarından hesaplanır; sistem mesajı ve kullanıcı turları maskelenir. Qwen3
  için TRL otomatik chat template patch uygular (jinja `{% generation %}` ekleme gerektirmez).
- **v5 bağlantısı:** v5 gerilemesinin kök sebebi sentetik-QA reçetesinin disiplin
  refusal tokenlerini bozuk loss hesabıyla (sistem turu dahil) ezmesiydi. `assistant_only_loss`
  sistem/kullanıcı turlarını maskeler → refusal/abstain davranışını öğrenirken gereksiz
  sistem-token sinyali karışmaz.
- **GGUF-güvenli:** Evet — yalnız eğitim-zamanı loss maskeleme; mimariyi/ağırlıkları değiştirmez.
- **PEFT uyumlu:** Evet — TRL SFTTrainer + SFTConfig; bulut notebook zaten SFTConfig kullanıyor.
- **Kısıt:** Bulut notebook'ta veri formatı `"text"` alan kullanıyor (dil modelleme modu);
  `assistant_only_loss` yalnız conversational (mesaj listesi) formatında çalışır. Veri
  dönüşümü veya `dataset_text_field` kaldırılması gerekir. Bu yüzden **OPT-IN** olarak
  bırakılmalı; varsayılan bozulmamalı.

**Entegrasyon önerisi (kod değiştirilmedi — PR gerektirir):**

- `app/training/peft_lora_train.py` → `PeftTrainConfig`'e `assistant_only_loss: bool = False`
  alanı ekle; `build_training_kwargs` içinde `SFTConfig`'e (veya `TrainingArguments` yerine
  geçirilecek `SFTConfig`'e) bu bayrağı geç.
- `app/training/cloud_notebook.py` + şablon → `build_stage2_notebook` parametresine
  `assistant_only_loss: bool = False` ekle; notebook şablonunda SFTConfig'e enjekte et;
  veri formatını conversational moda çevir (messages listesi).
- `configs/lora/lora_profiles.yaml` → `discipline_safe` profiline `assistant_only_loss: true`
  satırını ekle (v5 reçetesiyle doğrudan uyumlu).

**NOT (Kural 2):** Reçete hipotezdir. Bulut eğitim koşusu + `adapter_eval` gate'i ile
doğrulanana kadar "daha iyi" denmez.

### Kaynaklar (Günlük tarama 2026-06-22)

| Teknik / Konu | Kaynak |
|---------------|--------|
| assistant_only_loss / TRL SFTConfig | <https://huggingface.co/docs/trl/sft_trainer> |
| TRL sft_config.py (parametre doğrulama) | <https://github.com/huggingface/trl/blob/main/trl/trainer/sft_config.py> |

---

## Tur 1 — 2026-06-17 (derin tur)

**Tetikleyici:** Kullanıcı isteği — "LoRA eğitimini iyileştirmek için makaleleri araştır,
dokümanı güncelle, entegre et, push et."

**Yöntem:** Çok-ajanlı workflow (`lora-research-sweep`): 8 paralel web-tarama açısı →
adversarial doğrulama (her teknik gerçek mi? PEFT/Unsloth destekli mi? Achilles'e uygun mu?
GGUF-güvenli mi? v5 regresyonuna yardım eder mi?) → önceliklendirilmiş sentez.

**Entegre edildi (kod):**
- **rsLoRA / DoRA / `init_lora_weights` (PiSSA/OLoRA/EVA/LoftQ/CorDA)** — `PeftTrainConfig`
  alanları + `build_lora_kwargs()` saf builder; `LoraConfig(**build_lora_kwargs(cfg))`.
- **LoRA+** — `loraplus_lr_ratio>0` ise `create_loraplus_optimizer` Trainer'a bağlanır.
- **NEFTune** — `neftune_noise_alpha` → `TrainingArguments`/`SFTConfig`.
- **Regularizasyon** — yerel trainer'a warmup·cosine·weight_decay·grad-clip·seed eklendi
  (`build_training_kwargs()`); bulut reçetesiyle hizalandı.
- **`discipline_safe` profili** — v5 catastrophic-forgetting reçetesi (düşük lr + az epoch +
  NEFTune + yüksek dropout + grad-clip).
- **Bulut notebook parametrik** — alpha/dropout/rsLoRA/NEFTune/weight_decay/warmup placeholder.
- **Degenerasyon tespiti güçlendirildi** — `_max_ngram_repeat` (token-düzeyi döngü) + satır tekrarı.

**Dosyalar:** `app/training/peft_lora_train.py`, `app/training/cloud_notebook.py`,
`app/training/templates/stage2_lora_colab.ipynb`, `app/training/adapter_eval.py`,
`configs/lora/lora_profiles.yaml`, `app/main.py` (`--profile`). Testler:
`tests/test_peft_lora_recipe.py`, `tests/test_adapter_eval_degenerate.py`.

**Doğrulama:** ruff + mypy temiz; 162 + 33 yeni test geçti; bulut notebook üretimi
uçtan uca doğrulandı (geçerli JSON, placeholder yok). **NOT (Kural 2):** Reçete bir
*hipotez*tir — bir bulut eğitim koşusu + `adapter_eval` gate'i ile doğrulanana kadar
"daha iyi" denmez.

### Kaynaklar (Tur 1)

| Teknik / Konu | Kaynak |
|---------------|--------|
| LoRA hiperparametre rehberi | <https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide> |
| Qwen3 fine-tune | <https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune> |
| rsLoRA/DoRA/init/LoRA+ API | <https://huggingface.co/docs/peft/main/en/developer_guides/lora> |
| NEFTune/SFT | <https://huggingface.co/docs/trl/sft_trainer> |
| rsLoRA | arXiv 2312.03732 |
| DoRA | arXiv 2402.09353 · <https://github.com/NVlabs/DoRA> |
| NEFTune | arXiv 2310.05914 · <https://github.com/neelsjain/NEFTune> |
| LoftQ | <https://github.com/yxli2123/LoftQ> |
| Nöral metin degenerasyonu | arXiv 1904.09751 |

> Not: Çok-ajanlı sweep bazı ek aday makaleler (örn. 2024-2025 catastrophic-forgetting
> çalışmaları) getirdi; bağlantısı/atfı kesin doğrulanmayanlar bu tabloya alınmadı (Kural 7).
