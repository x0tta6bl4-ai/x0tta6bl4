
try:
    import oqs
    print("oqs imported successfully")
    print(f"Enabled KEMs: {oqs.get_enabled_kem_mechanisms()}")
    print(f"Enabled Sigs: {oqs.get_enabled_sig_mechanisms()}")
except ImportError as e:
    print(f"Failed to import oqs: {e}")

try:
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway
    print("EBPFPQCGateway imported successfully")
except ImportError as e:
    print(f"Failed to import EBPFPQCGateway: {e}")
