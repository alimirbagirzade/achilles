#!/usr/bin/env bash
# Achilles Trader AI — tek komutla kurulum (macOS + Linux)
# Kullanim: bash setup.sh
set -euo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"
COLS=70

hr()   { printf '  +'; printf -- '-%.0s' $(seq 1 $COLS); printf '+\n'; }
info() { echo "  >>   $1"; }
ok()   { echo "  [OK] $1"; }
warn() { echo "  [!]  $1"; }
link() { echo "       $1"; }

echo ""
echo "  ======================================================"
echo "    Achilles Trader AI  -  Kurulum"
echo "    Platform: $OS / $ARCH"
echo "  ======================================================"
echo ""

# ==========================================================================
# MODEL SECIM MENUSU
# ==========================================================================
echo "  +--------------------------------------------------------------------+"
echo "  |  Hangi yapay zeka modelini kullanmak istiyorsunuz?                 |"
echo "  |  (Secimden sonra adim adim yol gosterilecektir)                    |"
echo "  +--------------------------------------------------------------------+"
echo "  |                                                                    |"
echo "  |  BULUT MODELLER  (internet + uyelik/api key gerekir)               |"
echo "  |                                                                    |"
echo "  |  -- OpenAI --                                                      |"
echo "  |  [1]  gpt-4o-mini        Ucuz, hizli           [ONERILEN]         |"
echo "  |  [2]  gpt-4o             Dengeli, guclu                            |"
echo "  |  [3]  o4-mini            Akil yurutme, ucuz                        |"
echo "  |  [4]  o3                 Derin akil, pahali                        |"
echo "  |                                                                    |"
echo "  |  -- Anthropic --                                                   |"
echo "  |  [5]  claude-haiku-4-5   Ucuz, hizli                               |"
echo "  |  [6]  claude-sonnet-4-6  Dengeli, en iyi kod yazan model           |"
echo "  |  [7]  claude-opus-4-8    En guclu, pahali                          |"
echo "  |                                                                    |"
echo "  |  -- Google --                                                      |"
echo "  |  [8]  gemini-2.0-flash   Ucuz, hizli                               |"
echo "  |  [9]  gemini-2.5-pro     Guclu, akil yurutme                       |"
echo "  |                                                                    |"
echo "  |  YEREL MODELLER  (internetsiz, ucretsiz, bilgisayarda calisir)     |"
echo "  |  (Ollama programi + model dosyasi otomatik indirilir)              |"
echo "  |                                                                    |"
echo "  |  -- Qwen3 (Alibaba) --                                             |"
echo "  |  [10] qwen3:4b    ~2.5 GB disk    8 GB+ RAM   Hizli               |"
echo "  |  [11] qwen3:8b    ~5 GB disk     16 GB+ RAM   Dengeli             |"
echo "  |  [12] qwen3:14b   ~9 GB disk     32 GB+ RAM   Guclu               |"
echo "  |  [13] qwen3:30b   ~20 GB disk    32 GB+ RAM   Cok guclu           |"
echo "  |                                                                    |"
echo "  |  -- Llama 3.1 (Meta) --                                            |"
echo "  |  [14] llama3.1:8b    ~5 GB disk  16 GB+ RAM                       |"
echo "  |  [15] llama3.1:70b  ~40 GB disk  80 GB+ RAM   Cok guclu           |"
echo "  |                                                                    |"
echo "  |  -- Mistral --                                                     |"
echo "  |  [16] mistral:7b    ~4 GB disk    8 GB+ RAM   Hizli               |"
echo "  |                                                                    |"
echo "  |  -- DeepSeek --                                                    |"
echo "  |  [17] deepseek-r1:8b    ~5 GB disk  16 GB+ RAM  Akil yurutme      |"
echo "  |  [18] deepseek-r1:14b   ~9 GB disk  32 GB+ RAM  Guclu             |"
echo "  |                                                                    |"
echo "  +--------------------------------------------------------------------+"
echo ""

read -r -p "  Seciminiz [1-18] (Enter = 1 / gpt-4o-mini): " CHOICE
CHOICE="${CHOICE:-1}"

LLM_BACKEND="openai"
LLM_MODEL="gpt-4o-mini"
MODEL_ENV="ACHILLES_OPENAI_MODEL"
API_KEY_ENV="ACHILLES_OPENAI_API_KEY"
NEED_OLLAMA=false
OLLAMA_RAM=0
OLLAMA_DSK=0

case "$CHOICE" in
  1)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o-mini";               MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY" ;;
  2)  LLM_BACKEND="openai";    LLM_MODEL="gpt-4o";                    MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY" ;;
  3)  LLM_BACKEND="openai";    LLM_MODEL="o4-mini";                   MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY" ;;
  4)  LLM_BACKEND="openai";    LLM_MODEL="o3";                        MODEL_ENV="ACHILLES_OPENAI_MODEL";    API_KEY_ENV="ACHILLES_OPENAI_API_KEY" ;;
  5)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-haiku-4-5-20251001"; MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY" ;;
  6)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-sonnet-4-6";         MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY" ;;
  7)  LLM_BACKEND="anthropic"; LLM_MODEL="claude-opus-4-8";           MODEL_ENV="ACHILLES_ANTHROPIC_MODEL"; API_KEY_ENV="ACHILLES_ANTHROPIC_API_KEY" ;;
  8)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.0-flash";          MODEL_ENV="ACHILLES_GOOGLE_MODEL";    API_KEY_ENV="ACHILLES_GOOGLE_API_KEY" ;;
  9)  LLM_BACKEND="google";    LLM_MODEL="gemini-2.5-pro";            MODEL_ENV="ACHILLES_GOOGLE_MODEL";    API_KEY_ENV="ACHILLES_GOOGLE_API_KEY" ;;
  10) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:4b";        NEED_OLLAMA=true; OLLAMA_RAM=8;  OLLAMA_DSK=3  ;;
  11) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:8b";        NEED_OLLAMA=true; OLLAMA_RAM=16; OLLAMA_DSK=5  ;;
  12) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:14b";       NEED_OLLAMA=true; OLLAMA_RAM=32; OLLAMA_DSK=9  ;;
  13) LLM_BACKEND="ollama"; LLM_MODEL="qwen3:30b";       NEED_OLLAMA=true; OLLAMA_RAM=32; OLLAMA_DSK=20 ;;
  14) LLM_BACKEND="ollama"; LLM_MODEL="llama3.1:8b";     NEED_OLLAMA=true; OLLAMA_RAM=16; OLLAMA_DSK=5  ;;
  15) LLM_BACKEND="ollama"; LLM_MODEL="llama3.1:70b";    NEED_OLLAMA=true; OLLAMA_RAM=80; OLLAMA_DSK=40 ;;
  16) LLM_BACKEND="ollama"; LLM_MODEL="mistral:7b";      NEED_OLLAMA=true; OLLAMA_RAM=8;  OLLAMA_DSK=4  ;;
  17) LLM_BACKEND="ollama"; LLM_MODEL="deepseek-r1:8b";  NEED_OLLAMA=true; OLLAMA_RAM=16; OLLAMA_DSK=5  ;;
  18) LLM_BACKEND="ollama"; LLM_MODEL="deepseek-r1:14b"; NEED_OLLAMA=true; OLLAMA_RAM=32; OLLAMA_DSK=9  ;;
  *)  LLM_BACKEND="openai"; LLM_MODEL="gpt-4o-mini" ;;
esac

# ==========================================================================
# CLOUD MODELLER: API KEY TALIMAT + DOGRULAMA
# ==========================================================================
API_KEY=""
if [ "$NEED_OLLAMA" = false ]; then
    echo ""
    echo "  ======================================================"
    echo "    API KEY NASIL ALINIR  —  Adim Adim Rehber"
    echo "  ======================================================"

    case "$LLM_BACKEND" in
      openai)
        echo ""
        echo "  OpenAI API key alinma adimlari:"
        echo ""
        info "1. Tarayicinizi acin (Chrome, Firefox, Safari vb.)"
        info "   -> https://platform.openai.com/api-keys"
        echo ""
        info "2. Henuz uye degilseniz:"
        info "   'Sign up' butonuna tiklayin"
        info "   E-posta + sifre ile kayit olun"
        info "   Veya Google / Microsoft hesabinizla giris yapin"
        echo ""
        info "3. API Keys sayfasinda:"
        info "   '+ Create new secret key' butonuna tiklayin"
        info "   Isim girin (ornegin: Achilles)"
        info "   'Create secret key' butonuna tiklayin"
        echo ""
        info "4. 'sk-...' ile baslayan kodu KOPYALAYIN"
        warn "   Bu kod sadece BIR KERE gosterilir! Mutlaka kopyalayin."
        echo ""
        info "5. Asagiya yapistirin"
        echo ""
        warn "ODEME: OpenAI API ucretlidir. Kart eklemek icin:"
        link "  platform.openai.com/settings/billing/payment-methods"
        warn "Baslamak icin 5-10 dolar kredi yeterlidir."
        echo ""
        # Tarayici ac (macOS ve Linux)
        if [ "$OS" = "Darwin" ]; then
            open "https://platform.openai.com/api-keys" 2>/dev/null || true
        else
            xdg-open "https://platform.openai.com/api-keys" 2>/dev/null || true
        fi
        ;;
      anthropic)
        echo ""
        echo "  Anthropic API key alinma adimlari:"
        echo ""
        info "1. Tarayicinizi acin"
        info "   -> https://console.anthropic.com"
        echo ""
        info "2. 'Sign up' ile yeni hesap acin"
        info "   E-posta + sifre veya Google ile giris yapin"
        echo ""
        info "3. Sol menuden 'API Keys' tiklayin"
        info "   Veya: console.anthropic.com/settings/keys"
        echo ""
        info "4. '+ Create Key' butonuna tiklayin"
        info "   'sk-ant-...' ile baslayan kodu KOPYALAYIN"
        warn "   Bu kod sadece BIR KERE gosterilir!"
        echo ""
        info "5. Asagiya yapistirin"
        echo ""
        warn "ODEME: Anthropic API ucretlidir. Kredi eklemek icin:"
        link "  console.anthropic.com/settings/billing"
        echo ""
        if [ "$OS" = "Darwin" ]; then
            open "https://console.anthropic.com/settings/keys" 2>/dev/null || true
        else
            xdg-open "https://console.anthropic.com/settings/keys" 2>/dev/null || true
        fi
        ;;
      google)
        echo ""
        echo "  Google AI Studio API key alinma adimlari:"
        echo ""
        info "1. Tarayicinizi acin"
        info "   -> https://aistudio.google.com/apikey"
        echo ""
        info "2. Google hesabinizla giris yapin"
        info "   (Gmail hesabiniz varsa direkt kullanabilirsiniz)"
        echo ""
        info "3. 'Create API key' butonuna tiklayin"
        info "   Proje secin veya 'Create new project' deyin"
        echo ""
        info "4. 'AIza...' ile baslayan kodu KOPYALAYIN"
        info "5. Asagiya yapistirin"
        echo ""
        ok  "UCRETSIZ: Google AI Studio sinirli ucretsiz kota saglar."
        info "Yuksek kullanim icin Google Cloud projesi gerekebilir."
        echo ""
        if [ "$OS" = "Darwin" ]; then
            open "https://aistudio.google.com/apikey" 2>/dev/null || true
        else
            xdg-open "https://aistudio.google.com/apikey" 2>/dev/null || true
        fi
        ;;
    esac

    sleep 2
    read -r -p "  API key buraya yapistirin: " API_KEY

    # Format dogrulama
    VALID_KEY=false
    case "$LLM_BACKEND" in
      openai)    echo "$API_KEY" | grep -qE "^sk-" && VALID_KEY=true ;;
      anthropic) echo "$API_KEY" | grep -qE "^sk-ant-" && VALID_KEY=true ;;
      google)    echo "$API_KEY" | grep -qE "^AIza" && VALID_KEY=true ;;
    esac

    if [ -z "$API_KEY" ]; then
        warn "API key girilmedi. Sonradan .env dosyasindaki ilgili satiri doldurun."
    elif [ "$VALID_KEY" = false ]; then
        warn "API key formati beklenenden farkli — yine de devam ediliyor."
        warn "OpenAI: 'sk-...'  |  Anthropic: 'sk-ant-...'  |  Google: 'AIza...'"
    else
        ok "API key formati gecerli"
    fi
fi

# ==========================================================================
# YEREL MODELLER: SISTEM KONTROLU
# ==========================================================================
if [ "$NEED_OLLAMA" = true ]; then
    echo ""
    echo "  ======================================================"
    echo "    SISTEM KONTROLU  —  $LLM_MODEL"
    echo "  ======================================================"
    echo ""

    # RAM kontrolu
    RAM_GB=0
    if [ "$OS" = "Darwin" ]; then
        RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
    elif [ -f /proc/meminfo ]; then
        RAM_GB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
    fi

    # Disk kontrolu
    DSK_GB=0
    DSK_GB=$(df -BG "$HOME" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo 0)

    info "Bilgisayariniz:  RAM = ${RAM_GB} GB  |  Bos disk = ~${DSK_GB} GB"
    info "Bu model icin:   RAM = ${OLLAMA_RAM} GB+  |  Disk = ~${OLLAMA_DSK} GB"

    if [ "$RAM_GB" -gt 0 ] && [ "$RAM_GB" -lt "$OLLAMA_RAM" ] 2>/dev/null; then
        warn "RAM yetersiz olabilir (${RAM_GB} GB < ${OLLAMA_RAM} GB). Model yavas calisabilir."
        read -r -p "  Devam etmek istiyor musunuz? [e/h]: " CONT
        [ "$CONT" != "e" ] && [ "$CONT" != "E" ] && exit 0
    else
        ok "RAM: ${RAM_GB} GB"
    fi

    if [ "$DSK_GB" -gt 0 ] && [ "$DSK_GB" -lt "$OLLAMA_DSK" ] 2>/dev/null; then
        warn "Disk alani yetersiz olabilir (${DSK_GB} GB bos, gerekli ~${OLLAMA_DSK} GB)."
        read -r -p "  Devam etmek istiyor musunuz? [e/h]: " CONT
        [ "$CONT" != "e" ] && [ "$CONT" != "E" ] && exit 0
    else
        ok "Disk: ${DSK_GB} GB bos"
    fi
fi

# ==========================================================================
# [1/3] UV
# ==========================================================================
echo ""
echo "[1/3] uv paket yoneticisi..."
if ! command -v uv &>/dev/null; then
    info "uv bulunamadi, kuruluyor..."
    info "Kaynak: https://astral.sh/uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
else
    ok "uv: $(uv --version)"
fi

# ==========================================================================
# [2/3] BAGIMLILIKLAR + OLLAMA
# ==========================================================================
echo "[2/3] Python kutuphaneleri yukleniyor..."
uv sync
ok "Kutuphaneler tamam"

if [ "$NEED_OLLAMA" = true ]; then
    echo ""
    echo "  ---- Ollama Kurulumu ----"
    echo ""
    info "Ollama: bilgisayarda yapay zeka modeli calistiran ucretsiz program"
    info "Resmi site: https://ollama.com"
    echo ""

    if ! command -v ollama &>/dev/null; then

        if [ "$OS" = "Darwin" ]; then
            # Homebrew yoksa kur
            if ! command -v brew &>/dev/null; then
                echo ""
                info "Homebrew bulunamadi — once Homebrew kuruluyor..."
                info "Homebrew: macOS icin ucretsiz paket yoneticisi (brew.sh)"
                info "Sudo sifreniz istenebilir, bu normaldir."
                echo ""
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                if [ "$ARCH" = "arm64" ]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
                    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile" 2>/dev/null || true
                else
                    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
                fi
                ok "Homebrew kuruldu"
            fi
            info "brew install ollama calistiriliyor..."
            brew install ollama
            info "Ollama servisi baslatiliyor (brew services start ollama)..."
            brew services start ollama

        elif [ "$OS" = "Linux" ]; then
            info "Resmi Linux kurulum scripti calistiriliyor..."
            info "Kaynak: https://ollama.com/install.sh"
            info "(sudo sifreniz istenebilir)"
            curl -fsSL https://ollama.com/install.sh | sh
            if command -v systemctl &>/dev/null; then
                sudo systemctl enable --now ollama 2>/dev/null || true
                ok "Ollama systemd servisi etkinlestirildi"
            else
                info "Ollama arka planda baslatiliyor..."
                ollama serve &>/tmp/ollama.log &
                sleep 3
            fi
        else
            warn "Desteklenmeyen platform: $OS"
            info "Ollama'yi elle kurun: https://ollama.com/download"
            read -r -p "  Kurulduktan sonra Enter'a basin: "
        fi
    else
        ok "Ollama zaten yuklu: $(ollama --version 2>/dev/null || echo '?')"
        if [ "$OS" = "Darwin" ]; then
            brew services start ollama 2>/dev/null || true
        fi
    fi

    # Servis hazir mi?
    info "Ollama servisi bekleniyor (max 30 saniye)..."
    READY=false
    for i in $(seq 1 15); do
        if curl -sf http://localhost:11434/api/tags &>/dev/null; then
            READY=true; break
        fi
        echo "  ... ($i/15)"
        sleep 2
    done

    if [ "$READY" = false ]; then
        warn "Ollama servisi yanit vermiyor."
        info "Yeni bir terminal acin ve 'ollama serve' yazin."
        read -r -p "  Ollama calisinca Enter'a basin: "
    else
        ok "Ollama servisi aktif (http://localhost:11434)"
    fi

    # Model indir
    echo ""
    echo "  ---- Model Indirme ----"
    echo ""
    info "Model: $LLM_MODEL  (boyut: ~${OLLAMA_DSK} GB)"
    info "Bu islem internet hizinize gore 5-30 dakika surebilir."
    info "Bilgisayari kapatmayin, interneti kesmeyin."
    echo ""
    ollama pull "$LLM_MODEL"
    echo ""
    info "Yaziya donusturme modeli: nomic-embed-text (~270 MB)..."
    ollama pull nomic-embed-text
    ok "Tum modeller indirildi ve hazir"
fi

# ==========================================================================
# [3/3] .ENV + VERITABANI
# ==========================================================================
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

ok ".env guncellendi: $LLM_BACKEND / $LLM_MODEL"
uv run achilles init
ok "Veritabani hazir"

# ==========================================================================
# TAMAMLANDI
# ==========================================================================
echo ""
echo "  ======================================================"
echo "    KURULUM TAMAMLANDI!"
echo "  ======================================================"
echo ""
echo "  Uygulamayi baslatmak icin:"
echo ""
echo "    uv run achilles-web"
echo ""
echo "  Tarayicinizda acin:"
echo "    http://127.0.0.1:8765"
echo ""
echo "  Baglanti testi (opsiyonel):"
echo "    uv run achilles status"
echo ""

if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    info "LoRA egitimi: Apple Silicon MLX ile destekleniyor (hizli)"
else
    info "LoRA egitimi: PEFT/CPU ile destekleniyor (macOS MLX'e gore yavas)"
    info "LoRA icin: uv pip install torch transformers peft datasets accelerate"
    info "RAG, backtest ve formul cikarma tam olarak calisir."
fi
echo ""
