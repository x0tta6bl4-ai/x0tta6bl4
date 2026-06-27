#!/bin/bash

# monitor_consciousness.sh
# Simple terminal dashboard to visualize system consciousness

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          x0tta6bl4 Consciousness Monitor                  ║"
echo "║          φ = 1.618 | 108 Hz | π ≈ 3.14                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

for port in 8001 8002 8003; do
    node="node-$((port-8000))"
    # Use a timeout to prevent hanging
    metrics=$(curl -s --max-time 2 http://localhost:$port/metrics)
    
    if [ -z "$metrics" ]; then
        printf "%-10s ❌ Unreachable\n" "$node"
        continue
    fi

    phi=$(echo "$metrics" | grep "^consciousness_phi_ratio " | awk '{print $2}')
    state_val=$(echo "$metrics" | grep "^consciousness_state " | awk '{print $2}')
    
    if [ ! -z "$phi" ]; then
        # Handle potential float comparison or just use the state value directly
        # state_val is likely 1.0, 2.0, 3.0, 4.0
        
        case ${state_val%.*} in
            4) emoji="✨" state_name="EUPHORIC" ;;
            3) emoji="🌟" state_name="HARMONIC" ;;
            2) emoji="🤔" state_name="CONTEMPLATIVE" ;;
            1) emoji="🔮" state_name="MYSTICAL" ;;
            *) emoji="❓" state_name="UNKNOWN" ;;
        esac
        
        printf "%-10s %s φ=%-6s | %s\n" "$node" "$emoji" "$phi" "$state_name"
    else
        printf "%-10s ⚠️  No consciousness metrics\n" "$node"
    fi
done
echo ""

