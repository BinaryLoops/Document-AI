# =============================================================================
# DocuMind AI Backend — Backup Script (Windows PowerShell)
# =============================================================================
# See scripts/backup.sh for the Linux/macOS equivalent and full documentation.
#
# Usage:
#   .\scripts\backup.ps1 -Destination .\backups
# =============================================================================
param(
    [string]$Destination = ".\backups",
    [string]$DataDir = "."
)

$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -AsUTC -Format "yyyyMMddTHHmmssZ"
$BackupName = "documind-backup-$Timestamp"
$Staging = Join-Path $env:TEMP $BackupName

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
New-Item -ItemType Directory -Force -Path $Staging | Out-Null

Write-Host "==> Backing up DocuMind AI data from: $DataDir"

$items = @(
    "digilocker.db", "digilocker.db-shm", "digilocker.db-wal",
    "verification.db", "verification.db-shm", "verification.db-wal",
    "tracking.db", "audit.db",
    "auth_store.json", "gen_store.json", "kg_store.json",
    "vault", "gen_keys", "generated_pdfs", ".env"
)

foreach ($item in $items) {
    $src = Join-Path $DataDir $item
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src -Destination $Staging
        Write-Host "  + $item"
    } else {
        Write-Host "  - $item (not found, skipping)"
    }
}

$ArchivePath = Join-Path $Destination "$BackupName.zip"
Compress-Archive -Path "$Staging\*" -DestinationPath $ArchivePath
Remove-Item -Recurse -Force $Staging

$Hash = Get-FileHash -Algorithm SHA256 $ArchivePath
"$($Hash.Hash)  $(Split-Path -Leaf $ArchivePath)" | Out-File -Encoding ascii "$ArchivePath.sha256"

Write-Host "==> Backup complete: $ArchivePath"
Write-Host "==> SHA-256: $($Hash.Hash)"

# Retention: keep the last 14 local backups
$old = Get-ChildItem $Destination -Filter "documind-backup-*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 14
foreach ($f in $old) {
    Write-Host "==> Pruning old backup: $($f.Name)"
    Remove-Item $f.FullName -Force
    Remove-Item "$($f.FullName).sha256" -Force -ErrorAction SilentlyContinue
}
