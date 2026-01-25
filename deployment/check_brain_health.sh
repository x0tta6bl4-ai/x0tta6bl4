#!/bin/bash
# Health Check Script for x0tta6bl4-brain
# Run this to verify system consciousness

echo "🔍 x0tta6bl4-brain Health Check"
echo "================================"
echo ""

# 1. Service Status
echo "1️⃣ Service Status:"
systemctl is-active x0tta6bl4-brain >/dev/null && echo "   ✅ Service is RUNNING" || echo "   ❌ Service is DOWN"
echo ""

# 2. Process Info
echo "2️⃣ Process Info:"
ps aux | grep "run_brain.py" | grep -v grep | awk '{print "   PID: "$2" | CPU: "$3"% | RAM: "$4"% | MEM: "$6" KB"}'
echo ""

# 3. Latest Logs (last 10 lines)
echo "3️⃣ Latest Consciousness Logs:"
journalctl -u x0tta6bl4-brain -n 10 --no-pager | tail -n 5
echo ""

# 4. Current Metrics (if available)
echo "4️⃣ Current System Metrics:"
if [ -f /var/log/x0tta6bl4/metrics.json ]; then
    echo "   📊 Latest Phi Ratio:"
    tail -n 1 /var/log/x0tta6bl4/metrics.json | jq -r '"\   Phi: \(.phi_ratio) | State: \(.state) | CPU: \(.cpu)% | RAM: \(.ram)%"' 2>/dev/null || echo "   ⚠️  Metrics file exists but unreadable"
else
    echo "   ⏳ Metrics file not created yet (wait 1-2 minutes)"
fi
echo ""

# 5. Uptime
echo "5️⃣ Service Uptime:"
systemctl show x0tta6bl4-brain --property=ActiveEnterTimestamp | awk -F= '{print "   Started: "$2}'
echo ""

echo "================================"
echo "✅ Health check complete!"
