"""
Batman-adv Node Manager & Health Monitoring
Lifecycle management and health checks for mesh nodes
"""

import asyncio
import copy
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Security Integration
try:
    from src.security.spiffe.workload.api_client import (X509SVID,
                                                         WorkloadAPIClient)

    SPIFFE_AVAILABLE = True
except ImportError:
    SPIFFE_AVAILABLE = False

# Hybrid TLS (PQC) Integration
try:
    from src.security.pqc.hybrid_tls import (HybridTLSContext, hybrid_encrypt,
                                             hybrid_handshake)

    HYBRID_TLS_AVAILABLE = True
except ImportError:
    HYBRID_TLS_AVAILABLE = False

# Obfuscation Integration
try:
    from src.libx0t.network.obfuscation import ObfuscationTransport, TransportManager

    OBFUSCATION_AVAILABLE = True
except ImportError:
    OBFUSCATION_AVAILABLE = False

# DAO Integration
try:
    from src.dao.governance import GovernanceEngine, VoteType

    DAO_AVAILABLE = True
except ImportError:
    DAO_AVAILABLE = False

# DAO Incident Workflow Integration
try:
    from src.dao.incident_workflow import (Incident, IncidentDAOWorkflow,
                                           IncidentSeverity)

    INCIDENT_WORKFLOW_AVAILABLE = True
except ImportError:
    INCIDENT_WORKFLOW_AVAILABLE = False

# Token Economics Integration
try:
    from src.dao.token import MeshToken, ResourceType

    TOKEN_AVAILABLE = True
except ImportError:
    TOKEN_AVAILABLE = False

# Traffic Shaping Integration
try:
    from src.libx0t.network.obfuscation.traffic_shaping import (TrafficProfile,
                                                            TrafficShaper)

    TRAFFIC_SHAPING_AVAILABLE = True
except ImportError:
    TRAFFIC_SHAPING_AVAILABLE = False

from src.core.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

# Batman-adv Optimizations
try:
    from .optimizations import BatmanAdvConfig, BatmanAdvOptimizations

    BATMAN_OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    BATMAN_OPTIMIZATIONS_AVAILABLE = False
    BatmanAdvOptimizations = None  # type: ignore
    BatmanAdvConfig = None  # type: ignore


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_node_ref(value: object) -> Dict[str, Any]:
    return {"hash": _safe_hash(value), "present": value is not None}


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_metric_band(value: float, warn: float, critical: float) -> str:
    if value < warn:
        return "normal"
    if value < critical:
        return "warning"
    return "critical"


def _address_family(address: str) -> str:
    if ":" in str(address):
        return "ipv6"
    if "." in str(address):
        return "ipv4"
    return "unknown"


class AttestationStrategy(Enum):
    """Node attestation strategies"""

    SELF_SIGNED = "self_signed"
    SPIFFE = "spiffe"
    TOKEN_BASED = "token_based"
    CHALLENGE_RESPONSE = "challenge_response"


@dataclass
class NodeMetrics:
    """Node health metrics"""

    cpu_percent: float
    memory_percent: float
    network_sent_bytes: int
    network_recv_bytes: int
    packet_loss_percent: float
    latency_to_gateway_ms: float
    timestamp: datetime = None

    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy node"""
        return (
            self.cpu_percent < 90
            and self.memory_percent < 85
            and self.packet_loss_percent < 5
            and self.latency_to_gateway_ms < 500
        )


class NodeManager:
    """
    Batman-adv Node Manager

    Responsibilities:
    - Node lifecycle (join, leave, bootstrap)
    - Attestation (verify node identity via SPIFFE/tokens)
    - Registration & discovery
    - Heartbeat monitoring
    """

    def __init__(
        self,
        mesh_id: str,
        local_node_id: str,
        obfuscation_transport: Optional["ObfuscationTransport"] = None,
        traffic_profile: str = "none",
        enable_optimizations: bool = True,
    ):
        self.mesh_id = mesh_id
        self.local_node_id = local_node_id
        self.nodes: Dict[str, Dict] = {}
        self.attestation_strategy = AttestationStrategy.SPIFFE
        self.bootstrap_nodes: List[str] = []
        self.obfuscation_transport = obfuscation_transport
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-batman-node-manager:{_safe_hash(local_node_id)}",
            role="healing",
            capabilities=("monitoring", "zero-trust", "coordinator"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "libx0t_batman_node_manager_init",
                "goal": "Initialize mesh node lifecycle decisions safely",
                "signals": {
                    "mesh_hash": _safe_hash(mesh_id),
                    "local_node": _safe_node_ref(local_node_id),
                    "traffic_profile": traffic_profile,
                    "optimizations_requested": enable_optimizations,
                },
                "safety_boundary": (
                    "Keep node identifiers, addresses, certificates, and tokens out "
                    "of thinking telemetry."
                ),
            }
        )

        # Initialize Batman-adv optimizations from Paradox Zone
        self.optimizations: Optional["BatmanAdvOptimizations"] = None
        if enable_optimizations and BATMAN_OPTIMIZATIONS_AVAILABLE:
            try:
                import os

                config = BatmanAdvConfig(
                    multipath_enabled=os.getenv(
                        "BATMAN_MULTIPATH_ENABLED", "true"
                    ).lower()
                    == "true",
                    multipath_max_paths=int(
                        os.getenv("BATMAN_MULTIPATH_MAX_PATHS", "3")
                    ),
                    aodv_enabled=os.getenv("BATMAN_AODV_ENABLED", "true").lower()
                    == "true",
                    originator_interval=os.getenv("BATMAN_ORIGINATOR_INTERVAL", "1s"),
                    echo_interval=os.getenv("BATMAN_ECHO_INTERVAL", "500ms"),
                    max_queue_length=int(os.getenv("BATMAN_MAX_QUEUE_LENGTH", "1000")),
                )
                self.optimizations = BatmanAdvOptimizations(config)
                logger.info("✅ Batman-adv optimizations enabled (Paradox Zone)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Batman-adv optimizations: {e}")

        # Traffic Shaping
        self.traffic_shaper = None
        if TRAFFIC_SHAPING_AVAILABLE and traffic_profile != "none":
            try:
                profile = TrafficProfile(traffic_profile)
                self.traffic_shaper = TrafficShaper(profile)
                logger.info(f"Traffic shaping enabled with profile: {traffic_profile}")
                self._record_traffic_profile_active(traffic_profile)
            except ValueError:
                logger.warning(
                    f"Unknown traffic profile: {traffic_profile}, shaping disabled"
                )

        # DAO Governance
        self.governance = None
        if DAO_AVAILABLE:
            self.governance = GovernanceEngine(node_id=local_node_id)
            logger.info(f"DAO Governance initialized for {local_node_id}")

        # Hybrid TLS context for encrypting heartbeats (optional)
        self._hybrid_tls_session_key = None
        # if HYBRID_TLS_AVAILABLE:
        #     try:
        #         client_ctx = HybridTLSContext("client")
        #         server_ctx = HybridTLSContext("server")
        #         self._hybrid_tls_session_key, _ = hybrid_handshake(client_ctx, server_ctx)
        #         logger.info("Hybrid TLS session key initialized for heartbeats")
        #     except Exception as e:
        #         logger.warning(f"Failed to initialize Hybrid TLS context: {e}")
        #         self._hybrid_tls_session_key = None

        # Token Economics (optional)
        self.token: Optional["MeshToken"] = None
        self._relay_count = 0

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "preserve_public_behavior": True,
                    "redact_node_identifiers": True,
                    "redact_network_addresses": True,
                    "redact_attestation_material": True,
                },
                "safety_boundary": (
                    "Use only hashes, counts, booleans, and metric bands in "
                    "thinking context."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def propose_network_update(self, title: str, action: Dict) -> Optional[str]:
        """Propose a network configuration update via DAO."""
        if not self.governance:
            self._record_thinking(
                "libx0t_batman_governance_proposal_unavailable",
                "Decide whether a network update can be proposed",
                {
                    "governance_available": False,
                    "title_hash": _safe_hash(title),
                    "action_key_count": len(action or {}),
                },
            )
            logger.warning("Governance not available")
            return None

        try:
            proposal = self.governance.create_proposal(
                title=title, description=f"Network update: {action}", actions=[action]
            )
            self._record_thinking(
                "libx0t_batman_governance_proposal_created",
                "Track network update proposal creation",
                {
                    "governance_available": True,
                    "title_hash": _safe_hash(title),
                    "action_key_count": len(action or {}),
                    "proposal": _safe_node_ref(proposal.id),
                },
            )
            return proposal.id
        except ValueError as e:
            self._record_thinking(
                "libx0t_batman_governance_proposal_invalid",
                "Reject invalid network update proposal",
                {
                    "title_hash": _safe_hash(title),
                    "action_key_count": len(action or {}),
                    "error_type": type(e).__name__,
                },
            )
            logger.warning(f"Invalid proposal parameters: {e}")
            return None

    def vote_on_proposal(self, proposal_id: str, vote_str: str) -> bool:
        """Vote on an existing proposal."""
        if not self.governance:
            self._record_thinking(
                "libx0t_batman_governance_vote_unavailable",
                "Decide whether a governance vote can be cast",
                {"governance_available": False, "proposal": _safe_node_ref(proposal_id)},
            )
            return False

        try:
            vote = VoteType[vote_str.upper()]
            result = self.governance.cast_vote(proposal_id, self.local_node_id, vote)
            self._record_thinking(
                "libx0t_batman_governance_vote_cast",
                "Record governance voting outcome",
                {
                    "proposal": _safe_node_ref(proposal_id),
                    "vote": getattr(vote, "name", str(vote)),
                    "success": result,
                },
            )
            return result
        except KeyError:
            self._record_thinking(
                "libx0t_batman_governance_vote_invalid",
                "Reject invalid governance vote",
                {
                    "proposal": _safe_node_ref(proposal_id),
                    "vote_hash": _safe_hash(vote_str),
                },
            )
            logger.error(f"Invalid vote type: {vote_str}")
            return False

    def check_governance(self):
        """Periodic governance check (tally votes, execute)."""
        if self.governance:
            self.governance.check_proposals()
            self._record_thinking(
                "libx0t_batman_governance_checked",
                "Run periodic governance maintenance",
                {"governance_available": True},
            )
            # In a real loop, we would check for PASSED proposals and execute actions here
            # self._execute_passed_proposals()

    def _record_traffic_profile_active(self, profile: str):
        """Record active traffic profile metric."""
        try:
            from src.monitoring.metrics import traffic_profile_active

            traffic_profile_active.labels(
                node_id=self.local_node_id, profile=profile
            ).set(1)
        except ImportError:
            pass

    def _record_traffic_shaping_metrics(
        self, original_len: int, shaped_len: int, delay: float, profile: str
    ):
        """Record traffic shaping metrics."""
        try:
            from src.monitoring.metrics import (
                traffic_shaped_packets_total, traffic_shaping_bytes_total,
                traffic_shaping_delay_seconds,
                traffic_shaping_padding_bytes_total)

            traffic_shaped_packets_total.labels(
                node_id=self.local_node_id, profile=profile
            ).inc()
            traffic_shaping_bytes_total.labels(
                node_id=self.local_node_id, profile=profile
            ).inc(shaped_len)
            padding = shaped_len - original_len - 2  # -2 for length prefix
            if padding > 0:
                traffic_shaping_padding_bytes_total.labels(
                    node_id=self.local_node_id, profile=profile
                ).inc(padding)
            if delay > 0:
                traffic_shaping_delay_seconds.labels(
                    node_id=self.local_node_id, profile=profile
                ).observe(delay)
        except ImportError:
            pass

    def send_heartbeat(self, target_node: str) -> bool:
        """Send heartbeat to a target node (with obfuscation and traffic shaping)."""
        self._record_thinking(
            "libx0t_batman_heartbeat_prepare",
            "Prepare a mesh heartbeat without exposing node identifiers",
            {
                "target": _safe_node_ref(target_node),
                "pqc_enabled": HYBRID_TLS_AVAILABLE
                and self._hybrid_tls_session_key is not None,
                "obfuscation_enabled": bool(self.obfuscation_transport),
                "traffic_shaping_enabled": bool(self.traffic_shaper),
            },
        )
        payload = {
            "type": "heartbeat",
            "node_id": self.local_node_id,
            "timestamp": datetime.now().isoformat(),
        }
        data = json.dumps(payload).encode("utf-8")
        len(data)

        # Apply Hybrid TLS encryption (PQC) before obfuscation
        if HYBRID_TLS_AVAILABLE and self._hybrid_tls_session_key is not None:
            try:
                data = hybrid_encrypt(self._hybrid_tls_session_key, data)
                try:
                    from src.monitoring.metrics import \
                        heartbeat_pqc_encrypted_total

                    heartbeat_pqc_encrypted_total.labels(
                        node_id=self.local_node_id
                    ).inc()
                except ImportError:
                    pass
            except Exception as e:
                self._record_thinking(
                    "libx0t_batman_heartbeat_pqc_failed",
                    "Stop heartbeat after PQC encryption failure",
                    {"target": _safe_node_ref(target_node), "error_type": type(e).__name__},
                )
                logger.error(f"Hybrid TLS encryption failed for heartbeat: {e}")
                return False

        # Apply obfuscation first
        if self.obfuscation_transport:
            try:
                data = self.obfuscation_transport.obfuscate(data)
                try:
                    from src.monitoring.metrics import \
                        heartbeat_obfuscated_total

                    heartbeat_obfuscated_total.inc()
                except ImportError:
                    pass
            except Exception as e:
                self._record_thinking(
                    "libx0t_batman_heartbeat_obfuscation_failed",
                    "Stop heartbeat after obfuscation failure",
                    {"target": _safe_node_ref(target_node), "error_type": type(e).__name__},
                )
                logger.error(f"Obfuscation failed for heartbeat: {e}")
                return False

        # Apply traffic shaping
        delay = 0.0
        if self.traffic_shaper:
            shaped_data = self.traffic_shaper.shape_packet(data)
            delay = self.traffic_shaper.get_send_delay()
            profile = self.traffic_shaper.profile.value
            self._record_traffic_shaping_metrics(
                len(data), len(shaped_data), delay, profile
            )
            data = shaped_data

        # In a real system, we would apply delay and send 'data' over the network.
        # logger.debug(f"Sent heartbeat to {target_node} ({len(data)} bytes, delay={delay:.3f}s)")
        self._record_thinking(
            "libx0t_batman_heartbeat_ready",
            "Confirm heartbeat packet is ready for transport",
            {
                "target": _safe_node_ref(target_node),
                "final_size_bucket": _safe_count_bucket(len(data)),
                "delay_band": _safe_metric_band(delay, 0.001, 0.1),
            },
        )
        return True

    def set_token(self, token: "MeshToken"):
        """Set token instance for relay rewards."""
        self.token = token
        logger.info(f"Token economics enabled for {self.local_node_id}")

    def relay_packet(
        self, source_node: str, dest_node: str, packet_size_bytes: int = 1024
    ) -> bool:
        """
        Relay a packet from source to destination.
        Earns X0T tokens for the relay service.

        Args:
            source_node: Original sender
            dest_node: Final destination
            packet_size_bytes: Size of relayed packet

        Returns:
            True if relay successful
        """
        # Allow relay to any node (in real mesh, routing handles this)
        # Only warn if destination is completely unknown and not self
        if dest_node not in self.nodes and dest_node != self.local_node_id:
            logger.debug(f"Relaying to external node: {dest_node}")

        self._relay_count += 1
        self._record_thinking(
            "libx0t_batman_relay_packet",
            "Decide whether to account for a relay operation",
            {
                "source": _safe_node_ref(source_node),
                "destination": _safe_node_ref(dest_node),
                "destination_known": dest_node in self.nodes
                or dest_node == self.local_node_id,
                "packet_size_bucket": _safe_count_bucket(packet_size_bytes),
                "relay_count_bucket": _safe_count_bucket(self._relay_count),
                "token_enabled": bool(self.token and TOKEN_AVAILABLE),
            },
        )

        # Record metrics
        try:
            from src.monitoring.metrics import record_resource_payment

            # Record as relay activity (even without payment for tracking)
        except ImportError:
            pass

        # Earn tokens for relay if token system is active
        if self.token and TOKEN_AVAILABLE:
            # Source pays this node for relay service
            # Price: 0.0001 X0T per relay (defined in MeshToken)
            success = self.token.pay_for_resource(
                payer_node=source_node,
                provider_node=self.local_node_id,
                resource_type=ResourceType.RELAY,
                amount=1,  # 1 relay
            )
            if success:
                logger.debug(
                    f"Relay reward: {self.local_node_id} earned X0T for relaying {source_node} -> {dest_node}"
                )

        return True

    def get_relay_count(self) -> int:
        """Get total number of packets relayed by this node."""
        return self._relay_count

    def get_relay_earnings(self) -> float:
        """Get estimated earnings from relay (based on relay count)."""
        if not self.token:
            return 0.0
        return self._relay_count * self.token.PRICE_PER_RELAY

    def send_topology_update(self, target_node: str, topology_data: Dict) -> bool:
        """Send topology update to a target node (with obfuscation and traffic shaping)."""
        topology_keys = sorted(str(key) for key in (topology_data or {}).keys())
        self._record_thinking(
            "libx0t_batman_topology_update_prepare",
            "Prepare topology update with redacted topology metadata",
            {
                "target": _safe_node_ref(target_node),
                "topology_key_count": len(topology_keys),
                "topology_keys_hash": _safe_hash("|".join(topology_keys)),
                "obfuscation_enabled": bool(self.obfuscation_transport),
                "traffic_shaping_enabled": bool(self.traffic_shaper),
            },
        )
        payload = {
            "type": "topology_update",
            "node_id": self.local_node_id,
            "data": topology_data,
            "timestamp": datetime.now().isoformat(),
        }
        data = json.dumps(payload).encode("utf-8")

        if self.obfuscation_transport:
            try:
                data = self.obfuscation_transport.obfuscate(data)
            except Exception as e:
                self._record_thinking(
                    "libx0t_batman_topology_obfuscation_failed",
                    "Stop topology update after obfuscation failure",
                    {"target": _safe_node_ref(target_node), "error_type": type(e).__name__},
                )
                logger.error(f"Obfuscation failed for topology update: {e}")
                return False

        # Apply traffic shaping
        if self.traffic_shaper:
            shaped_data = self.traffic_shaper.shape_packet(data)
            delay = self.traffic_shaper.get_send_delay()
            profile = self.traffic_shaper.profile.value
            self._record_traffic_shaping_metrics(
                len(data), len(shaped_data), delay, profile
            )
            data = shaped_data

        # In a real system, we would apply delay and send 'data' over the network.
        self._record_thinking(
            "libx0t_batman_topology_update_ready",
            "Confirm topology update packet is ready for transport",
            {
                "target": _safe_node_ref(target_node),
                "final_size_bucket": _safe_count_bucket(len(data)),
            },
        )
        return True

    def register_node(
        self,
        node_id: str,
        mac_address: str,
        ip_address: str,
        spiffe_id: Optional[str] = None,
        join_token: Optional[str] = None,
        cert_pem: Optional[bytes] = None,
        referrer_id: Optional[str] = None,
    ) -> bool:
        """Register a new node with the mesh"""
        if node_id in self.nodes:
            self._record_thinking(
                "libx0t_batman_node_register_duplicate",
                "Reject duplicate mesh node registration",
                {"node": _safe_node_ref(node_id), "node_count": len(self.nodes)},
            )
            logger.warning(f"Node {node_id} already registered")
            return False

        # Attestation
        if not self._attest_node(node_id, spiffe_id, join_token, cert_pem):
            self._record_thinking(
                "libx0t_batman_node_register_attestation_failed",
                "Reject node registration after attestation failure",
                {
                    "node": _safe_node_ref(node_id),
                    "address_family": _address_family(ip_address),
                    "strategy": self.attestation_strategy.value,
                    "spiffe_present": bool(spiffe_id),
                    "join_token_present": bool(join_token),
                    "certificate_present": bool(cert_pem),
                },
            )
            logger.error(f"Node attestation failed: {node_id}")
            return False

        self.nodes[node_id] = {
            "mac_address": mac_address,
            "ip_address": ip_address,
            "spiffe_id": spiffe_id,
            "joined_at": datetime.now(),
            "last_heartbeat": datetime.now(),
            "status": "online",
            "metrics": None,
        }

        logger.info(f"Registered node: {node_id} ({ip_address})")
        self._record_thinking(
            "libx0t_batman_node_registered",
            "Accept node registration after safety checks",
            {
                "node": _safe_node_ref(node_id),
                "address_family": _address_family(ip_address),
                "strategy": self.attestation_strategy.value,
                "spiffe_present": bool(spiffe_id),
                "certificate_present": bool(cert_pem),
                "node_count_bucket": _safe_count_bucket(len(self.nodes)),
                "referrer_present": bool(referrer_id),
            },
        )

        # Reward new node deployment
        if self.token and TOKEN_AVAILABLE:
            # Type check for reward_deployment signature update
            try:
                self.token.reward_deployment(node_id, referrer_id=referrer_id)
            except TypeError:
                self.token.reward_deployment(node_id)

        return True

    def _attest_node(
        self,
        node_id: str,
        spiffe_id: Optional[str],
        join_token: Optional[str],
        cert_pem: Optional[bytes] = None,
    ) -> bool:
        """Verify node identity before registration"""
        if self.attestation_strategy == AttestationStrategy.SPIFFE:
            if not spiffe_id or not spiffe_id.startswith("spiffe://"):
                self._record_thinking(
                    "libx0t_batman_attestation_spiffe_rejected",
                    "Reject SPIFFE attestation with missing or malformed identity",
                    {
                        "node": _safe_node_ref(node_id),
                        "spiffe_present": bool(spiffe_id),
                    },
                )
                return False

            # Enhanced Validation if module available and cert provided
            if SPIFFE_AVAILABLE and cert_pem:
                try:
                    # Construct SVID object for validation
                    # Parse certificate to get actual expiry
                    expiry = datetime.utcnow() + timedelta(hours=1)  # Default fallback
                    try:
                        from cryptography import x509
                        from cryptography.hazmat.backends import \
                            default_backend

                        # Parse PEM certificate
                        cert_bytes = (
                            cert_pem.encode() if isinstance(cert_pem, str) else cert_pem
                        )
                        cert = x509.load_pem_x509_certificate(
                            cert_bytes, default_backend()
                        )
                        expiry = cert.not_valid_after.replace(
                            tzinfo=None
                        )  # Remove timezone for compatibility
                        logger.debug(
                            f"Parsed certificate expiry: {expiry} for node {node_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse certificate expiry for {node_id}: {e}, using default 1h expiry"
                        )

                    svid = X509SVID(
                        spiffe_id=spiffe_id,
                        cert_chain=[cert_pem],
                        private_key=b"",  # Not needed for public validation
                        expiry=expiry,  # Real parsed expiry or fallback
                    )

                    # Use the WorkloadAPIClient logic (even if mocked)
                    # We instantiate client with default/dummy path as we only need logic
                    client = WorkloadAPIClient()
                    if not client.validate_peer_svid(svid, expected_id=spiffe_id):
                        self._record_thinking(
                            "libx0t_batman_attestation_svid_rejected",
                            "Reject SPIFFE SVID after peer validation",
                            {"node": _safe_node_ref(node_id), "certificate_present": True},
                        )
                        logger.error(f"SPIFFE SVID validation failed for {node_id}")
                        return False

                    logger.info(f"SPIFFE Strong Attestation success: {spiffe_id}")
                    self._record_thinking(
                        "libx0t_batman_attestation_svid_accepted",
                        "Accept SPIFFE SVID after peer validation",
                        {"node": _safe_node_ref(node_id), "certificate_present": True},
                    )

                    # Record metric
                    try:
                        from src.monitoring.metrics import \
                            set_node_spiffe_attested

                        set_node_spiffe_attested(node_id, spiffe_id, True)
                    except ImportError:
                        pass

                except Exception as e:
                    self._record_thinking(
                        "libx0t_batman_attestation_svid_error",
                        "Reject SPIFFE attestation after validation error",
                        {"node": _safe_node_ref(node_id), "error_type": type(e).__name__},
                    )
                    logger.error(f"SPIFFE validation error: {e}")
                    return False

            logger.debug(f"SPIFFE attestation passed: {spiffe_id}")
            self._record_thinking(
                "libx0t_batman_attestation_spiffe_accepted",
                "Accept SPIFFE attestation with syntactic identity check",
                {"node": _safe_node_ref(node_id), "certificate_present": bool(cert_pem)},
            )

        elif self.attestation_strategy == AttestationStrategy.TOKEN_BASED:
            if not join_token:
                self._record_thinking(
                    "libx0t_batman_attestation_token_rejected",
                    "Reject token attestation without token material",
                    {"node": _safe_node_ref(node_id), "join_token_present": False},
                )
                return False
            # Verify token (in production, check against token store)
            logger.debug(f"Token attestation: {join_token[:16]}...")
            self._record_thinking(
                "libx0t_batman_attestation_token_accepted",
                "Accept token attestation for registration flow",
                {"node": _safe_node_ref(node_id), "join_token_present": True},
            )

        return True

    def update_heartbeat(self, node_id: str) -> bool:
        """Update last heartbeat timestamp for node"""
        if node_id not in self.nodes:
            self._record_thinking(
                "libx0t_batman_heartbeat_update_missing_node",
                "Reject heartbeat update for unknown node",
                {"node": _safe_node_ref(node_id), "node_count": len(self.nodes)},
            )
            return False

        self.nodes[node_id]["last_heartbeat"] = datetime.now()
        self._record_thinking(
            "libx0t_batman_heartbeat_updated",
            "Update node heartbeat timestamp",
            {"node": _safe_node_ref(node_id), "node_count": len(self.nodes)},
        )
        return True

    def update_metrics(self, node_id: str, metrics: NodeMetrics) -> bool:
        """Update node health metrics"""
        if node_id not in self.nodes:
            self._record_thinking(
                "libx0t_batman_metrics_update_missing_node",
                "Reject metrics update for unknown node",
                {"node": _safe_node_ref(node_id), "node_count": len(self.nodes)},
            )
            return False

        self.nodes[node_id]["metrics"] = metrics

        # Update status based on metrics
        if metrics.is_healthy():
            self.nodes[node_id]["status"] = "online"
        else:
            self.nodes[node_id]["status"] = "degraded"

        self._record_thinking(
            "libx0t_batman_metrics_updated",
            "Classify node health from metrics bands",
            {
                "node": _safe_node_ref(node_id),
                "status": self.nodes[node_id]["status"],
                "cpu_band": _safe_metric_band(metrics.cpu_percent, 70, 90),
                "memory_band": _safe_metric_band(metrics.memory_percent, 70, 85),
                "packet_loss_band": _safe_metric_band(
                    metrics.packet_loss_percent, 1, 5
                ),
                "latency_band": _safe_metric_band(
                    metrics.latency_to_gateway_ms, 150, 500
                ),
            },
        )
        return True

    def deregister_node(self, node_id: str, reason: str = "unknown") -> bool:
        """Deregister a node from the mesh"""
        if node_id not in self.nodes:
            self._record_thinking(
                "libx0t_batman_node_deregister_missing",
                "Reject deregistration for unknown node",
                {"node": _safe_node_ref(node_id), "reason_hash": _safe_hash(reason)},
            )
            return False

        del self.nodes[node_id]
        self._record_thinking(
            "libx0t_batman_node_deregistered",
            "Remove node from mesh registry",
            {
                "node": _safe_node_ref(node_id),
                "reason_hash": _safe_hash(reason),
                "node_count_bucket": _safe_count_bucket(len(self.nodes)),
            },
        )
        logger.info(f"Deregistered node: {node_id} (reason: {reason})")
        return True

    def get_node_status(self, node_id: str) -> Optional[Dict]:
        """Get status of a specific node"""
        return self.nodes.get(node_id)

    def get_all_nodes(self) -> Dict[str, Dict]:
        """Get all registered nodes"""
        # Return a deep copy so callers cannot mutate internal manager state.
        return copy.deepcopy(self.nodes)

    def get_online_nodes(self) -> List[str]:
        """Get list of online nodes"""
        return [nid for nid, n in self.nodes.items() if n["status"] == "online"]


class HealthMonitor:
    """
    Continuous Health Monitoring for Mesh Network

    Monitors:
    - Node availability
    - Link quality
    - Network performance
    - Anomalies & failures
    """

    def __init__(
        self,
        check_interval: int = 30,
        incident_workflow: Optional["IncidentDAOWorkflow"] = None,
    ):
        self.check_interval = check_interval  # seconds
        self.health_checks: Dict[str, Callable] = {}
        self.alert_handlers: List[Callable] = []
        self.running = False
        self.incident_workflow = incident_workflow
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-batman-health-monitor:{_safe_hash(id(self))}",
            role="monitoring",
            capabilities=("healing", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "libx0t_batman_health_monitor_init",
                "goal": "Initialize mesh health monitoring decisions",
                "signals": {
                    "check_interval": check_interval,
                    "incident_workflow_available": bool(incident_workflow),
                },
                "safety_boundary": (
                    "Do not put raw node identifiers or topology endpoints in "
                    "health-monitor thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_node_identifiers": True,
                    "redact_topology_endpoints": True,
                    "preserve_monitoring_behavior": True,
                },
                "safety_boundary": (
                    "Use hashes and counts for health-alert thinking context."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def register_health_check(self, name: str, check_fn: Callable):
        """Register a custom health check"""
        self.health_checks[name] = check_fn
        self._record_thinking(
            "libx0t_batman_health_check_registered",
            "Register custom mesh health check",
            {
                "check_hash": _safe_hash(name),
                "health_check_count": len(self.health_checks),
            },
        )
        logger.info(f"Registered health check: {name}")

    def register_alert_handler(self, handler: Callable):
        """Register callback for health alerts"""
        self.alert_handlers.append(handler)
        self._record_thinking(
            "libx0t_batman_health_alert_handler_registered",
            "Register mesh health alert handler",
            {"alert_handler_count": len(self.alert_handlers)},
        )

    async def start_monitoring(self, node_manager: NodeManager, topology):
        """Start continuous health monitoring"""
        self.running = True
        logger.info("Starting health monitoring")

        while self.running:
            try:
                await self._perform_health_checks(node_manager, topology)

                # Distribute epoch rewards if token system is active
                if node_manager.token and TOKEN_AVAILABLE:
                    # For demo/MVP, we consider all online nodes as 100% uptime for the epoch
                    uptimes = {nid: 1.0 for nid in node_manager.get_online_nodes()}
                    node_manager.token.distribute_epoch_rewards(uptimes)

            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _perform_health_checks(self, node_manager: NodeManager, topology):
        """Execute all health checks"""
        # Check node heartbeats
        dead_nodes = self._check_node_heartbeats(node_manager)
        if dead_nodes:
            await self._handle_alert("dead_nodes", {"nodes": dead_nodes})

        # Check link quality
        degraded_links = self._check_link_quality(topology)
        if degraded_links:
            await self._handle_alert("degraded_links", {"links": degraded_links})

        # Run custom checks
        for check_name, check_fn in self.health_checks.items():
            try:
                result = (
                    await check_fn()
                    if asyncio.iscoroutinefunction(check_fn)
                    else check_fn()
                )
                if not result:
                    await self._handle_alert("check_failed", {"check": check_name})
            except Exception as e:
                logger.error(f"Check {check_name} failed: {e}")

        self._record_thinking(
            "libx0t_batman_health_checks_performed",
            "Summarize mesh health checks",
            {
                "dead_node_count": len(dead_nodes),
                "dead_node_hashes": [_safe_hash(node) for node in dead_nodes[:10]],
                "degraded_link_count": len(degraded_links),
                "custom_check_count": len(self.health_checks),
                "alert_handler_count": len(self.alert_handlers),
            },
        )

    def _check_node_heartbeats(
        self, node_manager: NodeManager, timeout: int = 120
    ) -> List[str]:
        """Check for nodes with missing heartbeats"""
        dead = []
        now = datetime.now()

        for node_id, node_info in node_manager.get_all_nodes().items():
            elapsed = (now - node_info["last_heartbeat"]).total_seconds()
            if elapsed > timeout:
                dead.append(node_id)
                logger.warning(
                    f"Dead node detected: {node_id} (no heartbeat for {elapsed}s)"
                )

        self._record_thinking(
            "libx0t_batman_heartbeat_scan",
            "Detect nodes with stale heartbeats",
            {
                "node_count": len(node_manager.get_all_nodes()),
                "dead_node_count": len(dead),
                "dead_node_hashes": [_safe_hash(node) for node in dead[:10]],
                "timeout_seconds": timeout,
            },
        )
        return dead

    def _check_link_quality(self, topology) -> List[Dict]:
        """Check for degraded links"""
        degraded = []
        for (src, dst), link in topology.links.items():
            if link.quality.value < 3:  # Less than FAIR
                degraded.append(
                    {
                        "source": src,
                        "destination": dst,
                        "quality": link.quality.name,
                    }
                )
        self._record_thinking(
            "libx0t_batman_link_quality_scan",
            "Detect degraded topology links",
            {
                "link_count": len(getattr(topology, "links", {}) or {}),
                "degraded_link_count": len(degraded),
                "quality_labels": sorted({item["quality"] for item in degraded}),
            },
        )
        return degraded

    async def _handle_alert(self, alert_type: str, data: Dict):
        """Process health alert"""
        logger.warning(f"Health alert: {alert_type} - {data}")
        self._record_thinking(
            "libx0t_batman_health_alert_handled",
            "Process mesh health alert safely",
            {
                "alert_type": alert_type,
                "node_count": len(data.get("nodes", []) or []),
                "node_hashes": [
                    _safe_hash(node) for node in (data.get("nodes", []) or [])[:10]
                ],
                "link_count": len(data.get("links", []) or []),
                "check_hash": _safe_hash(data.get("check"))
                if data.get("check")
                else None,
            },
        )

        # Bridge critical health alerts into DAO incident workflow
        if (
            alert_type == "dead_nodes"
            and self.incident_workflow
            and INCIDENT_WORKFLOW_AVAILABLE
        ):
            nodes = data.get("nodes", [])
            for node_id in nodes:
                incident = Incident(
                    incident_id=f"dead_node_{node_id}_{int(datetime.now().timestamp())}",
                    incident_type="node_down",
                    severity=IncidentSeverity.CRITICAL,
                    description=f"Node {node_id} has not sent heartbeat and is considered dead.",
                    detected_at=datetime.now().timestamp(),
                    metadata={"node_id": node_id},
                )

                proposal = self.incident_workflow.create_proposal_from_incident(
                    incident, duration_seconds=0.1
                )

                voters = {self.incident_workflow.governance.node_id: VoteType.YES}
                self.incident_workflow.auto_vote_and_execute(proposal.id, voters)

        for handler in self.alert_handlers:
            try:
                (
                    await handler(alert_type, data)
                    if asyncio.iscoroutinefunction(handler)
                    else handler(alert_type, data)
                )
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def stop_monitoring(self):
        """Stop health monitoring"""
        self.running = False
        self._record_thinking(
            "libx0t_batman_health_monitor_stopped",
            "Stop mesh health monitoring loop",
            {"running": self.running},
        )
        logger.info("Health monitoring stopped")


def create_incident_workflow_for_node_manager(
    node_manager: NodeManager,
) -> Optional["IncidentDAOWorkflow"]:
    """Factory to build an IncidentDAOWorkflow bound to a specific NodeManager.

    The executor will deregister dead nodes when an incident_response action
    with incident_type == "node_down" is executed.
    """

    if not (DAO_AVAILABLE and INCIDENT_WORKFLOW_AVAILABLE):
        return None

    # Reuse the same governance engine model as NodeManager uses (1 node = 1 vote).
    governance = GovernanceEngine(node_id=node_manager.local_node_id)

    def executor(action: Dict):
        if action.get("type") != "incident_response":
            return

        metadata = action.get("metadata", {}) or {}
        node_id = metadata.get("node_id")
        if not node_id:
            return

        # Deregister the dead node from the mesh.
        if node_id in node_manager.nodes:
            node_manager.deregister_node(node_id, reason="dao_incident_node_down")

            # Metrics / observability hook
            try:
                from src.monitoring.metrics import \
                    record_dao_incident_execution

                incident_type = action.get("incident_type", "node_down")
                severity = action.get("severity", "unknown")
                record_dao_incident_execution(
                    incident_type=incident_type,
                    severity=severity,
                    node_id=node_id,
                )
            except ImportError:
                pass

    return IncidentDAOWorkflow(governance=governance, executor=executor)
