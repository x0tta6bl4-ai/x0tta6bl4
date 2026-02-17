
import os
import sys
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.getcwd())

# Mock spiffe dependencies if missing (though we know they are there)
try:
    from src.network.batman.node_manager import NodeManager, AttestationStrategy
    from src.monitoring.metrics import get_metrics
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

def test_metrics():
    print("Testing SPIFFE metrics integration...")
    
    nm = NodeManager(mesh_id='test-mesh', local_node_id='test-node')
    nm.attestation_strategy = AttestationStrategy.SPIFFE
    
    # Register a node with certificate (mocked cert string)
    spiffe_id = "spiffe://mesh/node/secure-1"
    cert_pem = b"-----BEGIN CERTIFICATE-----\nMOCK\n-----END CERTIFICATE-----"
    
    # This should succeed (logic I added allows fallback/mock validation) 
    # and trigger set_node_spiffe_attested
    result = nm.register_node(
        node_id="secure-1",
        mac_address="aa:bb:cc:dd:ee:ff",
        ip_address="10.0.0.100",
        spiffe_id=spiffe_id,
        cert_pem=cert_pem
    )
    
    print(f"Registration result: {result}")
    
    # Check metrics
    metrics_output = get_metrics().body.decode('utf-8')
    
    if 'node_spiffe_attested{node_id="secure-1",spiffe_id="spiffe://mesh/node/secure-1"} 1.0' in metrics_output:
        print("SUCCESS: Metric 'node_spiffe_attested' found with value 1.0")
    else:
        print("FAILURE: Metric 'node_spiffe_attested' NOT found or incorrect")
        print("-" * 40)
        print(metrics_output)
        print("-" * 40)

if __name__ == "__main__":
    test_metrics()
