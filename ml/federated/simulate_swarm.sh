#!/bin/bash
# x0tta6bl4 FedML Swarm Simulation
# Status: READY FOR STRESS TEST

NUM_WORKERS=10
SERVER_PORT=8015
SERVER_URL="http://localhost:$SERVER_PORT"

echo "🚀 Starting FedML Swarm Simulation with $NUM_WORKERS workers..."

# 1. Сборка бинарных файлов
cd /mnt/projects
go build -o vps-aggregator ./cmd/vps-aggregator/main.go
go build -o edge-worker ./cmd/edge-worker/main.go

# 2. Запуск агрегатора в фоне
./vps-aggregator -port :$SERVER_PORT > /tmp/aggregator.log 2>&1 &
SERVER_PID=$!
sleep 2

echo "🔗 Aggregator live on port $SERVER_PORT. Spawning workers..."

# 3. Запуск воркеров параллельно
START_TIME=$(date +%s%N)

for i in $(seq 1 $NUM_WORKERS); do
    ./edge-worker -server $SERVER_URL -peer "worker-$i" > /dev/null 2>&1 &
    WORKER_PIDS[$i]=$!
done

# Ожидание завершения всех воркеров
for pid in ${WORKER_PIDS[*]}; do
    wait $pid
done

END_TIME=$(date +%s%N)
DURATION=$(( (END_TIME - START_TIME) / 1000000 ))

echo "✅ Swarm completed in $DURATION ms."
echo "📊 Average aggregation time per worker: $(( DURATION / NUM_WORKERS )) ms."

# 4. Очистка
kill $SERVER_PID
rm vps-aggregator edge-worker
