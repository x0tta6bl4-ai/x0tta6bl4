
import time
import sys
import os
import signal

def handler(signum, frame):
    raise Exception("Timeout!")

signal.signal(signal.SIGALRM, handler)

def test_import(module_name):
    start = time.time()
    print(f"Importing {module_name}...", end=" ", flush=True)
    signal.alarm(20) # 20 seconds timeout per module
    try:
        __import__(module_name)
        print(f"DONE in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        signal.alarm(0)

modules = [
    "numpy",
    "torch",
    "torch_geometric",
    "shap",
    "llama_cpp",
    "src.llm.local_llm",
    "src.ml.causal_analysis",
    "src.ml.graphsage_anomaly_detector",
    "src.core.consciousness",
    "src.core.mape_k_loop",
    "src.core.production_lifespan"
]

if __name__ == "__main__":
    os.environ["DATABASE_URL"] = "sqlite:///./x0tta6bl4.db"
    os.environ["MAAS_LIGHT_MODE"] = "false"
    for m in modules:
        test_import(m)
