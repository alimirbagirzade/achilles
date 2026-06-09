# Achilles Trader AI -- Windows Kurulum Scripti
# Gereksinim: Windows 10/11, PowerShell 5.1+, internet baglantisi
# Kullanim: PowerShell'i YONETICI olarak ac -> cd proje_klasoru -> .\setup.ps1

param([switch]$SkipOllama, [switch]$SkipModels)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) { Write-Host "`n[$n/3] $msg" -ForegroundColor Cyan }
function Write-OK($msg)       { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  UYARI: $msg" -ForegroundColor Yellow }
function Write-Info($msg)     { Write-Host "  --> $msg" -ForegroundColor White }

Write-Host "======================================" -ForegroundColor Magenta
Write-Host "  Achilles Trader AI - Windows Kurulum" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta
Write-Host ""

# --------------------------------------------------------------------------
# Model secim menusu
# --------------------------------------------------------------------------
Write-Host "+------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "|  LLM Model Secin                                                 |" -ForegroundColor Cyan
Write-Host "+------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "|  --- OpenAI  (API key: openai.com/api-keys) ---                  |" -ForegroundColor Yellow
Write-Host "|  [1]  gpt-4o-mini        ucuz, hizli          [ONERILEN]        |" -ForegroundColor Green
Write-Host "|  [2]  gpt-4o             dengeli, guclu                          |" -ForegroundColor White
Write-Host "|  [3]  o4-mini            akil yurutme, ucuz                      |" -ForegroundColor White
Write-Host "|  [4]  o3                 derin akil, pahali                      |" -ForegroundColor White
Write-Host "|  --- Anthropic  (API key: console.anthropic.com) ---             |" -ForegroundColor Yellow
Write-Host "|  [5]  claude-haiku-4-5   ucuz, hizli                             |" -ForegroundColor White
Write-Host "|  [6]  claude-sonnet-4-6  dengeli, en iyi kod                     |" -ForegroundColor White
Write-Host "|  [7]  claude-opus-4-8    en guclu, pahali                        |" -ForegroundColor White
Write-Host "|  --- Google  (API key: aistudio.google.com) ---                  |" -ForegroundColor Yellow
Write-Host "|  [8]  gemini-2.0-flash   ucuz, hizli                             |" -ForegroundColor White
Write-Host "|  [9]  gemini-2.5-pro     guclu, akil yurutme                     |" -ForegroundColor White
Write-Host "|  --- Yerel / Ollama  (internetsiz, ucretsiz - model ~5-40 GB) -- |" -ForegroundColor Yellow
Write-Host "|  [10] qwen3:4b       ~2.5GB   8GB+ RAM  hizli                   |" -ForegroundColor White
Write-Host "|  [11] qwen3:8b       ~5GB    16GB+ RAM  dengeli                 |" -ForegroundColor White
Write-Host "|  [12] qwen3:14b      ~9GB    32GB+ RAM  guclu                   |" -ForegroundColor White
Write-Host "|  [13] qwen3:30b      ~20GB   32GB+ RAM  cok guclu               |" -ForegroundColor White
Write-Host "|  [14] llama3.1:8b    ~5GB    16GB+ RAM  Meta                    |" -ForegroundColor White
Write-Host "|  [15] llama3.1:70b   ~40GB   80GB+ RAM  Meta, en guclu          |" -ForegroundColor White
Write-Host "|  [16] mistral:7b     ~4GB     8GB+ RAM  hizli, hafif            |" -ForegroundColor White
Write-Host "|  [17] deepseek-r1:8b  ~5GB   16GB+ RAM  akil yurutme            |" -ForegroundColor White
Write-Host "|  [18] deepseek-r1:14b ~9GB   32GB+ RAM  guclu akil yurutme      |" -ForegroundColor White
Write-Host "+------------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

$choice = Read-Host "  Seciminiz [1-18] (Enter = 1)"
if ($choice -eq "") { $choice = "1" }

$llmBackend = "openai"
$llmModel   = "gpt-4o-mini"
$modelEnv   = "ACHILLES_OPENAI_MODEL"
$apiKeyEnv  = "ACHILLES_OPENAI_API_KEY"
$apiKeyName = "OpenAI"
$needOllama = $false

switch ($choice) {
    "1"  { $llmBackend="openai";    $llmModel="gpt-4o-mini";                $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY";    $apiKeyName="OpenAI" }
    "2"  { $llmBackend="openai";    $llmModel="gpt-4o";                     $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY";    $apiKeyName="OpenAI" }
    "3"  { $llmBackend="openai";    $llmModel="o4-mini";                    $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY";    $apiKeyName="OpenAI" }
    "4"  { $llmBackend="openai";    $llmModel="o3";                         $modelEnv="ACHILLES_OPENAI_MODEL";    $apiKeyEnv="ACHILLES_OPENAI_API_KEY";    $apiKeyName="OpenAI" }
    "5"  { $llmBackend="anthropic"; $llmModel="claude-haiku-4-5-20251001";  $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY"; $apiKeyName="Anthropic" }
    "6"  { $llmBackend="anthropic"; $llmModel="claude-sonnet-4-6";          $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY"; $apiKeyName="Anthropic" }
    "7"  { $llmBackend="anthropic"; $llmModel="claude-opus-4-8";            $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY"; $apiKeyName="Anthropic" }
    "8"  { $llmBackend="google";    $llmModel="gemini-2.0-flash";           $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY";    $apiKeyName="Google" }
    "9"  { $llmBackend="google";    $llmModel="gemini-2.5-pro";             $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY";    $apiKeyName="Google" }
    "10" { $llmBackend="ollama"; $llmModel="qwen3:4b";        $needOllama=$true }
    "11" { $llmBackend="ollama"; $llmModel="qwen3:8b";        $needOllama=$true }
    "12" { $llmBackend="ollama"; $llmModel="qwen3:14b";       $needOllama=$true }
    "13" { $llmBackend="ollama"; $llmModel="qwen3:30b";       $needOllama=$true }
    "14" { $llmBackend="ollama"; $llmModel="llama3.1:8b";     $needOllama=$true }
    "15" { $llmBackend="ollama"; $llmModel="llama3.1:70b";    $needOllama=$true }
    "16" { $llmBackend="ollama"; $llmModel="mistral:7b";      $needOllama=$true }
    "17" { $llmBackend="ollama"; $llmModel="deepseek-r1:8b";  $needOllama=$true }
    "18" { $llmBackend="ollama"; $llmModel="deepseek-r1:14b"; $needOllama=$true }
    default { $llmBackend="openai"; $llmModel="gpt-4o-mini" }
}

Write-Host "  Secilen: $llmModel  ($llmBackend)" -ForegroundColor Cyan
Write-Host ""

$apiKey = ""
if (-not $needOllama) {
    Write-Host "  API key nereden alinir:" -ForegroundColor White
    switch ($llmBackend) {
        "openai"    { Write-Host "    https://platform.openai.com/api-keys" -ForegroundColor DarkCyan }
        "anthropic" { Write-Host "    https://console.anthropic.com/settings/keys" -ForegroundColor DarkCyan }
        "google"    { Write-Host "    https://aistudio.google.com/apikey" -ForegroundColor DarkCyan }
    }
    Write-Host ""
    $apiKey = Read-Host "  $apiKeyName API key girin"
    if ($apiKey -eq "") {
        Write-Warn "API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
    }
}

# --------------------------------------------------------------------------
# [1/3] Python
# --------------------------------------------------------------------------
Write-Step 1 "Python 3.12..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Info "Python bulunamadi — winget ile otomatik kuruluyor..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        $py = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Write-Warn "Python otomatik kurulamadi."
        Write-Info "1. https://python.org/downloads adresine git"
        Write-Info "2. Python 3.12 indir ve calistir"
        Write-Info "3. MUTLAKA 'Add Python to PATH' kutusunu isaretle"
        Write-Info "4. Bu pencereyi kapat, yeni PowerShell ac (Yonetici), tekrar calistir"
        Start-Process "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
        exit 1
    }
}
Write-OK (python --version 2>&1)

# --------------------------------------------------------------------------
# [2/3] uv + bagimliliklar + Ollama (gerekirse)
# --------------------------------------------------------------------------
$stepMsg = "uv ve bagimliliklar"
if ($needOllama) { $stepMsg += " + Ollama kurulumu + model indirme" }
Write-Step 2 $stepMsg

$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Info "uv paket yoneticisi indiriliyor..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uvPath = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvPath) { $env:PATH = "$uvPath;$env:PATH" }
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        Write-Warn "uv PATH'te bulunamadi. Bu pencereyi kapat, yeni PowerShell ac ve tekrar calistir."
        exit 1
    }
}
Write-OK "uv $(uv --version)"
uv sync
Write-OK "Python bagimliliklar tamam"

if ($needOllama -and -not $SkipOllama) {

    # ---- Ollama kurulumu ----
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        Write-Info "Ollama bulunamadi — kurulum basliyor..."
        $installed = $false

        # Yontem 1: winget (en temiz, sessiz kurulum)
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget -and -not $installed) {
            Write-Info "winget ile Ollama kuruluyor (~1-2 dakika)..."
            try {
                winget install --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
                $installed = $true
            } catch {
                Write-Warn "winget ile kurulamadi, alternatif yontem deneniyor..."
            }
        }

        # Yontem 2: Dogrudan resmi installer
        if (-not $installed) {
            $installer = "$env:TEMP\OllamaSetup.exe"
            Write-Info "Ollama resmi sitesinden indiriliyor (~500 MB)..."
            Write-Info "Kaynak: https://ollama.com/download/OllamaSetup.exe"
            try {
                Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" `
                    -OutFile $installer -UseBasicParsing -TimeoutSec 600
                Write-Info "Kuruluyor (Yonetici izni isterse EVET deyin)..."
                Start-Process -FilePath $installer -ArgumentList "/S" -Wait
                $installed = $true
            } catch {
                Write-Warn "Otomatik indirme basarisiz."
                Write-Host ""
                Write-Host "  ELLE KURULUM ADIMLARI:" -ForegroundColor Yellow
                Write-Info "  1. Tarayicinizi acin (Chrome/Edge/Firefox)"
                Write-Info "  2. https://ollama.com/download adresine gidin"
                Write-Info "  3. 'Download for Windows' butonuna tiklayin"
                Write-Info "  4. Indirilen OllamaSetup.exe dosyasini calistirin"
                Write-Info "  5. Kurulum sihirbazini tamamlayin (Next > Install > Finish)"
                Write-Info "  6. Tamamlandiktan sonra asagida Enter'a basin"
                Start-Process "https://ollama.com/download"
                Read-Host "`n  Ollama kurulumunu tamamladiktan sonra Enter'a basin"
            }
        }

        # PATH guncelle ve bekle
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        Start-Sleep -Seconds 3
        $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue

        if (-not $ollamaCmd) {
            Write-Warn "Ollama kuruldu ancak bu oturumda PATH'e eklenmedi."
            Write-Info "Bu pencereyi kapat, yeni bir PowerShell (Yonetici) ac ve tekrar calistir."
            exit 1
        }
    } else {
        Write-OK "Ollama zaten kurulu: $(ollama --version 2>&1)"
    }

    # ---- Ollama servisini baslat ----
    Write-Info "Ollama servisi baslatiliyor (arka planda)..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    # Servis hazir mi?
    $ready = $false
    for ($i = 1; $i -le 15; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Write-Info "Ollama servisi bekleniyor... ($i/15)"
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        Write-Warn "Ollama servisi 30 saniyede yanit vermedi."
        Write-Info "Ayri bir terminal acin ve 'ollama serve' calistirin, sonra Enter'a basin."
        Read-Host "  Ollama hazir oldugunda Enter'a basin"
    } else {
        Write-OK "Ollama servisi calisiyor"
    }

    # ---- Model indir ----
    if (-not $SkipModels) {
        Write-Host ""
        Write-Host "  Secilen model indiriliyor: $llmModel" -ForegroundColor Cyan
        Write-Info "Bu islem internet hizinize gore 5-30 dakika surebilir."
        Write-Info "Lutfen bilgisayari kapatmayin veya interneti kesmeyin."
        Write-Host ""
        ollama pull $llmModel
        Write-Info "Embedding modeli indiriliyor: nomic-embed-text (~270 MB)..."
        ollama pull nomic-embed-text
        Write-OK "Tum modeller hazir"
    }
}

# --------------------------------------------------------------------------
# [3/3] .env ve veritabani
# --------------------------------------------------------------------------
Write-Step 3 ".env ve veritabani..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-OK ".env olusturuldu"
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

uv run achilles init
Write-OK "Veritabani hazir"

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "  uv run achilles-web" -ForegroundColor Yellow
Write-Host "  Tarayici: http://127.0.0.1:8765" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOT: LoRA egitimi yalnizca macOS Apple Silicon'da calisir." -ForegroundColor DarkYellow
Write-Host ""
