# RLM güvenlik modeli (opsiyonel alexzhang motoru)

## Tehdit: REPL / kod yürütme

alexzhang13/rlm'in varsayılan yerel REPL ortamı, host process içinde Python `exec`
çalıştırabilir. Bu üretimde **uzaktan-kod-yürütme** sınıfı risktir. Achilles'te native
motor kod YÜRÜTMEZ; risk yalnız alexzhang motoru `environment="local"` ile açılırsa doğar.

## Güvenlik kapısı (`app/rlm/adapters/security.py`)

`AlexZhangRLMAdapter.complete()` çalışmadan ÖNCE `validate_rlm_runtime_security(config)`
çağrılır. Üretim modunda (`rlm_production_mode=True`, varsayılan) şunlar **reddedilir**
(`RLMUnsafeRuntimeError` → çağıran native'e düşer):

- `environment == "local"` (host-içi exec)
- `allow_local_exec=True`
- `allow_shell=True`
- `allow_network=True`
- `allow_filesystem_write=True`

Varsayılanlar (Settings) hepsi **kapalı** + `environment="docker"` → güvenli.

## Tool allowlist (`app/rlm/tool_registry.py`)

RLM'ye serbest tool verilmez. `SafeToolRegistry` yalnız `ALLOWED_TOOL_NAMES`'teki adları
kaydeder/çağırır; allowlist dışı ad → `ToolNotAllowed`. Her wrapper (`safe_tools.py`):
input doğrular, çıktıyı sınırlar, shell/network çalıştırmaz, secret/env okumaz, filesystem
yazmaz, exception'ı structured hataya çevirir.

## Secret yönetimi

- Gerçek key/token kodda/commit'te YOK. `ANTHROPIC_API_KEY` yalnız `.env`'de (ignore'da).
- `.env.example` boş şablondur (gerçek değer yok).
- `engine_config.public_engine_config()` API/CLI'ye yalnız sır-içermeyen görünüm verir.

## Network / filesystem

- Varsayılan: ağ kapalı, filesystem yazımı kapalı (güvenlik kapısı zorlar).
- Native motor yalnız mevcut Achilles servislerini (retriever/verifier/SQLite) okur.

## Public repo hijyeni

`.gitignore` kapsar: `.env`, `.env.*` (`!.env.example`), `storage/sqlite/*.db`,
`vector_db/chroma/*`, `reports/rlm_runs/*`, `reports/rlm/trajectories/`. Trajektori/run
logları, db, vector store, secret public repo'ya **girmez**. Regresyon testi:
`tests/test_rlm_engine_adapters.py::test_no_secret_patterns_in_rlm_engine_source`.

## Güvenlik incelemesi

Bu entegrasyon adversarial güvenlik incelemesinden geçirilir (bkz.
`.claude/agents/rlm-security-reviewer.md`): local-exec, shell, network, filesystem-write,
secret sızıntısı, tool allowlist, .env/.gitignore — PASS/FAIL.
