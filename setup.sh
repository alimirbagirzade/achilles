#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS + Linux)
# Kullanım: bash setup.sh
set -euo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=== Achilles Trader AI Kurulum ==="
echo "    Platform: $OS $ARCH"
echo ""

# --- 1. uv ---
if ! command -v uv &>/dev/null; then
  echo "[1/5] uv kuruluyor..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
  echo "[1/5] uv zaten kurulu: $(uv --version)"
fi

# --- 2. Python bağımlılıkları ---
echo "[2/5] Python bağımlılıkları yükleniyor..."
uv sync

# --- 3. Ollama ---
if ! command -v ollama &>/dev/null; then
  echo "[3/5] Ollama kuruluyor..."
  if [ "$OS" = "Darwin" ]; then
    if command -v brew &>/dev/null; then
      brew install ollama
      brew services start ollama
    else
      echo "  Homebrew bulunamadı — Ollama'yı manuel indir: https://ollama.com/download"
      echo "  Kur ve çalıştır, sonra bu scripti yeniden başlat."
      exit 1
    fi
  elif [ "$OS" = "Linux" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
    # Systemd varsa servisi başlat
    if command -v systemctl &>/dev/null; then
      sudo systemctl enable --now ollama 2>/dev/null || true
    else
      # Arka planda başlat
      ollama serve &>/tmp/ollama.log &
      sleep 3
    fi
  else
    echo "  Desteklenmeyen platform: $OS"
    echo "  Ollama'yı manuel kur: https://ollama.com/download"
    exit 1
  fi
else
  echo "[3/5] Ollama zaten kurulu."
  if [ "$OS" = "Darwin" ]; then
    brew services start ollama 2>/dev/null || true
  fi
fi

# --- 4. Ollama modelleri ---
echo "[4/5] LLM modelleri indiriliyor (ilk seferde ~2-4 GB)..."
# qwen3:4b — varsayilan (~2.5GB, 8GB RAM yeterli, thinking modu destekli)
# 16GB+ icin: ollama pull qwen3:8b
# 32GB+ icin: ollama pull qwen3:14b
ollama pull qwen3:4b
ollama pull nomic-embed-text

# --- 5. Proje başlatma ---
echo "[5/5] Veritabanı ve dizinler oluşturuluyor..."
cp -n .env.example .env 2>/dev/null || true
uv run achilles init

echo ""
echo "=== Kurulum tamamlandı! ==="
echo ""

# --- Donanım profili ve model önerisi ---
echo ">>> Donanımınız için önerilen modeller:"
echo ""
uv run achilles recommend 2>/dev/null || true
echo ""

# LoRA notu
if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  echo "  LoRA eğitimi: destekleniyor (Apple Silicon)"
else
  echo "  LoRA eğitimi: bu platformda desteklenmez (yalnızca macOS Apple Silicon)."
  echo "  RAG, backtest ve formula çıkarma tam çalışır."
fi

echo ""
echo "Web arayüzünü başlatmak için:"
echo "  uv run achilles-web"
echo "  → http://127.0.0.1:8765"
echo ""
echo "CLI kullanımı:"
echo "  uv run achilles status"
echo "  uv run achilles --help"
