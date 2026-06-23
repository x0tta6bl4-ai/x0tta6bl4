#!/bin/bash
# mesh_shutdown.sh - Safe shutdown for x0tta6bl4 local ecosystem

echo "🛑 Shutting down x0tta6bl4 ecosystem..."

# 1. Stop Mesh Nodes (Go Agents)
echo "🔌 Stopping Go Agents (Data Plane)..."
pkill -f "x0t-agent"

# 2. Stop MaaS API (Control Plane)
echo "🧠 Stopping MaaS API (Control Plane)..."
pkill -f "uvicorn"
pkill -f "multiprocessing.spawn"

# 3. Stop Yggdrasil Backend
echo "🌐 Stopping Yggdrasil..."
sudo pkill -f "yggdrasil"
sudo rm -f /tmp/yggdrasil.sock

# 4. Clean up temporary logs (optional)
# rm -f /mnt/projects/local_mesh/*.log

echo "✅ All components stopped. System resources freed."
free -m
