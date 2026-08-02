$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"
Set-Location $projectDir
$env:UV_NO_SYNC = "1"
& $pythonExe -c "from app.web.server import run; run()"
exit $LASTEXITCODE
