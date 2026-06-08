#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS + Linux)
# Kullanim: bash setup.sh
set -euo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=== Achilles Trader AI Kurulum ==="
echo "    Platform: $OS $ARCH"
echo "    LLM: OpenAI API (gpt-4o-mini)"
echo ""

read -r -p "  OpenAI API key girin (sk-...): " OPENAI_KEY
if [ -z "$OPENAI_KEY" ]; then
  echo "  UYARI: API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
fi

# --- 1. uv ---
if ! command -v uv &>/dev/null; then
  echo "[1/3] uv kuruluyor..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
  echo "[1/3] uv zaten kurulu: $(uv --version)"
fi

# --- 2. Python bagimliliklar ---
echo "[2/3] Python bagimliliklar yukleniyor..."
uv sync

# --- 3. .env ve veritabani ---
echo "[3/3] .env ve veritabani..."
cp -n .env.example .env 2>/dev/null || true

if grep -q "^ACHILLES_LLM_BACKEND=" .env; then
  sed -i.bak "s/^ACHILLES_LLM_BACKEND=.*/ACHILLES_LLM_BACKEND=openai/" .env && rm -f .env.bak
else
  echo "ACHILLES_LLM_BACKEND=openai" >> .env
fi

if [ -n "$OPENAI_KEY" ]; then
  if grep -q "^ACHILLES_OPENAI_API_KEY=" .env; then
    sed -i.bak "s/^ACHILLES_OPENAI_API_KEY=.*/ACHILLES_OPENAI_API_KEY=${OPENAI_KEY}/" .env && rm -f .env.bak
  else
    echo "ACHILLES_OPENAI_API_KEY=${OPENAI_KEY}" >> .env
  fi
fi

echo "    .env guncellendi: backend=openai"
uv run achilles init

echo ""
echo "=== Kurulum tamamlandi! ==="
echo ""

if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  echo "  LoRA egitimi: destekleniyor (Apple Silicon)"
else
  echo "  LoRA egitimi: bu platformda desteklenmez (yalnizca macOS Apple Silicon)."
  echo "  RAG, backtest ve formula cikarma tam calisir."
fi

echo ""
echo "Web arayuzunu baslatmak icin:"
echo "  uv run achilles-web"
echo "  -> http://127.0.0.1:8765"
echo ""
echo "CLI kullanimi:"
echo "  uv run achilles status"
echo "  uv run achilles --help"
