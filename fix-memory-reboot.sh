#!/usr/bin/env bash
set -euo pipefail

# Safe size for current free disk (~17G on /)
SWAP_FILE="/swap3.img"
SWAP_SIZE="8G"

if ! swapon --show | awk '{print $1}' | grep -qx "$SWAP_FILE"; then
  fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
  chmod 600 "$SWAP_FILE"
  mkswap "$SWAP_FILE"
  swapon -p 50 "$SWAP_FILE"
  if ! grep -q "^$SWAP_FILE " /etc/fstab; then
    echo "$SWAP_FILE none swap sw,pri=50 0 0" >> /etc/fstab
  fi
fi

apt-get update
apt-get install -y zram-tools

cat > /etc/default/zramswap <<'CFG'
ALGO=lz4
PERCENT=100
PRIORITY=100
CFG

systemctl restart zramswap.service

cat > /etc/sysctl.d/99-memory-pressure.conf <<'CFG'
vm.swappiness=90
vm.vfs_cache_pressure=150
CFG

sysctl --system >/tmp/sysctl-apply.log 2>&1 || {
  tail -n 200 /tmp/sysctl-apply.log
  exit 1
}

echo
echo '=== RESULT ==='
swapon --show
free -h
printf 'swappiness=%s\n' "$(cat /proc/sys/vm/swappiness)"
printf 'vfs_cache_pressure=%s\n' "$(cat /proc/sys/vm/vfs_cache_pressure)"
