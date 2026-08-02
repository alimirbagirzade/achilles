$ErrorActionPreference = "Continue"
$projectDir = Split-Path -Parent $PSScriptRoot
$statusFile = Join-Path $projectDir "storage\train_status.json"
$startScript = Join-Path $PSScriptRoot "start-train.ps1"

if (-not (Test-Path $statusFile)) { exit 0 }
$status = Get-Content $statusFile -Raw | ConvertFrom-Json
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='uv.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*peft_lora_train*' -or $_.CommandLine -like '*train*--run*' }
if ($running) { exit 0 }

& $startScript -Adapter $status.adapter -Iterations ([int]$status.iterations) -Dtype $status.dtype -Profile "discipline_safe_local"
