#!/usr/bin/env bash
# =============================================================================
# DocuMind AI Backend — Backup Script
# =============================================================================
# Backs up all stateful data the backend cannot regenerate on its own:
#   - SQLite databases (digilocker, verification, tracking, audit)
#   - JSON stores (auth, generation, knowledge graph)
#   - Digital Locker vault (encrypted document blobs)
#   - Document generation signing keys (gen_keys/) — CRITICAL, cannot be
#     regenerated; losing these invalidates every previously-issued document.
#   - Generated PDFs
#
# Usage:
#   ./scripts/backup.sh [destination_dir]
#
# Recommended: run on a schedule (cron / systemd timer / Kubernetes CronJob)
# and ship the resulting archive to off-site storage (S3, GCS, Azure Blob).
# =============================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="${1:-$APP_DIR/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_NAME="documind-backup-${TIMESTAMP}"
STAGING_DIR="$(mktemp -d)/${BACKUP_NAME}"

# Where the app's DB/JSON files live. If running under Docker Compose with
# the /app/data volume, point DATA_DIR at that mount instead.
DATA_DIR="${DATA_DIR:-$APP_DIR}"

mkdir -p "$DEST_DIR" "$STAGING_DIR"

echo "==> Backing up DocuMind AI data from: $DATA_DIR"

copy_if_exists() {
    local src="$1"
    if [ -e "$src" ]; then
        cp -a "$src" "$STAGING_DIR/"
        echo "  + $(basename "$src")"
    else
        echo "  - $(basename "$src") (not found, skipping)"
    fi
}

# SQLite databases (WAL files too, for consistency if not using .backup)
for f in digilocker.db digilocker.db-shm digilocker.db-wal \
         verification.db verification.db-shm verification.db-wal \
         tracking.db audit.db; do
    copy_if_exists "$DATA_DIR/$f"
done

# JSON stores
for f in auth_store.json gen_store.json kg_store.json; do
    copy_if_exists "$DATA_DIR/$f"
done

# Vault (encrypted document blobs) and signing keys — CRITICAL
copy_if_exists "$DATA_DIR/vault"
copy_if_exists "$DATA_DIR/gen_keys"
copy_if_exists "$DATA_DIR/generated_pdfs"

# Environment file (contains config, NOT secrets if using a secrets manager —
# review before shipping this off-site).
copy_if_exists "$DATA_DIR/.env"

# Archive + compress
ARCHIVE_PATH="$DEST_DIR/${BACKUP_NAME}.tar.gz"
tar -czf "$ARCHIVE_PATH" -C "$(dirname "$STAGING_DIR")" "$BACKUP_NAME"
rm -rf "$STAGING_DIR"

# Checksum for integrity verification on restore
sha256sum "$ARCHIVE_PATH" > "${ARCHIVE_PATH}.sha256"

echo "==> Backup complete: $ARCHIVE_PATH"
echo "==> SHA-256: $(cat "${ARCHIVE_PATH}.sha256")"

# Retention: keep the last 14 local backups (tune to your RPO/storage budget)
RETENTION=14
ls -1t "$DEST_DIR"/documind-backup-*.tar.gz 2>/dev/null | tail -n +$((RETENTION + 1)) | while read -r old; do
    echo "==> Pruning old backup: $old"
    rm -f "$old" "${old}.sha256"
done
