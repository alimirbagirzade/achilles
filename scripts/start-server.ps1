# Achilles Web Server -- Windows arkaplan servisi
# Kullanim:
#   .\scripts\start-server.ps1           -- arka planda baslat
#   .\scripts\start-server.ps1 -Install  -- Windows acilisinda otomatik baslat
#   .\scripts\start-server.ps1 -Stop     -- durdur
#   .\scripts\start-server.ps1 -Status   -- durum goster

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Stop
)

$TaskName   = "AchillesWeb"
$ScriptDir  = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir     = Join-Path $ProjectDir "logs"
$LogOut     = Join-Path $LogDir "achilles-web.log"
$LogErr     = Join-Path $LogDir "achilles-web-err.log"
$PidFile    = Join-Path $ProjectDir ".web.pid"

# uv yolunu bul (PATH + bilinen konumlar)
$UvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvPath -or -not (Test-Path $UvPath)) {
    $UvPath = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
}
if (-not (Test-Path $UvPath)) {
    Write-Host "  [HATA] uv bulunamadi." -ForegroundColor Red
    Write-Host "  Kurulum: winget install astral-sh.uv" -ForegroundColor Yellow
    exit 1
}

function Get-WebPid {
    if (Test-Path $PidFile) {
        $stored = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($stored -match '^\d+$' -and (Get-Process -Id ([int]$stored) -ErrorAction SilentlyContinue)) {
            return [int]$stored
        }
    }
    return $null
}

function Start-AchillesServer {
    $running = Get-WebPid
    if ($running) {
        Write-Host "  [OK] Achilles Web zaten calisiyor (PID $running) -- http://127.0.0.1:8765" -ForegroundColor Green
        return
    }
    $null = New-Item -ItemType Directory -Path $LogDir -Force
    $proc = Start-Process -FilePath $UvPath `
        -ArgumentList "run", "--project", "`"$ProjectDir`"", "achilles-web" `
        -WorkingDirectory $ProjectDir `
        -RedirectStandardOutput $LogOut `
        -RedirectStandardError  $LogErr `
        -WindowStyle Hidden `
        -PassThru
    $proc.Id | Out-File $PidFile -Force -Encoding ascii
    Start-Sleep -Seconds 4
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/status" `
            -TimeoutSec 6 -UseBasicParsing -ErrorAction Stop
        Write-Host "  [OK] Achilles Web calisiyor -- http://127.0.0.1:8765" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Basliyor, birka saniye bekle veya log'a bak: $LogErr" -ForegroundColor Yellow
    }
}

function Stop-AchillesServer {
    $webPid = Get-WebPid
    if ($webPid) {
        Stop-Process -Id $webPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] Achilles Web durduruldu (PID $webPid)" -ForegroundColor Yellow
    } else {
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*achilles*" }
        if ($procs) {
            $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Write-Host "  [OK] Achilles Web durduruldu." -ForegroundColor Yellow
        } else {
            Write-Host "  Achilles Web zaten calismiyor." -ForegroundColor Gray
        }
    }
}

function Install-Task {
    $action   = New-ScheduledTaskAction -Execute $UvPath `
        -Argument "run --project `"$ProjectDir`" achilles-web" `
        -WorkingDirectory $ProjectDir
    $trigger  = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit 0 `
        -RestartCount 5 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action `
        -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  [OK] Gorev Zamanlayici'ya eklendi -- Windows acilisinda otomatik baslar" -ForegroundColor Green
    # Hemen baslat (login bekleme)
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 4
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/status" `
            -TimeoutSec 6 -UseBasicParsing -ErrorAction Stop
        Write-Host "  [OK] Servis aktif -- http://127.0.0.1:8765" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Servis kaydedildi, birka saniye sonra hazir olacak." -ForegroundColor Yellow
    }
}

function Uninstall-Task {
    Stop-AchillesServer
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  [OK] Gorev Zamanlayici'dan silindi." -ForegroundColor Yellow
}

function Show-Status {
    $webPid = Get-WebPid
    if ($webPid) {
        Write-Host "  Proses     : CALISIYOR (PID $webPid)" -ForegroundColor Green
        Write-Host "  Adres      : http://127.0.0.1:8765" -ForegroundColor Cyan
    } else {
        Write-Host "  Proses     : CALISMYOR" -ForegroundColor Red
    }
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $taskState = if ($task) { $task.State } else { "kayitli degil" }
    Write-Host "  Zamanlayici: $taskState" -ForegroundColor Gray
    Write-Host "  Log        : $LogOut" -ForegroundColor Gray
}

if ($Install)   { Install-Task;        exit 0 }
if ($Uninstall) { Uninstall-Task;      exit 0 }
if ($Stop)      { Stop-AchillesServer; exit 0 }
if ($Status)    { Show-Status;         exit 0 }

Start-AchillesServer
