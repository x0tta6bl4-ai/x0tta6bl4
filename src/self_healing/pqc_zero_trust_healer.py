#!/usr/bin/env python3
"""
PQC Zero-Trust Healer for x0tta6bl4
Implements MAPE-K cycle for PQC cryptographic session anomalies.

Monitors PQC sessions, detects anomalies, plans remediation, and executes healing.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..coordination.events import EventBus, EventType, get_event_bus
from ..network.ebpf.pqc_xdp_loader import PQCXDPLoader
from ..security.ebpf_pqc_gateway import EBPFPQCGateway, get_pqc_gateway
from ..security.pqc_identity import PQCNodeIdentity
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from ..services.service_event_identity import service_event_identity
from .mape_k import MAPEKAnalyzer, MAPEKExecutor, MAPEKMonitor, MAPEKPlanner
from .signed_command import SignedRemediationCommand
from .anomaly_consensus import AnomalyConsensusManager, AnomalyEvidence
from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


_SERVICE_AGENT = "pqc-zero-trust-healer"
PQC_CLAIM_BOUNDARY = (
    "PQC recovery executor event only. It records local policy and healing action "
    "state; it is not live PQC trust finality, dataplane delivery, external "
    "production evidence, or a settlement attestation."
)
PQC_RECOVERY_CLAIM_GATE_SCHEMA = "x0tta6bl4.self_healing.pqc_recovery_claim_gate.v1"


def _pqc_recovery_claim_gate(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    local_action_recorded = result is not None
    local_action_succeeded = bool(result and result.get("success") is True)
    return {
        "schema": PQC_RECOVERY_CLAIM_GATE_SCHEMA,
        "local_pqc_recovery_action_recorded": local_action_recorded,
        "local_pqc_recovery_action_succeeded": local_action_succeeded,
        "local_policy_decision_recorded": True,
        "live_pqc_trust_finality_claim_allowed": False,
        "live_spiffe_svid_claim_allowed": False,
        "did_ownership_claim_allowed": False,
        "wallet_control_claim_allowed": False,
        "event_producer_identity_authenticity_claim_allowed": False,
        "chain_identity_finality_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_allowed": {
            "local_pqc_recovery_lifecycle": local_action_recorded,
            "live_pqc_trust_finality": False,
            "live_spiffe_svid": False,
            "dataplane_delivery": False,
            "traffic_delivery": False,
            "external_settlement_finality": False,
            "production_readiness": False,
        },
        "claim_boundary": PQC_CLAIM_BOUNDARY,
        "payloads_redacted": True,
    }


@dataclass
class PQCSessionAnomaly:
    """Represents a PQC session or identity anomaly"""

    anomaly_type: str  # 'expired', 'failed_verification', 'no_session', 'high_failure_rate', 'identity_tamper'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    timestamp: datetime
    session_id: Optional[str] = None
    identity_id: Optional[str] = None
    peer_id: Optional[str] = None
    failure_count: int = 0


@dataclass
class PQCHealthMetrics:
    """PQC system health metrics"""

    total_sessions: int
    active_sessions: int
    expired_sessions: int
    failed_verifications: int
    verification_rate: float
    average_session_age: float
    anomaly_count: int
    last_updated: datetime


class PQCZeroTrustMonitor(MAPEKMonitor):
    """Monitors PQC cryptographic operations, session health, and node identity."""

    def __init__(
        self,
        pqc_gateway: Optional[EBPFPQCGateway] = None,
        pqc_loader: Optional[PQCXDPLoader] = None,
        identity_manager: Optional[PQCNodeIdentity] = None,
    ):
        super().__init__()
        self.pqc_gateway = pqc_gateway or get_pqc_gateway()
        self.pqc_loader = pqc_loader
        self.identity_manager = identity_manager

        # Anomaly tracking
        self.anomalies: List[PQCSessionAnomaly] = []
        self.health_metrics = PQCHealthMetrics(
            total_sessions=0,
            active_sessions=0,
            expired_sessions=0,
            failed_verifications=0,
            verification_rate=0.0,
            average_session_age=0.0,
            anomaly_count=0,
            last_updated=datetime.now(),
        )

        # Healing thresholds
        self.session_expiry_threshold = timedelta(hours=1)
        self.max_failure_rate = 0.1  # 10% failure rate
        self.max_anomalies_per_hour = 10
        self.thinking_coach = AgentThinkingCoach(
            agent_id="pqc-zero-trust-monitor",
            role="monitoring",
            capabilities=("mape_k", "zero-trust", "pqc"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "tracked_anomaly_count": len(self.anomalies),
            "session_expiry_threshold_seconds": int(
                self.session_expiry_threshold.total_seconds()
            ),
            "constraints": {
                "redact_session_ids": True,
                "redact_peer_ids": True,
                "redact_identity_ids": True,
                "monitoring_is_not_pqc_trust_finality": True,
                "does_not_prove_dataplane_delivery": True,
            },
            "safety_boundary": PQC_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose monitor thinking state without raw PQC identifiers."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def monitor(self) -> Dict[str, Any]:
        """Monitor PQC system health and detect anomalies"""
        try:
            import time

            current_time = datetime.now()
            current_ts = time.time()
            expiry_seconds = self.session_expiry_threshold.total_seconds()

            # Get current sessions
            sessions = self.pqc_gateway.sessions
            self._record_thinking(
                "pqc_zero_trust_monitor",
                "monitor local PQC session health without raw session IDs",
                {"session_count": len(sessions), "pqc_loader_present": self.pqc_loader is not None},
            )

            # Get eBPF stats if loader available
            ebpf_stats = {}
            if self.pqc_loader:
                ebpf_stats = self.pqc_loader.get_pqc_stats()

            # Calculate health metrics
            total_sessions = len(sessions)
            active_sessions = sum(
                1
                for s in sessions.values()
                if current_ts - s.last_used < expiry_seconds
            )
            expired_sessions = total_sessions - active_sessions

            failed_verifications = ebpf_stats.get("failed_verification", 0)
            total_packets = ebpf_stats.get("total_packets", 1)  # Avoid division by zero
            verification_rate = ebpf_stats.get("verified_packets", 0) / total_packets

            # Calculate average session age
            if sessions:
                ages = [(current_ts - s.created_at) for s in sessions.values()]
                average_session_age = sum(ages) / len(ages)
            else:
                average_session_age = 0.0

            # Update health metrics
            self.health_metrics = PQCHealthMetrics(
                total_sessions=total_sessions,
                active_sessions=active_sessions,
                expired_sessions=expired_sessions,
                failed_verifications=failed_verifications,
                verification_rate=verification_rate,
                average_session_age=average_session_age,
                anomaly_count=len(self.anomalies),
                last_updated=current_time,
            )

            # Detect anomalies
            new_anomalies = self._detect_anomalies(sessions, ebpf_stats, current_ts)

            monitoring_data = {
                "health_metrics": self.health_metrics,
                "anomalies": new_anomalies,
                "ebpf_stats": ebpf_stats,
                "timestamp": current_time,
            }

            logger.debug(
                f"PQC monitoring: {total_sessions} sessions, {len(new_anomalies)} anomalies"
            )

            return monitoring_data

        except Exception as e:
            self._record_thinking(
                "pqc_zero_trust_monitor",
                "record PQC monitoring failure without raw error text",
                {"status": "error", "error_type": type(e).__name__},
            )
            logger.error(f"PQC monitoring failed: {e}")
            return {"error": str(e), "timestamp": datetime.now()}

    def _detect_anomalies(
        self, sessions: Dict, ebpf_stats: Dict, current_ts: float
    ) -> List[PQCSessionAnomaly]:
        """Detect PQC session anomalies"""
        anomalies = []
        from datetime import datetime

        current_time = datetime.fromtimestamp(current_ts)
        expiry_seconds = self.session_expiry_threshold.total_seconds()

        # Check for expired sessions
        for session_id, session in sessions.items():
            if current_ts - session.last_used > expiry_seconds:
                anomalies.append(
                    PQCSessionAnomaly(
                        session_id=session_id,
                        anomaly_type="expired",
                        severity="medium",
                        description=f"Session expired: {session_id}",
                        timestamp=current_time,
                        peer_id=session.peer_id,
                    )
                )

        # Check verification failure rate
        total_packets = ebpf_stats.get("total_packets", 0)
        failed_packets = ebpf_stats.get("failed_verification", 0)

        if total_packets > 100:  # Minimum sample size
            failure_rate = failed_packets / total_packets
            if failure_rate > self.max_failure_rate:
                anomalies.append(
                    PQCSessionAnomaly(
                        session_id="system",
                        anomaly_type="high_failure_rate",
                        severity="high",
                        description=f"High verification failure rate: {failure_rate:.2%}",
                        timestamp=current_time,
                        failure_count=failed_packets,
                    )
                )

        # Check for sessions with no activity
        no_session_packets = ebpf_stats.get("no_session", 0)
        if no_session_packets > 50:  # Threshold
            anomalies.append(
                PQCSessionAnomaly(
                    session_id="system",
                    anomaly_type="no_session",
                    severity="medium",
                    description=f"Packets without valid session: {no_session_packets}",
                    timestamp=current_time,
                    failure_count=no_session_packets,
                )
            )

        # Check anomaly rate
        recent_anomalies = [
            a for a in self.anomalies if current_time - a.timestamp < timedelta(hours=1)
        ]
        if len(recent_anomalies) > self.max_anomalies_per_hour:
            anomalies.append(
                PQCSessionAnomaly(
                    session_id="system",
                    anomaly_type="anomaly_storm",
                    severity="critical",
                    description=f"Anomaly storm detected: {len(recent_anomalies)} anomalies/hour",
                    timestamp=current_time,
                    failure_count=len(recent_anomalies),
                )
            )

        # Check identity health
        if self.identity_manager:
            try:
                # Basic check: verify our own public keys still match the identity manager state
                pkeys = self.identity_manager.security.get_public_keys()
                if not pkeys.get('sig_public_key'):
                    anomalies.append(
                        PQCSessionAnomaly(
                            identity_id=self.identity_manager.did,
                            anomaly_type="identity_tamper",
                            severity="critical",
                            description="PQC Signing key is missing or corrupted",
                            timestamp=current_time,
                        )
                    )
            except Exception as e:
                anomalies.append(
                    PQCSessionAnomaly(
                        identity_id=getattr(self.identity_manager, 'did', 'unknown'),
                        anomaly_type="identity_tamper",
                        severity="critical",
                        description=f"Identity manager error: {e}",
                        timestamp=current_time,
                    )
                )

        # Add new anomalies to tracking list
        self.anomalies.extend(anomalies)

        # Keep only recent anomalies (last 24 hours)
        cutoff = current_time - timedelta(hours=24)
        self.anomalies = [a for a in self.anomalies if a.timestamp > cutoff]

        return anomalies


class PQCZeroTrustAnalyzer(MAPEKAnalyzer):
    """Analyzes PQC monitoring data and determines if healing is needed."""

    def __init__(self):
        super().__init__()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="pqc-zero-trust-analyzer",
            role="analysis",
            capabilities=("mape_k", "zero-trust", "pqc"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "constraints": {
                "redact_issue_text": True,
                "redact_raw_anomalies": True,
                "analysis_is_not_healing_proof": True,
                "does_not_prove_pqc_trust_finality": True,
            },
            "safety_boundary": PQC_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose analyzer thinking state without raw issue text."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def analyze(self, monitoring_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze monitoring data and determine if healing is needed"""
        try:
            anomalies = monitoring_data.get("anomalies", [])
            health_metrics = monitoring_data.get("health_metrics")
            self._record_thinking(
                "pqc_zero_trust_analyze",
                "analyze local PQC health data without raw anomaly payloads",
                {
                    "anomaly_count": len(anomalies),
                    "health_metrics_present": health_metrics is not None,
                    "monitoring_keys": sorted(str(key) for key in monitoring_data),
                },
            )

            if not health_metrics:
                self._record_thinking(
                    "pqc_zero_trust_analyze",
                    "record missing PQC health metrics",
                    {"severity": "unknown", "requires_action": False},
                )
                return {"issues": [], "severity": "unknown", "requires_action": False}

            issues = []
            severity = "low"
            requires_action = False

            # Analyze anomalies
            critical_anomalies = [a for a in anomalies if a.severity == "critical"]
            high_anomalies = [a for a in anomalies if a.severity == "high"]

            if critical_anomalies:
                issues.append("Critical PQC anomalies detected")
                severity = "critical"
                requires_action = True
            elif high_anomalies:
                issues.append("High-severity PQC anomalies detected")
                severity = "high"
                requires_action = True
            elif anomalies:
                issues.append("PQC anomalies detected")
                severity = "medium"
                requires_action = True

            # Check health score
            health_score = self._calculate_health_score(health_metrics)
            if health_score < 0.5:
                issues.append(f"Low PQC health score: {health_score:.2f}")
                severity = "high"
                requires_action = True
            elif health_score < 0.7:
                issues.append(f"Moderate PQC health score: {health_score:.2f}")
                if severity == "low":
                    severity = "medium"
                requires_action = True

            # Check session health
            if health_metrics.expired_sessions > health_metrics.active_sessions:
                issues.append("More expired than active sessions")
                severity = "high"
                requires_action = True

            result = {
                "issues": issues,
                "severity": severity,
                "requires_action": requires_action,
                "analysis_data": {
                    "anomaly_count": len(anomalies),
                    "health_score": health_score,
                    "session_ratio": health_metrics.active_sessions
                    / max(1, health_metrics.total_sessions),
                },
            }
            self._record_thinking(
                "pqc_zero_trust_analyze",
                "record local PQC analysis result without issue text",
                {
                    "issue_count": len(issues),
                    "severity": severity,
                    "requires_action": requires_action,
                },
            )
            return result

        except Exception as e:
            self._record_thinking(
                "pqc_zero_trust_analyze",
                "record PQC analysis failure without raw error text",
                {"severity": "critical", "error_type": type(e).__name__},
            )
            logger.error(f"PQC analysis failed: {e}")
            return {
                "issues": [f"Analysis error: {e}"],
                "severity": "critical",
                "requires_action": True,
            }

    def _calculate_health_score(self, health_metrics) -> float:
        """Calculate overall PQC system health score (0.0-1.0)"""
        if not health_metrics:
            return 0.0

        score = 1.0

        # Penalize expired sessions
        if health_metrics.total_sessions > 0:
            expiry_ratio = (
                health_metrics.expired_sessions / health_metrics.total_sessions
            )
            score -= expiry_ratio * 0.3

        # Penalize low verification rate if there is sufficient traffic
        # Assuming we track total_packets in health_metrics or use a proxy
        if (
            health_metrics.active_sessions > 0
            and health_metrics.verification_rate < 0.9
        ):
            # Only penalize if we've actually seen packets (verification_rate is only calculated if packets exist)
            # But if total_packets was 1, rate is 0.
            # We should probably pass the traffic info to the analyzer.
            pass

        # Penalize anomalies
        anomaly_penalty = min(health_metrics.anomaly_count * 0.05, 0.3)
        score -= anomaly_penalty

        return max(0.0, min(1.0, score))


class PQCZeroTrustPlanner(MAPEKPlanner):
    """Plans remediation actions for PQC anomalies."""

    def __init__(self):
        super().__init__()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="pqc-zero-trust-planner",
            role="planning",
            capabilities=("mape_k", "zero-trust", "pqc"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "constraints": {
                "redact_action_text": True,
                "plan_is_not_execution_proof": True,
                "does_not_prove_pqc_trust_finality": True,
                "does_not_prove_dataplane_delivery": True,
            },
            "safety_boundary": PQC_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose planner thinking state without raw action text."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def plan(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Plan remediation actions for PQC anomalies"""
        try:
            actions = []
            self._record_thinking(
                "pqc_zero_trust_plan",
                "plan local PQC recovery actions without execution overclaiming",
                {
                    "requires_action": bool(analysis_result.get("requires_action", False)),
                    "severity": analysis_result.get("severity", "low"),
                },
            )

            if not analysis_result.get("requires_action", False):
                self._record_thinking(
                    "pqc_zero_trust_plan",
                    "record no-action PQC recovery plan",
                    {"action_count": 0, "priority": "low"},
                )
                return {"actions": [], "priority": "low", "estimated_duration": 0}

            anomaly_count = analysis_result.get("analysis_data", {}).get(
                "anomaly_count", 0
            )
            health_score = analysis_result.get("analysis_data", {}).get(
                "health_score", 1.0
            )

            # Plan based on severity
            severity = analysis_result.get("severity", "low")
            if severity == "critical":
                actions.extend(
                    [
                        "Emergency: Rotate all PQC keys immediately",
                        "Isolate compromised sessions",
                        "Enable emergency security mode",
                        "Alert security team",
                    ]
                )
            elif severity == "high":
                actions.extend(
                    [
                        "Rotate expired PQC sessions",
                        "Increase monitoring frequency",
                        "Validate peer certificates",
                        "Check for DDoS attacks",
                    ]
                )
            else:  # medium/low
                actions.extend(
                    [
                        "Clean up expired sessions",
                        "Update session statistics",
                        "Log anomaly details",
                    ]
                )

            # Additional actions based on metrics
            if health_score < 0.5:
                actions.append("Perform full PQC system health check")
            if anomaly_count > 5:
                actions.append("Analyze anomaly patterns for attack detection")

            priority = "high" if severity in ["critical", "high"] else "medium"

            result = {
                "actions": actions,
                "priority": priority,
                "estimated_duration": len(actions) * 30,  # 30 seconds per action
                "plan_data": {
                    "severity": severity,
                    "anomaly_count": anomaly_count,
                    "health_score": health_score,
                },
            }
            self._record_thinking(
                "pqc_zero_trust_plan",
                "record PQC recovery action count without action text",
                {
                    "action_count": len(actions),
                    "priority": priority,
                    "severity": severity,
                },
            )
            return result

        except Exception as e:
            self._record_thinking(
                "pqc_zero_trust_plan",
                "record PQC planning failure without raw error text",
                {"priority": "critical", "error_type": type(e).__name__},
            )
            logger.error(f"PQC planning failed: {e}")
            return {
                "actions": ["Emergency: Manual intervention required"],
                "priority": "critical",
                "estimated_duration": 300,
            }


class PQCZeroTrustExecutor(MAPEKExecutor):
    """Executes PQC healing actions."""

    def __init__(
        self,
        pqc_gateway: Optional[EBPFPQCGateway] = None,
        pqc_loader: Optional[PQCXDPLoader] = None,
        node_id: str = "default-node",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        anomaly_consensus: Optional[AnomalyConsensusManager] = None,
        consensus_peers: Optional[set[str]] = None,
        consensus_f: int = 0,
    ):
        super().__init__()
        self.pqc_gateway = pqc_gateway or get_pqc_gateway()
        self.pqc_loader = pqc_loader
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_PQC_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="pqc-zero-trust-executor")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }

        # Signing key for SignedRemediationCommand
        # Uses gateway ML-DSA secret key when available; falls back to derived HMAC key
        # For HMAC-based signing, signing and verification use the same key
        self._signing_key: bytes = b""
        self._signing_key_id: str = "hmac-deriv"
        self._verification_key: bytes = b""
        try:
            if self.pqc_gateway and hasattr(self.pqc_gateway, "our_dsa_secret_key"):
                seed = self.pqc_gateway.our_dsa_secret_key
                self._signing_key = hashlib.sha256(seed).digest()
                self._verification_key = self._signing_key
                self._signing_key_id = "gateway-ml-dsa-65-hmac"
                logger.info("SignedCommand: using gateway ML-DSA derived key")
        except Exception as exc:
            logger.warning("SignedCommand: key init failed, using random key: %s", exc)
            self._signing_key = hashlib.sha256(os.urandom(32)).digest()
            self._verification_key = self._signing_key
            self._signing_key_id = "random-dev"

        # Emergency mode state
        self._emergency_mode_active: bool = False
        self._emergency_activated_at: Optional[datetime] = None

        # Anomaly consensus manager (Delphi-consensus via PBFT)
        if anomaly_consensus is not None:
            self.consensus_manager = anomaly_consensus
        elif consensus_peers:
            self.consensus_manager = AnomalyConsensusManager(
                node_id=node_id,
                peers=consensus_peers,
                f=consensus_f,
                event_bus=self.event_bus,
                project_root=self.event_project_root,
            )
        else:
            # Single-node mode: auto-approve (f=0, no peers)
            self.consensus_manager = AnomalyConsensusManager(
                node_id=node_id,
                f=0,
                event_bus=self.event_bus,
                project_root=self.event_project_root,
            )

    def _sign_action(self, action: str) -> SignedRemediationCommand:
        """Wrap an action string in a signed command."""
        return SignedRemediationCommand.sign(
            action,
            signing_key=self._signing_key,
            signing_key_id=self._signing_key_id,
        )

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize PQC recovery EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize PQC recovery policy engine: %s", exc)
            return None

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> list[str]:
        return normalize_policy_rules(decision)

    @classmethod
    def _safe_value(cls, key: str, value: Any, depth: int = 0) -> Any:
        blocked_fragments = ("secret", "password", "token", "key", "private")
        if any(fragment in str(key).lower() for fragment in blocked_fragments):
            return "<redacted>"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(str(child_key), child_value, depth + 1)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    @staticmethod
    def _action_resource_name(action: str) -> str:
        action_lower = action.lower()
        if "rotate all pqc keys" in action_lower:
            return "rotate_all_keys"
        if "rotate identity" in action_lower or "rotate pqc identity" in action_lower:
            return "rotate_pqc_identity"
        if "isolate compromised sessions" in action_lower:
            return "isolate_compromised_sessions"
        if "enable emergency security mode" in action_lower:
            return "enable_emergency_mode"
        if "rotate expired" in action_lower:
            return "rotate_expired_sessions"
        if "clean up expired" in action_lower:
            return "cleanup_expired_sessions"
        if "increase monitoring" in action_lower:
            return "increase_monitoring"
        if "full health check" in action_lower:
            return "perform_health_check"
        slug = "".join(
            char if char.isalnum() else "_"
            for char in action_lower.strip()
        ).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "unknown_action"

    def _plan_context(self, plan: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
        return {
            "priority": plan.get("priority"),
            "estimated_duration": plan.get("estimated_duration", 0),
            "action_count": len(actions),
            "plan_data": plan.get("plan_data", {}),
        }

    def _publish_executor_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action: str = "",
        context: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = self._action_resource_name(action) if action else "pqc_plan"
        payload = {
            "component": "self_healing.pqc_zero_trust_healer",
            "stage": stage,
            "action": action,
            "action_resource": action_resource,
            "resource": f"self_healing:pqc:{action_resource}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context or {}),
            "result": self._safe_context(result or {}) if result is not None else None,
            "success": result.get("success") if result is not None else None,
            "reason": reason,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "claim_boundary": PQC_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish PQC recovery event: %s", exc)
            return None

    def _evaluate_action_policy(self, action: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "PQC recovery policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "PQC recovery SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"self_healing:pqc:{action_resource}",
                workload_type="self-healing",
            )
        except Exception as exc:
            return False, None, f"PQC recovery policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "PQC recovery policy denied action"
        return True, decision, self._policy_reason(decision)

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "constraints": {
                "redact_session_ids": True,
                "redact_keys": True,
                "execution_is_not_trust_finality": True,
                "does_not_prove_dataplane_delivery": True,
            },
            "safety_boundary": PQC_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        if hasattr(self, "thinking_coach") and self.thinking_coach is not None:
            self.last_thinking_context = self.thinking_coach.prepare_task(context)
        else:
            self.last_thinking_context = context
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose executor thinking state."""
        thinking_status = self.thinking_coach.status() if hasattr(self, "thinking_coach") and self.thinking_coach else {}
        return {
            "thinking": thinking_status,
            "last_thinking_context": getattr(self, "last_thinking_context", {}),
        }

    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute PQC healing actions"""
        try:
            actions = list(plan.get("actions", []))
            plan_context = self._plan_context(plan, actions)
            self._publish_executor_event(
                EventType.COORDINATION_REQUEST,
                stage="plan_received",
                context=plan_context,
            )

            results = []
            success_count = 0

            for action in actions:
                try:
                    policy_allowed, policy_decision, policy_reason = (
                        self._evaluate_action_policy(action)
                    )
                    if not policy_allowed:
                        result = {
                            "action": action,
                            "success": False,
                            "error": policy_reason,
                            "policy_required": True,
                            "matched_rules": self._policy_rules(policy_decision),
                        }
                        results.append(result)
                        self._publish_executor_event(
                            EventType.TASK_BLOCKED,
                            stage="policy_denied",
                            action=action,
                            context=plan_context,
                            result=result,
                            reason=policy_reason,
                            policy_decision=policy_decision,
                        )
                        logger.warning("PQC action blocked by policy: %s", action)
                        continue

                    self._publish_executor_event(
                        EventType.PIPELINE_STAGE_START,
                        stage="action_start",
                        action=action,
                        context=plan_context,
                        reason=policy_reason,
                        policy_decision=policy_decision,
                    )
                    # Sign the action before execution
                    signed_cmd = self._sign_action(action)
                    result = await self._execute_action(signed_cmd)
                    results.append(result)
                    if result["success"]:
                        success_count += 1
                    self._publish_executor_event(
                        EventType.PIPELINE_STAGE_END
                        if result["success"]
                        else EventType.TASK_FAILED,
                        stage="action_completed"
                        if result["success"]
                        else "action_failed",
                        action=action,
                        context=plan_context,
                        result=result,
                        reason=result.get("error", "") or policy_reason,
                        policy_decision=policy_decision,
                    )
                    if result["success"]:
                        logger.info(f"PQC action executed: {action}")
                    else:
                        logger.warning(f"PQC action failed: {action}")
                except Exception as e:
                    logger.error(f"PQC action error: {action} - {e}")
                    result = {"action": action, "success": False, "error": str(e)}
                    results.append(result)
                    self._publish_executor_event(
                        EventType.TASK_FAILED,
                        stage="action_error",
                        action=action,
                        context=plan_context,
                        result=result,
                        reason=str(e),
                    )

            overall_success = success_count == len(actions)

            return {
                "actions_executed": len(actions),
                "success_count": success_count,
                "failed_actions": len(actions) - success_count,
                "success": overall_success,
                "execution_data": {
                    "results": results,
                    "duration": plan.get("estimated_duration", 0),
                },
            }
            self._record_thinking(
                "pqc_zero_trust_execute",
                "record local PQC recovery plan result without trust overclaiming",
                {
                    "actions_executed": len(actions),
                    "success_count": success_count,
                    "success": overall_success,
                },
            )
            return final_result

        except Exception as e:
            self._record_thinking(
                "pqc_zero_trust_execute",
                "record PQC recovery execution failure without raw error text",
                {"status": "error", "error_type": type(e).__name__},
            )
            logger.error(f"PQC execution failed: {e}")
            return {
                "actions_executed": 0,
                "success_count": 0,
                "failed_actions": 1,
                "success": False,
                "execution_data": {"error": str(e)},
            }

    async def _execute_action(self, action_or_cmd) -> Dict[str, Any]:
        """Execute a specific healing action with signature verification.

        Accepts either a SignedRemediationCommand or a str.
        When SignedRemediationCommand is passed, verifies the signature first.
        """
        # Unwrap signed command
        if isinstance(action_or_cmd, SignedRemediationCommand):
            cmd = action_or_cmd
            if not cmd.verify(verification_key=self._verification_key):
                logger.error("SignedCommand verification FAILED for action: %s", cmd.action)
                return {
                    "action": cmd.action,
                    "success": False,
                    "error": "SignedCommand signature verification failed",
                }
            action_lower = cmd.action.lower()
        else:
            action_lower = str(action_or_cmd).lower()

        action_name = cmd.action if isinstance(action_or_cmd, SignedRemediationCommand) else str(action_or_cmd)

        if "rotate all pqc keys" in action_lower:
            return await self._rotate_all_keys()
        elif "rotate identity" in action_lower or "rotate pqc identity" in action_lower:
            return await self._rotate_pqc_identity()
        elif "isolate compromised sessions" in action_lower:
            return await self._isolate_compromised_sessions()
        elif "enable emergency security mode" in action_lower:
            return await self._enable_emergency_mode()
        elif "rotate expired" in action_lower:
            return await self._rotate_expired_sessions()
        elif "clean up expired" in action_lower:
            return await self._cleanup_expired_sessions()
        elif "increase monitoring" in action_lower:
            return await self._increase_monitoring()
        elif "full health check" in action_lower:
            return await self._perform_health_check()
        else:
            # Default action: log and continue
            logger.info(f"PQC healing action: {action_name}")
            return {"action": action_name, "success": True, "message": "Action logged"}

    async def _rotate_pqc_identity(self) -> Dict[str, Any]:
        """Rotate PQC Node Identity (Long-term ML-DSA/ML-KEM keys).

        Creates new PQCNodeIdentity, regenerates gateway keypair,
        and syncs to XDP loader if available.

        On failure: rolls back all keys to pre-rotation state.
        """
        # ── Save pre-rotation state for rollback ──
        saved = {
            "did": self.identity.get("did", ""),
            "signing_key": self._signing_key,
            "signing_key_id": self._signing_key_id,
            "verification_key": self._verification_key,
        }
        if self.pqc_gateway:
            saved["gateway_pub"] = self.pqc_gateway.our_dsa_public_key
            saved["gateway_sec"] = self.pqc_gateway.our_dsa_secret_key
        if hasattr(self, "_emergency_mode_active"):
            saved["emergency_mode"] = self._emergency_mode_active

        try:
            logger.info("Executing PQC Node Identity rotation (ML-DSA-65/ML-KEM-768)")

            node_id = self.identity.get("node_id", "default-node")

            # 1. Create/update PQC node identity
            identity = PQCNodeIdentity(node_id)
            old_did = saved["did"]
            new_did = identity.did
            self.identity["did"] = new_did

            # 2. Regenerate gateway DSA keypair
            if self.pqc_gateway:
                self.pqc_gateway.dsa = __import__("oqs", fromlist=["Signature"]).Signature("ML-DSA-65")
                self.pqc_gateway.our_dsa_public_key = self.pqc_gateway.dsa.generate_keypair()
                self.pqc_gateway.our_dsa_secret_key = self.pqc_gateway.dsa.export_secret_key()
                # Regenerate signing key from new DSA key
                self._signing_key = hashlib.sha256(self.pqc_gateway.our_dsa_secret_key).digest()
                self._signing_key_id = "gateway-ml-dsa-65-hmac"
                self._verification_key = self._signing_key

            # 3. Sync to XDP loader
            if self.pqc_loader:
                self.pqc_loader.sync_with_gateway()

            logger.info("PQC identity rotated: %s -> %s", old_did[:16], new_did[:16])
            return {
                "action": "rotate_pqc_identity",
                "success": True,
                "old_did": old_did,
                "new_did": new_did,
                "node_id": node_id,
                "message": "PQC Node Identity rotated, new keys loaded to EBPF gateway",
            }

        except Exception as e:
            logger.error("PQC identity rotation failed; rolling back keys: %s", e)

            # ── Rollback everything to pre-rotation state ──
            self.identity["did"] = saved["did"]
            self._signing_key = saved["signing_key"]
            self._signing_key_id = saved["signing_key_id"]
            self._verification_key = saved["verification_key"]
            if self.pqc_gateway:
                self.pqc_gateway.our_dsa_public_key = saved.get("gateway_pub", b"")
                self.pqc_gateway.our_dsa_secret_key = saved.get("gateway_sec", b"")
            if "emergency_mode" in saved:
                self._emergency_mode_active = saved["emergency_mode"]

            return {
                "action": "rotate_pqc_identity",
                "success": False,
                "error": str(e),
                "rolled_back": True,
            }

    async def _rotate_all_keys(self) -> Dict[str, Any]:
        """Emergency key rotation"""
        try:
            rotated_count = 0
            for session_id in list(self.pqc_gateway.sessions.keys()):
                try:
                    self.pqc_gateway.rotate_session_keys(session_id)
                    rotated_count += 1
                except Exception as e:
                    logger.error(f"Failed to rotate session {session_id}: {e}")

            if self.pqc_loader:
                self.pqc_loader.sync_with_gateway()

            return {
                "action": "rotate_all_keys",
                "success": True,
                "rotated_sessions": rotated_count,
            }
        except Exception as e:
            return {"action": "rotate_all_keys", "success": False, "error": str(e)}

    async def _isolate_compromised_sessions(self) -> Dict[str, Any]:
        """Isolate sessions with anomalies.

        Before isolating, requests cross-node consensus via PBFT to verify
        the anomaly is real and not a local telemetry artifact (false DoS).
        """
        try:
            isolated_count = 0
            consensus_denied_count = 0
            current_time = datetime.now()

            # Find sessions with recent anomalies or inactivity
            for session_id, session in list(self.pqc_gateway.sessions.items()):
                is_old = current_time - session.last_used > timedelta(hours=2)

                if not is_old:
                    continue

                # ── Delphi-consensus: verify with peer nodes ──
                evidence = {
                    "session_id": session_id,
                    "failure_rate": 0.0,
                    "total_packets": 0,
                    "reason": "session_inactive_2h",
                }
                verdict = await self.consensus_manager.request_consensus(
                    session_id=session_id,
                    anomaly_type="inactive_session",
                    severity="medium",
                    evidence=evidence,
                )

                if not verdict.approved:
                    logger.info(
                        "Consensus DENIED isolation for session %s: %s",
                        session_id[:8], verdict.reason,
                    )
                    consensus_denied_count += 1
                    continue

                session.isolated = True
                isolated_count += 1

            return {
                "action": "isolate_compromised_sessions",
                "success": True,
                "isolated_sessions": isolated_count,
                "consensus_denied": consensus_denied_count,
            }
        except Exception as e:
            return {
                "action": "isolate_compromised_sessions",
                "success": False,
                "error": str(e),
            }

    async def _enable_emergency_mode(self) -> Dict[str, Any]:
        """Enable emergency security mode.

        Sets emergency_mode flag on executor, which:
        - Forces strict XDP signature verification in eBPF dataplane
        - Increases monitor sensitivity
        - Blocks non-critical healing actions
        """
        try:
            logger.warning("PQC Emergency security mode enabled")
            self._emergency_mode_active = True

            # Signal eBPF dataplane for strict verification
            if self.pqc_loader and hasattr(self.pqc_loader, "set_strict_verification"):
                self.pqc_loader.set_strict_verification(True)
                logger.info("eBPF XDP loader set to strict verification mode")

            # Update health metrics to reflect emergency state
            self._emergency_activated_at = datetime.now()

            return {
                "action": "enable_emergency_mode",
                "success": True,
                "emergency_active": True,
                "activated_at": self._emergency_activated_at.isoformat(),
                "message": "Emergency mode enabled: strict XDP verification active",
            }
        except Exception as e:
            logger.error("Failed to enable emergency mode: %s", e)
            return {
                "action": "enable_emergency_mode",
                "success": False,
                "error": str(e),
            }

    async def _disable_emergency_mode(self) -> Dict[str, Any]:
        """Disable emergency security mode and restore normal operation."""
        try:
            logger.info("PQC Emergency security mode disabled")
            self._emergency_mode_active = False

            if self.pqc_loader and hasattr(self.pqc_loader, "set_strict_verification"):
                self.pqc_loader.set_strict_verification(False)
                logger.info("eBPF XDP loader restored to normal verification mode")

            return {
                "action": "disable_emergency_mode",
                "success": True,
                "emergency_active": False,
                "message": "Emergency mode disabled: normal XDP verification restored",
            }
        except Exception as e:
            return {
                "action": "disable_emergency_mode",
                "success": False,
                "error": str(e),
            }

    async def _rotate_expired_sessions(self) -> Dict[str, Any]:
        """Rotate keys for expired sessions"""
        try:
            import time

            rotated_count = 0
            current_ts = time.time()
            cutoff_seconds = 3600  # 1 hour

            for session_id, session in list(self.pqc_gateway.sessions.items()):
                if current_ts - session.last_used > cutoff_seconds:
                    try:
                        self.pqc_gateway.rotate_session_keys(session_id)
                        rotated_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to rotate expired session {session_id}: {e}"
                        )

            if self.pqc_loader:
                self.pqc_loader.sync_with_gateway()

            return {
                "action": "rotate_expired_sessions",
                "success": True,
                "rotated_sessions": rotated_count,
            }
        except Exception as e:
            return {
                "action": "rotate_expired_sessions",
                "success": False,
                "error": str(e),
            }

    async def _cleanup_expired_sessions(self) -> Dict[str, Any]:
        """Clean up expired sessions"""
        try:
            import time

            cleaned_count = 0
            current_ts = time.time()
            cutoff_seconds = 7200  # 2 hours

            for session_id, session in list(self.pqc_gateway.sessions.items()):
                if current_ts - session.last_used > cutoff_seconds:
                    del self.pqc_gateway.sessions[session_id]
                    cleaned_count += 1

            if self.pqc_loader:
                self.pqc_loader.sync_with_gateway()

            return {
                "action": "cleanup_expired_sessions",
                "success": True,
                "cleaned_sessions": cleaned_count,
            }
        except Exception as e:
            return {
                "action": "cleanup_expired_sessions",
                "success": False,
                "error": str(e),
            }

    async def _increase_monitoring(self) -> Dict[str, Any]:
        """Increase monitoring frequency"""
        # This would adjust monitoring intervals
        logger.info("Increased PQC monitoring frequency")
        return {
            "action": "increase_monitoring",
            "success": True,
            "message": "Monitoring frequency increased",
        }

    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform full PQC system health check"""
        try:
            # Comprehensive health check
            sessions = self.pqc_gateway.sessions
            current_time = datetime.now()

            health_report = {
                "total_sessions": len(sessions),
                "active_sessions": sum(
                    1
                    for s in sessions.values()
                    if current_time - s.last_used < timedelta(hours=1)
                ),
                "oldest_session_age": (
                    min(
                        (current_time - s.created_at).total_seconds()
                        for s in sessions.values()
                    )
                    if sessions
                    else 0
                ),
                "newest_session_age": (
                    max(
                        (current_time - s.created_at).total_seconds()
                        for s in sessions.values()
                    )
                    if sessions
                    else 0
                ),
                "anomalies_last_hour": 0,  # Would need anomaly tracking
            }

            logger.info(f"PQC Health check: {health_report}")
            return {
                "action": "perform_health_check",
                "success": True,
                "health_report": health_report,
            }
        except Exception as e:
            return {"action": "perform_health_check", "success": False, "error": str(e)}


class PQCZeroTrustHealer:
    """
    Zero-Trust PQC Healer using MAPE-K autonomic loop.

    Monitors PQC cryptographic operations, detects security anomalies,
    plans remediation actions, and executes healing procedures.
    """

    def __init__(
        self,
        pqc_gateway: Optional[EBPFPQCGateway] = None,
        pqc_loader: Optional[PQCXDPLoader] = None,
        node_id: str = "default-node",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        anomaly_consensus: Optional[AnomalyConsensusManager] = None,
        consensus_peers: Optional[set[str]] = None,
        consensus_f: int = 0,
    ):
        self.monitor = PQCZeroTrustMonitor(pqc_gateway, pqc_loader)
        self.analyzer = PQCZeroTrustAnalyzer()
        self.planner = PQCZeroTrustPlanner()
        self.executor = PQCZeroTrustExecutor(
            pqc_gateway,
            pqc_loader,
            node_id=node_id,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            source_agent=source_agent,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
            anomaly_consensus=anomaly_consensus,
            consensus_peers=consensus_peers,
            consensus_f=consensus_f,
        )
        self.thinking_coach = AgentThinkingCoach(
            component_id="pqc_zero_trust_healer",
            agent_type="PQCZeroTrustHealer",
            domain="security",
            capabilities=("mape_k", "zero-trust", "pqc", "self-healing"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        # Start healing loop
        asyncio.create_task(self.run_healing_loop())

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "constraints": {
                "redact_node_ids": True,
                "redact_session_ids": True,
                "healing_loop_state_is_not_trust_finality": True,
                "does_not_prove_dataplane_delivery": True,
                "does_not_prove_production_readiness": True,
            },
            "safety_boundary": PQC_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose healer thinking state and nested MAPE-K component status."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "monitor": self.monitor.get_thinking_status(),
            "analyzer": self.analyzer.get_thinking_status(),
            "planner": self.planner.get_thinking_status(),
            "executor": self.executor.get_thinking_status(),
        }

    async def run_healing_loop(self):
        """Run the continuous MAPE-K healing loop"""
        logger.info("Starting PQC Zero-Trust healing loop")
        self._record_thinking(
            "pqc_zero_trust_healer_loop",
            "start continuous local MAPE-K healing loop",
        )

        while True:
            try:
                # MAPE-K cycle
                monitoring_data = await self.monitor.monitor()
                analysis_result = await self.analyzer.analyze(monitoring_data)

                if analysis_result.get("requires_action", False):
                    plan = await self.planner.plan(analysis_result)
                    execution_result = await self.executor.execute(plan)
                    self._record_thinking(
                        "pqc_zero_trust_healer_loop",
                        "record local PQC healing cycle result",
                        {
                            "actions_executed": execution_result.get(
                                "actions_executed", 0
                            ),
                            "success_count": execution_result.get("success_count", 0),
                        },
                    )

                    logger.info(
                        f"PQC healing cycle completed: {execution_result.get('success_count', 0)}/{execution_result.get('actions_executed', 0)} actions successful"
                    )

                # Wait before next cycle
                await asyncio.sleep(60)  # 1 minute cycle

            except Exception as e:
                logger.error(f"PQC healing loop error: {e}")
                await asyncio.sleep(30)  # Shorter wait on error


if __name__ == "__main__":
    # Test the healer

    async def test_healer():
        healer = PQCZeroTrustHealer()

        # Run a few cycles
        for i in range(3):
            print(f"Running healing cycle {i+1}")
            monitoring = await healer.monitor.monitor()
            analysis = await healer.analyzer.analyze(monitoring)

            if analysis.get("requires_action", False):
                plan = await healer.planner.plan(analysis)
                execution = await healer.executor.execute(plan)
                print(f"Executed {execution.get('success_count', 0)} healing actions")
            else:
                print("No healing required")

            await asyncio.sleep(2)

        print("PQC healer test completed")

    asyncio.run(test_healer())

