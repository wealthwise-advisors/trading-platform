#!/usr/bin/env bash
#
# Nightly backup of everything that exists ONLY on this instance.
#
#   sudo /opt/wealthwise/repo/scripts/backup.sh
#
# Run from cron on the EC2 host. Uploads one gzipped tarball per run to S3.
#
# WHAT IS IN IT, AND WHY EACH THING IS IRREPLACEABLE
# --------------------------------------------------
#   autotrader.db            accounts, sessions, OAuth identities, saved runs.
#                            Signup is open, so this now holds other people's
#                            data, not just the operator's.
#   config/credentials.yaml  gitignored -- exists nowhere else, not in the
#   config/schwab_tokens.json  image, not in the repository, not on a laptop.
#                            Losing these means re-authenticating Schwab from
#                            scratch.
#
# Everything else on this box is rebuildable from git in one deploy.
#
# THE FILE IS NOT COPIED WITH cp
# ------------------------------
# SQLite runs in WAL mode here. See scripts/sqlite_online_backup.py for why a
# plain copy can be silently torn, and what is used instead.
#
# SECRETS GO TO S3, SO THE BUCKET IS PART OF THE DESIGN
# -----------------------------------------------------
# This tarball contains live brokerage credentials. docs/BACKUP.md sets the
# bucket up with public access blocked, default encryption on, and versioning.
# Those are not optional hardening -- they are what makes putting this file in
# S3 acceptable at all.
#
set -euo pipefail

# ── settings ────────────────────────────────────────────────────────────────
BUCKET="${BACKUP_BUCKET:?BACKUP_BUCKET is not set -- see docs/BACKUP.md}"
PREFIX="${BACKUP_PREFIX:-autotrader}"
CONTAINER="${API_CONTAINER:-repo-api-1}"
REPO_DIR="${REPO_DIR:-/opt/wealthwise/repo}"
DB_IN_CONTAINER="${DB_IN_CONTAINER:-/app/data/autotrader.db}"
RETAIN_DAYS="${RETAIN_DAYS:-30}"

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
NAME="${PREFIX}-${STAMP}"

# 077 before anything is created: this working directory holds the database and
# the credentials in the clear for the length of the run.
umask 077
WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

log() { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
fail() { printf '%s  FAILED: %s\n' "$(date -u +%H:%M:%SZ)" "$*" >&2; exit 1; }

log "backup ${NAME} starting"

# ── 1 · the database, via SQLite's own online backup API ────────────────────
#
# Run INSIDE the container because that is where the volume is mounted, and it
# already has Python. The script it runs is the same one the restore test
# exercises -- not a copy of the logic.
docker cp "${REPO_DIR}/scripts/sqlite_online_backup.py" \
          "${CONTAINER}:/tmp/_backup_helper.py" >/dev/null \
  || fail "could not copy the backup helper into ${CONTAINER}"

if ! docker exec "$CONTAINER" python /tmp/_backup_helper.py \
        "$DB_IN_CONTAINER" /tmp/_snapshot.db; then
    docker exec "$CONTAINER" rm -f /tmp/_backup_helper.py /tmp/_snapshot.db || true
    fail "the online backup refused the snapshot (see the error above)"
fi

docker cp "${CONTAINER}:/tmp/_snapshot.db" "${WORK}/autotrader.db" >/dev/null \
  || fail "could not copy the snapshot out of the container"
docker exec "$CONTAINER" rm -f /tmp/_backup_helper.py /tmp/_snapshot.db || true
log "database snapshot: $(stat -c%s "${WORK}/autotrader.db") bytes"

# ── 2 · the two files that exist nowhere else ───────────────────────────────
mkdir -p "${WORK}/config"
for f in credentials.yaml schwab_tokens.json; do
    if [ -f "${REPO_DIR}/config/${f}" ]; then
        cp -p "${REPO_DIR}/config/${f}" "${WORK}/config/${f}"
        log "included config/${f}"
    else
        # Not fatal: a box without Schwab configured is a valid state, and
        # failing the whole backup over it would mean no database backup
        # either. Say so loudly instead.
        log "WARNING: ${REPO_DIR}/config/${f} not found -- not in this backup"
    fi
done

# A manifest, so a restore years from now does not have to guess what it holds.
{
    echo "created_utc   ${STAMP}"
    echo "host          $(hostname)"
    echo "commit        $(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "db_bytes      $(stat -c%s "${WORK}/autotrader.db")"
    echo "schema_version $(docker exec "$CONTAINER" python -c \
        "import sqlite3;print(sqlite3.connect('${DB_IN_CONTAINER}').execute('PRAGMA user_version').fetchone()[0])" 2>/dev/null || echo unknown)"
} > "${WORK}/MANIFEST.txt"

# ── 3 · one tarball ─────────────────────────────────────────────────────────
TARBALL="${WORK}/${NAME}.tar.gz"
tar -czf "$TARBALL" -C "$WORK" autotrader.db config MANIFEST.txt 2>/dev/null \
  || tar -czf "$TARBALL" -C "$WORK" autotrader.db MANIFEST.txt
SIZE="$(stat -c%s "$TARBALL")"
log "tarball: ${SIZE} bytes"

# Prove the archive is readable before it is the only copy of anything.
tar -tzf "$TARBALL" >/dev/null || fail "the tarball will not list -- not uploading"

# ── 4 · upload ──────────────────────────────────────────────────────────────
KEY="s3://${BUCKET}/${PREFIX}/${STAMP}.tar.gz"
aws s3 cp "$TARBALL" "$KEY" --only-show-errors \
    --sse AES256 \
  || fail "upload to ${KEY} failed"

# ── 5 · verify the object that is now in the bucket ─────────────────────────
#
# "The upload command exited 0" is not the same as "the object is there and is
# the right size". This is the same reasoning as the deploy asking the server
# which commit it is serving rather than trusting that it restarted.
REMOTE_SIZE="$(aws s3api head-object --bucket "$BUCKET" \
                 --key "${PREFIX}/${STAMP}.tar.gz" \
                 --query ContentLength --output text 2>/dev/null || echo missing)"
[ "$REMOTE_SIZE" = "$SIZE" ] \
  || fail "uploaded ${SIZE} bytes but the bucket reports ${REMOTE_SIZE}"
log "verified in S3: ${KEY} (${REMOTE_SIZE} bytes)"

# ── 6 · retention ───────────────────────────────────────────────────────────
#
# Deliberately a floor, not a ceiling: this only ever deletes objects OLDER
# than the window, and only after the new one is verified present above. A
# retention step that runs before the upload succeeds is how you end up with
# nothing at all.
CUTOFF="$(date -u -d "${RETAIN_DAYS} days ago" +%Y-%m-%d 2>/dev/null || echo "")"
if [ -n "$CUTOFF" ]; then
    aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "${PREFIX}/" \
        --query "Contents[?LastModified<'${CUTOFF}'].Key" --output text 2>/dev/null \
    | tr '\t' '\n' | grep -v '^$' | grep -v 'None' \
    | while read -r old; do
          aws s3 rm "s3://${BUCKET}/${old}" --only-show-errors && log "pruned ${old}"
      done
fi

log "backup ${NAME} complete"
