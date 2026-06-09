# Achilles Trader AI -- Windows Yukleyici
# Bu dosyayi HERHANGI BIR YERDEN calistiabilirsiniz.
# Her zaman dogru konuma (Belgelerim\achilles) kurar.
#
# Kullanim (PowerShell):
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
#   .\install.ps1
#
# Veya tek satirda (internetten direkt):
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; irm https://raw.githubusercontent.com/alimirbagirzade/achilles/main/install.ps1 | iex

$ErrorActionPreference = "Continue"

$TARGET = Join-Path $env:USERPROFILE "achilles"

Write-Host ""
Write-Host "  ====================================================" -ForegroundColor Magenta
Write-Host "    Achilles Trader AI  --  Yukleyici" -ForegroundColor Magenta
Write-Host "  ====================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Kurulum konumu: $TARGET" -ForegroundColor Cyan
Write-Host ""

# --- Git kontrolu ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  >> Git kuruluyor (winget)..." -ForegroundColor White
    winget install --id Git.Git -e --source winget --silent
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "  [HATA] Git kurulamadi." -ForegroundColor Red
        Write-Host "  Lutfen https://git-scm.com adresinden Git'i indirip kurun," -ForegroundColor Yellow
        Write-Host "  sonra bu scripti tekrar calistirin." -ForegroundColor Yellow
        Read-Host "  Cikmak icin Enter'a basin"
        exit 1
    }
    Write-Host "  [OK] Git hazir" -ForegroundColor Green
}

# --- Mevcut kurulum kontrolu ---
if (Test-Path (Join-Path $TARGET ".git")) {
    Write-Host "  [OK] Mevcut kurulum bulundu: $TARGET" -ForegroundColor Green
    Write-Host "  >> Guncellemeler indiriliyor..." -ForegroundColor White
    Push-Location $TARGET
    git pull --ff-only 2>&1 | Out-Null
    Pop-Location
} else {
    if (Test-Path $TARGET) {
        Write-Host "  >> Eski klasor temizleniyor..." -ForegroundColor White
        Remove-Item $TARGET -Recurse -Force
    }
    Write-Host "  >> Proje indiriliyor..." -ForegroundColor White
    git clone https://github.com/alimirbagirzade/achilles.git "$TARGET"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  [HATA] Indirme basarisiz. Internet baglantinizi kontrol edin." -ForegroundColor Red
        Read-Host "  Cikmak icin Enter'a basin"
        exit 1
    }
    Write-Host "  [OK] Proje indirildi: $TARGET" -ForegroundColor Green
}

# --- Kurulumu dogru dizinden baslat ---
Write-Host ""
Write-Host "  >> Kurulum baslatiliyor..." -ForegroundColor Cyan
Write-Host ""

Set-Location $TARGET
& powershell.exe -ExecutionPolicy RemoteSigned -File (Join-Path $TARGET "setup.ps1")
