# RLM çalışma-zamanı modları

Talimat §4'teki dört seviye. Bu PR Level 0 + 1 + temel Level 2'yi kapsar; Level 3 için
güvenlik kapısı + config iskeleti hazırdır (ortam yoksa temiz hata).

## Level 0 — Native (varsayılan)

```
ACHILLES_RLM_ENGINE_PROVIDER=native
```
Achilles kendi deterministik `RlmController`'ı ile çalışır. `rlms` bağımlılığı GEREKMEZ.
En güvenli, her zaman kullanılabilir. Kod yürütmez.

## Level 1 — Optional package mode

```bash
uv sync --extra rlm        # rlms>=0.1.2 kurar
```
`rlms` kuruluysa `AlexZhangRLMAdapter` kullanılabilir; **varsayılan yine native** kalır.
Kurulu değilse `is_available()=False`, `complete()` temiz hata → native fallback.

## Level 2 — Anthropic backend

```
ACHILLES_RLM_ALEXZHANG_BACKEND=anthropic
ACHILLES_RLM_ALEXZHANG_MODEL=          # boşsa anthropic_model'e düşer
ANTHROPIC_API_KEY=...                  # .env'de, commit etme
```
OpenAI key/provider GEREKMEZ. Yerel vLLM/OpenAI-uyumlu endpoint yalnız açıkça config'te
`local_openai_compatible` ile (OpenAI cloud default değil).

## Level 3 — İzole REPL (ortam gerektirir)

| environment | izolasyon | üretim |
|-------------|-----------|--------|
| `docker`  | konteyner REPL | ✓ önerilen |
| `ipython` | izole IPython/subprocess | ✓ |
| `local`   | host-içi exec | ✗ **YASAK** (güvenlik kapısı reddeder) |

```
ACHILLES_RLM_ALEXZHANG_ENVIRONMENT=docker
ACHILLES_RLM_PRODUCTION_MODE=true        # local exec/shell/network/fs-write kapalı
```

Üretimde `environment=local` veya `allow_local_exec/shell/network/filesystem_write=true`
→ `RLMUnsafeRuntimeError` → native fallback. Detay: [`rlm_security_model.md`](rlm_security_model.md).

## Fallback zinciri

```
provider=alexzhang + enabled + paket kurulu + güvenli + başarılı  → alexzhang (doğrulanmış)
herhangi biri sağlanmazsa                                          → native (her zaman çalışır)
```
