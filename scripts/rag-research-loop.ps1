<#
.SYNOPSIS
    Achilles RAG guncel-arastirma turunu headless Claude Code ile calistirir;
    istege bagli olarak periyodik bir Windows Scheduled Task kurar/kaldirir.

    Iki mod (iki-katmanli, esik-tetikli tasarim):
      -Mode Scan       : UCUZ tarama. Yeni adaylari docs/egitim/rag-watchlist.md'ye isler.
                         Kod/surum/PDF/test yok; yalniz watchlist push. Varsayilan ritim: 24 saat.
      -Mode Integrate  : AGIR entegrasyon (varsayilan). Watchlist'te >=1 guclu aday varsa
                         tam tur kosar (entegre -> surumle -> ruff/mypy/pytest -> commit+push);
                         yoksa no-op. Varsayilan ritim: 168 saat (haftalik).

.DESCRIPTION
    Anahtarsiz: secili -Mode icin TEK tur kosar (hemen).
    -Register   : secili -Mode icin (mod-basina varsayilan veya -IntervalHours) periyodik gorev kurar.
    -Unregister : secili -Mode gorevini kaldirir.
    -RunNow     : -Register ile birlikte; kurduktan sonra bir tur hemen kosar.

    Onerilen kurulum (gunluk tarama + haftalik entegrasyon):
      .\scripts\rag-research-loop.ps1 -Mode Scan -Register
      .\scripts\rag-research-loop.ps1 -Mode Integrate -Register

.PARAMETER PermissionMode
    Headless izin modu. Varsayilan 'acceptEdits'. TAM gozetimsiz otomasyon (pytest + git push
    sorulmadan) icin 'bypassPermissions' gerekebilir -- guvenlik etkisini bilerek sec.

.EXAMPLE
    .\scripts\rag-research-loop.ps1 -Mode Scan            # tek tarama turu (elle)
.EXAMPLE
    .\scripts\rag-research-loop.ps1 -Mode Integrate -Register -RunNow
.EXAMPLE
    .\scripts\rag-research-loop.ps1 -Mode Scan -Unregister
#>
[CmdletBinding()]
param(
    [ValidateSet('Scan', 'Integrate')]
    [string]$Mode = 'Integrate',
    [switch]$Register,
    [switch]$Unregister,
    [switch]$RunNow,
    [int]$IntervalHours = 0,
    [ValidateSet('acceptEdits', 'bypassPermissions', 'default', 'plan')]
    [string]$PermissionMode = 'acceptEdits'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $PSScriptRoot 'rag-research-loop.ps1'
$TaskName = "Achilles-RAG-$Mode"
$PromptFile = if ($Mode -eq 'Scan') { 'rag-research-scan.md' } else { 'rag-research-cycle.md' }
$PromptPath = Join-Path $PSScriptRoot $PromptFile

# Mod-basina varsayilan ritim (kullanici -IntervalHours vermediyse).
if ($IntervalHours -le 0) {
    $IntervalHours = if ($Mode -eq 'Scan') { 24 } else { 168 }
}

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
    $log = Join-Path $logDir "rag-$($Mode.ToLower())-$stamp.log"
    $prompt = Get-Content -Raw -Encoding utf8 $PromptPath

    Write-Host "[$(Get-Date -Format o)] RAG $Mode turu basliyor -> $log"
    & $claude.Source -p $prompt --permission-mode $PermissionMode *>> $log
    $code = $LASTEXITCODE
    Write-Host "[$(Get-Date -Format o)] $Mode turu bitti (exit=$code). Log: $log"
    return $code
}

function Register-Loop {
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -Mode $Mode -PermissionMode $PermissionMode"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
        -RepetitionInterval (New-TimeSpan -Hours $IntervalHours)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Achilles RAG $Mode turu (her $IntervalHours saat)" `
        -Force | Out-Null
    Write-Host "Gorev kuruldu: '$TaskName' -- her $IntervalHours saatte bir."
    Write-Host "Kaldirmak icin: .\scripts\rag-research-loop.ps1 -Mode $Mode -Unregister"
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
