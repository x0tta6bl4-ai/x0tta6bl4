#!/bin/bash
# Deploy x0tta6bl4 systemd services to NL VPS
# Run as root on the target VPS

set -euo pipefail

INSTALL_DIR="/opt/x0tta6bl4"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== x0tta6bl4 systemd deployment ==="

# 1. Create user if not exists
if ! id -u x0tta6bl4 >/dev/null 2>&1; then
    echo "Creating user x0tta6bl4..."
    useradd -r -s /bin/false -d "$INSTALL_DIR" x0tta6bl4
fi

# 2. Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"/{var,sockets,run,venv,src}
chown -R x0tta6bl4:x0tta6bl4 "$INSTALL_DIR"

# 3. Copy systemd files
echo "Installing systemd units..."
cp "$SCRIPT_DIR/x0tta6bl4-node.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/x0tta6bl4-healthcheck.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/x0tta6bl4-healthcheck.timer" "$SYSTEMD_DIR/"

# 4. Install sysctl
echo "Installing sysctl settings..."
cp "$SCRIPT_DIR/99-x0tta6bl4.conf" /etc/sysctl.d/
sysctl --system 2>/dev/null || true

# 5. Reload and enable
echo "Enabling services..."
systemctl daemon-reload
systemctl enable x0tta6bl4-node.service
systemctl enable x0tta6bl4-healthcheck.timer

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Next steps:"
echo "  1. Deploy code to $INSTALL_DIR"
echo "  2. Configure env vars in $INSTALL_DIR/.env"
echo "  3. Start services:"
echo "     systemctl start x0tta6bl4-node"
echo "     systemctl start x0tta6bl4-healthcheck.timer"
echo "  4. Check status:"
echo "     systemctl status x0tta6bl4-node"
echo "     systemctl list-timers | grep x0tta6bl4"
