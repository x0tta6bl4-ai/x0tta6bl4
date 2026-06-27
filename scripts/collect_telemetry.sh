#!/bin/bash
export DATABASE_URL=sqlite:////mnt/projects/x0tta6bl4_enterprise.db
export PYTHONPATH=$PYTHONPATH:.
# Start server in background
nohup python3 -m uvicorn libx0t.core.app:app --host 0.0.0.0 --port 8000 > server_telemetry_collection.log 2>&1 &
SERVER_PID=$!

echo "Waiting for server to start..."
# Wait for port 8000 to be open
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "Server is UP!"
        break
    fi
    sleep 1
done

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Server failed to start!"
    cat server_telemetry_collection.log
    exit 1
fi

echo "Sending heartbeats for 15 nodes..."
for node_num in {1..11}; do
    node_id=$(printf "node-%03d" $node_num)
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"node_id\":\"$node_id\", \"cpu_usage\":$((RANDOM % 30 + 10)), \"memory_usage\":$((RANDOM % 40 + 20)), \"neighbors_count\":$((RANDOM % 5 + 1)), \"routing_table_size\":20, \"uptime\":$((RANDOM % 1000 + 100)), \"latency_ms\":$((RANDOM % 50 + 5))}" \
        http://localhost:8000/api/v1/maas/heartbeat > /dev/null
done

for node_id in chaos-node-1 node-b35b85 node-3f8134 node-07e3bc; do
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"node_id\":\"$node_id\", \"cpu_usage\":25.0, \"memory_usage\":45.0, \"neighbors_count\":3, \"routing_table_size\":20, \"uptime\":5000, \"latency_ms\":12.5}" \
        http://localhost:8000/api/v1/maas/heartbeat > /dev/null
done

echo "Telemetry sent. Checking topology..."
curl -s -H "X-API-Key: admin-key" http://localhost:8000/api/v1/maas/demo-mesh/topology | python3 -m json.tool

# Stop server
kill $SERVER_PID
echo "Done."
