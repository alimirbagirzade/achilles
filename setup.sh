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
echo "|  --- OpenAI  (API key: openai.com/api-keys) ---                  |"
echo "|  [1]  gpt-4o-mini        ucuz, hizli          [ONERILEN]        |"
echo "|  [2]  gpt-4o             dengeli, guclu                          |"
echo "|  [3]  o4-mini            akil yurutme, ucuz                      |"
echo "|  [4]  o3                 derin akil, pahali                      |"
echo "|  --- Anthropic  (API key: console.anthropic.com) ---             |"
echo "|  [5]  claude-haiku-4-5   ucuz, hizli                             |"
echo "|  [6]  claude-sonnet-4-6  dengeli, en iyi kod                     |"
echo "|  [7]  claude-opus-4-8    en guclu, pahali                        |"
echo "|  --- Google  (API key: aistudio.google.com) ---                  |"
echo "|  [8]  gemini-2.0-flash   ucuz, hizli                             |"
echo "|  [9]  gemini-2.5-pro     guclu, akil yurutme                     |"
echo "|  --- Yerel / Ollama  (internetsiz, ucretsiz - model ~5-40 GB) -- |"
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
API_KEY_URL="https://platform.openai.com/api-keys"
NEED_OLLAMA=false

case "$CHOICE" in
  1)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o-mini";               MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI";    API_KEY_URL="https://platform.openai.com/api-keys" ;;
  2)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o";                    MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI";    API_KEY_URL="https://platform.openai.com/api-keys" ;;
  3)  LLM_BACKEND="openai";    LLM_MODEL="o4-mini";                   MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI";    API_KEY_URL="https://platform.openai.com/api-keys" ;;
  4)  LLM_BACKEND="openai";    LLM_MODEL="o3";                        MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY";    API_KEY_NAME="OpenAI";    API_KEY_URL="https://platform.openai.com/api-keys" ;;
  5)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-haiku-4-5-20251001"; MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic"; API_KEY_URL="https://console.anthropic.com/settings/keys" ;;
  6)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-sonnet-4-6";         MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic"; API_KEY_URL="https://console.anthropic.com/settings/keys" ;;
  7)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-opus-4-8";           MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY"; API_KEY_NAME="Anthropic"; API_KEY_URL="https://console.anthropic.com/settings/keys" ;;
  8)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.0-flash";          MODEL_ENV="ACHILLES_GOOGLE_MODEL";    API_KEY_ENV="ACHILLES_GOOGLE_API_KEY";    API_KEY_NAME="Google";    API_KEY_URL="https://aistudio.google.com/apikey" ;;
  9)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.5-pro";            MODEL_ENV="ACHILLES_GOOGLE_MODEL";    API_KEY_ENV="ACHILLES_GOOGLE_API_KEY";    API_KEY_NAME="Google";    API_KEY_URL="https://aistudio.google.com/apikey" ;;
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
    echo "  API key nereden alinir:"
    echo "    $API_KEY_URL"
    echo ""
    read -r -p "  $API_KEY_NAME API key girin: " API_KEY
    if [ -z "$API_KEY" ]; then
        echo "  UYARI: API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
    fi
fi

# --------------------------------------------------------------------------
# [1/3] uv
# --------------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
    echo "[1/3] uv paket yoneticisi kuruluyor..."
    echo "  Kaynak: https://astral.sh/uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
    echo "[1/3] uv: $(uv --version)"
fi

# --------------------------------------------------------------------------
# [2/3] Python bagimliliklar + Ollama (gerekirse)
# --------------------------------------------------------------------------
echo "[2/3] Python bagimliliklar yukleniyor..."
uv sync
echo "  Bagimliliklar tamam"

if [ "$NEED_OLLAMA" = true ]; then

    # ---- Ollama kurulumu ----
    if ! command -v ollama &>/dev/null; then
        echo ""
        echo "  Ollama bulunamadi — kurulum basliyor..."

        if [ "$OS" = "Darwin" ]; then
            # Homebrew yoksa kur
            if ! command -v brew &>/dev/null; then
                echo "  Homebrew bulunamadi — kuruluyor (sudo sifreniz istenebilir)..."
                echo "  Kaynak: https://brew.sh"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                if [ "$ARCH" = "arm64" ]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
                else
                    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
                fi
            fi
            echo "  Homebrew ile Ollama kuruluyor..."
            echo "  Kaynak: https://ollama.com"
            brew install ollama
            brew services start ollama
            echo "  Ollama servisi baslatildi"

        elif [ "$OS" = "Linux" ]; then
            echo "  Resmi Linux kurulum scripti calistiriliyor..."
            echo "  Kaynak: https://ollama.com/install.sh"
            curl -fsSL https://ollama.com/install.sh | sh
            if command -v systemctl &>/dev/null; then
                sudo systemctl enable --now ollama 2>/dev/null || true
                echo "  Ollama systemd servisi etkinlestirildi"
            else
                ollama serve &>/tmp/ollama.log &
                sleep 3
            fi
        else
            echo "  Desteklenmeyen platform: $OS"
            echo "  Ollama'yi elle kurun: https://ollama.com/download"
            read -r -p "  Kurulduktan sonra Enter'a basin: "
        fi
    else
        echo "  Ollama zaten kurulu: $(ollama --version 2>/dev/null || echo 'versiyon alinamadi')"
        if [ "$OS" = "Darwin" ]; then
            brew services start ollama 2>/dev/null || true
        fi
    fi

    # ---- Servis hazir mi? ----
    echo "  Ollama servisi bekleniyor..."
    READY=false
    for i in $(seq 1 15); do
        if curl -sf http://localhost:11434/api/tags &>/dev/null; then
            READY=true
            break
        fi
        echo "  ... ($i/15) bekleniyor"
        sleep 2
    done

    if [ "$READY" = false ]; then
        echo "  UYARI: Ollama servisi 30 saniyede yanit vermedi."
        echo "  Baska bir terminal acin ve 'ollama serve' calistirin."
        read -r -p "  Ollama hazir olunca Enter'a basin: "
    else
        echo "  Ollama servisi calisiyor"
    fi

    # ---- Model indir ----
    echo ""
    echo "  Secilen model indiriliyor: $LLM_MODEL"
    echo "  Bu islem internet hizinize gore 5-30 dakika surebilir."
    echo "  Lutfen internet baglantisini kesmeyin."
    echo ""
    ollama pull "$LLM_MODEL"
    echo "  Embedding modeli indiriliyor: nomic-embed-text (~270 MB)..."
    ollama pull nomic-embed-text
    echo "  Tum modeller hazir"
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

echo "  .env guncellendi: $LLM_BACKEND / $LLM_MODEL"
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
echo "  uv run achilles-web"
echo "  -> http://127.0.0.1:8765"
echo ""
