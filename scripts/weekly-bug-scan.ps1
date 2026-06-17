# Achilles weekly bug-hunt scan -- TIER 1 (REPORT-ONLY).  ASCII-only (Windows PS 5.1 safe).
#
# What it does:
#   1) Validation gate: ruff + mypy + pytest (offline, --no-sync avoids the web .exe lock).
#   2) Lightweight LLM bug scan: one `claude -p` call over recent diff + core (best-effort).
#   3) Writes reports/bug-scan/scan-<date>.md + one-line summary to HANDOFF.md.
#
# Does NOT edit code, does NOT commit/push. Findings are fixed in the next SUPERVISED
# session (see CLAUDE.md "Bug-avi kadansi" -- Tier 2 deep hunt is human-supervised).
#
# Run: Windows Task Scheduler (weekly) or manually:  powershell scripts\weekly-bug-scan.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$outDir = Join-Path $repo "reports\bug-scan"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$report = Join-Path $outDir "scan-$stamp.md"

function Append([string]$text) { $text | Out-File -FilePath $report -Append -Encoding utf8 }
function LastLine([string]$s) {
    ($s -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1)
}

"# Achilles bug-hunt scan -- $stamp (Tier 1, report-only)" | Out-File -FilePath $report -Encoding utf8
Append ""

# --- 1) Validation gate ------------------------------------------------------
Append "## Validation gate"
$ruff   = (uv run --no-sync ruff check . 2>&1 | Out-String).Trim()
$mypy   = (uv run --no-sync mypy app 2>&1 | Out-String).Trim()
$pytest = (uv run --no-sync pytest -q --basetemp=.pytest_tmp -p no:cacheprovider 2>&1 | Out-String).Trim()
Append '```'
Append ("RUFF   : " + (LastLine $ruff))
Append ("MYPY   : " + (LastLine $mypy))
Append ("PYTEST : " + (LastLine $pytest))
Append '```'

# --- 2) Lightweight LLM bug scan (best-effort) -------------------------------
Append ""
Append "## LLM bug scan (Tier 1)"
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    $prompt = @'
Run a LIGHTWEIGHT, REPORT-ONLY bug scan on the Achilles trading-RESEARCH project.
DO NOT edit code, DO NOT run git/file-write operations -- only find and summarize.
Focus: recent git diff (HEAD~15..HEAD) + core (app/trading, app/brain, app/memory,
app/verification, app/lora, app/training). Highest priority = CLAUDE.md absolute rules:
look-ahead bias, costs (commission+slippage), determinism (seed), no eval/exec, no source fabrication.
List each REAL, code-verified bug: [severity] file:line -- why -- suggested fix.
If none, write "temiz". Output: short plain markdown.
'@
    try {
        $scan = (claude -p $prompt 2>&1 | Out-String).Trim()
        Append $scan
    } catch {
        Append ("_LLM scan failed: " + $_.Exception.Message + "_")
    }
} else {
    Append "_claude CLI not on PATH -- LLM scan skipped (gate results above)._"
}

# --- 3) HANDOFF summary ------------------------------------------------------
$handoff = Join-Path $repo "HANDOFF.md"
if (Test-Path $handoff) {
    "`n> [bug-scan $stamp] Weekly Tier-1 scan done -> reports/bug-scan/scan-$stamp.md" |
        Out-File -FilePath $handoff -Append -Encoding utf8
}

Write-Output "Bug-hunt scan done -> $report"
