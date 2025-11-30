#!/bin/bash
# scripts/sprint2/deploy_apparmor_profiles.sh
set -euo pipefail

PROFILE_NAME="batman-adv-profile"

log() { echo "[$(date -Iseconds)] $*" >&2; }

deploy_profile_to_node() {
  local node=$1
  log "Deploying AppArmor profile to $node..."
  kubectl debug node/"$node" -it --image=ubuntu:22.04 -- bash -c "
    set -e
    mkdir -p /host/etc/apparmor.d
    cat > /host/etc/apparmor.d/$PROFILE_NAME << 'PROFILE_EOF'
#include <tunables/global>

profile batman-adv-profile flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  capability sys_module,
  capability net_admin,
  capability net_raw,
  capability net_bind_service,
  /lib/modules/** r,
  /sys/module/batman_adv/** rw,
  /sys/class/net/** rw,
  /proc/sys/net/** rw,
  /proc/net/** r,
  /dev/net/tun rw,
  /usr/sbin/batctl rix,
  /usr/lib/** rm,
  /lib/** rm,
  /etc/batman-adv/** r,
  /var/log/batman-adv/** rw,
  /tmp/** rw,
  deny /etc/shadow r,
  deny /etc/passwd w,
  deny /root/** rw,
  deny /home/** rw,
  deny /boot/** rw,
  /bin/ip rix,
  /bin/bash rix,
  /bin/sh rix,
  deny /bin/** x,
  deny /usr/bin/** x,
  deny /sbin/** x,
  deny /usr/sbin/** x,
  /usr/sbin/batctl ix,
  /bin/ip ix,
  /bin/bash ix,
  /bin/sh ix,
}
PROFILE_EOF
    apparmor_parser -r /host/etc/apparmor.d/$PROFILE_NAME
    aa-status | grep batman-adv || true
  "
}

main() {
  log "=== Deploying AppArmor Profiles ==="
  nodes=$(kubectl get nodes -l batman-adv-capable=true -o jsonpath='{.items[*].metadata.name}')
  if [[ -z "$nodes" ]]; then
    log "ERROR: No batman-adv-capable nodes found"
    exit 1
  fi
  for node in $nodes; do
    deploy_profile_to_node "$node"
  done
  log "=== AppArmor Deployment Complete ==="
}

main "$@"
