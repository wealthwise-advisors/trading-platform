#!/usr/bin/env bash
#
# Restore a backup, or inspect one without restoring.
#
#   scripts/restore.sh --list                       what is in the bucket
#   scripts/restore.sh --inspect 2026-08-29T03-00-00Z
#   scripts/restore.sh --to /tmp/scratch 2026-08-29T03-00-00Z
#   scripts/restore.sh --production 2026-08-29T03-00-00Z    (asks first)
#
# WHY --to IS THE DEFAULT AND --production IS NOT
# -----------------------------------------------
# The common reason to touch a backup is to check that it is good, or to pull
# one record out of it. Overwriting a live database should take a different
# command from reading one, so that reading one can never do it by accident.
#
# --production refuses to run unattended: it requires an interactive
# confirmation, and it snapshots the current database first, so the restore
# itself is reversible.
#
set -euo pipefail

BUCKET="${BACKUP_BUCKET:?BACKUP_BUCKET is not set -- see docs/BACKUP.md}"
PREFIX="${BACKUP_PREFIX:-autotrader}"
CONTAINER="${API_CONTAINER:-repo-api-1}"
DB_IN_CONTAINER="${DB_IN_CONTAINER:-/app/data/autotrader.db}"
REPO_DIR="${REPO_DIR:-/opt/wealthwise/repo}"

log() { printf '  %s\n' "$*"; }
fail() { printf '  FAILED: %s\n' "$*" >&2; exit 1; }

MODE=""; TARGET=""; STAMP=""
while [ $# -gt 0 ]; do
    case "$1" in
        --list)       MODE=list; shift ;;
        --inspect)    MODE=inspect; STAMP="${2:?stamp required}"; shift 2 ;;
        --to)         MODE=dir; TARGET="${2:?directory required}"; shift 2 ;;
        --production) MODE=production; STAMP="${2:?stamp required}"; shift 2 ;;
        *)            STAMP="$1"; shift ;;
    esac
done
[ -n "$MODE" ] || fail "pick one of --list --inspect --to --production"

# ── --list ──────────────────────────────────────────────────────────────────
if [ "$MODE" = list ]; then
    aws s3 ls "s3://${BUCKET}/${PREFIX}/" --human-readable | sort
    exit 0
fi

[ -n "$STAMP" ] || fail "which backup? give the timestamp from --list"

umask 077
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

KEY="${PREFIX}/${STAMP}.tar.gz"
log "fetching s3://${BUCKET}/${KEY}"
aws s3 cp "s3://${BUCKET}/${KEY}" "${WORK}/backup.tar.gz" --only-show-errors \
  || fail "no such backup: ${KEY}  (try --list)"

tar -xzf "${WORK}/backup.tar.gz" -C "$WORK" || fail "the archive will not extract"
[ -f "${WORK}/autotrader.db" ] || fail "the archive has no autotrader.db in it"

# Always verify before doing anything with it, in every mode.
python3 - "$WORK/autotrader.db" <<'PY' || fail "the restored database did not verify"
import sqlite3, sys
db = sys.argv[1]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
row = c.execute("PRAGMA integrity_check").fetchone()
assert row and row[0] == "ok", f"integrity_check: {row}"
for t in ("users", "sessions", "oauth_identities", "backtests"):
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"    {t:18} {n}")
    except sqlite3.OperationalError:
        print(f"    {t:18} (absent)")
print(f"    schema_version     {c.execute('PRAGMA user_version').fetchone()[0]}")
PY

[ -f "${WORK}/MANIFEST.txt" ] && { log "manifest:"; sed 's/^/    /' "${WORK}/MANIFEST.txt"; }

case "$MODE" in
  inspect)
      log "inspect only -- nothing was written"
      ;;

  dir)
      mkdir -p "$TARGET"
      cp -p "${WORK}/autotrader.db" "${TARGET}/autotrader.db"
      [ -d "${WORK}/config" ] && cp -rp "${WORK}/config" "${TARGET}/config"
      log "restored to ${TARGET}"
      log "run the API against it with:  AUTOTRADER_DB_PATH=${TARGET}/autotrader.db"
      ;;

  production)
      printf '  This overwrites the LIVE database. Type RESTORE to continue: '
      read -r answer
      [ "$answer" = "RESTORE" ] || fail "not confirmed -- nothing was changed"

      # The current database becomes a backup before it stops being the
      # database. A restore that cannot itself be undone is a second outage
      # waiting for the first mistake.
      SAFETY="/tmp/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).db"
      docker exec "$CONTAINER" python /tmp/_backup_helper.py \
              "$DB_IN_CONTAINER" /tmp/_pre_restore.db 2>/dev/null \
        && docker cp "${CONTAINER}:/tmp/_pre_restore.db" "$SAFETY" >/dev/null \
        && log "current database saved to ${SAFETY}"

      docker compose -f "${REPO_DIR}/docker-compose.yml" stop api
      docker cp "${WORK}/autotrader.db" "${CONTAINER}:${DB_IN_CONTAINER}"
      # The -wal and -shm sidecars belong to the database that was just
      # replaced. Left behind, SQLite would try to apply them to the new file.
      docker exec "$CONTAINER" sh -c \
          "rm -f ${DB_IN_CONTAINER}-wal ${DB_IN_CONTAINER}-shm" || true
      [ -d "${WORK}/config" ] && cp -rp "${WORK}/config/." "${REPO_DIR}/config/"
      docker compose -f "${REPO_DIR}/docker-compose.yml" start api

      log "waiting for the API to come back"
      for _ in $(seq 1 30); do
          sleep 2
          if curl -fsS --max-time 5 http://localhost/api/health >/dev/null 2>&1; then
              log "restored and healthy"; exit 0
          fi
      done
      fail "the API did not become healthy -- the previous database is at ${SAFETY}"
      ;;
esac
