# Achilles Trader AI — Otomatik Guncelleme Scripti
# Gelistirici GitHub'a yeni surum gonderince bu scripti calistir.
# Kullanim: .\update.ps1
#
# Otomatik zamanlama (her gun saat 09:00):
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#                -Argument "-NonInteractive -File `"C:\achilles\update.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
#   Register-ScheduledTask -TaskName "AchillesUpdate" -Action $action -Trigger $trigger -RunLevel Highest

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Achilles - Guncelleme Basladi" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# --- 1. Mevcut sunucuyu durdur (port 8765) ---
Write-Host "`n[1/4] Sunucu durduruluyor..."
try {
    $conn = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "  Sunucu durduruldu." -ForegroundColor Yellow
    } else {
        Write-Host "  Sunucu zaten calismiyor." -ForegroundColor Gray
    }
} catch {
    Write-Host "  Sunucu kontrol edilemedi, devam ediliyor." -ForegroundColor Gray
}

# --- 2. Git'ten son surumu cek ---
Write-Host "`n[2/4] GitHub'dan guncellemeler cekiliyor..."
git fetch origin main 2>&1 | Out-Null
$localHash  = git rev-parse HEAD
$remoteHash = git rev-parse origin/main
if ($localHash -eq $remoteHash) {
    Write-Host "  Zaten guncel — guncelleme yok." -ForegroundColor Green
} else {
    $commitCount = git rev-list HEAD..origin/main --count
    Write-Host "  $commitCount yeni commit bulundu, indiriliyor..." -ForegroundColor Yellow
    git pull --ff-only origin main
    Write-Host "  Kod guncellendi." -ForegroundColor Green
}

# --- 3. Bagimlilikları guncelle ---
Write-Host "`n[3/4] Python bagimliliklar guncelleniyor..."
uv sync
Write-Host "  Bagimliliklar guncellendi." -ForegroundColor Green

# --- 4. Sunucuyu yeniden baslat ---
Write-Host "`n[4/4] Sunucu yeniden baslatiliyor..."
$logPath    = Join-Path $ProjectDir "achilles_web.log"
$logErrPath = Join-Path $ProjectDir "achilles_web_err.log"

Start-Process -FilePath "uv" `
    -ArgumentList "run", "achilles-web" `
    -WorkingDirectory $ProjectDir `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError  $logErrPath `
    -WindowStyle Hidden

Start-Sleep -Seconds 5

# Canlilik kontrolu
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/status" -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host "  Sunucu hazir: http://127.0.0.1:8765" -ForegroundColor Green
    }
} catch {
    Write-Host "  Sunucu henuz cevap vermiyor. Birkas saniye bekle." -ForegroundColor Yellow
    Write-Host "  Log dosyasi: $logPath" -ForegroundColor Gray
}

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "  Guncelleme tamamlandi!" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
