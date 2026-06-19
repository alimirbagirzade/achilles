param(
    [int]$Target = 1300,
    [int]$Batch = 3,
    [string]$Output = "data/lora_sft",
    [int]$StartSeed = 100
)

$ProjectRoot = "C:\Users\sevinc\Development\achilles"
$UvExe = "C:\Users\sevinc\.local\bin\uv.exe"
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Get-CurrentCount {
    $jsonlPath = Join-Path $ProjectRoot $Output "synthetic_qa.jsonl"
    if (-not (Test-Path $jsonlPath)) { return 0 }
    return (Get-Content $jsonlPath -Encoding utf8 | Where-Object { $_ -ne "" }).Count
}

$seeds = @(100, 200, 300, 400) | Where-Object { $_ -ge $StartSeed }
foreach ($seed in $seeds) {
    $count = Get-CurrentCount
    Write-Host "$(Get-Date -Format 'HH:mm:ss') — Mevcut: $count örnek"
    if ($count -ge $Target) {
        Write-Host "Hedef $Target'a ulaşıldı — çıkılıyor."
        break
    }
    $logFile = Join-Path $LogDir "synth_qa_seed${seed}.log"
    Write-Host "$(Get-Date -Format 'HH:mm:ss') — seed=$seed başlatılıyor (hedef=$Target)…"
    $proc = Start-Process -FilePath $UvExe `
        -ArgumentList "run","achilles","synth-qa-bulk","--seed","$seed","--target","$Target","--output",$Output,"--batch","$Batch" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logFile.err" `
        -PassThru -NoNewWindow
    Write-Host "PID: $($proc.Id)"
    $proc.WaitForExit()
    $count = Get-CurrentCount
    Write-Host "$(Get-Date -Format 'HH:mm:ss') — seed=$seed bitti → $count örnek"
}

$finalCount = Get-CurrentCount
Write-Host "$(Get-Date -Format 'HH:mm:ss') — TAMAMLANDI: $finalCount örnek"
if ($finalCount -ge $Target) {
    Write-Host "SONRAKI ADIM: uv run achilles lora-split — ardından Kaggle 'Run All' tıkla"
}
