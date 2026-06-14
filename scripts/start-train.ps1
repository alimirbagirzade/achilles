# Achilles LoRA egitimi -- DETACHED (Claude Code/terminal kapansa da surer; PC acik kaldikca)
#
# Kullanim:
#   .\scripts\start-train.ps1                         -- bf16, achilles_lora_v5, 1 epoch (1203)
#   .\scripts\start-train.ps1 -Iterations 2406        -- 2 epoch
#   .\scripts\start-train.ps1 -Dtype fp32             -- fp32 (hizli ama web/Ollama kapatilmali)
#   .\scripts\start-train.ps1 -Stop                   -- egitimi durdur
#   .\scripts\start-train.ps1 -Status                 -- durum
#
# Start-Process ile baslatildigi icin baslatan kabuk (Claude Code dahil) kapansa da
# egitim bagimsiz surer. KOSULLAR: bilgisayar acik kalmali (uyku/hazirda bekleme YOK),
# kullanici oturumu acik kalmali (logoff egitimi durdurur).

param(
    [string]$Adapter = "achilles_lora_v5",
    [int]$Iterations = 1203,
    [string]$Dtype = "bf16",
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Continue"
$ScriptDir  = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectDir = Split-Path -Parent $ScriptDir
$LogOut     = Join-Path $ProjectDir "logs\train-full.log"
$LogErr     = Join-Path $ProjectDir "logs\train-full-err.log"

function Find-Uv {
    $fromPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if ($fromPath -and (Test-Path $fromPath)) { return $fromPath }
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\uv\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "uv\uv.exe")
    )
    foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }
    return $null
}

function Get-TrainProcs {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='uv.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*peft_lora_train*' -or $_.CommandLine -like '*train*--run*' }
}

if ($Status) {
    $p = Get-TrainProcs
    if ($p) { Write-Host "  Egitim: CALISIYOR ($(($p | Measure-Object).Count) surec)" -ForegroundColor Green }
    else    { Write-Host "  Egitim: calismyor" -ForegroundColor Yellow }
    if (Test-Path $LogErr) { Write-Host "  Son satir:"; Get-Content $LogErr -Tail 1 }
    exit 0
}

if ($Stop) {
    $p = Get-TrainProcs
    if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host "  [OK] Egitim durduruldu." -ForegroundColor Yellow }
    else    { Write-Host "  Zaten calismiyor." -ForegroundColor Gray }
    exit 0
}

if (Get-TrainProcs) {
    Write-Host "  [OK] Egitim zaten calisiyor (Status icin -Status)." -ForegroundColor Green
    exit 0
}

$uv = Find-Uv
if (-not $uv) { Write-Host "  [HATA] uv bulunamadi." -ForegroundColor Red; exit 1 }

$null = New-Item -ItemType Directory -Path (Split-Path $LogOut) -Force
$env:ACHILLES_TRAIN_DTYPE = $Dtype
Start-Process -FilePath $uv `
    -ArgumentList "run", "--project", "`"$ProjectDir`"", "achilles", "train", "--run", `
                  "--backend", "peft", "--adapter-name", $Adapter, "--iterations", "$Iterations" `
    -WorkingDirectory $ProjectDir `
    -RedirectStandardOutput $LogOut `
    -RedirectStandardError $LogErr `
    -WindowStyle Hidden
Write-Host "  [OK] Egitim DETACHED baslatildi (dtype=$Dtype, adapter=$Adapter, iters=$Iterations)." -ForegroundColor Green
Write-Host "       Claude Code/terminal kapansa da surer. PC acik + oturum acik kalmali." -ForegroundColor Cyan
Write-Host "       Ilerleme: logs\train-full-err.log" -ForegroundColor Gray
