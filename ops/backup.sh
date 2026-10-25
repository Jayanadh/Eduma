#!/usr/bin/env bash
# Back up Eduma: the database (pg_dump custom format, from the db container) and private media, with a manifest of
# SHA-256s, then record it so the health page knows the backup age. Run daily from cron (see docs/operations.md).
# Development stores backups on this machine, unencrypted; production must encrypt them and keep them elsewhere.
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_DIR/$stamp"
mkdir -p "$dest"

docker compose exec -T db pg_dump -U eduma -d eduma --format=custom > "$dest/eduma.dump"
tar -C backend -cf "$dest/private_media.tar" private_media

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
size() { stat -f%z "$1" 2>/dev/null || stat -c%s "$1"; }
cat > "$dest/manifest.json" <<JSON
{
  "taken_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database": {"file": "$dest/eduma.dump", "sha256": "$(sha "$dest/eduma.dump")", "bytes": $(size "$dest/eduma.dump")},
  "media": {"file": "$dest/private_media.tar", "sha256": "$(sha "$dest/private_media.tar")", "bytes": $(size "$dest/private_media.tar")}
}
JSON
backend/.venv/bin/python backend/manage.py record_backup "$dest/manifest.json"
echo "Backup written to $dest"
