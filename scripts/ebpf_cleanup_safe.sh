#!/usr/bin/env bash
# scripts/ebpf_cleanup_safe.sh
# Safely detaches x0tta6bl4 XDP programs and removes project-specific BPF pins.
# Prevents kernel panics by avoiding recursive rm -rf on /sys/fs/bpf.

set -euo pipefail

BPF_FS_DIR="/sys/fs/bpf/x0tta6bl4-prod"
PROG_NAME="xdp_mesh_filter_prog"
MAPS=("packet_stats" "obf_config" "mesh_routes")

echo "🛡️ Starting safe eBPF cleanup..."

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# 1. Detach from network interfaces
echo "1. Detaching XDP programs from interfaces..."
# Find all interfaces with our program
IFACES=$(bpftool net show | grep "$PROG_NAME" | awk '{print $1}' | sed 's/(.*)//' || true)

for iface in $IFACES; do
    echo "  → Detaching from $iface..."
    ip link set dev "$iface" xdp off || echo "  ⚠️ Failed to detach from $iface"
done

# 2. Remove program pins
echo "2. Removing program pins..."
if [ -d "$BPF_FS_DIR/meshcore" ]; then
    find "$BPF_FS_DIR/meshcore" -type f -delete || echo "  ⚠️ Failed to delete some program pins"
    rmdir "$BPF_FS_DIR/meshcore" 2>/dev/null || true
fi

# 3. Remove map pins
echo "3. Removing map pins..."
if [ -d "$BPF_FS_DIR/maps" ]; then
    for map_name in "${MAPS[@]}"; do
        PIN_PATH="$BPF_FS_DIR/maps/$map_name"
        if [ -f "$PIN_PATH" ]; then
            echo "  → Deleting map pin: $map_name"
            rm "$PIN_PATH"
        fi
    done
    rmdir "$BPF_FS_DIR/maps" 2>/dev/null || true
fi

# 4. Final cleanup
echo "4. Finalizing..."
rmdir "$BPF_FS_DIR" 2>/dev/null || echo "  ℹ️ Base directory $BPF_FS_DIR not empty or already gone"

echo "✅ Safe eBPF cleanup completed"
