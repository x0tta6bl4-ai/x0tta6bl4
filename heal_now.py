
import asyncio
import logging
from unittest.mock import patch
from src.core.mape_k_loop import MAPEKLoop
from src.core.consciousness import ConsciousnessEngine
from src.mesh.network_manager import MeshNetworkManager
from src.monitoring.prometheus_client import PrometheusExporter
from src.security.zero_trust import ZeroTrustValidator

async def force_heal():
    logging.basicConfig(level=logging.INFO)
    
    # MOCK TORCH TO SKIP 3-MINUTE HANG
    with patch("src.ml.graphsage_anomaly_detector.is_torch_available", return_value=False):
        print("🚀 Starting FAST MAPE-K cycle (ML disabled)...")
        
        consciousness = ConsciousnessEngine(enable_advanced_metrics=False)
        mesh = MeshNetworkManager(node_id="chaos-test-manager")
        prometheus = PrometheusExporter()
        zero_trust = ZeroTrustValidator()
        
        loop = MAPEKLoop(consciousness, mesh, prometheus, zero_trust)
        
        # 1. First, we need to ensure the node is seen as offline by the monitor
        print("🔍 Scanning for offline nodes...")
        await loop._execute_cycle()
        
        print("✅ Cycle complete.")

if __name__ == "__main__":
    asyncio.run(force_heal())
