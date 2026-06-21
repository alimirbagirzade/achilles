# Seans Handoff — 2026-06-19 · Bulut eğitim kararı + Kademe-2 av + pretrain-gate

> Bu, tek bir oturumun kapanış özetidir. Kalıcı kısa-hafıza Claude memory'sinde
> (`cloud-training-decision`, `concurrent-session-worktree-collision`,
> `pretrain-gate-deferred-recovery`). Eşzamanlı oturum(lar) paralel çalıştığı için
> `HANDOFF.md` ana dosyasına dokunulmadı (çakışma riski); bu ayrı tarihli rapordur.

## Yapılanlar (hepsi commit'li + push'lu)

1. **pretrain-gate CLI geri eklendi** — `app/main.py` (commit `9286aa8`, main). LLM'siz GO/NO-GO
   eğitim-öncesi kalite kapısı; `audit_dataset` çağırır, açılış-ezberi/garanti-vaadi/boyut denetler.
   ruff+mypy temiz, 706 test yeşil, canlı **GO**.

2. **lora_sft.jsonl yeniden inşa** — 671 örnek (synth 310 + kart → dedup 503 + %25 disiplin).
   Kapı **GO**, en sık açılış "we propose" %7 (v5 zehiri pasaja-göre %68 → çözüldü), epoch 2.

3. **Kaggle-native eğitim paketi** (commit `68a2f3a`, main) — `notebooks/achilles_lora_stage2.ipynb`
   (HF GEREKMEZ, `/kaggle/input`'tan okur, discipline_safe reçetesi lr 1e-4 + NEFTune 5),
   `Modelfile`, `KAGGLE_EGITIM_ADIM_ADIM.md` (9 adım sıfır-varsayım kılavuz).

4. **Kademe-2 eğitim-öncesi ZORUNLU derin bug avı** (workflow, 77 ajan, 25 aday → 4 onay ≥2/3 oy):
   - Onaylanıp düzeltilenler (commit `9082b2b`, eşzamanlı oturum bundle'ına girdi):
     **BM25 berabere tie-break** (Kural 6 determinizm, ampirik üretildi), **citation_score
     gerçek-atıftan** (eval dürüstlüğü), **chunker embedding-güvenli cap** (sessiz-kesilme).
   - `auto_pipeline` base_model + `rag_exam` fake-pass zaten önceki sprint'te düzeltilmişti.
   - **backtest + indikatör alt-sistemleri tarandı → temiz** (tüm adaylar yanlış-pozitif).

## Ana karar (ölçümle): yerel 4B LoRA pratik değil → eğitim adımı bulutta

Smoke testi (qwen3-4B, **bf16**, önceki çöküş float32'ydi): **219 sn/adım · ~38.75 saat/epoch ·
bf16'da bile swap** (i7-1165G7, GPU yok, 32GB RAM'in ~17GB'si dolu). **Kullanıcı kararı:** tek
seferlik fine-tuning hesabı **ücretsiz Kaggle T4×2** (~20dk), `.gguf` indirilip **yerelde** çalışır.
Model+RAG+veri %100 yerel kalır. Paket main'de, kapı GO.

## Bekleyen işler

- **[KULLANICI]** Kaggle: hesap (Google) → telefon doğrula → `lora_sft.jsonl` Dataset yükle →
  notebook import → GPU T4×2 + Internet ON + Input ekle → **Run All** (~20dk) → `achilles-Q4_K_M.gguf`
  + `Modelfile` indir. Detay: `notebooks/KAGGLE_EGITIM_ADIM_ADIM.md`.
- **[CLAUDE, gguf inince]** `ollama create achilles -f Modelfile` →
  `uv run achilles evaluate evals/discipline_core.jsonl` + `lora-eval` (adapter'ı gerçekten yükle,
  base ile kıyasla) → disiplin sınavı geçerse **koşullu terfi**, geçmezse reçete revizyonu (kural 8).
- **PR** `feat/agent-runtime-phase2` → main: `gh` kurulu olmadığından elle açılacak →
  https://github.com/alimirbagirzade/achilles/compare/main...feat/agent-runtime-phase2?expand=1

## Bilinen sorun (eşzamanlı oturum domeni)

- **Web UI (8765) restart'ta numpy döngüsel-import yarışı** (`server.py` başlangıçta çoklu-thread
  numpy import → partially-initialized). numpy tek başına sağlam (2.4.6, test suite yeşil); şanslı
  restart / autostart ile gelir. `app/web/server.py`'yi eşzamanlı oturum düzenliyor → dokunulmadı.
