#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS + Linux)
# Kullanım: bash setup.sh
set -euo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=== Achilles Trader AI Kurulum ==="
echo "    Platform: $OS $ARCH"
echo ""

# --- 0. LLM Backend seçimi ---
echo "┌──────────────────────────────────────────────────┐"
echo "│  LLM Backend Seçin                               │"
echo "│                                                  │"
echo "│  [1] OpenAI API  — gpt-4o-mini  [ÖNERİLEN]      │"
echo "│      • Daha hızlı ve güçlü                       │"
echo "│      • sk-... API key gerekir (openai.com)       │"
echo "│  [2] Ollama      — yerel/ücretsiz                │"
echo "│      • İnternet gerekmez, gizlilik               │"
echo "│      • 4-14 GB disk + GPU önerilen               │"
echo "│  [3] İkisi de (auto)  — OpenAI varsa O, yoksa   │"
echo "│      Ollama'ya geç                               │"
echo "└──────────────────────────────────────────────────┘"
echo ""
read -r -p "  Seçiminiz [1/2/3] (Enter = 1): " BACKEND_CHOICE
BACKEND_CHOICE="${BACKEND_CHOICE:-1}"

LLM_BACKEND="auto"
OPENAI_KEY=""
case "$BACKEND_CHOICE" in
  2) LLM_BACKEND="ollama" ;;
  3) LLM_BACKEND="auto"   ;;
  *) LLM_BACKEND="openai" ;;
esac

if [ "$LLM_BACKEND" = "openai" ] || [ "$LLM_BACKEND" = "auto" ]; then
  echo ""
  echo "  OpenAI API key'inizi girin (boş bırakmak için Enter):"
  read -r -p "  sk-... : " OPENAI_KEY
fi

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

# --- 3. Ollama (yalnızca Ollama veya auto seçildiyse) ---
LLM_MODEL="qwen3:4b"
if [ "$LLM_BACKEND" != "openai" ]; then
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
      if command -v systemctl &>/dev/null; then
        sudo systemctl enable --now ollama 2>/dev/null || true
      else
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
    [ "$OS" = "Darwin" ] && brew services start ollama 2>/dev/null || true
  fi

  # --- 4. Ollama modelleri ---
  echo "[4/5] LLM modeli seciliyor..."
  RAM_GB=$(python3 -c "import os; print(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')//1024//1024//1024)" 2>/dev/null || echo 8)
  echo "    Sistemde ~${RAM_GB} GB RAM tespit edildi."
  echo ""
  echo "+--------------------------------------------------------------+"
  echo "|  Acik Kaynak (OSS) Model Secin                               |"
  echo "+--------------------------------------------------------------+"
  echo "|  --- Qwen3 (Alibaba) ---                                     |"
  echo "|  [1] qwen3:4b    ~2.5 GB  8GB+ RAM   hizli, trading OK      |"
  echo "|  [2] qwen3:8b    ~5 GB   16GB+ RAM   dengeli                |"
  echo "|  [3] qwen3:14b   ~9 GB   32GB+ RAM   guclu                  |"
  echo "|  [4] qwen3:30b   ~20 GB  48GB+ RAM   cok guclu              |"
  echo "|  --- Llama 3.1 (Meta) ---                                    |"
  echo "|  [5] llama3.1:8b   ~5 GB  16GB+ RAM  genel amac             |"
  echo "|  [6] llama3.1:70b  ~40 GB 80GB+ RAM  en guclu llama         |"
  echo "|  --- Mistral ---                                              |"
  echo "|  [7] mistral:7b    ~4 GB   8GB+ RAM  hizli, hafif            |"
  echo "|  --- DeepSeek ---                                             |"
  echo "|  [8] deepseek-r1:8b   ~5 GB  16GB+ RAM  akil yurutme        |"
  echo "|  [9] deepseek-r1:14b  ~9 GB  32GB+ RAM  guclu akil yurutme  |"
  echo "+--------------------------------------------------------------+"
  echo ""
  if   [ "$RAM_GB" -ge 80 ] 2>/dev/null; then DEFAULT="6"
  elif [ "$RAM_GB" -ge 48 ] 2>/dev/null; then DEFAULT="4"
  elif [ "$RAM_GB" -ge 32 ] 2>/dev/null; then DEFAULT="3"
  elif [ "$RAM_GB" -ge 16 ] 2>/dev/null; then DEFAULT="2"
  else DEFAULT="1"; fi
  read -r -p "    Seciminiz [1-9] (Enter = $DEFAULT - RAM'inize gore onerilen): " CHOICE
  CHOICE="${CHOICE:-$DEFAULT}"
  case "$CHOICE" in
    2) LLM_MODEL="qwen3:8b"        ;;
    3) LLM_MODEL="qwen3:14b"       ;;
    4) LLM_MODEL="qwen3:30b"       ;;
    5) LLM_MODEL="llama3.1:8b"     ;;
    6) LLM_MODEL="llama3.1:70b"    ;;
    7) LLM_MODEL="mistral:7b"      ;;
    8) LLM_MODEL="deepseek-r1:8b"  ;;
    9) LLM_MODEL="deepseek-r1:14b" ;;
    *) LLM_MODEL="qwen3:4b"        ;;
  esac
  echo "    $LLM_MODEL indiriliyor..."
  ollama pull "$LLM_MODEL"
  ollama pull nomic-embed-text
else
  echo "[3/5] Ollama atlandı (OpenAI backend seçildi)."
  echo "[4/5] Ollama modeli atlandı."
fi

# --- 5. Proje başlatma ---
echo "[5/5] Veritabanı ve dizinler oluşturuluyor..."
cp -n .env.example .env 2>/dev/null || true
# Backend ve model ayarlarını .env'e yaz
{
  # LLM_BACKEND
  if grep -q "^ACHILLES_LLM_BACKEND=" .env; then
    sed -i.bak "s/^ACHILLES_LLM_BACKEND=.*/ACHILLES_LLM_BACKEND=${LLM_BACKEND}/" .env && rm -f .env.bak
  else
    echo "ACHILLES_LLM_BACKEND=${LLM_BACKEND}" >> .env
  fi
  # OPENAI KEY
  if [ -n "$OPENAI_KEY" ]; then
    if grep -q "^ACHILLES_OPENAI_API_KEY=" .env; then
      sed -i.bak "s/^ACHILLES_OPENAI_API_KEY=.*/ACHILLES_OPENAI_API_KEY=${OPENAI_KEY}/" .env && rm -f .env.bak
    else
      echo "ACHILLES_OPENAI_API_KEY=${OPENAI_KEY}" >> .env
    fi
  fi
  # Ollama model
  if [ "$LLM_BACKEND" != "openai" ]; then
    if grep -q "^ACHILLES_LLM_MODEL=" .env; then
      sed -i.bak "s/^ACHILLES_LLM_MODEL=.*/ACHILLES_LLM_MODEL=${LLM_MODEL}/" .env && rm -f .env.bak
    else
      echo "ACHILLES_LLM_MODEL=${LLM_MODEL}" >> .env
    fi
  fi
} 2>/dev/null
echo "    .env guncellendi: backend=${LLM_BACKEND}"
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
