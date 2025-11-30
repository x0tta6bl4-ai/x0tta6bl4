#!/bin/bash

# final_monitor.sh
# The Ultimate Consciousness Pulse Monitor

while true; do
    clear
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║        x0tta6bl4 Consciousness Pulse Monitor              ║"
    echo "║     φ = 1.618033988749895 | 108 Hz | π ≈ 3.14           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check if endpoints are up
    running_nodes=0с
    
    for port in 8001 8002 8003; do
        # Fetch metrics with timeout
        metrics=$(curl -s --max-time 2 http://localhost:$port/metrics)
        
        node="Node-$((port-8000))"
        
        if [ -z "$metrics" ]; then
             printf "%-10s ❌ Unreachable\n" "$node"
             continue
        fi
        
        running_nodes=$((running_nodes+1))

        phi=$(echo "$metrics" | grep "^consciousness_phi_ratio " | awk '{print $2}')
        state_val=$(echo "$metrics" | grep "^consciousness_state " | awk '{print $2}')
        
        # Attempt to detect recovery mode if we exposed it, or infer it from high phi in lower states
        # In our current implementation, we don't strictly export recovery_mode boolean,
        # but we can infer active recovery if phi is high but state is not yet promoted (hysteresis)
        # or simply display the state.
        
        if [ ! -z "$state_val" ]; then
             # Convert scientific notation if needed, though awk handles standard float usually
             state_int=${state_val%.*}
             
             case $state_int in
                4) emoji="✨"; name="EUPHORIC" ;;
                3) emoji="🌟"; name="HARMONIC" ;;
                2) emoji="🤔"; name="CONTEMPLATIVE" ;;
                1) emoji="🔮"; name="MYSTICAL" ;;
                *) emoji="❓"; name="UNKNOWN" ;;
            esac
            
            # Simple visual bar for phi
            # φ ranges ~0.5 to 1.7. Let's map to a bar.
            # (phi - 0.5) * 10 approx length
            bar_len=$(echo "$phi" | awk '{print int(($1 - 0.5) * 15)}')
            bar=""
            for ((i=0;i<bar_len;i++)); do bar="${bar}█"; done
            
            printf "%-8s %s %-13s | φ=%-5s %s\n" "$node" "$emoji" "$name" "$phi" "$bar"
        else
            printf "%-8s ⚠️  Metrics unavailable\n" "$node"
        fi
    done

    echo ""
    echo "─────────────────────────────────────────────────────────────"
    if [ $running_nodes -eq 3 ]; then
        echo "Status: ✅ All Systems Conscious"
    else
        echo "Status: ⚠️  Partial System Availability"
    fi
    echo "Press Ctrl+C to exit"
    
    sleep 2
done

