#!/usr/bin/env bash
# =============================================================================
# DocuMind AI Backend — Restore Script
# =============================================================================
# Restores a backup produced by scripts/backup.sh.
#
# Usage:
#   ./scripts/restore.sh /path/to/documind-backup-20260101T000000Z.tar.gz [target_dir]
#
# IMPORTANT: Stop the backend (docker compose stop api / systemctl stop
# documind) before restoring so no process is writing to the SQLite files
# during the copy.
# =============================================================================
set -euo pipefail

ARCHIVE="${1:?Usage: restore.sh <backup.tar.gz> [target_dir]}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${2:-$APP_DIR}"

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: backup archive not found: $ARCHIVE" >&2
    exit 1
fi

# Verify checksum if available
if [ -f "${ARCHIVE}.sha256" ]; then
    echo "==> Verifying checksum..."
    (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "${ARCHIVE}.sha256")")
fi

echo "==> WARNING: this will overwrite existing data in: $TARGET_DIR"
read -r -p "    Type 'yes' to continue: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

STAGING_DIR="$(mktemp -d)"
tar -xzf "$ARCHIVE" -C "$STAGING_DIR"
EXTRACTED_DIR="$(find "$STAGING_DIR" -maxdepth 1 -mindepth 1 -type d | head -n1)"

echo "==> Restoring data into: $TARGET_DIR"
# Take a safety snapshot of anything we're about to overwrite
SAFETY_DIR="$TARGET_DIR/.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$SAFETY_DIR"

for item in "$EXTRACTED_DIR"/*; do
    name="$(basename "$item")"
    if [ -e "$TARGET_DIR/$name" ]; then
        mv "$TARGET_DIR/$name" "$SAFETY_DIR/" || true
    fi
    cp -a "$item" "$TARGET_DIR/"
    echo "  + restored $name"
done

rm -rf "$STAGING_DIR"

echo "==> Restore complete."
echo "==> Pre-restore snapshot of overwritten files kept at: $SAFETY_DIR"
echo "==> Start the backend and verify: curl http://localhost:8000/health"
