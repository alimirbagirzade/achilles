# RLM motor adapter — alexzhang13/rlm opsiyonel entegrasyonu

_Kaynak talimat: `Desktop/RAG Kaynak/RLM/achilles_alexzhang_rlm_claude_integration_prompt.txt`_

## RLM nedir, Achilles'te ne işe yarar?

[alexzhang13/rlm](https://github.com/alexzhang13/rlm) (PyPI: `rlms`, import: `rlm`),
**Recursive Language Models** için bir inference kütüphanesidir: uzun context'i tek
seferde modele basmak yerine programatik olarak parçalayıp recursive alt-LLM çağrıları
yapar. Achilles'te bu, RLM Controller'ın **altında OPSİYONEL bir motor**dur.

## RAG / Paper Mastery'nin YERİNE GEÇMEZ

| Bileşen | Rol |
|---------|-----|
| Achilles RAG (Chroma + SQLite) | bilgi hafızası — değişmez |
| Paper Mastery | makalenin kullanılabilirlik testi — değişmez |
| Verifier'lar | cevabın kaynakla desteklendiğini ölçer — değişmez |
| **RLM Controller (native)** | **çekirdek + VARSAYILAN reasoning motoru** |
| alexzhang13/rlm (opsiyonel) | yalnız recursive inference motoru (RAG/parser/embedding DEĞİL) |

```
PDF → Achilles ingestion → chunks → embeddings → Paper Registry → Paper Mastery
User query → RAG retrieval → Evidence Pack → RLM adapter (native|alexzhang) → Verifier → grounded answer
```

## Varsayılan: native (rlms gerekmez)

`rlm_engine_provider=native` (varsayılan) → mevcut `RlmController` tüm grounded akışı yapar.
`rlms` paketi **kurulu olmasa bile** Achilles tam çalışır.

## OpenAI VARSAYILAN değildir

alexzhang adapter backend'i `anthropic`'tir (veya açıkça verilen yerel OpenAI-uyumlu
endpoint). OpenAI cloud zorunlu dependency/default DEĞİLDİR; `OPENAI_API_KEY` gerekmez.
Geliştirmede Claude Code kullanılır; runtime'da Anthropic/Claude veya yerel Ollama/native.

## alexzhang motoru nasıl açılır?

```bash
# 1) opsiyonel paketi kur (yoksa native çalışmaya devam eder)
uv sync --extra rlm            # veya: uv pip install -e ".[rlm]"

# 2) env ile aç (varsayılan native + kapalı)
ACHILLES_RLM_ENGINE_PROVIDER=alexzhang
ACHILLES_RLM_ALEXZHANG_ENABLED=true
ACHILLES_RLM_ALEXZHANG_BACKEND=anthropic   # OpenAI değil
ACHILLES_RLM_ALEXZHANG_ENVIRONMENT=docker  # üretimde 'local' yasak
ANTHROPIC_API_KEY=...                       # yalnız gerekiyorsa, .env'de (commit etme)
```

Kurulu değil/güvensiz/başarısızsa sistem otomatik **native'e düşer** (bozulmaz).

## Çalışma modları (özet)

| Mod | environment | Açıklama |
|-----|-------------|----------|
| native | — | rlms gerekmez; RlmController (varsayılan) |
| docker | docker | rlms recursive motoru izole konteyner REPL'inde (önerilen) |
| ipython | ipython | izole IPython/subprocess |
| local | local | host-içi exec — **üretimde YASAK** (güvenlik kapısı reddeder) |

Detay: [`rlm_runtime_modes.md`](rlm_runtime_modes.md), [`rlm_security_model.md`](rlm_security_model.md).

## CLI

```bash
uv run achilles rlm-engine                    # motor config (salt-okuma)
uv run achilles rlm-test-adapter --adapter native
uv run achilles rlm-test-adapter --adapter alexzhang
# kaynaklı cevap (native varsayılan):
uv run achilles rlm-answer "Momentum stratejisi yüksek volatilitede zayıflıyor mu?"
# opsiyonel motoru dene (kurulu+açık+güvenli değilse sessizce native'e düşer):
uv run achilles rlm-answer "..." --engine alexzhang
# güvenli tool allowlist'i listele veya saf bir tool'u çağır:
uv run achilles rlm-tools
uv run achilles rlm-tools --call calculator --expr "2*(3+4)"
uv run python -m app.rlm.answer_pipeline --query "..." --adapter native
```

## API uçları

```text
POST /api/rlm/answer            # RLM Controller (native): kaynaklı + doğrulanmış cevap
GET  /api/rlm/runs              # son koşular
GET  /api/rlm/runs/{run_id}     # koşu detayı (adım + kanıt + doğrulama)
GET  /api/rlm/config            # motor config (salt-okuma; sır YOK)
POST /api/rlm/test-adapter      # ?adapter=native|alexzhang → uygunluk (çağrı yapmaz)
```

## Tool allowlist

RLM motoruna serbest Python/exec verilmez. Yalnız `app/rlm/engine_config.ALLOWED_TOOL_NAMES`
(rag_search, get_paper_chunks, get_paper_metadata, citation_check, grounding_check,
contradiction_check, formula_check, calculator) — her biri `app/rlm/safe_tools.py`'de
input-doğrulamalı, shell/network/secret-erişimsiz güvenli wrapper.

## Public GitHub güvenlik notları

- Gerçek key/token commit edilmez (`.env` ignore'da; `.env.example` boş şablon).
- RLM trajektori logları (`reports/rlm/trajectories/`, `reports/rlm_runs/`) ignore'da.
- Üretimde local exec/shell/network/filesystem-write kapalı (güvenlik kapısı).

## Eklenen dosyalar

`app/rlm/adapters/{base,native,alexzhang_rlm,security}.py`, `app/rlm/{engine_config,
tool_registry,safe_tools,answer_pipeline}.py`; Settings `rlm_engine_*`/`rlm_alexzhang_*`;
CLI `rlm-engine`/`rlm-test-adapter`/`rlm-tools` + `rlm-answer --engine`; web `GET /api/rlm/config`
+ `POST /api/rlm/test-adapter`; testler `tests/test_rlm_engine_*`, `test_rlm_tool_allowlist`.

alexzhang yolu cevabı verifier'la doğrular, kaynaklara `support_level` (strong|partial|weak)
ekler ve koşuyu `rlm_store`'a yazar (best-effort) → `rlm-runs` / `/api/rlm/runs` görür.

## Kalan / sonraki adımlar

- Level 3 izole REPL (docker/ipython) gerçek koşumu — ortam hazır olunca; şu an güvenlik
  kapısı + config iskeleti hazır, ortam yoksa temiz hata.
- Trajektori logları (`reports/rlm/trajectories/`) — alexzhang motoru kurulu+çalışınca üretilir
  (dizin `.gitignore`'da; runtime çıktısı).
