# Achilles Trader AI -- TEK KOMUT guncelleme (KURULU makinede calistir)
#
#   .\update.ps1           -- normal: yerel degisiklikleri saklayip GitHub'dan cek
#   .\update.ps1 -Force    -- yereli AT, origin/main ile birebir esitle (salt-kopya kurulum)
#
# Yapar: web sunucusunu durdur -> GitHub'dan cek -> uv sync --extra web ->
#        web'i yeniden baslat -> saglik kontrolu.  EGITIME DOKUNMAZ.
#
# Tarayicida son halini gormek icin sonunda: Ctrl+Shift+R (sert yenileme).

param([switch]$Force)

$ErrorActionPreference = "Continue"
$ProjectDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $ProjectDir

function Find-Uv {
    $fromPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if ($fromPath -and (Test-Path $fromPath)) { return $fromPath }
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\uv\uv.exe"),
        (Join-Path $env:APPDATA "uv\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "uv\uv.exe")
    )
    foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }
    return $null
}
function Find-Git {
    $fromPath = (Get-Command git -ErrorAction SilentlyContinue).Source
    if ($fromPath -and (Test-Path $fromPath)) { return $fromPath }
    $candidates = @(
        "C:\Program Files\Git\bin\git.exe",
        "C:\Program Files (x86)\Git\bin\git.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Git\bin\git.exe")
    )
    foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }
    return $null
}

$UvPath  = Find-Uv
$GitPath = Find-Git
if (-not $UvPath)  { Write-Host "[HATA] uv bulunamadi (once install.ps1)." -ForegroundColor Red; exit 1 }
if (-not $GitPath) { Write-Host "[HATA] git bulunamadi." -ForegroundColor Red; exit 1 }

& $GitPath rev-parse --is-inside-work-tree 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[HATA] Bu klasor bir git deposu degil: $ProjectDir" -ForegroundColor Red
    Write-Host "       Dogru klasorde calistir (Achilles deposu)." -ForegroundColor Yellow
    exit 1
}

$LogDir = Join-Path $ProjectDir "logs"
$null   = New-Item -ItemType Directory -Path $LogDir -Force
$LogFile = Join-Path $LogDir "update.log"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Guncelleme basliyor (Force=$Force)..." | Add-Content $LogFile

# --- 1. Web sunucusunu KESIN durdur (port 8765 + achilles-web). EGITIME dokunma. ---
function Stop-Web {
    $pidFile = Join-Path $ProjectDir ".web.pid"
    if (Test-Path $pidFile) {
        $stored = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($stored -match '^\d+$') { Stop-Process -Id ([int]$stored) -Force -ErrorAction SilentlyContinue }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    try {
        Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    } catch {}
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='uv.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'achilles-web|achilles_web' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Stop-Web
Start-Sleep -Seconds 1

# --- 2. GitHub'dan cek ---
& $GitPath fetch origin main 2>$null
$localHash  = (& $GitPath rev-parse HEAD 2>$null).Trim()
$remoteHash = (& $GitPath rev-parse origin/main 2>$null).Trim()

if ($Force) {
    Write-Host "[!] -Force: yerel kod degisiklikleri ATILIYOR, origin/main'e esitleniyor." -ForegroundColor Yellow
    & $GitPath reset --hard origin/main 2>&1 | Out-Null
} elseif ($localHash -ne $remoteHash) {
    $stashOut = (& $GitPath stash 2>&1)
    $didStash = ($stashOut -notmatch "No local changes")
    $pullOut  = (& $GitPath pull origin main 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[HATA] git pull basarisiz:" -ForegroundColor Red
        Write-Host ($pullOut | Out-String) -ForegroundColor Yellow
        Write-Host "      Cozum: yerel degisiklik engelliyorsa ->  .\update.ps1 -Force" -ForegroundColor Cyan
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] pull HATASI: $pullOut" | Add-Content $LogFile
        if ($didStash) { & $GitPath stash pop 2>&1 | Out-Null }
    } elseif ($didStash) {
        & $GitPath stash pop 2>&1 | Out-Null
    }
} else {
    Write-Host "[OK] Kod zaten guncel ($($localHash.Substring(0,7)))." -ForegroundColor Cyan
}

$newHash = (& $GitPath rev-parse HEAD 2>$null).Trim()
$updated = ($newHash -ne $localHash)
if ($updated) {
    Write-Host "[OK] Kod guncellendi: $($localHash.Substring(0,7)) -> $($newHash.Substring(0,7))" -ForegroundColor Green
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Kod $($localHash.Substring(0,7)) -> $($newHash.Substring(0,7))." | Add-Content $LogFile
}

# --- 3. Bagimliliklar (WEB extra DAHIL -- duz 'uv sync' web paketlerini budar) ---
if ($updated -or $Force) {
    Write-Host "[..] Bagimliliklar esitleniyor (uv sync --extra web)..." -ForegroundColor Gray
    & $UvPath sync --extra web 2>&1 | Out-Null
}

# --- 4. Web'i yeniden baslat ---
$LogOut = Join-Path $LogDir "achilles-web.log"
$LogErr = Join-Path $LogDir "achilles-web-err.log"
$proc = Start-Process `
    -FilePath $UvPath `
    -ArgumentList "run", "--project", "`"$ProjectDir`"", "achilles-web" `
    -WorkingDirectory $ProjectDir `
    -RedirectStandardOutput $LogOut `
    -RedirectStandardError  $LogErr `
    -WindowStyle Hidden `
    -PassThru
$proc.Id | Out-File (Join-Path $ProjectDir ".web.pid") -Force -Encoding ascii
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Sunucu baslatildi (PID $($proc.Id))." | Add-Content $LogFile

# --- 5. Saglik kontrolu (port dinliyor mu) ---
$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { $ok = $true; break }
    Start-Sleep -Seconds 2
}
Write-Host ""
if ($ok) {
    Write-Host "[OK] Web calisiyor: http://127.0.0.1:8765" -ForegroundColor Green
    Write-Host "     >> Son halini gormek icin tarayicida: Ctrl+Shift+R (sert yenileme!)" -ForegroundColor Cyan
} else {
    Write-Host "[UYARI] Web 30 sn'de acilmadi -- log: logs\achilles-web-err.log" -ForegroundColor Yellow
}
