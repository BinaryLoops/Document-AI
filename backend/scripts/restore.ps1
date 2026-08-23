# =============================================================================
# DocuMind AI Backend — Restore Script (Windows PowerShell)
# =============================================================================
# See scripts/restore.sh for the Linux/macOS equivalent and full documentation.
#
# Usage:
#   .\scripts\restore.ps1 -Archive .\backups\documind-backup-20260101T000000Z.zip
# =============================================================================
param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [string]$TargetDir = "."
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Archive)) {
    Write-Error "Backup archive not found: $Archive"
    exit 1
}

if (Test-Path "$Archive.sha256") {
    Write-Host "==> Verifying checksum..."
    $expected = (Get-Content "$Archive.sha256").Split(" ")[0]
    $actual = (Get-FileHash -Algorithm SHA256 $Archive).Hash
    if ($expected -ne $actual) {
        Write-Error "Checksum mismatch! Backup may be corrupted."
        exit 1
    }
    Write-Host "    OK"
}

Write-Host "==> WARNING: this will overwrite existing data in: $TargetDir"
$confirm = Read-Host "    Type 'yes' to continue"
if ($confirm -ne "yes") {
    Write-Host "Aborted."
    exit 1
}

$Staging = Join-Path $env:TEMP "documind-restore-$(Get-Date -Format 'yyyyMMddHHmmss')"
Expand-Archive -Path $Archive -DestinationPath $Staging

$SafetyDir = Join-Path $TargetDir ".pre-restore-$(Get-Date -AsUTC -Format 'yyyyMMddTHHmmssZ')"
New-Item -ItemType Directory -Force -Path $SafetyDir | Out-Null

Get-ChildItem $Staging | ForEach-Object {
    $dest = Join-Path $TargetDir $_.Name
    if (Test-Path $dest) {
        Move-Item $dest $SafetyDir -Force
    }
    Copy-Item -Recurse -Force $_.FullName -Destination $TargetDir
    Write-Host "  + restored $($_.Name)"
}

Remove-Item -Recurse -Force $Staging

Write-Host "==> Restore complete."
Write-Host "==> Pre-restore snapshot of overwritten files kept at: $SafetyDir"
Write-Host "==> Start the backend and verify: curl http://localhost:8000/health"
