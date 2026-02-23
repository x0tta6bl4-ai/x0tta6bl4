
import asyncio
import logging
from src.core.mape_k_loop import MAPEKLoop
from src.core.consciousness import ConsciousnessEngine
from src.mesh.network_manager import MeshNetworkManager
from src.monitoring.prometheus_client import PrometheusExporter
from src.security.zero_trust import ZeroTrustValidator

async def test_single_cycle():
    logging.basicConfig(level=logging.INFO)
    
    # Init components
    consciousness = ConsciousnessEngine(enable_advanced_metrics=False)
    mesh = MeshNetworkManager(node_id="chaos-test-manager")
    prometheus = PrometheusExporter()
    zero_trust = ZeroTrustValidator()
    
    loop = MAPEKLoop(consciousness, mesh, prometheus, zero_trust)
    
    print("--- STARTING SINGLE MAPE-K CYCLE ---")
    await loop._execute_cycle()
    print("--- CYCLE COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_single_cycle())
