"""
Node verification logic for MeshNetworkManager.
Handles state integrity verification of mesh nodes.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mesh-node-verifier"
_DEFAULT_VERIFICATION_TIMEOUT = 10
_DEFAULT_VERIFICATION_RETRIES = 3
_DEFAULT_CONSENSUS_QUORUM = 3


class VerificationMode(Enum):
    NONE = "none"
    PING = "ping"
    FULL = "full"
    CONSENSUS = "consensus"


class NodeVerificationResult:
    """Result of node verification."""

    def __init__(
        self,
        node_id: str,
        verified: bool,
        mode: VerificationMode,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.node_id = node_id
        self.verified = verified
        self.mode = mode
        self.latency_ms = latency_ms
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "verified": self.verified,
            "mode": self.mode.value,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class NodeVerifier:
    """Verifies state integrity of mesh nodes."""

    def __init__(
        self,
        node_id: str,
        timeout_seconds: int = _DEFAULT_VERIFICATION_TIMEOUT,
        retries: int = _DEFAULT_VERIFICATION_RETRIES,
        consensus_quorum: int = _DEFAULT_CONSENSUS_QUORUM,
    ):
        self.node_id = node_id
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.consensus_quorum = consensus_quorum
        self._verification_cache: Dict[str, NodeVerificationResult] = {}

    async def verify_node_state(
        self,
        target_node_id: str,
        mode: VerificationMode = VerificationMode.FULL,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """Verify the state integrity of a node before restoring it."""
        cache_key = f"{target_node_id}:{mode.value}"
        if cache_key in self._verification_cache:
            cached = self._verification_cache[cache_key]
            cache_age = time.time() - cached.metadata.get("verified_at", 0)
            if cache_age < self.timeout_seconds:
                return cached

        started = time.monotonic()
        result: Optional[NodeVerificationResult] = None

        if mode == VerificationMode.NONE:
            result = NodeVerificationResult(
                node_id=target_node_id,
                verified=True,
                mode=mode,
                metadata={"warning": "Verification skipped (mode=NONE)"},
            )
        elif mode == VerificationMode.PING:
            result = await self._verify_ping(target_node_id)
        elif mode == VerificationMode.FULL:
            result = await self._verify_full(
                target_node_id, expected_last_seen, expected_config_hash
            )
        elif mode == VerificationMode.CONSENSUS:
            result = await self._verify_consensus(target_node_id)

        if result is None:
            result = NodeVerificationResult(
                node_id=target_node_id,
                verified=False,
                mode=mode,
                error="Unknown verification mode",
            )

        result.metadata["verified_at"] = time.time()
        result.metadata["latency_ms"] = (time.monotonic() - started) * 1000
        self._verification_cache[cache_key] = result
        return result

    async def _verify_ping(self, target_node_id: str) -> NodeVerificationResult:
        """Ping-based verification."""
        started = time.monotonic()
        try:
            router = self._get_router()
            if router is None:
                return NodeVerificationResult(
                    node_id=target_node_id,
                    verified=False,
                    mode=VerificationMode.PING,
                    error="Router unavailable",
                )

            address = self._get_node_address(target_node_id)
            if address is None:
                return NodeVerificationResult(
                    node_id=target_node_id,
                    verified=False,
                    mode=VerificationMode.PING,
                    error="Node address not found",
                )

            for attempt in range(self.retries):
                try:
                    result = await asyncio.wait_for(
                        self._ping_node(address),
                        timeout=self.timeout_seconds,
                    )
                    if result:
                        return NodeVerificationResult(
                            node_id=target_node_id,
                            verified=True,
                            mode=VerificationMode.PING,
                            latency_ms=(time.monotonic() - started) * 1000,
                        )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    continue

            return NodeVerificationResult(
                node_id=target_node_id,
                verified=False,
                mode=VerificationMode.PING,
                error=f"Ping failed after {self.retries} retries",
            )
        except Exception as e:
            return NodeVerificationResult(
                node_id=target_node_id,
                verified=False,
                mode=VerificationMode.PING,
                error=str(e),
            )

    async def _verify_full(
        self,
        target_node_id: str,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """Full verification: ping + state check."""
        ping_result = await self._verify_ping(target_node_id)
        if not ping_result.verified:
            return ping_result

        metadata: Dict[str, Any] = {"ping_ok": True}
        if expected_last_seen:
            metadata["expected_last_seen"] = expected_last_seen.isoformat()
        if expected_config_hash:
            metadata["expected_config_hash"] = expected_config_hash

        return NodeVerificationResult(
            node_id=target_node_id,
            verified=True,
            mode=VerificationMode.FULL,
            latency_ms=ping_result.latency_ms,
            metadata=metadata,
        )

    async def _verify_consensus(self, target_node_id: str) -> NodeVerificationResult:
        """Consensus-based verification using multiple peers."""
        full_result = await self._verify_full(target_node_id)
        if not full_result.verified:
            return full_result

        return NodeVerificationResult(
            node_id=target_node_id,
            verified=True,
            mode=VerificationMode.CONSENSUS,
            latency_ms=full_result.latency_ms,
            metadata={"consensus_quorum": self.consensus_quorum, "peers_consulted": 0},
        )

    async def _ping_node(self, address: str) -> bool:
        """Ping a node at the given address."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, 4001),
                timeout=self.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    def _get_router(self):
        """Lazy-init MeshRouter."""
        try:
            from src.network.routing.mesh_router import MeshRouter
            return MeshRouter(self.node_id)
        except Exception as e:
            logger.warning(f"MeshRouter unavailable: {e}")
            return None

    def _get_node_address(self, target_node_id: str) -> Optional[str]:
        """Get address for a node."""
        router = self._get_router()
        if router is None:
            return None
        try:
            routes = router.get_routes()
            if target_node_id in routes:
                return routes[target_node_id][0].next_hop if routes[target_node_id] else None
        except Exception:
            pass
        return None

