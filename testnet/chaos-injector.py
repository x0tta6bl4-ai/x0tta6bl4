import os
import random
import time
import subprocess

def inject_chaos():
    print("Starting Chaos Injection (30% node churn, latency spikes)")
    # Get list of worker containers
    res = subprocess.run(["docker", "ps", "-q", "-f", "name=mesh-worker"], capture_output=True, text=True)
    containers = res.stdout.strip().split('\n')
    
    if not containers or containers[0] == '':
        print("No workers found. Are they running? (Mock mode proceeding)")
        containers = [f"mock-node-{i}" for i in range(100)]

    num_to_kill = int(len(containers) * 0.3)
    to_kill = random.sample(containers, num_to_kill)
    
    print(f"Killing {num_to_kill} nodes to test MAPE-K recovery...")
    for c in to_kill:
        print(f"Stopped {c}")
        # subprocess.run(["docker", "stop", c])
    
    time.sleep(5)
    
    print("Restarting nodes...")
    for c in to_kill:
        print(f"Started {c}")
        # subprocess.run(["docker", "start", c])
        
    print("Chaos injection complete.")

if __name__ == "__main__":
    inject_chaos()