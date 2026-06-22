#!/usr/bin/env python3
import sys
import os
import time
import logging
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("x0tta6bl4-verifier")

def print_banner():
    print("""
    \033[0;32m
      ___       ___       ___       ___       ___       ___   
     /\\  \\     /\\  \\     /\\  \\     /\\  \\     /\\  \\     /\\  \\  
    /::\\  \\   /::\\  \\   /::\\  \\   /::\\  \\   /::\\  \\   /::\\  \\ 
   /:/\\:\\__\\ /:/\\:\\__\\ /:/\\:\\__\\ /:/\\:\\__\\ /:/\\:\\__\\ /::\\:\\__\\
   \\:\\/:/  / \\:\\/:/  / \\:\\/:/  / \\:\\/:/  / \\:\\/:/  / \\/\\::/  /
    \\::/  /   \\::/  /   \\::/  /   \\::/  /   \\::/  /    /:/  / 
     \\/__/     \\/__/     \\/__/     \\/__/     \\/__/     \\/__/  
    \033[0m
    """)
    print("\033[1;36m>>> INITIATING FINAL SYSTEM VERIFICATION <<<\033[0m\n")

def check_pqc():
    print("\033[1;33m[1/3] Verifying Post-Quantum Cryptography (PQC)...\033[0m")
    try:
        sys.path.append(os.getcwd())
        from src.security.pqc.simple import PQC
        
        pqc = PQC(algorithm="Kyber768")
        pub, priv = pqc.generate_keypair()
        
        print(f"   Using Algorithm: \033[1;32m{pqc.algorithm}\033[0m")
        print(f"   Public Key Size: {len(pub)} bytes")
        print(f"   Private Key Size: {len(priv)} bytes")
        
        # Test Encapsulation
        shared_secret, ciphertext = pqc.encapsulate(pub)
        print(f"   Encapsulation: \033[1;32mSUCCESS\033[0m")
        
        # Test Decapsulation
        decrypted_secret = pqc.decapsulate(ciphertext, priv)
        
        if shared_secret == decrypted_secret:
             print(f"   Key Exchange: \033[1;32mVERIFIED (Secrets Match)\033[0m")
        else:
             print(f"   Key Exchange: \033[1;31mFAILED\033[0m")
             return False
             
    except Exception as e:
        print(f"   PQC Check Failed: {e}")
        return False
    return True

def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %.2f", name, value, default)
        return default

def _local_cpu_percent() -> float:
    try:
        load_1m = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        return max(0.0, min(100.0, (load_1m / cpu_count) * 100.0))
    except (AttributeError, OSError):
        return 0.0

def _local_memory_percent() -> float:
    try:
        values: Dict[str, float] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, raw_value = line.split(":", 1)
                values[key] = float(raw_value.strip().split()[0])
        total = values.get("MemTotal", 0.0)
        available = values.get("MemAvailable", 0.0)
        if total <= 0:
            return 0.0
        return max(0.0, min(100.0, ((total - available) / total) * 100.0))
    except (OSError, ValueError, IndexError):
        return 0.0

def collect_local_mapek_metrics() -> Dict[str, float | str]:
    return {
        "node_id": os.getenv("x0tta6bl4_NODE_ID", "local-verifier"),
        "cpu_percent": _env_float("x0tta6bl4_VERIFY_CPU_PERCENT", _local_cpu_percent()),
        "memory_percent": _env_float(
            "x0tta6bl4_VERIFY_MEMORY_PERCENT",
            _local_memory_percent(),
        ),
        "packet_loss_percent": _env_float("x0tta6bl4_VERIFY_PACKET_LOSS_PERCENT", 0.0),
    }

def _allow_remediation_execution() -> bool:
    return os.getenv("x0tta6bl4_VERIFY_ALLOW_REMEDIATION", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

def check_mape_k():
    print("\n\033[1;33m[2/3] Verifying MAPE-K Self-Healing Loop...\033[0m")
    try:
        from src.self_healing.mape_k import MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor
        
        # 1. Monitor
        monitor = MAPEKMonitor()
        metrics = collect_local_mapek_metrics()
        print(f"   [Monitor] Local Metrics: {metrics}")
        monitor_result = monitor.check(metrics)
        print(f"   [Monitor] Result: {monitor_result}")
        
        # 2. Analyze
        analyzer = MAPEKAnalyzer()
        analysis = analyzer.analyze(metrics)
        print(f"   [Analyze] Detection: \033[1;36m{analysis}\033[0m")

        # 3. Plan
        planner = MAPEKPlanner()
        plan = planner.plan(analysis)
        print(f"   [Plan] Strategy: \033[1;36m{plan}\033[0m")
        
        # 4. Execute
        executor = MAPEKExecutor()
        if executor._is_noop_action(plan):
            result = executor.execute(plan, {"verification": True, "metrics": metrics})
        elif _allow_remediation_execution():
            print("   [Execute] Applying remediation because env opt-in is enabled...")
            result = executor.execute(plan, {"verification": True, "metrics": metrics})
        else:
            print(
                "   [Execute] Remediation required but not executed. "
                "Set x0tta6bl4_VERIFY_ALLOW_REMEDIATION=true to opt in."
            )
            return False
        if not result:
            print("   Self-Healing Cycle: \033[1;31mFAILED\033[0m")
            return False
        time.sleep(0.1)
        print("   Self-Healing Cycle: \033[1;32mCOMPLETED\033[0m")
        
    except Exception as e:
        print(f"   MAPE-K Failed: {e}")
        return False
    return True

def check_infra():
    print("\n\033[1;33m[3/3] Verifying Infrastructure Artifacts...\033[0m")
    
    files = [
        "install.sh",
        "docker-compose.yml", 
        "pyproject.toml",
        "README.md",
        "GRANT_APPLICATION.md",
        "src/web/landing/index.html"
    ]
    
    all_exist = True
    for f in files:
        if os.path.exists(f):
            print(f"   [FILE] {f}: \033[1;32mFOUND\033[0m")
        else:
            print(f"   [FILE] {f}: \033[1;31mMISSING\033[0m")
            all_exist = False
            
    return all_exist

if __name__ == "__main__":
    print_banner()
    
    pqc_status = check_pqc()
    mapek_status = check_mape_k()
    infra_status = check_infra()
    
    print("\n" + "="*60)
    if pqc_status and mapek_status and infra_status:
        print("   \033[1;32mPROOF OF WORK: VALIDATED\033[0m")
        print("   Local verification checks passed.")
    else:
        print("   \033[1;31mPROOF OF WORK: COMPROMISED\033[0m")
        print("   Check logs for details.")
    print("="*60 + "\n")
