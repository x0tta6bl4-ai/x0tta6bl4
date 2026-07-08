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
import socket

from prometheus_client import Counter, Gauge, start_http_server

from src.self_healing.anomaly_consensus import AnomalyConsensusManager
from src.self_healing.svid_signer import SVIDSigner

logger = logging.getLogger("mesh-node")

NODE_ID = os.environ.get("NODE_ID", "node-a")
PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
PEER_IDS = [p for p in os.environ.get("PEER_IDS", "").split(",") if p]
PORT = int(os.environ.get("PORT", "9100"))
MESH_METRICS_PORT = int(os.environ.get("MESH_METRICS_PORT", "9190"))
PEER_PORTS = os.environ.get("PEER_PORTS", "").split(",")

pqc_handshakes_total = Counter(
    "pqc_handshakes_total",
    "Total PQC handshakes completed",
    ["node_id", "peer"],
)

mapek_recovery_actions_total = Counter(
    "mapek_recovery_actions_total",
    "Total MAPE-K recovery actions taken",
    ["node_id", "peer"],
)

mesh_routing_table_size = Gauge(
    "mesh_routing_table_size",
    "Current number of entries in the mesh routing table",
    ["node_id"],
)

mesh_forwarded_messages_total = Counter(
    "mesh_forwarded_messages_total",
    "Total messages forwarded by this node",
    ["node_id", "destination"],
)

mesh_route_refresh_total = Gauge(
    "mesh_route_refresh_total",
    "Total route discovery refreshes performed for this node",
    ["node_id"],
)


class PQC_Handshake:
    """Application-level mock PQC handshake using stdlib hashing only."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._secret = hashlib.sha256(node_id.encode()).digest()

    def encapsulate(self, peer: str) -> dict:
        shared_secret = hashlib.sha256(self._secret + peer.encode()).digest()
        ciphertext = hashlib.sha256(shared_secret + b"encap").digest()[:32]
        signature = hashlib.sha256(self._secret + ciphertext).digest()[:64]
        return {
            "peer": peer,
            "ciphertext": ciphertext.hex(),
            "signature": signature.hex(),
            "algorithm": "mock-aes-kem",
        }

    def decapsulate(self, peer: str, ciphertext_hex: str) -> bytes:
        shared_secret = hashlib.sha256(self._secret + peer.encode()).digest()
        expected = hashlib.sha256(shared_secret + b"encap").digest()[:32]
        return expected if bytes.fromhex(ciphertext_hex) == expected else b""

    def verify_signature(self, peer: str, message: bytes, signature_hex: str) -> bool:
        expected = hashlib.sha256(self._secret + message).digest()[:64]
        return bytes.fromhex(signature_hex) == expected


class MeshRoutingTable:
    def __init__(self, node_id: str, peers: set[str]) -> None:
        self.node_id = node_id
        self._entries: dict[str, dict] = {}
        self._peers = list(peers)
        for peer in self._peers:
            address = _resolve_peer_address(peer)
            self._entries[peer] = {
                "peer_id": peer,
                "address": address or peer,
                "status": "resolved" if address else "unresolved",
                "last_updated": time.time(),
            }
        mesh_routing_table_size.labels(node_id=self.node_id).set(len(self._entries))

    @property
    def entries(self) -> dict[str, dict]:
        return dict(self._entries)

    def get_next_hop(self, destination: str) -> str | None:
        if destination == self.node_id:
            return None
        info = self._entries.get(destination)
        if info:
            return info["address"]
        return None

    def update_peer_address(self, peer: str, address: str | None) -> bool:
        """Refresh peer address and update routing entry if it changed."""
        if peer not in self._entries:
            return False
        info = self._entries[peer]
        resolved = address or peer
        changed = info["address"] != resolved
        info["address"] = resolved
        info["status"] = "resolved" if address else "unresolved"
        info["last_updated"] = time.time()
        return changed

    def as_json(self) -> dict:
        return {
            "node_id": self.node_id,
            "entries": [
                {
                    "peer_id": info["peer_id"],
                    "address": info["address"],
                    "status": info["status"],
                    "last_updated": info["last_updated"],
                }
                for info in self._entries.values()
            ],
        }


def _resolve_peer_address(peer: str) -> str | None:
    """Resolve peer hostname within the internal Docker network."""
    try:
        return socket.gethostbyname(peer)
    except socket.gaierror:
        return None

# SVID key — deterministic per node for dev
_SVID_KEY = hashlib.sha256(NODE_ID.encode()).digest()
SVD_BYPASS = os.environ.get("SVD_BYPASS", "").lower() in ("1", "true", "yes")


class MeshNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.peers = set(PEERS)
        self.f = min(1, max(0, len(self.peers) // 3))
        self.start_time = time.time()
        self.consensus_count = 0
        self.health_score = Gauge(
            "mesh_health_score", "Mesh node health score baseline", ["node_id"]
        )
        self.health_score.labels(node_id=self.node_id).set(20.0)
        self._last_health_score = 20.0

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

        self.pqc = PQC_Handshake(NODE_ID)
        self.routing_table = MeshRoutingTable(self.node_id, self.peers)
        self._pqc_discovery_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._pqc_handshakes_by_peer: dict[str, int] = {}
        self._route_discovery_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._mapek_task: asyncio.Task | None = None  # type: ignore[type-arg]

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

    async def forward_message(self, destination: str, payload: dict) -> dict:
        next_hop = self.routing_table.get_next_hop(destination)
        if not next_hop:
            return {"status": "error", "reason": f"No route to {destination}"}

        mesh_forwarded_messages_total.labels(node_id=self.node_id, destination=destination).inc()

        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{next_hop}:{PORT}/message",
                    json={"destination": destination, "payload": payload},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"status": "error", "reason": f"HTTP {resp.status}"}
        except Exception as exc:
            logger.warning("Forward to %s failed: %s", next_hop, exc)
            return {"status": "error", "reason": str(exc)}

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
                    if SVD_BYPASS:
                        logger.warning("SVID verification failed (bypass=ON)")
                    else:
                        logger.warning("SVID verification BLOCKED")
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

        async def handle_routing(request):
            return aiohttp.web.json_response(self.routing_table.as_json())

        async def handle_routes(request):
            return aiohttp.web.json_response(self.routing_table.as_json())

        async def handle_message(request):
            try:
                data = await request.json()
                destination = data.get("destination", "")
                payload = data.get("payload", {})
                if not destination:
                    return aiohttp.web.json_response(
                        {"status": "error", "reason": "missing destination"}, status=400
                    )
                if destination == self.node_id:
                    return aiohttp.web.json_response(
                        {"status": "delivered", "destination": destination, "payload": payload}
                    )
                result = await self.forward_message(destination, payload)
                return aiohttp.web.json_response(result)
            except Exception as exc:
                logger.error("message handler error: %s", exc)
                return aiohttp.web.json_response(
                    {"status": "error", "reason": str(exc)}, status=500
                )

        app = aiohttp.web.Application()
        app.router.add_get("/health", health)
        app.router.add_post("/consensus", handle_consensus)
        app.router.add_get("/routing", handle_routing)
        app.router.add_get("/routes", handle_routes)
        app.router.add_post("/message", handle_message)
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
                self._last_health_score = float(self.health_score.labels(node_id=self.node_id)._value.get())
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

                self._last_health_score = float(self.health_score.labels(node_id=self.node_id)._value.get())

            await asyncio.sleep(30)

    async def run_pqc_discovery(self) -> None:
        """Resolve peers and establish mock PQC handshakes."""
        await asyncio.sleep(2)
        while True:
            for peer in sorted(self.peers):
                peer_address = _resolve_peer_address(peer)
                if peer_address is None:
                    logger.info("Peer %s unresolved", peer)
                    continue

                handshake = self.pqc.encapsulate(peer)
                decapsulated = self.pqc.decapsulate(peer, handshake["ciphertext"])
                valid = bool(decapsulated) and self.pqc.verify_signature(
                    peer,
                    handshake["ciphertext"].encode(),
                    handshake["signature"],
                )
                if valid:
                    logger.info(
                        "PQC Handshake established with %s",
                        peer,
                        extra={"peer": peer, "node_id": self.node_id},
                    )
                    pqc_handshakes_total.labels(node_id=self.node_id, peer=peer).inc()
                    self._pqc_handshakes_by_peer[peer] = self._pqc_handshakes_by_peer.get(peer, 0) + 1
                else:
                    logger.warning("PQC Handshake failed with %s", peer)

            await asyncio.sleep(60)

    async def run_route_discovery(self) -> None:
        """Periodically refresh peer addresses and update routing table."""
        await asyncio.sleep(5)
        while True:
            for peer in sorted(self.peers):
                address = _resolve_peer_address(peer)
                updated = self.routing_table.update_peer_address(peer, address)
                if updated:
                    mesh_route_refresh_total.labels(node_id=self.node_id).inc()
                    logger.info(
                        "Route refreshed for %s -> %s",
                        peer,
                        address or peer,
                    )
                else:
                    logger.debug("Route unchanged for %s", peer)
            await asyncio.sleep(30)

    async def _apply_mape_k_recovery(self, peer: str | None = None) -> None:
        """Plan & Execute: lightweight consensus heartbeat + score restore."""
        target_peer = peer or (sorted(self.peers)[0] if self.peers else None)
        logger.warning(
            "MAPE-K intervention: restoring mesh_health_score and restarting heartbeat for node=%s peer=%s",
            self.node_id,
            target_peer,
            extra={"node_id": self.node_id, "peer": target_peer},
        )

        self.health_score.labels(node_id=self.node_id).set(20.0)
        mapek_recovery_actions_total.labels(node_id=self.node_id, peer=target_peer or "").inc()

        if target_peer and target_peer in self.peers:
            peer_result = await self.send_consensus_http(
                f"mapek-{self.consensus_count}",
                {
                    "type": "mapek_recovery",
                    "severity": "high",
                    "failure_rate": 1.0,
                    "total_packets": 0,
                },
                target_peer,
            )
            logger.info("MAPE-K peer verdict: %s", peer_result)

        if self._pqc_discovery_task is None or self._pqc_discovery_task.done():
            self._pqc_discovery_task = asyncio.create_task(self.run_pqc_discovery())

    async def run_mape_k(self) -> None:
        """Monitor & Analyze: periodic anomaly detection on health score and PQC handshakes."""
        await asyncio.sleep(10)
        last_total_by_peer: dict[str, int] = dict(self._pqc_handshakes_by_peer)
        while True:
            try:
                health_value = self._last_health_score
            except Exception:
                health_value = 20.0

            anomaly = health_value < 10.0
            if not anomaly and self.peers:
                stale_peers = [
                    peer
                    for peer in self.peers
                    if self._pqc_handshakes_by_peer.get(peer, 0) == last_total_by_peer.get(peer, 0)
                ]
                if stale_peers:
                    logger.warning("Stale PQC handshakes for peers: %s", stale_peers)
                anomaly = bool(stale_peers)

            if anomaly:
                await self._apply_mape_k_recovery()

            last_total_by_peer = dict(self._pqc_handshakes_by_peer)
            await asyncio.sleep(30)

    async def run(self):
        logger.info("Starting mesh node %s", NODE_ID)
        try:
            start_http_server(MESH_METRICS_PORT)
            logger.info("Prometheus metrics on :%d/metrics", MESH_METRICS_PORT)
        except OSError as exc:
            logger.warning("Metrics port %s busy: %s", MESH_METRICS_PORT, exc)

        tasks = [self.run_http_server(), self.run_heartbeat()]
        if self.peers:
            self._pqc_discovery_task = asyncio.create_task(self.run_pqc_discovery())
            tasks.append(self._pqc_discovery_task)
            self._route_discovery_task = asyncio.create_task(self.run_route_discovery())
            tasks.append(self._route_discovery_task)

        self._mapek_task = asyncio.create_task(self.run_mape_k())
        tasks.append(self._mapek_task)

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(MeshNode().run())
