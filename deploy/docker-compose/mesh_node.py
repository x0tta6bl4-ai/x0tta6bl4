#!/usr/bin/env python3
"""
Mesh node for Docker Compose — x0tta6bl4 local mesh demo.

Runs with auto_approve=False and two peers, demonstrating
SVID-signed PBFT consensus messages over HTTP.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Path setup
CODE_DIR = Path("/code")
if CODE_DIR.exists():
    sys.path.insert(0, str(CODE_DIR))
else:
    CODE_DIR = Path(os.environ.get("PYTHONPATH", "/mnt/projects/src"))
    sys.path.insert(0, str(CODE_DIR.parent) if str(CODE_DIR).endswith("/src") else str(CODE_DIR))

# Mock oqs AND other heavy deps that the import chain pulls in
import types

_HEAVY_MOCKS = {
    "kubernetes": types.ModuleType("kubernetes"),
    "flwr": types.ModuleType("flwr"),
    "eth_account": types.ModuleType("eth_account"),
    "web3": types.ModuleType("web3"),
    "sentence_transformers": types.ModuleType("sentence_transformers"),
}
for mod_name, mod in _HEAVY_MOCKS.items():
    sys.modules[mod_name] = mod

# Mock oqs (liboqs-python mismatch with oqs 0.15)
_mock_oqs = types.ModuleType("oqs")
_mock_oqs.Signature = lambda alg, sek=None: types.SimpleNamespace(
    generate_keypair=lambda: b"pub" + bytes(32),
    export_secret_key=lambda: b"sec" + bytes(32),
    sign=lambda d: b"sig" + bytes(64),
    verify=lambda d, s, p: True,
)()
_mock_oqs.KeyEncapsulation = lambda alg: types.SimpleNamespace(
    generate_keypair=lambda: b"pub" + bytes(32),
    export_secret_key=lambda: b"sec" + bytes(32),
    encap_secret=lambda p: (b"ct" + bytes(32), b"ss" + bytes(32)),
    decap_secret=lambda ct: b"ss" + bytes(32),
)()
sys.modules["oqs"] = _mock_oqs
sys.modules["liboqs"] = _mock_oqs

import hashlib

from src.self_healing.anomaly_consensus import AnomalyConsensusManager
from src.self_healing.svid_signer import SVIDSigner

logger = logging.getLogger("mesh-node")

NODE_ID = os.environ.get("NODE_ID", "node-a")
PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
PORT = int(os.environ.get("PORT", "9100"))
PEER_PORTS = os.environ.get("PEER_PORTS", "").split(",")

# SVID key — deterministic per node for dev
_SVID_KEY = hashlib.sha256(NODE_ID.encode()).digest()


class MeshNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.peers = set(PEERS)
        self.f = min(1, max(0, len(self.peers) // 3))
        self.start_time = time.time()
        self.consensus_count = 0

        self.svid_signer = SVIDSigner(
            spiffe_id=f"spiffe://x0tta6bl4.mesh/workload/{NODE_ID}",
            mode="dev",
        )
        self.svid_signer.set_signing_key(_SVID_KEY)

        # Register peers
        for peer in self.peers:
            peer_key = hashlib.sha256(peer.encode()).digest()
            self.svid_signer.register_peer(
                f"spiffe://x0tta6bl4.mesh/workload/{peer}",
                verification_key=peer_key,
            )

        self.consensus = AnomalyConsensusManager(
            node_id=NODE_ID,
            peers=self.peers,
            f=self.f,
            consensus_timeout=5.0,
            auto_approve=not bool(self.peers),
            svid_signer=self.svid_signer,
        )

        logger.info(
            "Node %s: peers=%s f=%d auto_approve=%s port=%d",
            NODE_ID, sorted(self.peers), self.f, self.consensus.auto_approve, PORT,
        )

    async def send_consensus_http(self, session_id: str, evidence: dict, target_peer: str) -> dict:
        """Send consensus request to a peer via HTTP."""
        import aiohttp

        # Map peer name to port (use sorted order to match PEER_PORTS)
        peer_idx = sorted(list(self.peers)).index(target_peer)
        target_port = PEER_PORTS[peer_idx]

        payload = {
            "type": "anomaly_consensus",
            "session_id": session_id,
            "anomaly_type": evidence.get("type", "unknown"),
            "severity": evidence.get("severity", "low"),
            "failure_rate": evidence.get("failure_rate", 0.0),
            "total_packets": evidence.get("total_packets", 0),
        }

        # Sign with SVID
        signed = self.svid_signer.sign_payload(payload)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{target_peer}:{target_port}/consensus",
                    json=signed,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"approved": False, "reason": f"HTTP {resp.status}"}
        except Exception as exc:
            logger.warning("Peer %s unreachable: %s", target_peer, exc)
            return {"approved": False, "reason": str(exc)}

    async def run_http_server(self):
        """HTTP server with health + consensus endpoint."""
        import aiohttp.web

        async def health(request):
            return aiohttp.web.json_response({
                "node_id": self.node_id,
                "status": "ok",
                "uptime": int(time.time() - self.start_time),
                "peers": sorted(self.peers),
                "consensus_count": self.consensus_count,
            })

        async def handle_consensus(request):
            """Receive consensus request from peer, signed with SVID."""
            try:
                data = await request.json()
                # Verify SVID signature
                if not self.svid_signer.verify_payload(data):
                    return aiohttp.web.json_response(
                        {"approved": False, "reason": "invalid SVID signature"},
                        status=403,
                    )

                # Evaluate locally
                result = self.consensus._evaluate_anomaly(data)
                return aiohttp.web.json_response(result)
            except Exception as exc:
                logger.error("consensus handler error: %s", exc)
                return aiohttp.web.json_response(
                    {"approved": False, "reason": str(exc)},
                    status=500,
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
        """Periodic consensus round."""
        await asyncio.sleep(5)  # Let HTTP server start
        while True:
            self.consensus_count += 1
            evidence = {
                "type": "routine_check",
                "severity": "low",
                "failure_rate": 0.0,
                "total_packets": 10,
            }

            if self.peers:
                # Multi-node: broadcast to all peers
                for peer in self.peers:
                    peer_result = await self.send_consensus_http(
                        f"hb-{self.consensus_count}", evidence, peer
                    )
                    logger.info("Peer %s verdict: %s", peer, peer_result)
            else:
                # Single node: auto-approve
                verdict = await self.consensus.request_consensus(
                    session_id=f"hb-{self.consensus_count}",
                    anomaly_type="routine_check",
                    severity="low",
                    evidence=evidence,
                )
                logger.info("HB #%d: %s (%.0fms)", self.consensus_count,
                            "approve" if verdict.approved else "skip",
                            verdict.duration_ms)

            await asyncio.sleep(30)

    async def run(self):
        logger.info("Starting mesh node %s", NODE_ID)
        await asyncio.gather(self.run_http_server(), self.run_heartbeat())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(MeshNode().run())
