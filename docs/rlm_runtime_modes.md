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
| `docker`  | konteyner REPL | ✓ **üretimde tek izinli** |
| `ipython` | izole IPython/subprocess | ✗ üretimde reddedilir (yalnız `production_mode=false` dev) |
| `local`   | host-içi exec | ✗ **YASAK** (güvenlik kapısı reddeder) |

```
ACHILLES_RLM_ALEXZHANG_ENVIRONMENT=docker
ACHILLES_RLM_PRODUCTION_MODE=true        # local exec/shell/network/fs-write kapalı
```

Güvenlik kapısı **allow-list**'tir: üretimde yalnız `docker` geçer; `ipython`, `local` ve
bilinmeyen ortamlar `RLMUnsafeRuntimeError` ile reddedilir → native fallback.
Detay: [`rlm_security_model.md`](rlm_security_model.md).

### Ortam preflight'ı (Level 3 sertleştirme)

Güvenlik kapısından SONRA, motoru çağırmadan ÖNCE ortam hazırlığı kontrol edilir; eksikse
`rlms` içinde derin/anlaşılmaz stack yerine **temiz hata** verilir (`success=False` → native):

- `environment=docker` ama `docker` CLI PATH'te yok → "Docker bulunamadı…" + native fallback.
- `environment=ipython` ama IPython kurulu değil → "IPython kurulu değil…" + native fallback.

Uygunluğu çağrı yapmadan görmek için:
```bash
uv run achilles rlm-test-adapter --adapter alexzhang   # rlms + ortam hazırlığı
```
veya web: `POST /api/rlm/test-adapter?adapter=alexzhang` → `{available, environment_ready, note}`.

## Fallback zinciri

```
provider=alexzhang + enabled + paket kurulu + güvenli + başarılı  → alexzhang (doğrulanmış)
herhangi biri sağlanmazsa                                          → native (her zaman çalışır)
```
