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
        try {
            Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" `
                -OutFile $installer -TimeoutSec 120
            Write-Host "  Ollama kuruluyor... Tamamlaninca bu pencereye don."
            Start-Process -FilePath $installer -Wait
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        } catch {
            Write-Warn "Otomatik indirme basarisiz oldu."
            Write-Warn "Lutfen Ollama'yi manuel kur:"
            Write-Host "  1. https://ollama.com/download adresine git" -ForegroundColor White
            Write-Host "  2. 'Download for Windows' butonuna tikla" -ForegroundColor White
            Write-Host "  3. OllamaSetup.exe'yi indir ve calistir" -ForegroundColor White
            Read-Host "`n  Ollama kurulduktan sonra Enter'a bas"
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        }
        $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        if (-not $ollamaCmd) {
            Write-Warn "Ollama PATH'te bulunamadi. Kurulumdan sonra PowerShell'i yeniden ac."
            exit 1
        }
    } else {
        Write-OK "Ollama zaten kurulu"
    }
}

# --- 5. LLM modeller ---
Write-Step 5 "LLM modeli seciliyor..."
if ($SkipModels) {
    Write-OK "Atlandı (--SkipModels)"
} else {
    # RAM miktarına göre önerilen modeli hesapla
    $ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    Write-Host "  Sistemde $ramGB GB RAM tespit edildi." -ForegroundColor White
    Write-Host ""
    Write-Host "  Hangi modeli kurmak istersiniz?" -ForegroundColor Cyan
    Write-Host "  [1] qwen3:4b   — ~2.5 GB VRAM, 8 GB+ RAM  (varsayilan, hizli)" -ForegroundColor White
    Write-Host "  [2] qwen3:8b   — ~5 GB VRAM,  16 GB+ RAM  (daha iyi)" -ForegroundColor White
    Write-Host "  [3] qwen3:14b  — ~9 GB VRAM,  32 GB+ RAM  (en iyi)" -ForegroundColor White
    Write-Host ""

    if ($ramGB -ge 32) {
        $defaultChoice = "3"
    } elseif ($ramGB -ge 16) {
        $defaultChoice = "2"
    } else {
        $defaultChoice = "1"
    }

    $choice = Read-Host "  Seciminiz [1/2/3] (Enter = $defaultChoice)"
    if ($choice -eq "") { $choice = $defaultChoice }

    switch ($choice) {
        "2" { $llmModel = "qwen3:8b";  $llmSize = "~5 GB" }
        "3" { $llmModel = "qwen3:14b"; $llmSize = "~9 GB" }
        default { $llmModel = "qwen3:4b"; $llmSize = "~2.5 GB" }
    }

    Write-Host "  $llmModel indiriliyor ($llmSize)..." -ForegroundColor Cyan
    ollama pull $llmModel
    Write-Host "  nomic-embed-text indiriliyor (~270 MB)..."
    ollama pull nomic-embed-text

    # .env dosyasında modeli güncelle
    if (Test-Path ".env") {
        (Get-Content ".env") -replace "^ACHILLES_LLM_MODEL=.*", "ACHILLES_LLM_MODEL=$llmModel" |
            Set-Content ".env"
        Write-OK ".env guncellendi: ACHILLES_LLM_MODEL=$llmModel"
    }
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
