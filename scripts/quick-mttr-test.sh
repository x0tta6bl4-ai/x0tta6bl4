#!/bin/bash
# Quick MTTR test on 3 servers

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       ТЕСТ MTTR НА 3 СЕРВЕРАХ                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

RESULTS=""

for ctx in "kind-x0tta6bl4-local" "kind-x0tta6bl4-staging" "kind-x0tta6bl4-prod"; do
    name=$(echo $ctx | sed 's/kind-x0tta6bl4-//' | tr '[:lower:]' '[:upper:]')
    echo "🧪 Тест на $name..."
    
    # Get pod
    pod=$(kubectl get pods -n mesh-system --context $ctx -o name 2>/dev/null | head -1)
    if [ -z "$pod" ]; then
        echo "   ❌ Нет подов"
        RESULTS="$RESULTS\n$name: FAIL"
        continue
    fi
    
    # Kill and measure
    start=$(date +%s%N)
    kubectl delete $pod -n mesh-system --context $ctx --grace-period=0 --force 2>/dev/null
    
    # Wait for recovery
    for i in $(seq 1 60); do
        ready=$(kubectl get pods -n mesh-system --context $ctx --no-headers 2>/dev/null | grep -c "1/1.*Running")
        if [ "$ready" -ge 4 ]; then
            break
        fi
        sleep 0.5
    done
    
    end=$(date +%s%N)
    mttr=$(echo "scale=2; ($end - $start) / 1000000000" | bc)
    echo "   ✅ MTTR: ${mttr}s"
    RESULTS="$RESULTS$name: ${mttr}s\n"
    sleep 2
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ"
echo "═══════════════════════════════════════════════════════════════"
echo -e "$RESULTS"
echo ""
echo "Target: ≤5s"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🏆 ТЕСТ ЗАВЕРШЁН НА 3 СЕРВЕРАХ                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
