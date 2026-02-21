#!/bin/bash
# create_docker_loop.sh — Create EXT4 loop image on NTFS for Docker storage

set -e

IMG_PATH="/mnt/projects/docker_storage.img"
MOUNT_POINT="/mnt/projects/docker-ext4"
CONFIG_FILE="/etc/docker/daemon.json"

echo "🧹 Cleaning up previous attempts..."
sudo rm -rf /mnt/projects/docker-data || true

echo "📦 Creating 100GB virtual disk image (sparse)..."
# Truncate creates a sparse file: it takes 0 bytes on disk until data is written
truncate -s 100G "$IMG_PATH"

echo "format Formatting image to EXT4..."
mkfs.ext4 -F "$IMG_PATH"

echo "🔌 Creating mount point and mounting..."
sudo mkdir -p "$MOUNT_POINT"
sudo mount -o loop "$IMG_PATH" "$MOUNT_POINT"

echo "⚙️ Configuring Docker..."
sudo python3 -c "
import json, os
config = {}
if os.path.exists('$CONFIG_FILE'):
    with open('$CONFIG_FILE', 'r') as f:
        try:
            config = json.load(f)
        except:
            config = {}
config['data-root'] = '$MOUNT_POINT'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=4)
"

echo "🛑 Restarting Docker..."
sudo systemctl stop docker.socket || true
sudo systemctl stop docker
sudo systemctl start docker

echo "📊 Verifying..."
docker info | grep "Docker Root Dir"

echo "🎉 DONE! Docker is now using a virtual EXT4 disk on your HDD."
echo "⚠️ Note: To keep this after reboot, you'll need to mount the image again."
