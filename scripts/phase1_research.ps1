# Faz 1 — Araştırma döngüsü orkestrasyonu (Windows, qwen3:30b CPU)
# Adımlar: kalan kartları üret -> mastery skor -> çapraz sentez (formül + araştırma)
# Her ağır LLM adımı arasında soğuma molası (bilgisayar ısınmasın).
#
# Kullanım:
#   $env:PYTHONUTF8=1; .\scripts\phase1_research.ps1
#
# Not: card üretimi idempotent değil (yeniden üretir); bu yüzden zaten kart
# üretilmiş makaleleri listeden çıkarın.

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = 1

# Soğuma molası (saniye) — ağır CPU adımları arasında.
$Cooldown = 150

function Log([string]$msg) {
    Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg)
}

function Cooldown-Break([string]$why) {
    Log "Soguma molasi ($Cooldown sn) — $why"
    Start-Sleep -Seconds $Cooldown
}

# Kart üretilecek makaleler (canary paper_bcb8810089c9 hariç — ayrı üretildi).
$Papers = @(
    "paper_ba2108ae4c22",
    "paper_00a33ccb1411",
    "paper_eb8ddde99a7f",
    "paper_b0bc463b9a90",
    "paper_2961fb6c5408"
)

Log "=== FAZ 1 BASLIYOR ==="

# --- 1) Bilgi kartlari ---
$i = 0
foreach ($pid in $Papers) {
    $i++
    $t = Get-Date
    Log "[$i/$($Papers.Count)] Kart uretiliyor: $pid"
    uv run achilles card $pid 2>&1 | Select-Object -Last 3
    $dk = [math]::Round(((Get-Date) - $t).TotalMinutes, 1)
    Log "[$i/$($Papers.Count)] Bitti: $pid ($dk dk)"
    if ($i -lt $Papers.Count) { Cooldown-Break "kartlar arasi" }
}

Cooldown-Break "kart -> mastery gecisi"

# --- 2) Mastery skorlari (LLM gerektirmez, deterministik) ---
Log "=== MASTERY SKORLARI ==="
uv run achilles mastery-queue --enqueue-all 2>&1 | Select-Object -Last 3
uv run achilles mastery-queue --run-all 2>&1 | Select-Object -Last 10

Cooldown-Break "mastery -> sentez gecisi"

# --- 3) Capraz sentez: formul cikarimi (tum makaleler) ---
Log "=== CAPRAZ SENTEZ: FORMUL CIKARIMI ==="
uv run achilles extract-formulas 2>&1 | Select-Object -Last 10

Log "=== FAZ 1 TAMAMLANDI ==="
