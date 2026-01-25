from typing import Dict
import asyncio

class MeshNetworkManager:
    async def get_statistics(self) -> Dict[str, float]:
        return {
            'active_peers': 5,
            'avg_latency_ms': 85.0,
            'packet_loss_percent': 1.0,
            'mttr_minutes': 3.14
        }

    async def set_route_preference(self, preference: str) -> bool:
        return True

    async def trigger_aggressive_healing(self) -> int:
        return 1

    async def trigger_preemptive_checks(self):
        pass

