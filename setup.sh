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
echo "[4/5] LLM modeli seciliyor..."
RAM_GB=$(python3 -c "import os; print(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')//1024//1024//1024)" 2>/dev/null || echo 8)
echo "    Sistemde ~${RAM_GB} GB RAM tespit edildi."
echo ""
echo "    Hangi modeli kurmak istersiniz?"
echo "    [1] qwen3:4b   (~2.5 GB, 8GB+ RAM)  — varsayilan, hizli"
echo "    [2] qwen3:8b   (~5 GB,  16GB+ RAM)  — daha iyi"
echo "    [3] qwen3:14b  (~9 GB,  32GB+ RAM)  — en iyi"
echo ""
if   [ "$RAM_GB" -ge 32 ] 2>/dev/null; then DEFAULT="3"
elif [ "$RAM_GB" -ge 16 ] 2>/dev/null; then DEFAULT="2"
else DEFAULT="1"; fi
read -r -p "    Seciminiz [1/2/3] (Enter = $DEFAULT): " CHOICE
CHOICE="${CHOICE:-$DEFAULT}"
case "$CHOICE" in
  2) LLM_MODEL="qwen3:8b"  ;;
  3) LLM_MODEL="qwen3:14b" ;;
  *) LLM_MODEL="qwen3:4b"  ;;
esac
echo "    $LLM_MODEL indiriliyor..."
ollama pull "$LLM_MODEL"
ollama pull nomic-embed-text
# .env'deki modeli güncelle
if [ -f .env ]; then
  sed -i.bak "s/^ACHILLES_LLM_MODEL=.*/ACHILLES_LLM_MODEL=${LLM_MODEL}/" .env && rm -f .env.bak
  echo "    .env guncellendi: ACHILLES_LLM_MODEL=${LLM_MODEL}"
fi

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
