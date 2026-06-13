"""Achilles Web MCP sunucusu — web API'sini MCP tool'larına çevirir.

Tasarım (otomatik senkron):
- OpenAPI spec'i Achilles FastAPI uygulamasından IN-PROCESS üretilir
  (`app.web.server.app.openapi()`), böylece web'e her yeni route eklendiğinde
  MCP yeniden başlatıldığında otomatik yansır — elle güncelleme gerekmez.
- Tool çağrıları ise ÇALIŞAN web sunucusuna (http://127.0.0.1:8765) httpx ile
  proxy'lenir; uygulama MCP içinde yeniden init edilmez, SQLite kilit çakışması olmaz.

Çalıştırma (stdio MCP):
    uv run python mcp/achilles_mcp.py

Kayıt:
    claude mcp add achilles -- uv run --project <repo> python mcp/achilles_mcp.py

Senkron protokolü: web (app/web/server.py) değişince → MCP'yi yeniden başlat
(veya Claude Code'u). Spec her başlangıçta taze üretildiği için tool listesi güncellenir.
Ayrıntı: docs/PROTOKOL_MCP.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo kökünü path'e ekle (script doğrudan çalıştırılabilsin)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("ACHILLES_WEB_URL", "http://127.0.0.1:8765")


def build_mcp():
    """Achilles OpenAPI'sinden FastMCP sunucusu kur (proxy → çalışan web)."""
    import httpx
    from fastmcp import FastMCP

    from app.web.server import app as achilles_app

    spec = achilles_app.openapi()  # in-process, güvenilir (65+ path)
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=120.0)
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="achilles-web",
    )


mcp = build_mcp()


if __name__ == "__main__":
    mcp.run()
