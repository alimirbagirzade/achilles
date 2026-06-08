# Achilles Trader AI — Windows Kurulum Scripti
# Gereksinim: Windows 10/11, PowerShell 5.1+, internet baglantisi
# Kullanim: PowerShell'i YONETICI olarak ac -> cd proje_klasoru -> .\setup.ps1

param(
    [switch]$SkipOllama,   # Ollama zaten kuruluysa atla
    [switch]$SkipModels    # Modeller zaten indirilmisse atla
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($n, $msg) { Write-Host "`n[$n/5] $msg" -ForegroundColor Cyan }
function Write-OK($msg)       { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn($msg)     { Write-Host "  UYARI: $msg" -ForegroundColor Yellow }

Write-Host "======================================" -ForegroundColor Magenta
Write-Host "  Achilles Trader AI - Windows Kurulum" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta

# --- 1. Python 3.12 kontrol ---
Write-Step 1 "Python 3.12 kontrol ediliyor..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Warn "Python bulunamadi."
    Write-Warn "https://python.org adresinden Python 3.12 indir ve kur."
    Write-Warn "Kurulumda 'Add Python to PATH' secenegini mutlaka isaretle!"
    Start-Process "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
    Read-Host "Python kurulduktan sonra Enter'a bas ve bu scripti yeniden calistir"
    exit 1
}
$pyVer = python --version 2>&1
Write-OK $pyVer

# --- 2. uv kur ---
Write-Step 2 "uv paket yoneticisi..."
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

# --- 3. Python bagimliliklar ---
Write-Step 3 "Python bagimliliklar yukleniyor..."
uv sync
Write-OK "Bagimliliklar tamam"

# --- 4. Ollama ---
Write-Step 4 "Ollama..."
if ($SkipOllama) {
    Write-OK "Atlandı (--SkipOllama)"
} else {
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        Write-Host "  Ollama indiriliyor (~500 MB)..."
        $installer = "$env:TEMP\OllamaSetup.exe"
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer
        Write-Host "  Ollama kuruluyor... Tamamlaninca bu pencereye don."
        Start-Process -FilePath $installer -Wait
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
    } else {
        Write-OK "Ollama zaten kurulu"
    }
}

# --- 5. LLM modeller ---
Write-Step 5 "LLM modelleri indiriliyor (ilk seferinde ~2-4 GB)..."
if ($SkipModels) {
    Write-OK "Atlandı (--SkipModels)"
} else {
    Write-Host "  qwen2.5-coder:3b indiriliyor..."
    ollama pull qwen2.5-coder:3b
    Write-Host "  nomic-embed-text indiriliyor..."
    ollama pull nomic-embed-text
    Write-OK "Modeller hazir"
}

# --- .env ---
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-OK ".env olusturuldu"
} else {
    Write-OK ".env zaten var"
}

# --- Veritabani ---
Write-Host "`n  Veritabani ve klasorler olusturuluyor..."
uv run achilles init
Write-OK "Veritabani hazir"

Write-Host "`n======================================" -ForegroundColor Green
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "======================================`n" -ForegroundColor Green

Write-Host ">>> Donanim profiliniz ve onerilen modeller:" -ForegroundColor Cyan
Write-Host ""
try { uv run achilles recommend } catch { Write-Host "  (profil alinamadi)" -ForegroundColor Gray }
Write-Host ""

Write-Host "Sunucuyu baslatmak icin:" -ForegroundColor White
Write-Host "  uv run achilles-web" -ForegroundColor Yellow
Write-Host "  Tarayicide ac: http://127.0.0.1:8765`n" -ForegroundColor Yellow
Write-Host "Guncelleme icin (gelistirici yeni surum yayinlayinca):" -ForegroundColor White
Write-Host "  .\update.ps1`n" -ForegroundColor Yellow
Write-Host "NOT: LoRA egitimi sadece macOS Apple Silicon'da calisir." -ForegroundColor DarkYellow
Write-Host "     Windows'ta RAG, backtest, formul cikarma tam calisir.`n" -ForegroundColor DarkYellow
