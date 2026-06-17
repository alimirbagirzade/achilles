<#
.SYNOPSIS
    Achilles RAG guncel-arastirma turunu headless Claude Code ile calistirir;
    istege bagli olarak ~6 saatlik bir Windows Scheduled Task kurar/kaldirir.

.DESCRIPTION
    Bir "tur" = scripts/rag-research-cycle.md talimatini headless `claude -p` ile
    kosturmak: guncel RAG literaturunu tara -> ise yarayani entegre et -> dokumani
    surumle/guncelle -> dogrula (ruff/mypy/pytest) -> commit + push. Cikti logs/'a yazilir.

    Anahtarsiz calistirma: TEK tur kosar (hemen).
    -Register   : her -IntervalHours saatte bir bu betigi (tek tur) calistiran gorev kurar.
    -Unregister : gorevi kaldirir.
    -RunNow     : -Register ile birlikte; kurduktan sonra bir tur hemen kosar.

.PARAMETER PermissionMode
    Headless izin modu. Varsayilan 'acceptEdits' (dosya duzenlemeleri otomatik kabul;
    bash/push ise proje settings.local.json allow kurallarina tabi). TAM gozetimsiz
    otomasyon (pytest + git push dahil her sey sorulmadan) icin 'bypassPermissions'
    gerekebilir -- guvenlik etkisini bilerek sec.

.EXAMPLE
    # Tek tur (elle):
    .\scripts\rag-research-loop.ps1

.EXAMPLE
    # 6 saatlik dongunu kur (ve hemen bir tur kos):
    .\scripts\rag-research-loop.ps1 -Register -RunNow

.EXAMPLE
    # Dongunu kaldir:
    .\scripts\rag-research-loop.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [switch]$Register,
    [switch]$Unregister,
    [switch]$RunNow,
    [int]$IntervalHours = 6,
    [ValidateSet('acceptEdits', 'bypassPermissions', 'default', 'plan')]
    [string]$PermissionMode = 'acceptEdits'
)

$ErrorActionPreference = 'Stop'
$TaskName = 'Achilles-RAG-Research-Loop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PromptPath = Join-Path $PSScriptRoot 'rag-research-cycle.md'
$ScriptPath = Join-Path $PSScriptRoot 'rag-research-loop.ps1'

function Invoke-Cycle {
    if (-not (Test-Path $PromptPath)) {
        throw "Tur talimati bulunamadi: $PromptPath"
    }
    $claude = (Get-Command claude -ErrorAction SilentlyContinue)
    if ($null -eq $claude) {
        throw "claude CLI PATH'te bulunamadi. Claude Code kurulu mu?"
    }
    Set-Location $RepoRoot
    $logDir = Join-Path $RepoRoot 'logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $log = Join-Path $logDir "rag-research-$stamp.log"
    $prompt = Get-Content -Raw -Encoding utf8 $PromptPath

    Write-Host "[$(Get-Date -Format o)] RAG arastirma turu basliyor -> $log"
    # Headless print modu. stderr dahil log'a yaz.
    & $claude.Source -p $prompt --permission-mode $PermissionMode *>> $log
    $code = $LASTEXITCODE
    Write-Host "[$(Get-Date -Format o)] Tur bitti (exit=$code). Log: $log"
    return $code
}

function Register-Loop {
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -PermissionMode $PermissionMode"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
    # Simdi (2 dk sonra) basla, her $IntervalHours saatte bir tekrarla (suresiz).
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
        -RepetitionInterval (New-TimeSpan -Hours $IntervalHours)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description 'Achilles RAG guncel-arastirma 6 saatlik otonom tur' `
        -Force | Out-Null
    Write-Host "Gorev kuruldu: '$TaskName' -- her $IntervalHours saatte bir."
    Write-Host "Kaldirmak icin: .\scripts\rag-research-loop.ps1 -Unregister"
}

function Unregister-Loop {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        Write-Host "Gorev zaten yok: '$TaskName'"
        return
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Gorev kaldirildi: '$TaskName'"
}

if ($Unregister) {
    Unregister-Loop
    return
}
if ($Register) {
    Register-Loop
    if ($RunNow) { Invoke-Cycle | Out-Null }
    return
}

# Anahtarsiz: tek tur kos.
exit (Invoke-Cycle)
