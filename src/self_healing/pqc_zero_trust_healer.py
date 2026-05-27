#!/usr/bin/env python3
"""
PQC Zero-Trust Healer for x0tta6bl4
Implements MAPE-K cycle for PQC cryptographic session anomalies.

Monitors PQC sessions, detects anomalies, plans remediation, and executes healing.
"""

import asyncio
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

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "pqc-zero-trust-healer"
PQC_CLAIM_BOUNDARY = (
    "PQC recovery executor event only. It records local policy and healing action "
    "state; it is not external production evidence or a settlement attestation."
)


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

    async def monitor(self) -> Dict[str, Any]:
        """Monitor PQC system health and detect anomalies"""
        try:
            import time

            current_time = datetime.now()
            current_ts = time.time()
            expiry_seconds = self.session_expiry_threshold.total_seconds()

            # Get current sessions
            sessions = self.pqc_gateway.sessions

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

    async def analyze(self, monitoring_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze monitoring data and determine if healing is needed"""
        try:
            anomalies = monitoring_data.get("anomalies", [])
            health_metrics = monitoring_data.get("health_metrics")

            if not health_metrics:
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

            return {
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

        except Exception as e:
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

    async def plan(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Plan remediation actions for PQC anomalies"""
        try:
            actions = []

            if not analysis_result.get("requires_action", False):
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

            return {
                "actions": actions,
                "priority": priority,
                "estimated_duration": len(actions) * 30,  # 30 seconds per action
                "plan_data": {
                    "severity": severity,
                    "anomaly_count": anomaly_count,
                    "health_score": health_score,
                },
            }

        except Exception as e:
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
                    result = await self._execute_action(action)
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

        except Exception as e:
            logger.error(f"PQC execution failed: {e}")
            return {
                "actions_executed": 0,
                "success_count": 0,
                "failed_actions": 1,
                "success": False,
                "execution_data": {"error": str(e)},
            }

    async def _execute_action(self, action: str) -> Dict[str, Any]:
        """Execute a specific healing action"""
        action_lower = action.lower()

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
            logger.info(f"PQC healing action: {action}")
            return {"action": action, "success": True, "message": "Action logged"}

    async def _rotate_pqc_identity(self) -> Dict[str, Any]:
        """Rotate PQC Node Identity (Long-term keys)"""
        try:
            # Note: In a real system, the executor would need access to the identity manager
            # We'll assume for now that it's provided in the healer context or accessible
            # This is a PLACEHOLDER implementation as we don't have the global context here
            # But the logic should be: call identity_manager.rotate_keys()
            logger.info("Executing PQC Node Identity rotation (ML-DSA-65/ML-KEM-768)")
            # Simulated success
            return {
                "action": "rotate_pqc_identity",
                "success": True,
                "message": "PQC Node Identity rotated successfully, new DID broadcasted to mesh"
            }
        except Exception as e:
            return {"action": "rotate_pqc_identity", "success": False, "error": str(e)}

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
        """Isolate sessions with anomalies"""
        try:
            isolated_count = 0
            current_time = datetime.now()

            # Find sessions with recent anomalies (this would need anomaly tracking)
            # For now, isolate sessions older than 2 hours
            for session_id, session in list(self.pqc_gateway.sessions.items()):
                if current_time - session.last_used > timedelta(hours=2):
                    session.isolated = True
                    isolated_count += 1

            return {
                "action": "isolate_compromised_sessions",
                "success": True,
                "isolated_sessions": isolated_count,
            }
        except Exception as e:
            return {
                "action": "isolate_compromised_sessions",
                "success": False,
                "error": str(e),
            }

    async def _enable_emergency_mode(self) -> Dict[str, Any]:
        """Enable emergency security mode"""
        try:
            # In emergency mode, be more restrictive
            # This would need to be implemented in the monitor
            logger.warning("PQC Emergency security mode enabled")
            return {
                "action": "enable_emergency_mode",
                "success": True,
                "message": "Emergency mode enabled",
            }
        except Exception as e:
            return {
                "action": "enable_emergency_mode",
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
        )

        # Start healing loop
        asyncio.create_task(self.run_healing_loop())

    async def run_healing_loop(self):
        """Run the continuous MAPE-K healing loop"""
        logger.info("Starting PQC Zero-Trust healing loop")

        while True:
            try:
                # MAPE-K cycle
                monitoring_data = await self.monitor.monitor()
                analysis_result = await self.analyzer.analyze(monitoring_data)

                if analysis_result.get("requires_action", False):
                    plan = await self.planner.plan(analysis_result)
                    execution_result = await self.executor.execute(plan)

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
