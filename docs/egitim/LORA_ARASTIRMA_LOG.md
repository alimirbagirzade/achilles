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
`NEFTune` · `gaussian-init` · `QLoRA` · `train_on_responses_only` · `cosine-warmup` ·
`weight-decay` · `gradient-clipping` · `replay/rehearsal` · `n-gram-repetition-detection`

## Kapsanan kaynaklar (arXiv ID / URL)

- arXiv 2312.03732 (rsLoRA) · arXiv 2402.09353 (DoRA) · arXiv 2310.05914 (NEFTune) ·
  arXiv 1904.09751 (neural text degeneration)
- unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide
- unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune
- huggingface.co/docs/peft/main/en/developer_guides/lora (rsLoRA/DoRA/init/LoRA+)
- huggingface.co/docs/trl/sft_trainer (NEFTune/response-only/packing)
- github.com/NVlabs/DoRA · github.com/neelsjain/NEFTune · github.com/yxli2123/LoftQ

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
