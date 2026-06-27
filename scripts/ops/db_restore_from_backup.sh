#!/usr/bin/env bash
# scripts/ops/db_restore_from_backup.sh
#
# DR scenario: restore PostgreSQL database from a pg_dump backup file.
# Safe for x0tta6bl4 production/staging restore procedures.
#
# Usage:
#   ./scripts/ops/db_restore_from_backup.sh --backup /path/to/backup.dump \
#       --target-url "postgresql://user:pass@host:5432/dbname" \
#       [--dry-run] [--skip-confirm]
#
# Exit codes:
#   0  — restore completed successfully
#   1  — restore failed
#   2  — pre-flight check failed (backup not found, bad URL, etc.)
#
# Environment variables (override CLI flags):
#   RESTORE_BACKUP_FILE   — path to .dump file
#   RESTORE_TARGET_URL    — postgresql:// DSN for target database
#   RESTORE_DRY_RUN       — set to "true" to skip actual restore
#   RESTORE_SKIP_CONFIRM  — set to "true" to skip interactive prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_FILE="${ROOT_DIR}/logs/dr_restore_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "${ROOT_DIR}/logs"

# ─── Defaults ──────────────────────────────────────────────────────────────
BACKUP_FILE="${RESTORE_BACKUP_FILE:-}"
TARGET_URL="${RESTORE_TARGET_URL:-}"
DRY_RUN="${RESTORE_DRY_RUN:-false}"
SKIP_CONFIRM="${RESTORE_SKIP_CONFIRM:-false}"
START_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "${LOG_FILE}"; }
die() { log "ERROR: $*"; exit 1; }
warn() { log "WARN: $*"; }

# ─── Argument parsing ──────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup)       BACKUP_FILE="$2"; shift 2 ;;
    --target-url)   TARGET_URL="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --skip-confirm) SKIP_CONFIRM=true; shift ;;
    *) die "Unknown argument: $1" ;;
  esac
done

log "======================================================"
log "x0tta6bl4 DB Restore — DR Procedure"
log "Start: ${START_TS}"
log "Log:   ${LOG_FILE}"
log "======================================================"

# ─── Pre-flight checks ────────────────────────────────────────────────────
log "── Pre-flight checks ──────────────────────────────────"

[[ -z "${BACKUP_FILE}" ]] && die "--backup / RESTORE_BACKUP_FILE is required"
[[ -z "${TARGET_URL}" ]]  && die "--target-url / RESTORE_TARGET_URL is required"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  die "Backup file not found: ${BACKUP_FILE}"
fi

BACKUP_SIZE_BYTES=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null || echo "0")
BACKUP_SIZE_MB=$(( BACKUP_SIZE_BYTES / 1024 / 1024 ))
log "Backup file: ${BACKUP_FILE} (${BACKUP_SIZE_MB} MB)"

# Validate pg_restore is available
if ! command -v pg_restore &>/dev/null && ! command -v psql &>/dev/null; then
  die "pg_restore and psql not found — install postgresql-client"
fi

# Validate target URL is reachable
log "Checking target DB connectivity..."
if command -v pg_isready &>/dev/null; then
  PG_HOST=$(echo "${TARGET_URL}" | sed -n 's|.*@\([^:/]*\).*|\1|p')
  PG_PORT=$(echo "${TARGET_URL}" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
  PG_PORT="${PG_PORT:-5432}"
  set +e
  pg_isready -h "${PG_HOST}" -p "${PG_PORT}" -t 10 >> "${LOG_FILE}" 2>&1
  READY_STATUS=$?
  set -e
  if [[ "${READY_STATUS}" -ne 0 ]]; then
    die "Target DB at ${PG_HOST}:${PG_PORT} is not ready (pg_isready exit ${READY_STATUS})"
  fi
  log "Target DB is reachable: ${PG_HOST}:${PG_PORT}"
else
  warn "pg_isready not found — skipping connectivity check"
fi

# ─── Summary + confirmation ───────────────────────────────────────────────
log ""
log "Restore plan:"
log "  Source backup : ${BACKUP_FILE}"
log "  Target DB URL : ${TARGET_URL//:*@/:***@}"   # mask password
log "  Dry run       : ${DRY_RUN}"
log ""

if [[ "${DRY_RUN}" == "true" ]]; then
  log "[DRY-RUN] Would execute restore. Exiting without changes."
  exit 0
fi

if [[ "${SKIP_CONFIRM}" != "true" ]]; then
  echo ""
  echo "WARNING: This will OVERWRITE the target database."
  echo "Press ENTER to continue or Ctrl+C to abort."
  read -r
fi

# ─── Step 1: Create pre-restore snapshot tag (metadata only) ─────────────
log "── Step 1: Pre-restore checkpoint ────────────────────"
CHECKPOINT_FILE="${ROOT_DIR}/logs/dr_checkpoint_${START_TS//[:T]/-}.txt"
cat > "${CHECKPOINT_FILE}" <<EOF
DR Restore Checkpoint
=====================
Timestamp  : ${START_TS}
Backup     : ${BACKUP_FILE}
Backup MD5 : $(md5sum "${BACKUP_FILE}" 2>/dev/null | awk '{print $1}' || echo "unavailable")
Target     : ${TARGET_URL//:*@/:***@}
Operator   : ${USER:-unknown}
Hostname   : $(hostname)
EOF
log "Checkpoint written: ${CHECKPOINT_FILE}"

# ─── Step 2: Drop and recreate public schema ─────────────────────────────
log "── Step 2: Drop and recreate public schema ────────────"
set +e
psql "${TARGET_URL}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
  >> "${LOG_FILE}" 2>&1
SCHEMA_STATUS=$?
set -e
if [[ "${SCHEMA_STATUS}" -ne 0 ]]; then
  die "Failed to reset public schema (exit ${SCHEMA_STATUS})"
fi
log "Schema reset: OK"

# ─── Step 3: Restore from dump ───────────────────────────────────────────
log "── Step 3: pg_restore ────────────────────────────────"
RESTORE_START=$(date +%s)
set +e
pg_restore \
  --no-owner \
  --no-acl \
  --exit-on-error \
  --dbname="${TARGET_URL}" \
  "${BACKUP_FILE}" \
  >> "${LOG_FILE}" 2>&1
RESTORE_STATUS=$?
set -e
RESTORE_END=$(date +%s)
RESTORE_DURATION=$(( RESTORE_END - RESTORE_START ))

if [[ "${RESTORE_STATUS}" -ne 0 ]]; then
  die "pg_restore failed (exit ${RESTORE_STATUS}) — see ${LOG_FILE}"
fi
log "pg_restore completed in ${RESTORE_DURATION}s: OK"

# ─── Step 4: Run Alembic upgrade head ────────────────────────────────────
log "── Step 4: Alembic upgrade head ──────────────────────"
if command -v alembic &>/dev/null && [[ -f "${ROOT_DIR}/alembic.ini" ]]; then
  set +e
  DATABASE_URL="${TARGET_URL}" alembic -c "${ROOT_DIR}/alembic.ini" upgrade head \
    >> "${LOG_FILE}" 2>&1
  ALEMBIC_STATUS=$?
  set -e
  if [[ "${ALEMBIC_STATUS}" -ne 0 ]]; then
    warn "Alembic upgrade head returned ${ALEMBIC_STATUS} — check ${LOG_FILE}"
    warn "This may be expected if backup is from the same revision."
  else
    log "Alembic upgrade head: OK"
  fi
else
  warn "alembic not installed or alembic.ini not found — skipping migration step"
fi

# ─── Step 5: Smoke check ──────────────────────────────────────────────────
log "── Step 5: Smoke check ───────────────────────────────"
SMOKE_RESULT=$(psql "${TARGET_URL}" -t -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
  2>>"${LOG_FILE}" || echo "0")
TABLE_COUNT=$(echo "${SMOKE_RESULT}" | tr -d ' \n')
log "Public tables found: ${TABLE_COUNT}"
if [[ "${TABLE_COUNT}" -lt 1 ]]; then
  die "Smoke check failed: no tables in restored database"
fi

# ─── Step 6: Verify alembic version table ────────────────────────────────
log "── Step 6: Verify alembic_version ───────────────────"
set +e
ALEMBIC_HEAD=$(psql "${TARGET_URL}" -t -c \
  "SELECT version_num FROM alembic_version LIMIT 1;" 2>>"${LOG_FILE}" || echo "unknown")
set -e
ALEMBIC_HEAD=$(echo "${ALEMBIC_HEAD}" | tr -d ' \n')
log "Current alembic head: ${ALEMBIC_HEAD}"

# ─── Final summary ────────────────────────────────────────────────────────
END_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TOTAL_DURATION=$(( $(date +%s) - RESTORE_START ))

log ""
log "======================================================"
log "DR Restore COMPLETE"
log "  End time      : ${END_TS}"
log "  Total duration: ${TOTAL_DURATION}s"
log "  Tables found  : ${TABLE_COUNT}"
log "  Alembic head  : ${ALEMBIC_HEAD}"
log "  Full log      : ${LOG_FILE}"
log "======================================================"

exit 0
