# Achilles Trader AI -- Windows Kurulum Scripti
# Gereksinim: Windows 10/11, PowerShell 5.1+, internet baglantisi
# Kullanim: PowerShell'i YONETICI olarak ac -> cd proje_klasoru -> .\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) { Write-Host "`n[$n/3] $msg" -ForegroundColor Cyan }
function Write-OK($msg)       { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  UYARI: $msg" -ForegroundColor Yellow }

Write-Host "======================================" -ForegroundColor Magenta
Write-Host "  Achilles Trader AI - Windows Kurulum" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  LLM: OpenAI API (gpt-4o-mini)" -ForegroundColor Cyan
Write-Host ""

$openaiKey = Read-Host "  OpenAI API key girin (sk-...)"
if ($openaiKey -eq "") {
    Write-Warn "API key bos birakildi. Sonradan .env dosyasina ekleyebilirsiniz."
}

# --- 1. Python 3.12 kontrol ---
Write-Step 1 "Python 3.12 kontrol ediliyor..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Warn "Python bulunamadi. Otomatik kuruluyor..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  winget ile Python 3.12 kuruluyor..." -ForegroundColor Cyan
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
        $py = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Write-Warn "Python otomatik kurulamadi. Manuel kur:"
        Write-Host "  1. https://python.org/downloads adresine git" -ForegroundColor White
        Write-Host "  2. Python 3.12 indir ve calistir" -ForegroundColor White
        Write-Host "  3. Kurulumda 'Add Python to PATH' kutusunu MUTLAKA isaretle!" -ForegroundColor Yellow
        Write-Host "  4. PowerShell'i kapat, yeniden ac, bu scripti tekrar calistir" -ForegroundColor White
        Start-Process "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
        exit 1
    }
}
$pyVer = python --version 2>&1
Write-OK $pyVer

# --- 2. uv + bagimliliklar ---
Write-Step 2 "uv ve Python bagimliliklar..."
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "  uv indiriliyor..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uvPath = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvPath) { $env:PATH = "$uvPath;$env:PATH" }
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        Write-Warn "uv PATH'te bulunamadi. PowerShell'i kapatip yeniden ac, sonra tekrar calistir."
        exit 1
    }
}
Write-OK "uv $(uv --version)"
uv sync
Write-OK "Bagimliliklar tamam"

# --- 3. .env ve veritabani ---
Write-Step 3 ".env ve veritabani..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-OK ".env olusturuldu"
} else {
    Write-OK ".env zaten var"
}

$envContent = Get-Content ".env"
$envContent = $envContent -replace "^ACHILLES_LLM_BACKEND=.*", "ACHILLES_LLM_BACKEND=openai"
if (-not ($envContent -match "^ACHILLES_LLM_BACKEND=")) {
    $envContent += "ACHILLES_LLM_BACKEND=openai"
}
if ($openaiKey -ne "") {
    if ($envContent -match "^ACHILLES_OPENAI_API_KEY=") {
        $envContent = $envContent -replace "^ACHILLES_OPENAI_API_KEY=.*", "ACHILLES_OPENAI_API_KEY=$openaiKey"
    } else {
        $envContent += "ACHILLES_OPENAI_API_KEY=$openaiKey"
    }
}
$envContent | Set-Content ".env"
Write-OK ".env guncellendi: backend=openai"

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
