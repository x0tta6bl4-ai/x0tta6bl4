
import sys
import os

sys.path.append(os.getcwd())

print(f"Python path: {sys.path}")

try:
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway
    print("Use EBPFPQCGateway success")
except ImportError as e:
    print(f"Failed to import EBPFPQCGateway: {e}")

try:
    from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
    print("Use PQCXDPLoader success")
except ImportError as e:
    print(f"Failed to import PQCXDPLoader: {e}")

try:
    from src.self_healing.pqc_zero_trust_healer import PQCZeroTrustHealer
    print("Use PQCZeroTrustHealer success")
except ImportError as e:
    print(f"Failed to import PQCZeroTrustHealer: {e}")
