#!/usr/bin/env python3
import time
import os
import json

def simulate_failure():
    print("\033[1;31m[CHAOS] Killing simulated mesh subprocess...\033[0m")
    # In a real scenario, we might kill the actual binary.
    # Here we update the state to trigger MAPE-K.
    stats = {
        "balance": "1000.0",
        "packets": 42,
        "uptime": 3600,
        "mesh": {"status": "CRITICAL", "peers": 0}
    }
    with open("node_stats.json", "w") as f:
        json.dump(stats, f)
    print("[CHAOS] State corrupted. Watching MAPE-K response...")

if __name__ == "__main__":
    simulate_failure()
    # Wait for MAPE-K to detect (running in dashboard background)
    time.sleep(5)
    print("\033[1;32m[RECOVERY] MAPE-K loop should now show 'ANALYZE' and 'PLAN' in dashboard.\033[0m")
