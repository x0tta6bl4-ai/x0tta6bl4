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

# Lightweight stdlib/HTTP imports used across the node.
import aiohttp

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

active_peers_count = Gauge(
    "active_peers_count",
    "Number of currently valid/active peers known to this node",
    ["node_id"],
)


class PeerRegistry:
    """Lightweight HTTP-based peer registry for service discovery."""

    def __init__(self, node_id: str, peers: list[str], peer_ports: list[str], port: int) -> None:
        self.node_id = node_id
        self._peers = [p for p in peers if p]
        self._peer_ports = [p for p in peer_ports if p]
        self.port = port
        self._entries: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self.announcement_interval = int(os.environ.get("PEER_ANNOUNCE_INTERVAL_SEC", "20"))
        self.max_missed_announcements = int(os.environ.get("PEER_MAX_MISSED_ANNOUNCE", "3"))

        for idx, peer in enumerate(self._peers):
            target_port = self._peer_ports[idx] if idx < len(self._peer_ports) else str(self.port)
            self._entries[peer] = {
                "peer_id": peer,
                "address": f"{peer}:{target_port}",
                "status": "unknown",
                "last_seen": None,
                "missed_announcements": 0,
            }

    @property
    def entries(self) -> dict[str, dict]:
        return {peer: dict(info) for peer, info in self._entries.items()}

    def _resolve_target(self, peer: str) -> str:
        for idx, known in enumerate(self._peers):
            if known == peer and idx < len(self._peer_ports):
                return f"{peer}:{self._peer_ports[idx]}"
        return f"{peer}:{self.port}"

    def _current_announce_payload(self) -> dict:
        return {
            "node_id": self.node_id,
            "port": self.port,
            "status": "online",
            "ts": time.time(),
        }

    async def refresh_peer_addresses(self) -> None:
        for peer in self._peers:
            address = _resolve_peer_address(peer)
            if address is None:
                continue
            entry = self._entries.get(peer)
            if entry is None:
                continue
            entry["address"] = f"{address}:{self._resolve_target(peer).split(':')[-1]}"

    async def record_announcement(self, peer: str, payload: dict) -> None:
        async with self._lock:
            entry = self._entries.get(peer)
            if entry is None:
                entry = {
                    "peer_id": peer,
                    "address": payload.get("address", f"{peer}:{self.port}"),
                    "status": "active",
                    "last_seen": time.time(),
                    "missed_announcements": 0,
                }
                self._entries[peer] = entry
            entry["last_seen"] = time.time()
            entry["missed_announcements"] = 0
            entry["status"] = "active"
            entry["address"] = payload.get("address", entry["address"])

    async def mark_missed(self, peer: str) -> None:
        async with self._lock:
            entry = self._entries.get(peer)
            if entry is None:
                return
            entry["missed_announcements"] = int(entry.get("missed_announcements", 0)) + 1
            if entry["missed_announcements"] >= self.max_missed_announcements:
                entry["status"] = "invalid"
                logger.warning(
                    "Peer %s marked invalid after %d missed announcements",
                    peer,
                    entry["missed_announcements"],
                )
            else:
                entry["status"] = "stale"

    async def sync_stale_peers(self) -> None:
        now = time.time()
        max_idle = self.announcement_interval * self.max_missed_announcements
        async with self._lock:
            for peer, entry in list(self._entries.items()):
                last_seen = entry.get("last_seen")
                if last_seen is None:
                    entry["missed_announcements"] = int(entry.get("missed_announcements", 0)) + 1
                elif (now - float(last_seen)) > max_idle:
                    entry["missed_announcements"] = int(entry.get("missed_announcements", 0)) + 1
                else:
                    continue

                if entry["missed_announcements"] >= self.max_missed_announcements:
                    entry["status"] = "invalid"
                elif entry["missed_announcements"] > 0:
                    entry["status"] = "stale"

    async def announce_to_peers(self, http_session: aiohttp.ClientSession) -> None:
        payload = self._current_announce_payload()
        for peer in self._peers:
            target = self._resolve_target(peer)
            try:
                async with http_session.post(
                    f"http://{target}/peers/announce",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        await self.record_announcement(peer, payload)
            except Exception as exc:
                logger.debug("Announce to %s failed: %s", target, exc)
                await self.mark_missed(peer)

    async def run_announcements(self) -> None:
        await asyncio.sleep(2)
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    while True:
                        await self.announce_to_peers(session)
                        await self.sync_stale_peers()
                        await asyncio.sleep(self.announcement_interval)
            except Exception as exc:
                logger.warning("Announcement loop restarted: %s", exc)
                await asyncio.sleep(self.announcement_interval)

    def active_count(self) -> int:
        return sum(1 for info in self._entries.values() if info.get("status") == "active")

    def update_prometheus(self) -> None:
        active_peers_count.labels(node_id=self.node_id).set(self.active_count())


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
        self.peer_registry = PeerRegistry(
            node_id=NODE_ID,
            peers=list(self.peers),
            peer_ports=PEER_PORTS,
            port=PORT,
        )
        self._pqc_discovery_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._pqc_handshakes_by_peer: dict[str, int] = {}
        self._route_discovery_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._mapek_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._peer_announce_task: asyncio.Task | None = None  # type: ignore[type-arg]

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

        async def handle_peers(request):
            self.peer_registry.update_prometheus()
            return aiohttp.web.json_response(self.peer_registry.entries)

        async def handle_peers_announce(request):
            try:
                payload = await request.json()
                peer_id = payload.get("node_id", request.remote or "unknown")
                await self.peer_registry.record_announcement(peer_id, payload)
                return aiohttp.web.json_response({"status": "accepted"})
            except Exception as exc:
                logger.error("peers announce handler error: %s", exc)
                return aiohttp.web.json_response(
                    {"status": "error", "reason": str(exc)}, status=400
                )

        app = aiohttp.web.Application()
        app.router.add_get("/health", health)
        app.router.add_post("/consensus", handle_consensus)
        app.router.add_get("/routing", handle_routing)
        app.router.add_get("/routes", handle_routes)
        app.router.add_post("/message", handle_message)
        app.router.add_get("/peers", handle_peers)
        app.router.add_post("/peers/announce", handle_peers_announce)
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

    async def run_peer_registry(self) -> None:
        await asyncio.sleep(3)
        await self.peer_registry.refresh_peer_addresses()
        self._peer_announce_task = asyncio.create_task(self.peer_registry.run_announcements())
        try:
            while True:
                await asyncio.sleep(10)
                await self.peer_registry.sync_stale_peers()
                self.peer_registry.update_prometheus()
        finally:
            if self._peer_announce_task and not self._peer_announce_task.done():
                self._peer_announce_task.cancel()

    async def run(self):
        # Initialize Vault if env vars are present
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if vault_addr and vault_token:
            try:
                from src.security.vault_client import VaultClient
                from src.security.vault_secrets import VaultSecretManager, ApiCredentials
                
                logger.info("Initializing Vault client and writing node secrets...")
                client = VaultClient(vault_addr=vault_addr, vault_token=vault_token)
                await client.connect()
                secrets_mgr = VaultSecretManager(client)
                cred = ApiCredentials(api_key=f"key-for-{NODE_ID}", api_secret=f"secret-for-{NODE_ID}")
                await secrets_mgr.store_api_credentials(f"node-{NODE_ID}", cred)
                logger.info("Node secrets successfully stored in Vault!")
                # Verify retrieval
                retrieved = await secrets_mgr.get_api_credentials(f"node-{NODE_ID}")
                logger.info("Verified Vault secret retrieval: api_key=%s", retrieved.api_key)
                await client.close()
            except Exception as e:
                logger.error("Failed to initialize Vault configuration: %s", e)

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
            self._peer_registry_task = asyncio.create_task(self.run_peer_registry())
            tasks.append(self._peer_registry_task)

        self._mapek_task = asyncio.create_task(self.run_mape_k())
        tasks.append(self._mapek_task)

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(MeshNode().run())
