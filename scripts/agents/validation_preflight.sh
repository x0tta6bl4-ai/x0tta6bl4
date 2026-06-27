#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUEUE_FILE="${ROOT_DIR}/plans/ROADMAP_AGENT_QUEUE.json"

agent=""
iface="${IFACE:-}"
json=0

usage() {
  cat <<'EOF'
usage: validation_preflight.sh --agent AGENT [--iface IFACE] [--json]
EOF
}

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --agent)
      agent="${2:-}"
      shift 2
      ;;
    --iface)
      iface="${2:-}"
      shift 2
      ;;
    --json)
      json=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "validation_preflight: unknown argument '${1}'" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "${agent}" ]] || { usage >&2; exit 2; }

python3 - "${QUEUE_FILE}" "${agent}" "${iface}" "${json}" <<'PY'
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

queue_file = Path(sys.argv[1])
agent = sys.argv[2]
iface_hint = sys.argv[3].strip()
json_mode = sys.argv[4] == "1"

if not queue_file.exists():
    print(f"validation preflight: missing queue file {queue_file}", file=sys.stderr)
    sys.exit(2)

payload = json.loads(queue_file.read_text(encoding="utf-8"))
tasks = [
    task for task in payload.get("tasks", [])
    if task.get("agent") == agent and task.get("mode") == "validation"
]

def sh_ok(cmd: list[str]) -> bool:
    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        return completed.returncode == 0
    except Exception:
        return False

def find_real_iface(preferred: str) -> tuple[str, str]:
    net_root = Path("/sys/class/net")
    if preferred:
        candidate = net_root / preferred
        if not candidate.exists():
            return preferred, "missing"
        if preferred == "lo":
            return preferred, "loopback"
        return preferred, "ok"

    if not net_root.exists():
        return "", "missing-net-root"

    candidates = sorted(p.name for p in net_root.iterdir() if p.name != "lo")
    if not candidates:
        return "", "no-real-nic"
    return candidates[0], "ok"

checks: list[dict[str, str]] = []
blockers: list[str] = []

required = set()
for task in tasks:
    for prereq in task.get("prereqs", []):
        required.add(str(prereq))

if not tasks:
    result = {
        "agent": agent,
        "status": "pass",
        "summary": "no validation tasks assigned",
        "tasks": [],
        "checks": [],
        "blockers": [],
    }
    if json_mode:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"[preflight] {agent}: no validation tasks assigned")
    sys.exit(0)

if "sudo-noninteractive" in required:
    ok = sh_ok(["sudo", "-n", "true"])
    checks.append({
        "name": "sudo-noninteractive",
        "status": "pass" if ok else "block",
        "detail": "sudo -n true"
    })
    if not ok:
        blockers.append("sudo -n true failed; root is required for current validation tasks")

iface_name = ""
if "real-nic" in required:
    iface_name, iface_status = find_real_iface(iface_hint)
    checks.append({
        "name": "real-nic",
        "status": "pass" if iface_status == "ok" else "block",
        "detail": iface_name or "(none)",
    })
    if iface_status == "missing":
        blockers.append(f"interface '{iface_name}' not found under /sys/class/net")
    elif iface_status == "loopback":
        blockers.append("loopback is not a valid live XDP target; choose a real NIC")
    elif iface_status == "missing-net-root":
        blockers.append("/sys/class/net is unavailable in this environment")
    elif iface_status == "no-real-nic":
        blockers.append("no non-loopback NIC is present")

if "btf-vmlinux" in required:
    ok = Path("/sys/kernel/btf/vmlinux").exists()
    checks.append({
        "name": "btf-vmlinux",
        "status": "pass" if ok else "block",
        "detail": "/sys/kernel/btf/vmlinux",
    })
    if not ok:
        blockers.append("missing /sys/kernel/btf/vmlinux required for current eBPF validation path")

if "pktgen-available" in required:
    pktgen_loaded = Path("/proc/net/pktgen").exists()
    pktgen_modinfo = shutil.which("modinfo") is not None and sh_ok(["modinfo", "pktgen"])
    ok = pktgen_loaded or pktgen_modinfo
    detail = "/proc/net/pktgen present" if pktgen_loaded else "modinfo pktgen"
    checks.append({
        "name": "pktgen-available",
        "status": "pass" if ok else "block",
        "detail": detail,
    })
    if not ok:
        blockers.append("pktgen is not loaded and modinfo pktgen did not succeed")

if "sigstore-id-token" in required:
    ok = bool(os.environ.get("SIGSTORE_ID_TOKEN", "").strip())
    checks.append({
        "name": "sigstore-id-token",
        "status": "pass" if ok else "block",
        "detail": "SIGSTORE_ID_TOKEN",
    })
    if not ok:
        blockers.append("SIGSTORE_ID_TOKEN is required for current validation tasks")

status = "pass" if not blockers else "blocked"
summary = "validation preflight passed" if status == "pass" else "validation preflight blocked"
result = {
    "agent": agent,
    "status": status,
    "summary": summary,
    "iface": iface_name or iface_hint or None,
    "tasks": [
        {
            "id": task.get("id"),
            "summary": task.get("summary"),
            "status": task.get("status"),
        }
        for task in tasks
    ],
    "checks": checks,
    "blockers": blockers,
}

if json_mode:
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
else:
    print(f"[preflight] {agent}: {summary}")
    if result.get("iface"):
        print(f"  iface: {result['iface']}")
    for check in checks:
        print(f"  - {check['status'].upper()} {check['name']}: {check['detail']}")
    if blockers:
        print("  blockers:")
        for blocker in blockers:
            print(f"    * {blocker}")

sys.exit(0 if status == "pass" else 2)
PY
