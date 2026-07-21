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

# Sürücü kimliği başlıkları — app/web/driver_scope.py ile AYNI adlar (tek kaynak orada).
# Buraya elle yazılır çünkü bu modül `app` paketi kurulu olmadan da içe aktarılabilmelidir.
_DRIVER_TOKEN_ENV = "ACHILLES_DRIVER_TOKEN"
_DRIVER_RUN_ID_ENV = "ACHILLES_DRIVER_RUN_ID"
_DRIVER_TOKEN_HEADER = "x-achilles-driver-token"
_RUN_ID_HEADER = "x-achilles-run-id"


def driver_headers(env: dict[str, str] | None = None) -> dict[str, str]:
    """Ortamdaki sürücü kimliğini HTTP başlıklarına çevir (yoksa BOŞ sözlük).

    ⚠️ GÜVENLİK — KİMLİK AKLAMA (identity laundering) ÖNLEMİ:
    Bu sunucu MCP çağrılarını çalışan web'e httpx ile proxy'ler. Başlıklar
    taşınmazsa, doğurulan motorun ``driver`` kimliği proxy'de KAYBOLUR ve istek
    sunucuya ``human`` gibi ulaşır (``app/web/security.py:resolve_scope`` başlık
    yoksa ``"human"`` döner). O durumda motor, MCP üzerinden ``/api/training/run``
    ve ``/api/approvals/{id}/approve`` gibi ``human_only`` uçları çağırıp KENDİ
    eğitimini onaylayıp başlatabilirdi → CLAUDE.md Kural 8 delinir.

    İnsan bu MCP sunucusunu kendi oturumunda kullandığında bu değişkenler ortamda
    YOKTUR → başlık eklenmez → davranış eskisiyle birebir aynı (``human``).
    """
    src = os.environ if env is None else env
    token = (src.get(_DRIVER_TOKEN_ENV) or "").strip()
    run_id = (src.get(_DRIVER_RUN_ID_ENV) or "").strip()
    if not token:
        return {}
    headers = {_DRIVER_TOKEN_HEADER: token}
    if run_id:
        # run_id da gönderilir: token yalnız bağlı olduğu koşuda geçerlidir.
        headers[_RUN_ID_HEADER] = run_id
    return headers


def build_mcp():
    """Achilles OpenAPI'sinden FastMCP sunucusu kur (proxy → çalışan web)."""
    import httpx
    from fastmcp import FastMCP

    from app.web.server import app as achilles_app

    spec = achilles_app.openapi()  # in-process, güvenilir (65+ path)
    # Sürücü başlıkları TÜM proxy isteklerine iliştirilir → scope sunucuda çözülür.
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=driver_headers())
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="achilles-web",
    )


if __name__ == "__main__":
    # `mcp` modül düzeyinde KURULMAZ: içe aktarma `fastmcp` (opsiyonel `mcp` extra) ve
    # tüm web uygulamasını gerektirir. Böylece `driver_headers` çevrimdışı test edilebilir.
    build_mcp().run()
