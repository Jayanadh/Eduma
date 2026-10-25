#!/usr/bin/env bash
# Restore drill: put the latest backup into a scratch database (eduma_drill) in the same container, time it, then
# compare every table's row count and each institution's fee trial balance with the live database and record the
# result as a RestoreDrill (health shows it). The live database is never touched. Run monthly (docs/operations.md).
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
latest="$(ls -1d "$BACKUP_DIR"/*/ | sort | tail -1)"
dump="${latest}eduma.dump"
expected="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['database']['sha256'])" "${latest}manifest.json")"
actual="$(shasum -a 256 "$dump" | cut -d' ' -f1)"
[ "$expected" = "$actual" ] || { echo "The dump doesn't match its manifest; not restoring." >&2; exit 1; }

start=$(python3 -c 'import time; print(time.time())')
docker compose exec -T db dropdb -U eduma --if-exists eduma_drill
docker compose exec -T db createdb -U eduma eduma_drill
docker compose exec -T db pg_restore -U eduma -d eduma_drill --no-owner < "$dump"
mkdir -p /tmp/eduma-drill-media && tar -C /tmp/eduma-drill-media -xf "${latest}private_media.tar"
seconds=$(python3 -c "import time; print(round(time.time() - $start, 1))")

backend/.venv/bin/python backend/manage.py restore_check --restored eduma_drill --seconds "$seconds"
echo "Restored $latest in $seconds s"
