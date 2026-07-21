"""Achilles Web MCP sunucusu — web API'sini MCP tool'larına çevirir.

Tasarım (otomatik senkron):
- OpenAPI spec'i Achilles FastAPI uygulamasından IN-PROCESS üretilir
  (`app.web.server.app.openapi()`), böylece web'e her yeni route eklendiğinde
  MCP yeniden başlatıldığında otomatik yansır — elle güncelleme gerekmez.
- Tool çağrıları ise ÇALIŞAN web sunucusuna (http://127.0.0.1:8765) httpx ile
  proxy'lenir; uygulama MCP içinde yeniden init edilmez, SQLite kilit çakışması olmaz.

Gereksinim: ``fastmcp`` — opsiyonel ``mcp`` extra'sındadır::

    uv sync --extra mcp

Bu extra kurulmadan aşağıdaki komutlar ``ModuleNotFoundError`` ile düşer.

Çalıştırma (stdio MCP):
    uv run python mcp_server/achilles_mcp.py

Kayıt:
    claude mcp add achilles -- uv run --project <repo> python mcp_server/achilles_mcp.py

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


def auth_headers() -> dict[str, str]:
    """Web API'sine gidecek kimlik başlıkları.

    ``ACHILLES_API_TOKEN`` ayarlıysa proxy istekleri ``Authorization: Bearer ...``
    ile imzalanır. Bu olmadan token açıkken TÜM MCP tool çağrıları 401 alırdı →
    "token aç, MCP kırılsın / MCP çalışsın, kapı açık kalsın" kısır döngüsü.
    Token boşsa (varsayılan yerel mod) başlık gönderilmez; web tarafı da doğrulamaz.

    Ayar `.env` üzerinden de gelebildiği için önce ayarlar, sonra ham env okunur.
    """
    token = ""
    try:
        from app.config import get_settings

        token = get_settings().api_token.strip()
    except Exception:  # ayar katmanı yüklenemezse ham env'e düş
        token = ""
    if not token:
        token = os.environ.get("ACHILLES_API_TOKEN", "").strip()
    if token:
        _warn_if_token_leaves_loopback()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _warn_if_token_leaves_loopback() -> None:
    """``ACHILLES_WEB_URL`` loopback dışıysa stderr'e uyar (token o host'a gider).

    Sert hata DEĞİL bilinçli olarak: token ayarlamanın amacı zaten ağa açmaktır ve
    web sunucusu meşru biçimde başka bir makinede olabilir. Ama bearer token'ın
    yabancı bir host'a gideceği sessiz kalmamalı — stdio MCP'de stderr güvenlidir
    (protokol stdout'u kullanır).
    """
    from urllib.parse import urlparse

    host = (urlparse(BASE_URL).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1", "[::1]"}:
        print(
            f"GÜVENLİK UYARISI: ACHILLES_WEB_URL loopback değil ({BASE_URL}) — "
            "API token'ı bu host'a gönderilecek. Kasıtlı değilse ACHILLES_WEB_URL'i düzelt.",
            file=sys.stderr,
        )


def build_mcp():
    """Achilles OpenAPI'sinden FastMCP sunucusu kur (proxy → çalışan web).

    Spec, FastMCP'ye verilmeden ÖNCE ``allowlist.filter_spec`` ile budanır:
    yalnız açıkça izin verilen salt-okuma uçları tool olur (varsayılan kapalı).
    """
    import httpx
    from fastmcp import FastMCP
    from mcp_server.allowlist import filter_spec

    from app.web.server import app as achilles_app

    spec = filter_spec(achilles_app.openapi())  # varsayılan-kapalı budama
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=120.0,
        headers=auth_headers(),
    )
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="achilles-web",
    )


def __getattr__(name: str):
    """``mcp`` niteliğini TEMBEL kur (modül import'u yan etkisiz kalsın).

    Önceden modül seviyesinde ``mcp = build_mcp()`` vardı: modülü sadece import etmek
    tüm FastMCP sunucusunu kuruyor ve ``fastmcp``'yi zorunlu kılıyordu. Bu yüzden
    ``auth_headers``'ı test etmek bile opsiyonel ``mcp`` extra'sını gerektiriyordu
    (CI ``--extra dev`` ile kurduğu için `ModuleNotFoundError: fastmcp` veriyordu).

    ``mcp`` niteliği hâlâ erişilebilir (``from mcp_server.achilles_mcp import mcp``)
    — yalnız ilk erişimde kurulur. PEP 562 modül düzeyi ``__getattr__``.
    """
    if name == "mcp":
        return build_mcp()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    build_mcp().run()
