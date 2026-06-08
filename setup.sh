#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS Apple Silicon)
# Kullanım: bash setup.sh
set -euo pipefail

echo "=== Achilles Trader AI Kurulum ==="
echo ""

# --- 1. uv ---
if ! command -v uv &>/dev/null; then
  echo "[1/5] uv kuruluyor..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
else
  echo "[1/5] uv zaten kurulu: $(uv --version)"
fi

# --- 2. Python bağımlılıkları ---
echo "[2/5] Python bağımlılıkları yükleniyor..."
uv sync

# --- 3. Ollama ---
if ! command -v ollama &>/dev/null; then
  echo "[3/5] Ollama kuruluyor (brew)..."
  if ! command -v brew &>/dev/null; then
    echo "  Homebrew bulunamadı. Manuel olarak kur: https://brew.sh"
    echo "  Sonra: brew install ollama && brew services start ollama"
  else
    brew install ollama
    brew services start ollama
  fi
else
  echo "[3/5] Ollama zaten kurulu."
  brew services start ollama 2>/dev/null || true
fi

# --- 4. Ollama modelleri ---
echo "[4/5] LLM modelleri indiriliyor (ilk seferde ~2-4 GB)..."
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text

# --- 5. Proje başlatma ---
echo "[5/5] Veritabanı ve dizinler oluşturuluyor..."
cp -n .env.example .env 2>/dev/null || true
uv run achilles init

echo ""
echo "=== Kurulum tamamlandı! ==="
echo ""
echo "Web arayüzünü başlatmak için:"
echo "  uv run achilles-web"
echo "  → http://127.0.0.1:8765"
echo ""
echo "CLI kullanımı:"
echo "  uv run achilles status"
echo "  uv run achilles --help"
