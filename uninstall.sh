#!/bin/bash
# x0tta6bl4 Uninstaller
# Removes service, user, and installation directory.

SERVICE_NAME="x0tta6bl4-node"
INSTALL_DIR="/opt/x0tta6bl4"
USER="x0tta6bl4"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root."
  exit 1
fi

echo "Uninstalling x0tta6bl4..."

# Stop and Disable Service
if systemctl is-active --quiet $SERVICE_NAME; then
    systemctl stop $SERVICE_NAME
    echo "Service stopped."
fi
systemctl disable $SERVICE_NAME 2>/dev/null
rm -f /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
echo "Service removed."

# Remove Application Files
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Files removed from $INSTALL_DIR."
fi

# Remove User (Optional - commented out for safety)
# userdel $USER
# echo "User $USER removed."

echo "Uninstallation Complete."
