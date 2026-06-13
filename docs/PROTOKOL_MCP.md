# MCP SENKRON PROTOKOLÜ — Achilles Web → MCP

> Achilles web API'sini (68 endpoint) MCP tool'ları olarak dışarı açar; başka
> Claude oturumları / araçlar Achilles ile **tool** üzerinden konuşabilir.
> Sunucu: `mcp_server/achilles_mcp.py` · Skill: `/achilles-web`

## Nasıl çalışır (otomatik senkron)

```
app/web/server.py (FastAPI, 68 route)
        │  app.openapi()  (IN-PROCESS, her başlangıçta taze)
        ▼
mcp_server/achilles_mcp.py  ──FastMCP.from_openapi──►  68 MCP tool
        │  httpx proxy
        ▼
çalışan web sunucusu (http://127.0.0.1:8765)  ──►  gerçek iş
```

- **Spec in-process üretilir** (`achilles_app.openapi()`) — web'e yeni route
  eklendiğinde MCP **yeniden başlatıldığında** tool listesi otomatik güncellenir.
- **Çağrılar çalışan web'e proxy'lenir** — MCP içinde uygulama yeniden init edilmez,
  SQLite kilit çakışması olmaz. (Web sunucusu açık olmalı: `uv run achilles-web`.)

## Senkron kuralı (ZORUNLU)

**`app/web/server.py` her değiştiğinde → MCP yeniden başlatılmalı** ki yeni/değişen
endpoint'ler tool olarak yansısın. Elle spec güncellemeye gerek YOK (in-process üretilir).

```bash
# Yeniden senkronla (web değişikliğinden sonra):
bash scripts/sync-mcp.sh
```

> CLAUDE.md doğrulama akışına ek madde: `app/web/server.py` değiştiyse
> `make test`'ten sonra `bash scripts/sync-mcp.sh` çalıştır (MCP'yi tazele).

## Kurulum / kayıt

```bash
claude mcp add achilles -- uv run --project <repo-yolu> python mcp_server/achilles_mcp.py
claude mcp list            # 'achilles' bağlı mı kontrol
```

## Kullanım
Kayıt sonrası `achilles-*` tool'ları erişilebilir olur (örn. `api_status`,
`api_ask`, `api_rag_mastery`, `api_synthesis_reports`...). Detaylı kullanım: `/achilles-web` skill.

## Doğrulama
```bash
uv run python -c "import asyncio; from mcp_server.achilles_mcp import mcp; \
import asyncio as a; print(a.run(mcp.list_tools().__await__().__next__) if False else len(a.run(mcp.list_tools())))"
# beklenen: 68 (web route sayısıyla eşleşmeli)
```
