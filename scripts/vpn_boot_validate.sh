#!/usr/bin/env bash
# Validate the NL VPN contour after boot and persist the evidence.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/mnt/projects}"
LOG_DIR="${VPN_BOOT_VALIDATE_LOG_DIR:-/var/log/x0tta6bl4}"
LOG_FILE="${VPN_BOOT_VALIDATE_LOG_FILE:-$LOG_DIR/vpn_boot_validation.log}"
RESULT_FILE="${VPN_BOOT_VALIDATE_RESULT_FILE:-$LOG_DIR/vpn_boot_validation.last}"
ATTEMPTS="${VPN_BOOT_VALIDATE_ATTEMPTS:-12}"
SLEEP_SEC="${VPN_BOOT_VALIDATE_SLEEP_SEC:-10}"
BOOT_ID="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown)"

mkdir -p "$LOG_DIR"

write_result() {
    local status="$1"
    local attempt="$2"
    local detail="$3"

    {
        echo "status=$status"
        echo "timestamp=$(date -Is)"
        echo "boot_id=$BOOT_ID"
        echo "attempt=$attempt"
        echo "detail=$detail"
    } > "$RESULT_FILE"
}

{
    echo
    echo "=== x0tta VPN boot validation $(date -Is) ==="
    echo "boot_id=$BOOT_ID"
    echo "project_dir=$PROJECT_DIR attempts=$ATTEMPTS sleep_sec=$SLEEP_SEC"
} >> "$LOG_FILE"

for attempt in $(seq 1 "$ATTEMPTS"); do
    {
        echo "--- attempt $attempt/$ATTEMPTS $(date -Is) ---"
    } >> "$LOG_FILE"

    if (cd "$PROJECT_DIR" && bash scripts/vpn_status.sh --check --no-color) >> "$LOG_FILE" 2>&1; then
        {
            echo "PASS attempt=$attempt boot_id=$BOOT_ID"
            echo "=== validation complete $(date -Is) ==="
        } >> "$LOG_FILE"
        write_result "PASS" "$attempt" "vpn_status_check_passed"
        exit 0
    fi

    rc=$?
    echo "attempt $attempt failed rc=$rc" >> "$LOG_FILE"
    if [ "$attempt" -lt "$ATTEMPTS" ]; then
        sleep "$SLEEP_SEC"
    fi
done

{
    echo "FAIL boot_id=$BOOT_ID after $ATTEMPTS attempts"
    echo "=== validation failed $(date -Is) ==="
} >> "$LOG_FILE"
write_result "FAIL" "$ATTEMPTS" "vpn_status_check_failed"
exit 1
