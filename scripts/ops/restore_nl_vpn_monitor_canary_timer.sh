#!/usr/bin/env bash
set -euo pipefail

REQUIRED_CONFIRM="APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER"
CONFIRM_VALUE="${RESTORE_NL_VPN_MONITOR_CONFIRM:-}"
NL_HOST="${NL_HOST:-nl}"
SSH_CONNECT_TIMEOUT="${SSH_CONNECT_TIMEOUT:-10}"
MODE="dry-run"
RUN_PRECHECK=0

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh [--dry-run] [--precheck] [--host nl]
  RESTORE_NL_VPN_MONITOR_CONFIRM=APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER \
    bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --apply [--host nl]

Default is dry-run and performs no SSH writes.
--precheck runs read-only SSH checks only.
--apply enables/starts ghost-access-vpn-monitor.timer, runs one monitor pass,
and refreshes x0tta6bl4-runtime-state.service. It requires the exact confirm
value above because the monitor can touch x-ui canary client state.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      MODE="apply"
      ;;
    --dry-run)
      MODE="dry-run"
      ;;
    --precheck)
      RUN_PRECHECK=1
      ;;
    --host)
      shift
      NL_HOST="${1:?missing value for --host}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

ssh_readonly() {
  ssh -o BatchMode=yes -o ConnectTimeout="$SSH_CONNECT_TIMEOUT" "$NL_HOST" "$@"
}

run_precheck() {
  ssh_readonly 'set -euo pipefail
printf "PRECHECK generated_at=%s host=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)"
for unit in ghost-access-vpn-monitor.service ghost-access-vpn-monitor.timer x0tta6bl4-runtime-state.service x0tta6bl4-runtime-state.timer; do
  printf "\n## %s\n" "$unit"
  systemctl show "$unit" -p LoadState -p ActiveState -p UnitFileState -p Result -p ExecMainStatus -p FragmentPath --no-pager 2>/dev/null || true
done
printf "\n## verify\n"
systemd-analyze verify /etc/systemd/system/ghost-access-vpn-monitor.service /etc/systemd/system/ghost-access-vpn-monitor.timer 2>&1 || true
printf "\n## latest vpn-service-access-agent summary\n"
if [ -f /var/lib/ghost-access/vpn-service-access-agent/latest.json ] && command -v jq >/dev/null 2>&1; then
  jq "{generated_at,overall_status,transport_summary:{status:.transport_summary.status,best_path:.transport_summary.best_path,paths:.transport_summary.paths},vpn_delivery:{reality_canary:.vpn_delivery.reality_canary,secondary_reality_canary:.vpn_delivery.secondary_reality_canary}}" /var/lib/ghost-access/vpn-service-access-agent/latest.json
else
  ls -l /var/lib/ghost-access/vpn-service-access-agent/latest.json 2>/dev/null || true
fi
printf "\n## no writes were performed by precheck\n"'
}

print_dry_run() {
  cat <<EOF
DRY_RUN=1
target=${NL_HOST}
required_confirm=${REQUIRED_CONFIRM}

No NL writes were performed.

Apply command, only after explicit operator approval:

  RESTORE_NL_VPN_MONITOR_CONFIRM=${REQUIRED_CONFIRM} \\
    bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --apply --host ${NL_HOST}

Remote write scope when applied:

  1. Save unit-state and latest monitor evidence under /root/nl-vpn-monitor-restore-<timestamp>/
  2. sudo systemctl enable --now ghost-access-vpn-monitor.timer
  3. sudo systemctl start ghost-access-vpn-monitor.service
  4. sudo systemctl start x0tta6bl4-runtime-state.service
  5. Print redacted status and latest canary summary

Rollback command if the maintenance owner wants the previous timer-off state:

  ssh ${NL_HOST} 'sudo systemctl disable --now ghost-access-vpn-monitor.timer'
EOF
}

if [[ "$MODE" == "dry-run" ]]; then
  print_dry_run
  if [[ "$RUN_PRECHECK" == "1" ]]; then
    run_precheck
  fi
  exit 0
fi

if [[ "$CONFIRM_VALUE" != "$REQUIRED_CONFIRM" ]]; then
  printf 'Refusing to apply: set RESTORE_NL_VPN_MONITOR_CONFIRM=%s\n' "$REQUIRED_CONFIRM" >&2
  exit 2
fi

ssh_readonly 'set -euo pipefail
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="/root/nl-vpn-monitor-restore-${stamp}"
sudo mkdir -p "$backup_dir"
sudo systemctl cat ghost-access-vpn-monitor.service ghost-access-vpn-monitor.timer > "$backup_dir/unit-definitions.before.txt" 2>&1 || true
sudo systemctl show ghost-access-vpn-monitor.service ghost-access-vpn-monitor.timer x0tta6bl4-runtime-state.service -p LoadState -p ActiveState -p UnitFileState -p Result -p ExecMainStatus -p FragmentPath --no-pager > "$backup_dir/unit-state.before.txt" 2>&1 || true
if [ -f /var/lib/ghost-access/vpn-service-access-agent/latest.json ]; then
  sudo cp -a /var/lib/ghost-access/vpn-service-access-agent/latest.json "$backup_dir/vpn-service-access-agent.latest.before.json"
fi

sudo systemctl enable --now ghost-access-vpn-monitor.timer
sudo systemctl start ghost-access-vpn-monitor.service
sudo systemctl start x0tta6bl4-runtime-state.service

sudo systemctl show ghost-access-vpn-monitor.service ghost-access-vpn-monitor.timer x0tta6bl4-runtime-state.service -p LoadState -p ActiveState -p UnitFileState -p Result -p ExecMainStatus --no-pager
if command -v jq >/dev/null 2>&1 && [ -f /var/lib/ghost-access/vpn-service-access-agent/latest.json ]; then
  jq "{generated_at,overall_status,transport_summary:{status:.transport_summary.status,best_path:.transport_summary.best_path,paths:.transport_summary.paths},vpn_delivery:{reality_canary:.vpn_delivery.reality_canary,secondary_reality_canary:.vpn_delivery.secondary_reality_canary}}" /var/lib/ghost-access/vpn-service-access-agent/latest.json
fi
printf "backup_dir=%s\n" "$backup_dir"
printf "rollback_hint=sudo systemctl disable --now ghost-access-vpn-monitor.timer\n"'
