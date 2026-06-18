# Achilles — Automation Architecture (Phase 0/1)

_Durum: Phase 0 (belge + manifest) + Phase 1 (runtime gözlemci) tamamlandı.
Phase 2 (task queue + approvals + supervisor) HENÜZ YOK._

Bu belge, Achilles'in mevcut **otonomi yüzeyini** ve **güvenlik sınırlarını** tanımlar.
Tek, bildirimsel kaynak: [`automation_manifest.yaml`](../automation_manifest.yaml)
(`app/agents/runtime/registry.py` ile okunur).

---

## 1. Mevcut agent'lar (runtime)

15 runtime-agent-benzeri bileşen denetimde (audit) bulundu ve manifest'e işlendi.
Tam alanlar için manifest'e bakın; özet:

| agent_id | otonomi | tehlikeli | onay gerekir | varsayılan açık |
|----------|---------|-----------|--------------|-----------------|
| auto-lora-pipeline | requires_approval | ✅ | ✅ | ❌ |
| rag-learning-loop | autonomous | ❌ | ❌ | ❌ (kullanıcı açar) |
| research-orchestrator | semi_auto | ❌ | ❌ | ❌ |
| rag-trend-scanner | semi_auto | ❌ | ❌ | ❌ |
| reflection-agent | manual | ❌ | ❌ | ❌ |
| paper-mastery-agent | semi_auto | ❌ | ❌ | ❌ |
| status-manager | manual | ❌ | ❌ | ❌ |
| lora-control-plane | semi_auto | ❌ | ❌ | ❌ |
| adapter-eval | semi_auto | ❌ | ❌ | ❌ |
| dataset-quality-gate | semi_auto | ❌ | ❌ | ❌ |
| tool-use-trainer | semi_auto | ❌ | ❌ | ❌ |
| auto-researcher | semi_auto | ❌ | ❌ | ❌ |
| arxiv-fetcher | autonomous | ❌ | ❌ | ❌ |
| rules-updater | requires_approval | ❌ | ✅ | ❌ |
| model-advisor | autonomous | ❌ | ❌ | ❌ |

`agent_id` listesi `uv run achilles agents-list` ile de görülebilir.

## 2. Mevcut döngüler (loops)

İki gerçek arka plan döngüsü (web sunucusu açılışında asyncio task olarak başlar ama
**içeride varsayılan KAPALI**):

- **rag-learning-loop** (`app/research/rag_learning_loop.py`) — 15s heartbeat;
  `interval_min` dolunca bir tur çalışır: arXiv çek → indeksle → kart → skor → ustalık.
  **LoRA eğitimi sürerken kendini DURAKLATIR** (`_training_running` → `paused_training`).
  Web'den `/api/rag-loop/enable` ile açılır. Durum: `storage/rag_learning_state.json`.
- **auto-lora-pipeline** (`app/lora/auto_pipeline.py`) — `check_interval_min`'de onaylı
  kart sayısını kontrol eder; eşik geçilirse Gate 0-8 çalışır → `READY_TO_TRAIN`.
  **Eğitim ve terfi insan onayı bekler.** Durum: `storage/auto_lora_state.json`.

Kabuk (shell) döngüleri (uygulama dışı, Windows Task Scheduler / elle): bkz. §6.

## 3. Mevcut güvenlik kapıları (safety gates)

- **CLAUDE.md sert kuralları** koda gömülü (denetimle doğrulandı): maliyet (commission+slippage),
  look-ahead `shift(1)`, `eval`/`exec` yasağı (whitelist AST), seed determinizmi,
  boş-retrieval'da dürüst "kaynak yok", `train --run` varsayılan KAPALI.
- **Gate 0-8** (`lora/control_plane.py`): Gate 7 safety scanner = BLOCKER.
- **pretrain-gate** (`training/dataset_quality.py`): garanti-vaadi / açılış-ezberi → NO-GO.
- **adapter-eval** (`training/adapter_eval.py`): gerçek base-vs-adapter; regresyon → reject; TERFİ ETMEZ.
- **rag-learning-loop**: eğitim sırasında duraklar; `is_substantive_card` içerik kapısı.
- **Phase 1 gözlemci**: ajan koşuları artık `agent_runs`/`agent_events` + JSONL'e kaydedilir
  (gözlem **davranışı değiştirmez**, hata fırlatmaz).

## 4. Şu an otomatik olan

- Makale çekme/indeksleme (idempotent), kart üretimi, comprehension/mastery skorlama,
  RAG öğrenme turu (kullanıcı açarsa), arXiv trend tarama (zamanlanırsa),
  haftalık **rapor-only** bug-scan, CI (ruff+mypy+pytest offline).
- Auto-LoRA **denetim** (Gate 0-8) otomatik; **eğitim/terfi DEĞİL**.

## 5. Şu an otomatikleştirilmesi YASAK olan

- Gerçek LoRA eğitiminin gözetimsiz başlatılması.
- Adapter'ın production'a otomatik terfisi.
- `data/`, `storage/`, `vector_db/`, `models/adapters/` üzerinde otomatik ajan değişikliği.
- `main`'e otomatik push / auto-merge.

## 6. 🔒 GÜVENLİK DONDURMA (Safety Freeze)

Aşağıdakiler **Phase 2 supervisor + approval gelene kadar GÖZETİMSİZ çalıştırılmamalıdır**:

| Öğe | Neden | Şimdilik kural |
|-----|-------|----------------|
| `uv run achilles train --run` | gerçek LoRA eğitimi (geri alınması pahalı; v5 regresyonu) | her koşu **elle, ayrı onay** |
| `scripts/train-loop.ps1` | 24s döngüde tekrar tekrar `train --run` | elle başlat, denetimli; loop'ta bırakma |
| `scripts/mac-loop.sh` | MLX `train --run` her turda | elle, denetimli |
| `scripts/auto-chain.sh` | zincir sonunda 24s eğitim döngüsü | elle, denetimli |
| adapter promotion (`/api/auto-lora/promote`) | base'i değiştirir | yalnız EVAL_PASSED + **insan onayı** |

Phase 1 `train --run` çalıştırıldığında konsola bu uyarıyı basar (davranışı değiştirmez).

### Neden `train --run` manuel approval gerektirmeli?

1. **Geri alınması pahalı.** Eğitim saatler sürer (v5: 46.75 saat CPU) ve çıktı
   `models/adapters/` altına yazılır; kötü bir koşu zaman + disk + (terfi edilirse) kaliteyi yer.
2. **v5 dersi.** Otomatik kalite sinyalleri yanılabilir — v5 "başarıyla eğitildi" ama
   disiplinde GERİLEDİ; eval harness adapter'ı yüklemiyordu. Otomatik "geçti" güvenilmez.
3. **CLAUDE.md Kural 2 + 8.** "Test edilmeden başarılı deme" ve "otomatik ağır eğitim yok".
   CI offline testleri eğitim kalitesini KANITLAYAMAZ; bu yüzden insan kapısı şart.
4. **Kaynak çakışması.** Eğitim ~7GB RAM ister; LLM/RAG ile çakışır. Zamanlamayı insan görmeli.

Phase 2'de bu, supervisor + `approval_requests` ile **zorunlu** hale gelecek; Phase 1'de
yalnız **belge + uyarı** düzeyindedir (mevcut davranış bilinçli olarak korunmuştur).
