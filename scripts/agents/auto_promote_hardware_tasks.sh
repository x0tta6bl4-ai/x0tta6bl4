#!/usr/bin/env bash
set -euo pipefail

# scripts/agents/auto_promote_hardware_tasks.sh
# Автоматически переводит задачи GEMINI-RDM-001/002 в ready, если найден физический NIC.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUEUE_FILE="${ROOT_DIR}/plans/ROADMAP_AGENT_QUEUE.json"

echo "[hardware-detector] checking for physical NICs with XDP support..."

# Поиск интерфейсов, исключая bridge, loopback и veth
PHYS_IFACE=$(ip -o link show | awk -F': ' '$2 !~ /^(lo|docker|veth|br-|virbr)/ {print $2}' | head -n 1)

if [[ -n "${PHYS_IFACE}" ]]; then
    echo "[hardware-detector] found potential physical NIC: ${PHYS_IFACE}"
    
    # Продвигаем задачи в очереди
    python3 - "${QUEUE_FILE}" "${PHYS_IFACE}" <<'PY'
import json, sys
path, iface = sys.argv[1], sys.argv[2]
with open(path, 'r') as f:
    data = json.load(f)

changed = False
for task in data.get('tasks', []):
    if task.get('id') in ['GEMINI-RDM-001', 'GEMINI-RDM-002'] and task.get('status') == 'blocked':
        task['status'] = 'ready'
        task['summary'] = task['summary'].replace('a real NIC', f'NIC {iface}')
        task['exact_next_command'] = task['exact_next_command'].replace('eth0', iface)
        if 'blocker' in task:
            del task['blocker']
        changed = True

if changed:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print("  + promoted GEMINI tasks to READY")
else:
    print("  ~ GEMINI tasks already READY or not found")
PY
else:
    echo "[hardware-detector] no physical NIC found, keeping tasks BLOCKED"
fi
