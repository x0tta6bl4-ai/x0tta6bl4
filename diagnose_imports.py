
import time
import sys
import os

modules_to_test = [
    "src.core.consciousness",
    "src.core.mape_k_loop",
    "src.federated_learning.app_integration",
    "src.mesh.network_manager",
    "src.monitoring.prometheus_client",
    "src.security.zero_trust",
    "src.swarm.parl.controller",
    "src.core.production_lifespan"
]

def diagnose_imports():
    os.environ["DATABASE_URL"] = "sqlite:///./x0tta6bl4.db"
    os.environ["MAAS_LIGHT_MODE"] = "false"
    
    print("Starting import diagnostics...")
    for module in modules_to_test:
        start = time.time()
        print(f"Importing {module}...", end=" ", flush=True)
        try:
            # We use __import__ to dynamically import by name
            __import__(module)
            elapsed = time.time() - start
            print(f"DONE in {elapsed:.2f}s")
        except Exception as e:
            print(f"FAILED: {e}")
            # Stop if a critical import fails
            # break

if __name__ == "__main__":
    diagnose_imports()
