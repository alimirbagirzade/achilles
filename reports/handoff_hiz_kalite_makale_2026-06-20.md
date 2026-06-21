# HANDOFF — LoRA hız + okuma/anlama kalitesi (yeni makale uygulaması)

**Tarih:** 2026-06-20
**Branch:** `feat/otonom-baslangic-zinciri` (hepsi push'lu)
**Bağlam:** "LoRA hızlı + kaliteli okuma-anlama; yeni inen 27 makaleyi uygula/sentezle" isteği.
Çok-ajan workflow (anla→tasarla→adversarial doğrula→sentez) + 27-makale haritalama workflow'u.

---

## ✅ Bu seansta YAPILAN (commit+push, test yeşil)

| İş | Makale | Commit |
|----|--------|--------|
| R-Tuning abstain tuzakları (`gelecek_tahmin` + `canli_veri_yok`, kalibre "bilmiyorum") | 2311.09677 | `c420d3b` |
| Deflated Sharpe (`BacktestMetrics.sharpe_deflated`, Lo-2002 SE + parametre cezası) | 1905.05023 | `7a738a9` |
| `forbidden_pattern_rate` + `complexity_entropy` (Bandt-Pompe; registry FORBIDDEN/COMPLEXITY) | 0711.0729 + 1808.01926 | `d15c6d5` |
| ExamSpec FORBIDDEN + COMPLEXITY (anlama-sınavı kapsamı) | — | `f6dc98a` |
| S1 CLI veri-tazeleme hook + S3 RAGAS context_precision (gözlemsel) | 2309.15217 | `3de5082` |
| train-loop veri-tarafı fix (`assemble_sft.py`, synth+kart+disiplin) | — | `08790d1` |

**Veri/paket:** Bulut paketi 528 disiplinle (R-Tuning dahil) YENİDEN üretildi → `notebooks/achilles_lora_stage2.ipynb`. `pretrain-gate` **GO** (2020 örnek, açılış %4). Eğitim verisi artık abstention örnekleri içeriyor.

**Eğitim durumu:** CPU eğitimi terk edildi (4B ~150-230sn/adım ≈ 77h, step 8'de ölmüştü). Karar = bulut T4 (bkz memory `cloud-training-decision`: notebook "HF'siz", Kaggle T4). Phase-2 onay kapısı gözetimsiz loop'u bloke ediyor (tasarım gereği, Kural 8).

---

## ⏳ KALAN YOL HARİTASI (sonraki seans — workflow önerdi, henüz yapılmadı)

1. **Self-RAG karar kapısı** — iskelet `app/brain/self_refining_rag.py` VAR; retrieve-on-demand güven eşiği bağla.
2. **CRAG offline-fallback** — `app/reliability/source_trust.py`; getirme-sonrası relevance sınıflandırma → düşükte alternatif yerel chunk (web DEĞİL — offline ilkesi).
3. **RAGAS `answer_relevance` + regresyon kapısı** — `app/evals/rag_ragas_offline.py`'a metrik + `regression_runner.py`'a bağla.
4. **Kalman-Markov rejim indikatörü** (2601.05716) + Adaptive Conformal bantları (2202.07282).
5. **CoT-faithfulness L3/L4** (NLI gerekçe doğrulama) — büyük yeniden-tasarım; ertelendi.

**ELENDİ (boşa efor):** Qwen2.5-1.5B varsayılan base (4B invariant bozar), ALCE (`CitationCheck.supported` ölü kod), semantik retrieval (fake-embed SHA256), DeepAR (RNN/GPU).

---

## ⚠️ KRİTİK KURALLAR (sonraki seans unutma)

- **faithfulness/context_precision'ı L2 GEÇME kapısına AND olarak EKLEME** — korele token-proxy sınır cevapları haksız eler = v5-sınıfı over-tightening. Yalnız GÖZLEMSEL logla (Kural 2).
- Eşzamanlı oturum aynı repo'da çalışıyor; branch/HEAD kayabilir. Dar `git add <dosya>` + hemen commit+push.
- Bozuk plugin hook'u (`check-sql-files.py` eksik) her edit'te hata basıyor — zararsız, değişiklikleri etkilemiyor; `.claude` ayarından temizlenebilir.

İlgili memory: `hiz-kalite-makale-uygulama`, `lora-loop-guvenlik-verdicti`, `cloud-training-decision`, `v5-adapter-regression`.
