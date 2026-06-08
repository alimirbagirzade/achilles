# Achilles Trader AI -- Windows Kurulum Scripti
# Gereksinim: Windows 10/11, PowerShell 5.1+, internet baglantisi
# Kullanim: PowerShell'i YONETICI olarak ac -> cd proje_klasoru -> .\setup.ps1

param([switch]$SkipOllama, [switch]$SkipModels)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) { Write-Host "`n[$n/3] $msg" -ForegroundColor Cyan }
function Write-OK($msg)       { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  UYARI: $msg" -ForegroundColor Yellow }

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
Write-Host "|  --- OpenAI (openai.com/api-keys)  ---                           |" -ForegroundColor Yellow
Write-Host "|  [1]  gpt-4o-mini        ucuz, hizli          [ONERILEN]        |" -ForegroundColor Green
Write-Host "|  [2]  gpt-4o             dengeli, guclu                          |" -ForegroundColor White
Write-Host "|  [3]  o4-mini            akil yurutme, ucuz                      |" -ForegroundColor White
Write-Host "|  [4]  o3                 derin akil, pahali                      |" -ForegroundColor White
Write-Host "|  --- Anthropic (console.anthropic.com)  ---                      |" -ForegroundColor Yellow
Write-Host "|  [5]  claude-haiku-4-5   ucuz, hizli                             |" -ForegroundColor White
Write-Host "|  [6]  claude-sonnet-4-6  dengeli, en iyi kod                     |" -ForegroundColor White
Write-Host "|  [7]  claude-opus-4-8    en guclu, pahali                        |" -ForegroundColor White
Write-Host "|  --- Google (aistudio.google.com)  ---                           |" -ForegroundColor Yellow
Write-Host "|  [8]  gemini-2.0-flash   ucuz, hizli                             |" -ForegroundColor White
Write-Host "|  [9]  gemini-2.5-pro     guclu, akil yurutme                     |" -ForegroundColor White
Write-Host "|  --- Yerel / Ollama (internetsiz, ucretsiz)  ---                 |" -ForegroundColor Yellow
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
$apiKeyName = "OpenAI"
$apiKeyEnv  = "ACHILLES_OPENAI_API_KEY"
$modelEnv   = "ACHILLES_OPENAI_MODEL"
$needOllama = $false

switch ($choice) {
    "1"  { $llmBackend="openai";    $llmModel="gpt-4o-mini";               $modelEnv="ACHILLES_OPENAI_MODEL" }
    "2"  { $llmBackend="openai";    $llmModel="gpt-4o";                    $modelEnv="ACHILLES_OPENAI_MODEL" }
    "3"  { $llmBackend="openai";    $llmModel="o4-mini";                   $modelEnv="ACHILLES_OPENAI_MODEL" }
    "4"  { $llmBackend="openai";    $llmModel="o3";                        $modelEnv="ACHILLES_OPENAI_MODEL" }
    "5"  { $llmBackend="anthropic"; $llmModel="claude-haiku-4-5-20251001"; $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyName="Anthropic"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "6"  { $llmBackend="anthropic"; $llmModel="claude-sonnet-4-6";         $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyName="Anthropic"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "7"  { $llmBackend="anthropic"; $llmModel="claude-opus-4-8";           $modelEnv="ACHILLES_ANTHROPIC_MODEL"; $apiKeyName="Anthropic"; $apiKeyEnv="ACHILLES_ANTHROPIC_API_KEY" }
    "8"  { $llmBackend="google";    $llmModel="gemini-2.0-flash";          $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyName="Google";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY" }
    "9"  { $llmBackend="google";    $llmModel="gemini-2.5-pro";            $modelEnv="ACHILLES_GOOGLE_MODEL";    $apiKeyName="Google";    $apiKeyEnv="ACHILLES_GOOGLE_API_KEY" }
    "10" { $llmBackend="ollama";    $llmModel="qwen3:4b";       $needOllama=$true }
    "11" { $llmBackend="ollama";    $llmModel="qwen3:8b";       $needOllama=$true }
    "12" { $llmBackend="ollama";    $llmModel="qwen3:14b";      $needOllama=$true }
    "13" { $llmBackend="ollama";    $llmModel="qwen3:30b";      $needOllama=$true }
    "14" { $llmBackend="ollama";    $llmModel="llama3.1:8b";    $needOllama=$true }
    "15" { $llmBackend="ollama";    $llmModel="llama3.1:70b";   $needOllama=$true }
    "16" { $llmBackend="ollama";    $llmModel="mistral:7b";     $needOllama=$true }
    "17" { $llmBackend="ollama";    $llmModel="deepseek-r1:8b"; $needOllama=$true }
    "18" { $llmBackend="ollama";    $llmModel="deepseek-r1:14b";$needOllama=$true }
    default { $llmBackend="openai"; $llmModel="gpt-4o-mini" }
}

Write-Host "  Secilen: $llmModel ($llmBackend)" -ForegroundColor Cyan
Write-Host ""

$apiKey = ""
if (-not $needOllama) {
    $apiKey = Read-Host "  $apiKeyName API key girin"
    if ($apiKey -eq "") {
        Write-Warn "API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
    }
}

# --------------------------------------------------------------------------
# [1/3] Python
# --------------------------------------------------------------------------
Write-Step 1 "Python 3.12 kontrol ediliyor..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Warn "Python bulunamadi. Otomatik kuruluyor..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        $py = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Write-Warn "Python otomatik kurulamadi. Manuel kur:"
        Write-Host "  1. https://python.org/downloads" -ForegroundColor White
        Write-Host "  2. Python 3.12 indir ve 'Add Python to PATH' isaretle" -ForegroundColor Yellow
        Start-Process "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
        exit 1
    }
}
Write-OK (python --version 2>&1)

# --------------------------------------------------------------------------
# [2/3] uv + bagimliliklar + Ollama (gerekirse)
# --------------------------------------------------------------------------
Write-Step 2 "uv ve bagimliliklar..."
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uvPath = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvPath) { $env:PATH = "$uvPath;$env:PATH" }
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        Write-Warn "uv PATH'te bulunamadi. PowerShell'i kapatip yeniden ac."
        exit 1
    }
}
Write-OK "uv $(uv --version)"
uv sync
Write-OK "Bagimliliklar tamam"

if ($needOllama -and -not $SkipOllama) {
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        Write-Host "  Ollama indiriliyor..." -ForegroundColor Cyan
        $installer = "$env:TEMP\OllamaSetup.exe"
        try {
            Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer -TimeoutSec 300
            Start-Process -FilePath $installer -Wait
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        } catch {
            Write-Warn "Otomatik indirme basarisiz. https://ollama.com/download adresinden indir."
            Read-Host "  Ollama kurduktan sonra Enter'a bas"
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        }
    } else {
        Write-OK "Ollama zaten kurulu"
    }

    if (-not $SkipModels) {
        Write-Host "  $llmModel indiriliyor..." -ForegroundColor Cyan
        ollama pull $llmModel
        ollama pull nomic-embed-text
        Write-OK "Modeller hazir"
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
    if ($lines -match "^${key}=") {
        return $lines -replace "^${key}=.*", "${key}=${val}"
    }
    return $lines + "${key}=${val}"
}

$envContent = Set-EnvLine $envContent "ACHILLES_LLM_BACKEND" $llmBackend
$envContent = Set-EnvLine $envContent $modelEnv $llmModel

if ($apiKey -ne "") {
    $envContent = Set-EnvLine $envContent $apiKeyEnv $apiKey
}

$envContent | Set-Content ".env"
Write-OK ".env guncellendi: $llmBackend / $llmModel"

uv run achilles init
Write-OK "Veritabani hazir"

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Sunucuyu baslatmak icin:" -ForegroundColor White
Write-Host "  uv run achilles-web" -ForegroundColor Yellow
Write-Host "  Tarayicide ac: http://127.0.0.1:8765" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOT: LoRA egitimi sadece macOS Apple Silicon'da calisir." -ForegroundColor DarkYellow
Write-Host ""
