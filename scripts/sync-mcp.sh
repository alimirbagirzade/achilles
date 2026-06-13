#!/usr/bin/env bash
# Achilles MCP senkron — web değiştikten sonra MCP tool listesini tazele.
# MCP spec'i in-process üretildiği için "senkron" = MCP'yi yeniden kaydet/başlat.
# Bu script: (1) tool üretimini doğrular, (2) MCP'yi yeniden kaydeder.
set -u
cd "$(dirname "$0")/.." || exit 1
REPO="$(pwd)"

echo "[sync-mcp] tool üretimi doğrulanıyor..."
N=$(uv run python -c "
import asyncio
from mcp_server.achilles_mcp import mcp
print(len(asyncio.run(mcp.list_tools())))
" 2>/dev/null | tail -1)
echo "[sync-mcp] üretilen tool: ${N:-?}"

if [ -z "${N:-}" ] || [ "${N:-0}" -lt 1 ]; then
  echo "[sync-mcp] HATA: tool üretilemedi (web sunucusu açık mı? import hatası?)"
  exit 1
fi

echo "[sync-mcp] MCP yeniden kaydediliyor (achilles)..."
claude mcp remove achilles 2>/dev/null || true
claude mcp add achilles -- uv run --project "$REPO" python mcp_server/achilles_mcp.py
echo "[sync-mcp] tamam — Claude Code'u yeniden başlat / oturumu tazele ki MCP bağlansın."
