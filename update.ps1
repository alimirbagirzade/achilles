# Achilles Trader AI -- Otomatik Guncelleme
# Kurulum sirasinda otomatik zamanlanir; elle de calistirabilirsiniz:
#   .\update.ps1

$ErrorActionPreference = "Continue"

$ProjectDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $ProjectDir

# ---------------------------------------------------------------- uv bul
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

# ---------------------------------------------------------------- git bul
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

if (-not $UvPath)  { Write-Host "[HATA] uv bulunamadi."  -ForegroundColor Red; exit 1 }
if (-not $GitPath) { Write-Host "[HATA] git bulunamadi." -ForegroundColor Red; exit 1 }

$LogDir = Join-Path $ProjectDir "logs"
$null   = New-Item -ItemType Directory -Path $LogDir -Force
$LogFile = Join-Path $LogDir "update.log"

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Guncelleme basliyor..." | Add-Content $LogFile

# --- 1. Sunucuyu durdur ---
$PidFile = Join-Path $ProjectDir ".web.pid"
if (Test-Path $PidFile) {
    $stored = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($stored -match '^\d+$') {
        Stop-Process -Id ([int]$stored) -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

# --- 2. GitHub'dan guncelleme cek (sadece git pull -- push yok) ---
& $GitPath fetch origin main 2>$null
$localHash  = (& $GitPath rev-parse HEAD 2>$null).Trim()
$remoteHash = (& $GitPath rev-parse origin/main 2>$null).Trim()

$updated = $false
if ($localHash -ne $remoteHash) {
    & $GitPath pull --ff-only origin main 2>&1 | Out-Null
    $updated = $true
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Kod guncellendi ($($localHash.Substring(0,7)) -> $($remoteHash.Substring(0,7)))." |
        Add-Content $LogFile
} else {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Zaten guncel." | Add-Content $LogFile
}

# --- 3. Bagimliliklari guncelle (sadece kod degistiyse) ---
if ($updated) {
    & $UvPath sync 2>&1 | Out-Null
}

# --- 4. Sunucuyu yeniden baslat ---
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
$proc.Id | Out-File $PidFile -Force -Encoding ascii

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] Sunucu baslatildi (PID $($proc.Id))." | Add-Content $LogFile
