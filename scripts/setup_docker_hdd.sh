#!/bin/bash
# setup_docker_hdd.sh — Move Docker storage to HDD (/mnt/projects)

set -e

NEW_DOCKER_ROOT="/mnt/projects/docker-data"
CONFIG_FILE="/etc/docker/daemon.json"

echo "🚀 Starting Docker migration to HDD..."

# 1. Create new directory
sudo mkdir -p "$NEW_DOCKER_ROOT"

# 2. Prepare daemon.json
# We use python to safely merge or create JSON
sudo python3 -c "
import json, os
config = {}
if os.path.exists('$CONFIG_FILE'):
    with open('$CONFIG_FILE', 'r') as f:
        try:
            config = json.load(f)
        except:
            config = {}
config['data-root'] = '$NEW_DOCKER_ROOT'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=4)
"

echo "✅ Config updated in $CONFIG_FILE"

# 3. Stop Docker and Move data
echo "🛑 Stopping Docker service..."
sudo systemctl stop docker.socket || true
sudo systemctl stop docker

if [ -d "/var/lib/docker" ]; then
    echo "📦 Syncing existing data to HDD (this may take time)..."
    sudo rsync -aP /var/lib/docker/ "$NEW_DOCKER_ROOT/"
fi

# 4. Restart Docker
echo "🏁 Starting Docker service..."
sudo systemctl start docker

# 5. Verify
NEW_ROOT=$(docker info | grep "Docker Root Dir")
echo "📊 Current $NEW_ROOT"

if [[ "$NEW_ROOT" == *"$NEW_DOCKER_ROOT"* ]]; then
    echo "🎉 SUCCESS: Docker now uses HDD for images and containers."
else
    echo "❌ ERROR: Migration failed. Check system logs."
    exit 1
fi
