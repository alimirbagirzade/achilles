# Achilles Trader AI -- Windows Kurulum Scripti
# Gereksinim: Windows 10/11, PowerShell 5.1+, internet baglantisi
# Kullanim: PowerShell'i YONETICI olarak ac -> cd proje_klasoru -> .\setup.ps1

param([switch]$SkipOllama, [switch]$SkipModels)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) { Write-Host "`n[$n/3] $msg" -ForegroundColor Cyan }
function Write-OK($msg)       { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Info($msg)     { Write-Host "  >>   $msg" -ForegroundColor White }
function Write-Link($msg)     { Write-Host "       $msg" -ForegroundColor DarkCyan }
function Write-Sep           { Write-Host "  +------------------------------------------------------------------+" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "  ====================================================" -ForegroundColor Magenta
Write-Host "    Achilles Trader AI  -  Windows Kurulum" -ForegroundColor Magenta
Write-Host "  ====================================================" -ForegroundColor Magenta
Write-Host ""

# ==========================================================================
# DIZIN KONTROLU — sistem klasorlerinde calismayi otomatik duzelt
# ==========================================================================
# Proje klasoru kontrolu -- pyproject.toml ve app/ olmadan calisma
$_scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    $PWD.Path
}

$_hasProject = (Test-Path (Join-Path $_scriptDir "pyproject.toml")) -and
               (Test-Path (Join-Path $_scriptDir "app"))

if (-not $_hasProject) {
    Write-Host ""
    Write-Host "  ================================================================" -ForegroundColor Red
    Write-Host "   HATA: setup.ps1 yanlis klasorden calistirildi!" -ForegroundColor Red
    Write-Host "  ================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Mevcut konum  : $_scriptDir" -ForegroundColor Yellow
    Write-Host "  Beklenen dosya: pyproject.toml (bu klasorde yok)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Dogru kurulum icin asagidaki komutu PowerShell'e kopyalayip calistirin:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; irm https://raw.githubusercontent.com/alimirbagirzade/achilles/main/install.ps1 | iex" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Bu komut projeyi otomatik olarak dogru konuma indirir ve kurar." -ForegroundColor White
    Write-Host "  ================================================================" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Enter'a basin ve bu pencereyi kapatin"
    exit 1
}

# CWD'yi proje kokune sabitle (her kosulda tutarli calissin)
Set-Location $_scriptDir

# ==========================================================================
# MODEL SECIM MENUSU
# ==========================================================================
Write-Host "  +------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |  Hangi yapay zeka modelini kullanmak istiyorsunuz?               |" -ForegroundColor Cyan
Write-Host "  |  (Model seciminden sonra size adim adim yol gosterilecektir)     |" -ForegroundColor Cyan
Write-Host "  +------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  BULUT MODELLER  (internet + uyelik/api key gerekir)             |" -ForegroundColor Yellow
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- OpenAI --                                                    |" -ForegroundColor White
Write-Host "  |  [1]  gpt-4o-mini        Ucuz, hizli           [ONERILEN]       |" -ForegroundColor Green
Write-Host "  |  [2]  gpt-4o             Dengeli, guclu                          |" -ForegroundColor White
Write-Host "  |  [3]  o4-mini            Akil yurutme, ucuz                      |" -ForegroundColor White
Write-Host "  |  [4]  o3                 Derin akil, pahali                      |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- Anthropic --                                                 |" -ForegroundColor White
Write-Host "  |  [5]  claude-haiku-4-5   Ucuz, hizli                             |" -ForegroundColor White
Write-Host "  |  [6]  claude-sonnet-4-6  Dengeli, en iyi kod yazan model         |" -ForegroundColor White
Write-Host "  |  [7]  claude-opus-4-8    En guclu, pahali                        |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- Google --                                                    |" -ForegroundColor White
Write-Host "  |  [8]  gemini-2.0-flash   Ucuz, hizli                             |" -ForegroundColor White
Write-Host "  |  [9]  gemini-2.5-pro     Guclu, akil yurutme                     |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  YEREL MODELLER  (internet gerekmez, ucretsiz, bilgisayarda)     |" -ForegroundColor Yellow
Write-Host "  |  (Ollama uygulamasi + model dosyasi otomatik indirilir)          |" -ForegroundColor DarkGray
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- Qwen3 (Alibaba) --                                           |" -ForegroundColor White
Write-Host "  |  [10] qwen3:4b    ~2.5 GB disk    8 GB+ RAM   Hizli             |" -ForegroundColor White
Write-Host "  |  [11] qwen3:8b    ~5 GB disk     16 GB+ RAM   Dengeli           |" -ForegroundColor White
Write-Host "  |  [12] qwen3:14b   ~9 GB disk     32 GB+ RAM   Guclu             |" -ForegroundColor White
Write-Host "  |  [13] qwen3:30b   ~20 GB disk    32 GB+ RAM   Cok guclu         |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- Llama 3.1 (Meta) --                                          |" -ForegroundColor White
Write-Host "  |  [14] llama3.1:8b    ~5 GB disk  16 GB+ RAM                     |" -ForegroundColor White
Write-Host "  |  [15] llama3.1:70b  ~40 GB disk  80 GB+ RAM   Cok guclu         |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- Mistral --                                                   |" -ForegroundColor White
Write-Host "  |  [16] mistral:7b   ~4 GB disk    8 GB+ RAM    Hizli             |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  |  -- DeepSeek --                                                  |" -ForegroundColor White
Write-Host "  |  [17] deepseek-r1:8b    ~5 GB disk  16 GB+ RAM  Akil yurutme    |" -ForegroundColor White
Write-Host "  |  [18] deepseek-r1:14b   ~9 GB disk  32 GB+ RAM  Guclu           |" -ForegroundColor White
Write-Host "  |                                                                  |" -ForegroundColor Cyan
Write-Host "  +------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

$choice = Read-Host "  Seciminiz [1-18] (Enter = 1 / gpt-4o-mini)"
if ($choice -eq "") { $choice = "1" }

$llmBackend  = "openai"
$llmModel    = "gpt-4o-mini"
$modelEnv    = "ACHILLES_OPENAI_MODEL"
$apiKeyEnv   = "ACHILLES_OPENAI_API_KEY"
$needOllama  = $false
$ollamaRamGB = 0
$ollamaDskGB = 0

switch ($choice) {
    "1"  { $llmBackend="openai";    $llmModel="gpt-4o-mini";                $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY" }
    "2"  { $llmBackend="openai";    $llmModel="gpt-4o";                     $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY" }
    "3"  { $llmBackend="openai";    $llmModel="o4-mini";                    $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY" }
    "4"  { $llmBackend="openai";    $llmModel="o3";                         $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY" }
    "5"  { $llmBackend="anthropic"; $llmModel="claude-haiku-4-5-20251001";  $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "6"  { $llmBackend="anthropic"; $llmModel="claude-sonnet-4-6";          $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "7"  { $llmBackend="anthropic"; $llmModel="claude-opus-4-8";            $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "8"  { $llmBackend="google";    $llmModel="gemini-2.0-flash";           $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY" }
    "9"  { $llmBackend="google";    $llmModel="gemini-2.5-pro";             $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY" }
    "10" { $llmBackend="ollama"; $llmModel="qwen3:4b";        $needOllama=$true; $ollamaRamGB=8;  $ollamaDskGB=3  }
    "11" { $llmBackend="ollama"; $llmModel="qwen3:8b";        $needOllama=$true; $ollamaRamGB=16; $ollamaDskGB=5  }
    "12" { $llmBackend="ollama"; $llmModel="qwen3:14b";       $needOllama=$true; $ollamaRamGB=32; $ollamaDskGB=9  }
    "13" { $llmBackend="ollama"; $llmModel="qwen3:30b";       $needOllama=$true; $ollamaRamGB=32; $ollamaDskGB=20 }
    "14" { $llmBackend="ollama"; $llmModel="llama3.1:8b";     $needOllama=$true; $ollamaRamGB=16; $ollamaDskGB=5  }
    "15" { $llmBackend="ollama"; $llmModel="llama3.1:70b";    $needOllama=$true; $ollamaRamGB=80; $ollamaDskGB=40 }
    "16" { $llmBackend="ollama"; $llmModel="mistral:7b";      $needOllama=$true; $ollamaRamGB=8;  $ollamaDskGB=4  }
    "17" { $llmBackend="ollama"; $llmModel="deepseek-r1:8b";  $needOllama=$true; $ollamaRamGB=16; $ollamaDskGB=5  }
    "18" { $llmBackend="ollama"; $llmModel="deepseek-r1:14b"; $needOllama=$true; $ollamaRamGB=32; $ollamaDskGB=9  }
    default { $llmBackend="openai"; $llmModel="gpt-4o-mini" }
}

# ==========================================================================
# CLOUD MODELLER: API KEY TALIMAT + DOGRULAMA
# ==========================================================================
$apiKey = ""
if (-not $needOllama) {
    Write-Host ""
    Write-Host "  ====================================================" -ForegroundColor Cyan
    Write-Host "    API KEY NASIL ALINIR  --  Adim Adim Rehber" -ForegroundColor Cyan
    Write-Host "  ====================================================" -ForegroundColor Cyan

    switch ($llmBackend) {
        "openai" {
            Write-Host ""
            Write-Host "  OpenAI API key alinma adimlari:" -ForegroundColor Yellow
            Write-Host ""
            Write-Info "1. Asagida tarayiciniz otomatik acilacak"
            Write-Info "   -> https://platform.openai.com/api-keys"
            Write-Host ""
            Write-Info "2. Sayfada henuz uye degilseniz:"
            Write-Info "   'Sign up' butonuna tiklayin"
            Write-Info "   E-posta adresi + sifre ile kayit olun"
            Write-Info "   Veya Google / Microsoft hesabiyla giris yapin"
            Write-Host ""
            Write-Info "3. API Keys sayfasinda:"
            Write-Info "   '+ Create new secret key' butonuna tiklayin"
            Write-Info "   Isim girin (ornegin: Achilles)"
            Write-Info "   'Create secret key' butonuna tiklayin"
            Write-Host ""
            Write-Info "4. Gelen 'sk-...' ile baslayan kodu KOPYALAYIN"
            Write-Warn "   Bu kod sadece BIR KERE gosterilir! Mutlaka kopyalayin."
            Write-Host ""
            Write-Info "5. Asagiya yapistirin (Ctrl+V)"
            Write-Host ""
            Write-Warn "ODEME: OpenAI API ucretlidir. Kart eklemek icin:"
            Write-Link "platform.openai.com/settings/billing/payment-methods"
            Write-Warn "Baslamak icin 5-10 dolar kredi yeterlidir."
            Write-Host ""
            Write-Host "  Tarayici aciliyor..." -ForegroundColor Green
            Start-Process "https://platform.openai.com/api-keys"
        }
        "anthropic" {
            Write-Host ""
            Write-Host "  Anthropic API key alinma adimlari:" -ForegroundColor Yellow
            Write-Host ""
            Write-Info "1. Asagida tarayiciniz otomatik acilacak"
            Write-Info "   -> https://console.anthropic.com"
            Write-Host ""
            Write-Info "2. Sayfada 'Sign up' ile hesap acin"
            Write-Info "   E-posta + sifre veya Google ile giris yapin"
            Write-Host ""
            Write-Info "3. Giris yaptiktan sonra sol menude 'API Keys' tiklayin"
            Write-Info "   Yoksa: console.anthropic.com/settings/keys"
            Write-Host ""
            Write-Info "4. '+ Create Key' butonuna tiklayin"
            Write-Info "   'sk-ant-...' ile baslayan kodu KOPYALAYIN"
            Write-Warn "   Bu kod sadece BIR KERE gosterilir!"
            Write-Host ""
            Write-Info "5. Asagiya yapistirin (Ctrl+V)"
            Write-Host ""
            Write-Warn "ODEME: Anthropic API ucretlidir. Kredi eklemek icin:"
            Write-Link "console.anthropic.com/settings/billing"
            Write-Host ""
            Write-Host "  Tarayici aciliyor..." -ForegroundColor Green
            Start-Process "https://console.anthropic.com/settings/keys"
        }
        "google" {
            Write-Host ""
            Write-Host "  Google AI Studio API key alinma adimlari:" -ForegroundColor Yellow
            Write-Host ""
            Write-Info "1. Asagida tarayiciniz otomatik acilacak"
            Write-Info "   -> https://aistudio.google.com/apikey"
            Write-Host ""
            Write-Info "2. Google hesabinizla giris yapin"
            Write-Info "   (Gmail hesabiniz varsa direkt kullanabilirsiniz)"
            Write-Host ""
            Write-Info "3. 'Create API key' butonuna tiklayin"
            Write-Info "   Proje secin veya 'Create new project' deyin"
            Write-Host ""
            Write-Info "4. 'AIza...' ile baslayan kodu KOPYALAYIN"
            Write-Info "5. Asagiya yapistirin (Ctrl+V)"
            Write-Host ""
            Write-OK "UCRETSIZ: Google AI Studio sinirli ucretsiz kota saglar."
            Write-Info "Yuksek kullanim icin Google Cloud projesi gerekebilir."
            Write-Host ""
            Write-Host "  Tarayici aciliyor..." -ForegroundColor Green
            Start-Process "https://aistudio.google.com/apikey"
        }
    }

    Write-Host ""
    Start-Sleep -Seconds 2
    $apiKey = Read-Host "  API key buraya yapistirin"

    # Format dogrulama
    $validKey = $false
    switch ($llmBackend) {
        "openai"    { $validKey = $apiKey -match "^sk-" }
        "anthropic" { $validKey = $apiKey -match "^sk-ant-" }
        "google"    { $validKey = $apiKey -match "^AIza" }
    }

    if ($apiKey -eq "") {
        Write-Warn "API key girilmedi. Sonradan .env dosyasindaki ilgili satiri doldurun."
    } elseif (-not $validKey) {
        Write-Warn "API key formati beklenenden farkli gorunuyor -- yine de devam ediliyor."
        Write-Warn "OpenAI: 'sk-...' | Anthropic: 'sk-ant-...' | Google: 'AIza...'"
    } else {
        Write-OK "API key formati gecerli"
    }
}

# ==========================================================================
# YEREL MODELLER: SISTEM KONTROLU
# ==========================================================================
if ($needOllama) {
    Write-Host ""
    Write-Host "  ====================================================" -ForegroundColor Cyan
    Write-Host "    SISTEM KONTROLU  --  $llmModel" -ForegroundColor Cyan
    Write-Host "  ====================================================" -ForegroundColor Cyan
    Write-Host ""

    $ramGB  = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    $disk   = Get-PSDrive -Name C | Select-Object -ExpandProperty Free
    $diskGB = [math]::Round($disk / 1GB)

    Write-Info "Bilgisayariniz:  RAM = $ramGB GB  |  C: bos disk = $diskGB GB"
    Write-Info "Bu model icin:   RAM = $ollamaRamGB GB+  |  Disk = ~$ollamaDskGB GB"

    if ($ramGB -lt $ollamaRamGB) {
        Write-Warn "RAM yetersiz olabilir ($ramGB GB < $ollamaRamGB GB). Model yavas calisabilir."
        $cont = Read-Host "  Devam etmek istiyor musunuz? [E/H]"
        if ($cont -ne "E" -and $cont -ne "e") { exit 0 }
    } else {
        Write-OK "RAM yeterli ($ramGB GB)"
    }

    if ($diskGB -lt ($ollamaDskGB + 2)) {
        Write-Warn "Disk alani yetersiz olabilir ($diskGB GB bos, gerekli ~$ollamaDskGB GB)."
        $cont = Read-Host "  Devam etmek istiyor musunuz? [E/H]"
        if ($cont -ne "E" -and $cont -ne "e") { exit 0 }
    } else {
        Write-OK "Disk alani yeterli ($diskGB GB bos)"
    }
}

# ==========================================================================
# [1/3] PYTHON
# ==========================================================================
Write-Step 1 "Python 3.12 kurulumu..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Info "Python bulunamadi. Otomatik kurulum deneniyor..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Info "winget ile Python 3.12 kuruluyor..."
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        $py = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Write-Warn "Python otomatik kurulamadi. Elle kurulum gerekiyor:"
        Write-Host ""
        Write-Info "1. Tarayici aciliyor: python.org/downloads"
        Write-Info "2. 'Download Python 3.12' butonuna tiklayin"
        Write-Info "3. Indirilen dosyayi calistirin"
        Write-Info "4. KURULUMDA: 'Add Python to PATH' kutusunu ISARETLE (cok onemli!)"
        Write-Info "5. 'Install Now' tiklayin, bitmesini bekleyin"
        Write-Info "6. Bu pencereyi KAPAT, yeni PowerShell ac (Yonetici), tekrar calistir"
        Start-Process "https://www.python.org/downloads/"
        exit 1
    }
}
Write-OK "Python: $(python --version 2>&1)"

# ==========================================================================
# [2/3] UV + BAGIMLILIKLAR + OLLAMA (gerekirse)
# ==========================================================================
Write-Step 2 "Kurulum devam ediyor..."

# uv
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Info "uv paket yoneticisi kuruluyor (python.org/pypa alternatifi)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uvPath = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvPath) { $env:PATH = "$uvPath;$env:PATH" }
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        Write-Warn "uv PATH'e eklenemedi. Bu pencereyi kapat, yeni PowerShell ac, tekrar calistir."
        exit 1
    }
}
Write-OK "uv: $(uv --version)"

Write-Info "Python kutuphane bagimliliklar yukleniyor..."
uv sync
Write-OK "Kutuphaneler tamam"

# PEFT / LoRA egitim paketleri (Windows icin)
Write-Host ""
$installPeft = Read-Host "  LoRA model egitimi icin ek paketler kurulsun mu? (~2 GB) [E/H] (Enter = H)"
if ($installPeft -eq "E" -or $installPeft -eq "e") {
    Write-Info "PEFT paketleri kuruluyor (torch, transformers, peft, datasets)..."
    Write-Info "Bu islem 5-15 dakika surebilir, internet hizinize gore degisir."
    # Once sadece torch (PyTorch CPU index) -- transformers/peft PyPI'da yok
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu
    # Diger paketler normal PyPI'dan
    uv pip install transformers peft datasets accelerate
    Write-OK "LoRA egitim paketleri kuruldu (CPU modu)"
    Write-Warn "NVIDIA GPU icin: uv pip install torch --index-url https://download.pytorch.org/whl/cu121"
} else {
    Write-Info "LoRA paketleri atlandı. Sonradan kurmak icin:"
    Write-Host "  uv pip install torch --index-url https://download.pytorch.org/whl/cpu" -ForegroundColor Yellow
    Write-Host "  uv pip install transformers peft datasets accelerate" -ForegroundColor Yellow
}

# Ollama bolumu
if ($needOllama -and -not $SkipOllama) {

    Write-Host ""
    Write-Host "  ---- Ollama Kurulumu ----" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "Ollama: bilgisayarda yapay zeka modeli calistiran ucretsiz program"
    Write-Info "Resmi site: https://ollama.com"
    Write-Host ""

    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {

        $installed = $false

        # Yontem 1: winget
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Info "Yontem 1: winget ile sessiz kurulum deneniyor..."
            try {
                winget install --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
                $installed = $true
                Write-OK "winget ile Ollama kuruldu"
            } catch {
                Write-Warn "winget kurulumu basarisiz, alternatif deneniyor..."
            }
        }

        # Yontem 2: Resmi exe
        if (-not $installed) {
            $installer = "$env:TEMP\OllamaSetup.exe"
            Write-Info "Yontem 2: Resmi kurulum dosyasi indiriliyor (~500 MB)..."
            Write-Info "Kaynak: https://ollama.com/download/OllamaSetup.exe"
            try {
                Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" `
                    -OutFile $installer -UseBasicParsing -TimeoutSec 600
                Write-Info "Kuruluyor... Acilan pencerede 'Install' tiklayin."
                Start-Process -FilePath $installer -ArgumentList "/S" -Wait
                $installed = $true
                Write-OK "Ollama kuruldu"
            } catch {
                Write-Warn "Otomatik indirme basarisiz oldu."
                Write-Host ""
                Write-Host "  ELLE KURULUM GEREKIYOR:" -ForegroundColor Yellow
                Write-Info "1. Tarayici aciliyor: ollama.com/download"
                Write-Info "2. 'Download for Windows' butonuna tiklayin"
                Write-Info "3. Indirilen 'OllamaSetup.exe' dosyasini calistirin"
                Write-Info "4. Acilan sihirbazda 'Install' > 'Finish' tiklayin"
                Write-Info "5. Kurulum bittikten sonra ENTER'a basin"
                Start-Process "https://ollama.com/download"
                Read-Host "`n  Ollama kurulumunu tamamladiktan sonra Enter'a basin"
            }
        }

        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        Start-Sleep -Seconds 3
        $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        if (-not $ollamaCmd) {
            Write-Warn "Ollama kuruldu ancak bu oturumda taninamadi."
            Write-Info "Bu pencereyi kapat, yeni PowerShell (Yonetici) ac, tekrar calistir."
            exit 1
        }
    } else {
        Write-OK "Ollama zaten yuklu: $(ollama --version 2>&1)"
    }

    # Servis baslat
    Write-Info "Ollama arka plan servisi baslatiliyor..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    Write-Info "Servis hazir olana kadar bekleniyor (max 30 saniye)..."
    $ready = $false
    for ($i = 1; $i -le 15; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        Write-Warn "Ollama servisi yanit vermiyor."
        Write-Info "Baska bir terminal acin, 'ollama serve' yazin, Enter'a basin."
        Read-Host "  Ollama calisir hale gelince burada Enter'a basin"
    } else {
        Write-OK "Ollama servisi aktif (http://localhost:11434)"
    }

    # Model indir
    if (-not $SkipModels) {
        Write-Host ""
        Write-Host "  ---- Model Indirme ----" -ForegroundColor Cyan
        Write-Host ""
        Write-Info "Model: $llmModel  (boyut: ~$ollamaDskGB GB)"
        Write-Info "Bu islem internet hizinize gore 5-30 dakika surebilir."
        Write-Info "Bilgisayari kapatmayin, interneti kesmeyin."
        Write-Host ""
        ollama pull $llmModel
        Write-Host ""
        Write-Info "Yaziya donusturme modeli indiriliyor: nomic-embed-text (~270 MB)..."
        ollama pull nomic-embed-text
        Write-OK "Tum modeller indirildi ve hazir"
    }
}

# ==========================================================================
# [3/3] .ENV + VERITABANI
# ==========================================================================
Write-Step 3 ".env yapilandirmasi ve veritabani olusturuluyor..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-OK ".env dosyasi olusturuldu"
}

$envContent = Get-Content ".env"

function Set-EnvLine($lines, $key, $val) {
    if ($lines -match "^${key}=") { return $lines -replace "^${key}=.*", "${key}=${val}" }
    return $lines + "${key}=${val}"
}

$envContent = Set-EnvLine $envContent "ACHILLES_LLM_BACKEND" $llmBackend
$envContent = Set-EnvLine $envContent $modelEnv $llmModel
if ($apiKey -ne "") { $envContent = Set-EnvLine $envContent $apiKeyEnv $apiKey }
$envContent | Set-Content ".env"
Write-OK ".env guncellendi: $llmBackend / $llmModel"

Write-Info "Veritabani ve klasorler olusturuluyor..."
uv run achilles init
Write-OK "Veritabani hazir"

# ==========================================================================
# TAMAMLANDI
# ==========================================================================
Write-Host ""
Write-Host "  ====================================================" -ForegroundColor Green
Write-Host "    KURULUM TAMAMLANDI!" -ForegroundColor Green
Write-Host "  ====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Uygulamayi baslatmak icin:" -ForegroundColor White
Write-Host ""
Write-Host "    uv run achilles-web" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Tarayicinizda acin:" -ForegroundColor White
Write-Host "    http://127.0.0.1:8765" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Baglanti testi (opsiyonel):" -ForegroundColor DarkGray
Write-Host "    uv run achilles status" -ForegroundColor DarkGray
Write-Host ""
Write-Warn "NOT: LoRA egitim modlari -- macOS Apple Silicon: MLX (hizli), Windows/Linux: PEFT/CPU."
Write-Host "     Windows'ta tum ozellikler calismaktadir: RAG, backtest, formul cikarma, PEFT LoRA." -ForegroundColor White
Write-Host ""
