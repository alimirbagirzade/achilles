#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS + Linux)
# Kullanim: bash setup.sh
set -euo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=== Achilles Trader AI Kurulum ==="
echo "    Platform: $OS $ARCH"
echo ""

# --------------------------------------------------------------------------
# Model secim menusu
# --------------------------------------------------------------------------
echo "+------------------------------------------------------------------+"
echo "|  LLM Model Secin                                                 |"
echo "+------------------------------------------------------------------+"
echo "|  --- OpenAI (openai.com/api-keys) ---                            |"
echo "|  [1]  gpt-4o-mini        ucuz, hizli          [ONERILEN]        |"
echo "|  [2]  gpt-4o             dengeli, guclu                          |"
echo "|  [3]  o4-mini            akil yurutme, ucuz                      |"
echo "|  [4]  o3                 derin akil, pahali                      |"
echo "|  --- Anthropic (console.anthropic.com) ---                       |"
echo "|  [5]  claude-haiku-4-5   ucuz, hizli                             |"
echo "|  [6]  claude-sonnet-4-6  dengeli, en iyi kod                     |"
echo "|  [7]  claude-opus-4-8    en guclu, pahali                        |"
echo "|  --- Google (aistudio.google.com) ---                            |"
echo "|  [8]  gemini-2.0-flash   ucuz, hizli                             |"
echo "|  [9]  gemini-2.5-pro     guclu, akil yurutme                     |"
echo "|  --- Yerel / Ollama (internetsiz, ucretsiz) ---                  |"
echo "|  [10] qwen3:4b       ~2.5GB   8GB+ RAM  hizli                   |"
echo "|  [11] qwen3:8b       ~5GB    16GB+ RAM  dengeli                 |"
echo "|  [12] qwen3:14b      ~9GB    32GB+ RAM  guclu                   |"
echo "|  [13] qwen3:30b      ~20GB   32GB+ RAM  cok guclu               |"
echo "|  [14] llama3.1:8b    ~5GB    16GB+ RAM  Meta                    |"
echo "|  [15] llama3.1:70b   ~40GB   80GB+ RAM  Meta, en guclu          |"
echo "|  [16] mistral:7b     ~4GB     8GB+ RAM  hizli, hafif            |"
echo "|  [17] deepseek-r1:8b  ~5GB   16GB+ RAM  akil yurutme            |"
echo "|  [18] deepseek-r1:14b ~9GB   32GB+ RAM  guclu akil yurutme      |"
echo "+------------------------------------------------------------------+"
echo ""

read -r -p "  Seciminiz [1-18] (Enter = 1): " CHOICE
CHOICE="${CHOICE:-1}"

LLM_BACKEND="openai"
LLM_MODEL="gpt-4o-mini"
MODEL_ENV="ACHILLES_OPENAI_MODEL"
API_KEY_ENV="ACHILLES_OPENAI_API_KEY"
API_KEY_NAME="OpenAI"
NEED_OLLAMA=false

case "$CHOICE" in
  1)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o-mini";                MODEL_ENV="ACHILLES_OPENAI_MODEL";     API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI" ;;
  2)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o";                     MODEL_ENV="ACHILLES_OPENAI_MODEL";     API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI" ;;
  3)  LLM_BACKEND="openai";    LLM_MODEL="o4-mini";                    MODEL_ENV="ACHILLES_OPENAI_MODEL";     API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI" ;;
  4)  LLM_BACKEND="openai";    LLM_MODEL="o3";                         MODEL_ENV="ACHILLES_OPENAI_MODEL";     API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI" ;;
  5)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-haiku-4-5-20251001";  MODEL_ENV="ACHILLES_ANTHROPIC_MODEL";  API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic" ;;
  6)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-sonnet-4-6";          MODEL_ENV="ACHILLES_ANTHROPIC_MODEL";  API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic" ;;
  7)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-opus-4-8";            MODEL_ENV="ACHILLES_ANTHROPIC_MODEL";  API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic" ;;
  8)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.0-flash";           MODEL_ENV="ACHILLES_GOOGLE_MODEL";     API_KEY_ENV="ACHILLES_GOOGLE_API_KEY";    API_KEY_NAME="Google" ;;
  9)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.5-pro";             MODEL_ENV="ACHILLES_GOOGLE_MODEL";     API_KEY_ENV="ACHILLES_GOOGLE_API_KEY";    API_KEY_NAME="Google" ;;
  10) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:4b";        NEED_OLLAMA=true ;;
  11) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:8b";        NEED_OLLAMA=true ;;
  12) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:14b";       NEED_OLLAMA=true ;;
  13) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:30b";       NEED_OLLAMA=true ;;
  14) LLM_BACKEND="ollama"; LLM_MODEL="llama3.1:8b";     NEED_OLLAMA=true ;;
  15) LLM_BACKEND="ollama"; LLM_MODEL="llama3.1:70b";    NEED_OLLAMA=true ;;
  16) LLM_BACKEND="ollama"; LLM_MODEL="mistral:7b";      NEED_OLLAMA=true ;;
  17) LLM_BACKEND="ollama"; LLM_MODEL="deepseek-r1:8b";  NEED_OLLAMA=true ;;
  18) LLM_BACKEND="ollama"; LLM_MODEL="deepseek-r1:14b"; NEED_OLLAMA=true ;;
  *)  LLM_BACKEND="openai"; LLM_MODEL="gpt-4o-mini" ;;
esac

echo "  Secilen: $LLM_MODEL ($LLM_BACKEND)"
echo ""

API_KEY=""
if [ "$NEED_OLLAMA" = false ]; then
  read -r -p "  $API_KEY_NAME API key girin: " API_KEY
  if [ -z "$API_KEY" ]; then
    echo "  UYARI: API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
  fi
fi

# --------------------------------------------------------------------------
# [1/3] uv
# --------------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
  echo "[1/3] uv kuruluyor..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
  echo "[1/3] uv: $(uv --version)"
fi

# --------------------------------------------------------------------------
# [2/3] bagimliliklar + Ollama (gerekirse)
# --------------------------------------------------------------------------
echo "[2/3] Python bagimliliklar..."
uv sync

if [ "$NEED_OLLAMA" = true ]; then
  if ! command -v ollama &>/dev/null; then
    echo "  Ollama kuruluyor..."
    if [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
      brew install ollama && brew services start ollama
    elif [ "$OS" = "Linux" ]; then
      curl -fsSL https://ollama.com/install.sh | sh
      command -v systemctl &>/dev/null && sudo systemctl enable --now ollama 2>/dev/null || ollama serve &>/tmp/ollama.log &
      sleep 2
    else
      echo "  https://ollama.com/download adresinden Ollama'yi indir ve kur."
      read -r -p "  Kurulduktan sonra Enter'a bas: "
    fi
  else
    echo "  Ollama zaten kurulu"
    [ "$OS" = "Darwin" ] && brew services start ollama 2>/dev/null || true
  fi
  echo "  $LLM_MODEL indiriliyor..."
  ollama pull "$LLM_MODEL"
  ollama pull nomic-embed-text
  echo "  Modeller hazir"
fi

# --------------------------------------------------------------------------
# [3/3] .env ve veritabani
# --------------------------------------------------------------------------
echo "[3/3] .env ve veritabani..."
cp -n .env.example .env 2>/dev/null || true

set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
  else
    echo "${key}=${val}" >> .env
  fi
}

set_env "ACHILLES_LLM_BACKEND" "$LLM_BACKEND"
set_env "$MODEL_ENV"           "$LLM_MODEL"
[ -n "$API_KEY" ] && set_env "$API_KEY_ENV" "$API_KEY"

echo "    .env guncellendi: $LLM_BACKEND / $LLM_MODEL"
uv run achilles init

echo ""
echo "=== Kurulum tamamlandi! ==="
echo ""

if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  echo "  LoRA egitimi: destekleniyor (Apple Silicon)"
else
  echo "  LoRA egitimi: bu platformda yok (yalnizca macOS Apple Silicon)."
fi

echo ""
echo "Web arayuzunu baslatmak icin:"
echo "  uv run achilles-web"
echo "  -> http://127.0.0.1:8765"
echo ""
