# Achilles -- TEK KOMUTLA PR (Windows). open-pr.sh'in PowerShell karsiligi.
#
# Mevcut daldaki isi push eder ve otomatik PR acar. VARSAYILAN: CI gecince
# otomatik squash-merge. -NoMerge ile sadece PR acar (merge'i sen yaparsin).
#
# Kullanim (VARSAYILAN = tam otomatik):
#   .\scripts\open-pr.ps1                       # push + PR + oto-merge (onerilen)
#   .\scripts\open-pr.ps1 -Title "Ozel baslik"  # baslik sen ver
#   .\scripts\open-pr.ps1 -NoMerge              # sadece PR ac, merge'i sen yap
#   .\scripts\open-pr.ps1 -Base develop         # farkli hedef dal (vars. main)
#
# On kosul (bir kerelik):  gh auth login  +  setup-pr-automation (bir defa)
param(
    [string]$Base = "main",
    [string]$Title = "",
    [switch]$NoMerge
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# gh giris yapilmis mi?
gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[HATA] gh giris yapilmamis. Once bir kerelik:  gh auth login" -ForegroundColor Red
    exit 2
}

$Branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($Branch -eq $Base) {
    Write-Host "[!] '$Base' dalindasin -- PR icin once bir ozellik dalina gec:" -ForegroundColor Yellow
    Write-Host "      git switch -c feat/yeni-ozellik" -ForegroundColor Gray
    exit 1
}

if (git status --porcelain) {
    Write-Host "[!] Kaydedilmemis degisiklik var -- once commit et (yoksa PR'a girmez)." -ForegroundColor Yellow
}

Write-Host ">> '$Branch' dali push ediliyor..." -ForegroundColor Cyan
git push -u origin $Branch

gh pr view $Branch *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[i] Bu dal icin PR zaten var (guncellendi)." -ForegroundColor Gray
} else {
    Write-Host ">> PR olusturuluyor (hedef: $Base)..." -ForegroundColor Cyan
    if ($Title) {
        gh pr create --base $Base --head $Branch --title $Title --body "Otomatik PR (scripts/open-pr.ps1) -- degisiklikler '$Branch' dalinda."
    } else {
        gh pr create --base $Base --head $Branch --fill
    }
}

$Url = gh pr view $Branch --json url -q .url
Write-Host "[OK] PR: $Url" -ForegroundColor Green

if (-not $NoMerge) {
    Write-Host ">> Oto-merge ayarlaniyor (CI yesil olunca squash + dali sil)..." -ForegroundColor Cyan
    gh pr merge $Branch --squash --delete-branch --auto
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Oto-merge aktif (gerekli kontroller gecince birlesir)." -ForegroundColor Green
    } else {
        Write-Host "[!] Oto-merge ayarlanamadi (branch korumasi/checks gerekebilir) -- PR acik kaldi." -ForegroundColor Yellow
    }
}
