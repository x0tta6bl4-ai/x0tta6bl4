#!/usr/bin/env bash
# Collect fresh read-only VPN evidence and rebuild local planning reports.
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/mnt/projects}"
COLLECTOR="${COLLECTOR:-$ROOT_DIR/nl-diagnostics/collect_vpn_readonly_snapshot.sh}"
REFRESH="${REFRESH:-$ROOT_DIR/nl-diagnostics/refresh_vpn_planning_reports.py}"

export VPN_ENABLE_BLOCKING_PROBES="${VPN_ENABLE_BLOCKING_PROBES:-1}"
if [ -d "$ROOT_DIR/.tmp" ]; then
    export TMPDIR="${TMPDIR:-$ROOT_DIR/.tmp}"
fi

snapshot_dir="$("$COLLECTOR" | tail -n 1)"
case "$snapshot_dir" in
    "$ROOT_DIR"/nl-diagnostics/snapshots/*|nl-diagnostics/snapshots/*)
        ;;
    *)
        printf 'collector returned unexpected snapshot path: %s\n' "$snapshot_dir" >&2
        exit 2
        ;;
esac

python3 "$REFRESH" --snapshot "$snapshot_dir"

printf 'snapshot=%s\n' "$snapshot_dir"
printf 'refresh=%s\n' "$ROOT_DIR/nl-diagnostics/vpn-planning-refresh-2026-05-28.md"
