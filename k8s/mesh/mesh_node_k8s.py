#!/usr/bin/env python3
"""
Minimal mesh node for Kubernetes — x0tta6bl4
Runs without src/ dependency using mocks.
"""
import asyncio
import json
import logging
import os
import sys
import time
import hashlib
import types

# Mock heavy deps
for mod in ["kubernetes", "flwr", "eth_account", "web3", "sentence_transformers", "oqs", "liboqs"]:
    sys.modules[mod] = types.ModuleType(mod)

logger = logging.getLogger("mesh-node")
NODE_ID = os.environ.get("NODE_ID", "k8s-1")
PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
PEER_IDS = [p for p in os.environ.get("PEER_IDS", "").split(",") if p]
PORT = int(os.environ.get("PORT", "9100"))
PEER_PORTS = os.environ.get("PEER_PORTS", "").split(",")
SVD_BYPASS = os.environ.get("SVD_BYPASS", "").lower() in ("1", "true", "yes")
_SVID_KEY = hashlib.sha256(NODE_ID.encode()).digest()


class MeshNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.peers = set(PEERS)
        self.f = min(1, max(0, len(self.peers) // 3))
        self.start_time = time.time()
        self.consensus_count = 0

    async def send_consensus_http(self, session_id, evidence, target_peer):
        import aiohttp
        sorted_peers = sorted(list(self.peers))
        peer_idx = sorted_peers.index(target_peer)
        target_port = PEER_PORTS[peer_idx]
        payload = {
            "type": "anomaly_consensus",
            "session_id": session_id,
            "anomaly_type": evidence.get("type", "unknown"),
            "severity": evidence.get("severity", "low"),
            "failure_rate": evidence.get("failure_rate", 0.0),
            "total_packets": evidence.get("total_packets", 0),
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{target_peer}:{target_port}/consensus",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"approved": False, "reason": f"HTTP {resp.status}"}
        except Exception as exc:
            return {"approved": False, "reason": str(exc)}

    async def run_http_server(self):
        import aiohttp.web

        async def health(request):
            return aiohttp.web.json_response({
                "node_id": self.node_id,
                "status": "ok",
                "uptime": int(time.time() - self.start_time),
                "peers": sorted(self.peers),
                "consensus_count": self.consensus_count,
                "k8s": True,
            })

        async def handle_consensus(request):
            try:
                data = await request.json()
                return aiohttp.web.json_response({
                    "approved": True,
                    "reason": "k8s-mesh",
                    "node": self.node_id,
                })
            except Exception as exc:
                return aiohttp.web.json_response(
                    {"approved": False, "reason": str(exc)}, status=500
                )

        app = aiohttp.web.Application()
        app.router.add_get("/health", health)
        app.router.add_post("/consensus", handle_consensus)
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info("HTTP on :%d", PORT)
        while True:
            await asyncio.sleep(3600)

    async def run_heartbeat(self):
        await asyncio.sleep(5)
        while True:
            self.consensus_count += 1
            evidence = {
                "type": "routine_check",
                "severity": "low",
                "failure_rate": 0.0,
                "total_packets": 10,
            }
            if self.peers:
                for peer in self.peers:
                    result = await self.send_consensus_http(
                        f"hb-{self.consensus_count}", evidence, peer
                    )
                    logger.info("Peer %s verdict: %s", peer, result)
            else:
                logger.info("HB #%d: auto-approve (single node)", self.consensus_count)
            await asyncio.sleep(30)

    async def run(self):
        logger.info("Starting K8s mesh node %s", NODE_ID)
        await asyncio.gather(self.run_http_server(), self.run_heartbeat())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(MeshNode().run())
