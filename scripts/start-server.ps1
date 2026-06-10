# Achilles Web Server -- Windows kalici arka plan servisi
# Kullanim:
#   .\scripts\start-server.ps1            -- simdi baslat
#   .\scripts\start-server.ps1 -Install   -- Windows acilisina ekle + simdi baslat
#   .\scripts\start-server.ps1 -Uninstall -- Windows acilisindan kaldir + durdur
#   .\scripts\start-server.ps1 -Stop      -- durdur
#   .\scripts\start-server.ps1 -Status    -- durum goster

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Stop
)

$ErrorActionPreference = "Continue"

$ScriptDir  = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir     = Join-Path $ProjectDir "logs"
$LogOut     = Join-Path $LogDir "achilles-web.log"
$LogErr     = Join-Path $LogDir "achilles-web-err.log"
$PidFile    = Join-Path $ProjectDir ".web.pid"
$VbsFile    = Join-Path $ScriptDir "achilles-autostart.vbs"
$RegPath    = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RegKey     = "AchillesWeb"

# ---------------------------------------------------------------- uv bul
function Find-Uv {
    $fromPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if ($fromPath -and (Test-Path $fromPath)) { return $fromPath }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\uv\uv.exe"),
        (Join-Path $env:APPDATA "uv\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "uv\uv.exe"),
        "C:\uv\uv.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

$UvPath = Find-Uv
if (-not $UvPath) {
    Write-Host "  [HATA] uv bulunamadi." -ForegroundColor Red
    Write-Host "  Kur: winget install astral-sh.uv" -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------- yardimci
function Get-WebPid {
    if (Test-Path $PidFile) {
        $stored = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($stored -match '^\d+$') {
            $proc = Get-Process -Id ([int]$stored) -ErrorAction SilentlyContinue
            if ($proc) { return [int]$stored }
        }
    }
    return $null
}

function Start-OllamaIfNeeded {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" `
            -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return
    } catch {}

    $candidates = @(
        (Get-Command ollama -ErrorAction SilentlyContinue).Source,
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $env:LOCALAPPDATA "Ollama\ollama.exe")
    )
    foreach ($exe in $candidates) {
        if ($exe -and (Test-Path $exe)) {
            Start-Process -FilePath $exe -ArgumentList "serve" -WindowStyle Hidden
            Start-Sleep -Seconds 4
            Write-Host "  [OK] Ollama baslatildi" -ForegroundColor Green
            return
        }
    }
    Write-Host "  [!] Ollama bulunamadi -- RAG/LLM calismaaz" -ForegroundColor Yellow
}

function Start-AchillesServer {
    $running = Get-WebPid
    if ($running) {
        Write-Host "  [OK] Zaten calisiyor (PID $running) -- http://127.0.0.1:8765" -ForegroundColor Green
        return
    }
    $null = New-Item -ItemType Directory -Path $LogDir -Force
    $proc = Start-Process `
        -FilePath $UvPath `
        -ArgumentList "run", "--project", "`"$ProjectDir`"", "achilles-web" `
        -WorkingDirectory $ProjectDir `
        -RedirectStandardOutput $LogOut `
        -RedirectStandardError  $LogErr `
        -WindowStyle Hidden `
        -PassThru
    $proc.Id | Out-File $PidFile -Force -Encoding ascii
    Start-Sleep -Seconds 5
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/status" `
            -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
        Write-Host "  [OK] Achilles Web calisiyor -- http://127.0.0.1:8765" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Basliyor... log: $LogErr" -ForegroundColor Yellow
    }
}

function Stop-AchillesServer {
    $webPid = Get-WebPid
    if ($webPid) {
        Stop-Process -Id $webPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] Durduruldu (PID $webPid)" -ForegroundColor Yellow
        return
    }
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*achilles*" }
    if ($procs) {
        $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Write-Host "  [OK] Durduruldu." -ForegroundColor Yellow
    } else {
        Write-Host "  Zaten calismiyor." -ForegroundColor Gray
    }
}

# ---------------------------------------------------------------- kurulum
# Neden Registry + VBS?
# Task Scheduler PATH'i olmadan calisir -- uv bulunamaz.
# Registry Run anahtari WScript ile calisir, uv tam yolu VBS icinde gomerek
# PATH'e bagimliligi tamamen ortadan kaldirir.
function Install-Autostart {
    # VBS olustur: uv tam yolunu icerir, PATH'e bagimli degil
    $thisScript = Join-Path $ScriptDir "start-server.ps1"
    $vbsContent = @"
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File """ & "$($thisScript -replace '"','\"')" & """", 0, False
Set sh = Nothing
"@
    $vbsContent | Out-File -FilePath $VbsFile -Encoding ascii -Force

    # Registry Run anahtarina ekle (her login'de otomatik calisir)
    Set-ItemProperty -Path $RegPath -Name $RegKey -Value "wscript.exe `"$VbsFile`"" -Force
    Write-Host "  [OK] Windows acilisina eklendi (Registry Run)" -ForegroundColor Green
    Write-Host "       $VbsFile" -ForegroundColor Gray

    # Task Scheduler'a da ekle (yedek)
    $action   = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsFile`"" -WorkingDirectory $ProjectDir
    $trigger  = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -StartWhenAvailable `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2)
    Register-ScheduledTask -TaskName "AchillesWeb" -Action $action `
        -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  [OK] Gorev Zamanlayici yedegi eklendi" -ForegroundColor Green

    # Hemen baslat
    Start-OllamaIfNeeded
    Start-AchillesServer

    Write-Host ""
    Write-Host "  Artik PowerShell'i kapatabilirsiniz." -ForegroundColor Cyan
    Write-Host "  Bir sonraki Windows acilisinda otomatik baslar." -ForegroundColor Cyan
}

function Uninstall-Autostart {
    Stop-AchillesServer
    Remove-ItemProperty -Path $RegPath -Name $RegKey -ErrorAction SilentlyContinue
    Remove-Item $VbsFile -Force -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "AchillesWeb" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  [OK] Otomatik baslatma kaldirildi." -ForegroundColor Yellow
}

function Show-Status {
    $webPid = Get-WebPid
    if ($webPid) {
        Write-Host "  Proses     : CALISIYOR (PID $webPid)" -ForegroundColor Green
        Write-Host "  Adres      : http://127.0.0.1:8765" -ForegroundColor Cyan
    } else {
        Write-Host "  Proses     : CALISMYOR" -ForegroundColor Red
    }
    $reg = Get-ItemProperty -Path $RegPath -Name $RegKey -ErrorAction SilentlyContinue
    Write-Host "  Registry   : $(if ($reg) { 'kayitli' } else { 'kayitli degil' })" -ForegroundColor Gray
    $task = Get-ScheduledTask -TaskName "AchillesWeb" -ErrorAction SilentlyContinue
    Write-Host "  Zamanlayici: $(if ($task) { $task.State } else { 'kayitli degil' })" -ForegroundColor Gray
    Write-Host "  Log        : $LogOut" -ForegroundColor Gray
    Write-Host "  uv yolu    : $UvPath" -ForegroundColor Gray
}

# ---------------------------------------------------------------- ana
if ($Install)   { Install-Autostart;   exit 0 }
if ($Uninstall) { Uninstall-Autostart; exit 0 }
if ($Stop)      { Stop-AchillesServer; exit 0 }
if ($Status)    { Show-Status;         exit 0 }

Start-OllamaIfNeeded
Start-AchillesServer
