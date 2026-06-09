# Achilles Web Server -- Windows arkaplan baslangic scripti
# Kullanim: PowerShell'de calistir, Claude'dan bagimsiz calisir.
# Otomatik baslatmak icin: Gorev Zamanlayici'ya ekle (asagidaki talimata bak)

param(
    [switch]$Install,    # Gorev Zamanlayici'ya kaydet
    [switch]$Uninstall,  # Gorev Zamanlayici'dan sil
    [switch]$Status,     # Servis durumu goster
    [switch]$Stop        # Servisi durdur
)

$TaskName    = "AchillesWeb"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir  = Split-Path -Parent $ScriptDir
$UvPath      = (Get-Command uv -ErrorAction SilentlyContinue).Source
$LogFile     = Join-Path $ProjectDir "logs\achilles-web.log"

if (-not $UvPath) {
    Write-Error "uv bulunamadi. Kurulum: winget install astral-sh.uv"
    exit 1
}

function Start-AchillesServer {
    $null = New-Item -ItemType Directory -Path (Split-Path $LogFile) -Force
    $proc = Start-Process -FilePath $UvPath `
        -ArgumentList "run", "--project", "`"$ProjectDir`"", "achilles-web" `
        -WorkingDirectory $ProjectDir `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError  $LogFile `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "Achilles Web baslatildi (PID $($proc.Id)) -- http://localhost:8765"
    $proc.Id | Out-File (Join-Path $ProjectDir ".web.pid") -Force
}

function Stop-AchillesServer {
    $pidFile = Join-Path $ProjectDir ".web.pid"
    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Remove-Item $pidFile -Force
        Write-Host "Achilles Web durduruldu (PID $pid)"
    } else {
        Get-Process -Name "python*" | Where-Object { $_.CommandLine -like "*achilles*" } | Stop-Process -Force
        Write-Host "Achilles Web durduruldu."
    }
}

function Register-AchillesTask {
    $Action  = New-ScheduledTaskAction -Execute $UvPath `
        -Argument "run --project `"$ProjectDir`" achilles-web" `
        -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -RunLevel Highest -Force | Out-Null
    Write-Host "Gorev Zamanlayici'ya eklendi: '$TaskName'"
    Write-Host "Hemen baslatmak icin: Start-ScheduledTask -TaskName $TaskName"
}

function Unregister-AchillesTask {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Gorev Zamanlayici'dan silindi: '$TaskName'"
}

if ($Install)   { Register-AchillesTask; exit 0 }
if ($Uninstall) { Unregister-AchillesTask; exit 0 }
if ($Stop)      { Stop-AchillesServer; exit 0 }

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Gorev Zamanlayici: $($task.State)"
    } else {
        Write-Host "Gorev Zamanlayici: kayitli degil"
    }
    $pidFile = Join-Path $ProjectDir ".web.pid"
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) { Write-Host "Proses calisiyor (PID $p)" }
        else        { Write-Host "PID dosyasi var ama proses olmus" }
    }
    exit 0
}

# Varsayilan: arkaplanda baslat
Start-AchillesServer
