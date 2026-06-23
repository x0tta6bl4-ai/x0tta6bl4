"""
MAPE-K Loop Integration with SPIFFE/SPIRE Identity Management

Integrates Zero Trust identity provisioning into the MAPE-K autonomic loop:
- Monitor: Track identity expiration and revocation events
- Analyze: Detect identity anomalies and trust violations
- Plan: Schedule identity renewal and trust domain updates
- Execute: Provision and rotate SVIDs (Spiffe Verifiable Identity Documents)
- Knowledge: Maintain trust bundle and federation metadata

Example:
    >>> from src.self_healing.mape_k_spiffe_integration import SPIFFEMapEKLoop
    >>> loop = SPIFFEMapEKLoop()
    >>> asyncio.run(loop.execute_cycle())
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.security.spiffe import AttestationStrategy, SPIFFEController
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "spiffe-mapek-loop"
SPIFFE_CLAIM_BOUNDARY = (
    "SPIFFE MAPE-K recovery event only. It records local identity recovery "
    "policy and action state; it is not external production evidence."
)


@dataclass
class IdentityAnomalyAlert:
    """Alert for identity anomalies detected by MAPE-K"""

    anomaly_type: str  # "expiration_warning", "revocation", "trust_violation"
    workload_id: str
    spiffe_id: str
    severity: str  # "info", "warning", "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recommended_action: str = ""


class SPIFFEMapEKLoop:
    """
    MAPE-K loop with SPIFFE/SPIRE identity management.

    Continuously monitors and manages workload identities in the mesh.
    """

    def __init__(
        self,
        trust_domain: str = "x0tta6bl4.mesh",
        renewal_threshold: float = 0.5,  # Renew at 50% TTL
        check_interval: int = 300,  # Check every 5 minutes
        spiffe_controller: Optional[SPIFFEController] = None,
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
        """
        Initialize SPIFFE-integrated MAPE-K loop.

        Args:
            trust_domain: SPIFFE trust domain
            renewal_threshold: TTL fraction at which to renew (0.5 = 50%)
            check_interval: Seconds between monitoring cycles
        """
        self.trust_domain = trust_domain
        self.renewal_threshold = renewal_threshold
        self.check_interval = check_interval

        self.spiffe_controller = spiffe_controller or SPIFFEController(
            trust_domain=trust_domain,
            node_id=node_id,
        )
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_SPIFFE_MAPEK_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="spiffe-mapek-loop")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }

        # State tracking
        self.current_identities: Dict[str, Dict[str, Any]] = {}
        self.identity_history: List[IdentityAnomalyAlert] = []
        self.trust_bundle_version = 0

        logger.info(f"✅ SPIFFE MAPE-K loop initialized (domain: {trust_domain})")

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
            logger.error("Failed to initialize SPIFFE MAPE-K EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize SPIFFE MAPE-K policy engine: %s", exc)
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
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    @staticmethod
    def _action_resource_name(action_type: str) -> str:
        action_lower = str(action_type or "unknown_action").lower().strip()
        slug = "".join(
            char if char.isalnum() else "_"
            for char in action_lower
        ).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "unknown_action"

    def _plan_context(
        self,
        plan_data: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "priority": plan_data.get("priority"),
            "estimated_duration_seconds": plan_data.get(
                "estimated_duration_seconds",
                0,
            ),
            "action_count": len(actions),
            "phase": plan_data.get("phase"),
        }

    def _publish_recovery_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action_type: str = "",
        context: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = (
            self._action_resource_name(action_type) if action_type else "spiffe_plan"
        )
        payload = {
            "component": "self_healing.mape_k_spiffe_integration",
            "stage": stage,
            "action_type": action_type,
            "action_resource": action_resource,
            "resource": f"self_healing:spiffe:{action_resource}",
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
            "claim_boundary": SPIFFE_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish SPIFFE MAPE-K recovery event: %s", exc)
            return None

    def _evaluate_action_policy(self, action_type: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "SPIFFE MAPE-K policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "SPIFFE MAPE-K SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action_type)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"self_healing:spiffe:{action_resource}",
                workload_type="self-healing",
            )
        except Exception as exc:
            return False, None, f"SPIFFE MAPE-K policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "SPIFFE MAPE-K policy denied action"
        return True, decision, self._policy_reason(decision)

    async def initialize(self):
        """Initialize SPIFFE infrastructure."""
        try:
            logger.info("Initializing SPIFFE controller...")

            # Initialize with join token for development
            # In production, use AWS IID or Kubernetes PSAT attestation
            import os

            join_token = os.getenv("X0TTA6BL4_SPIRE_JOIN_TOKEN")
            if join_token is None:
                logger.error(
                    "X0TTA6BL4_SPIRE_JOIN_TOKEN environment variable is not set. Cannot proceed without a valid join token."
                )
                raise RuntimeError(
                    "X0TTA6BL4_SPIRE_JOIN_TOKEN environment variable is required"
                )

            self.spiffe_controller.initialize(
                attestation_strategy=AttestationStrategy.JOIN_TOKEN, token=join_token
            )

            logger.info("✅ SPIFFE initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SPIFFE: {e}")
            raise

    # === MONITOR PHASE ===
    async def monitor(self) -> Dict[str, Any]:
        """
        Monitor identity state and trust bundles.

        Returns:
            Dictionary with identity metrics and anomalies
        """
        logger.debug("MONITOR: Checking identity state...")

        try:
            # Get current workload identity
            workload_id = self.spiffe_controller.get_workload_id()
            current_svid = self.spiffe_controller.get_current_x509_svid()

            if not current_svid:
                logger.warning("No valid SVID available")
                return {"error": "no_valid_svid"}

            # Check expiration time
            now = datetime.utcnow()
            time_to_expiry = current_svid.expiry - now
            ttl_percentage = (
                time_to_expiry.total_seconds() / 3600.0
            ) * 100  # Assuming 1h TTL

            # Store identity state
            self.current_identities[workload_id] = {
                "spiffe_id": current_svid.spiffe_id,
                "expiry": current_svid.expiry,
                "ttl_remaining_seconds": time_to_expiry.total_seconds(),
                "ttl_percentage": ttl_percentage,
                "last_checked": now,
                "healthy": True,
            }

            # Detect anomalies
            anomalies = []

            # Check for expiration warning
            if ttl_percentage < (self.renewal_threshold * 100):
                alert = IdentityAnomalyAlert(
                    anomaly_type="expiration_warning",
                    workload_id=workload_id,
                    spiffe_id=current_svid.spiffe_id,
                    severity="warning",
                    message=f"SVID expires in {time_to_expiry.total_seconds():.0f}s ({ttl_percentage:.1f}% TTL remaining)",
                )
                anomalies.append(alert)
                logger.warning(f"⚠️ {alert.message}")

            # Check trust bundle freshness
            trust_bundle = self.spiffe_controller.get_trust_bundle()
            if (
                trust_bundle
                and trust_bundle.get("version", 0) != self.trust_bundle_version
            ):
                logger.info(
                    f"Trust bundle updated: v{self.trust_bundle_version} → v{trust_bundle['version']}"
                )
                self.trust_bundle_version = trust_bundle.get("version", 0)

            return {
                "phase": "MONITOR",
                "workload_id": workload_id,
                "spiffe_id": current_svid.spiffe_id,
                "ttl_remaining_seconds": time_to_expiry.total_seconds(),
                "ttl_percentage": ttl_percentage,
                "anomalies": anomalies,
                "status": "ok" if not anomalies else "alert",
            }

        except Exception as e:
            logger.error(f"Monitor phase error: {e}")
            return {"error": str(e), "phase": "MONITOR"}

    # === ANALYZE PHASE ===
    async def analyze(self, monitor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze identity metrics and detect patterns.

        Args:
            monitor_data: Output from monitor phase

        Returns:
            Analysis results with recommendations
        """
        logger.debug("ANALYZE: Analyzing identity state...")

        if "error" in monitor_data:
            return {"error": monitor_data["error"], "phase": "ANALYZE"}

        anomalies = monitor_data.get("anomalies", [])
        analysis = {
            "phase": "ANALYZE",
            "total_anomalies": len(anomalies),
            "anomaly_types": [a.anomaly_type for a in anomalies],
            "recommended_actions": [],
            "risk_level": "low",
        }

        for anomaly in anomalies:
            if anomaly.anomaly_type == "expiration_warning":
                analysis["recommended_actions"].append("renew_svid")
                analysis["risk_level"] = "medium"
                anomaly.recommended_action = "Renew SVID immediately"

            elif anomaly.anomaly_type == "revocation":
                analysis["recommended_actions"].append("revoke_and_re_attest")
                analysis["risk_level"] = "critical"
                anomaly.recommended_action = "Re-attest node identity"

            self.identity_history.append(anomaly)

        logger.info(
            f"📊 Analysis complete: {analysis['total_anomalies']} anomalies, risk_level={analysis['risk_level']}"
        )
        return analysis

    # === PLAN PHASE ===
    async def plan(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan recovery actions for identity management.

        Args:
            analysis_data: Output from analyze phase

        Returns:
            Plan with ordered recovery actions
        """
        logger.debug("PLAN: Planning recovery actions...")

        plan = {
            "phase": "PLAN",
            "actions": [],
            "priority": "normal",
            "estimated_duration_seconds": 0,
        }

        if "error" in analysis_data:
            return plan

        recommended_actions = analysis_data.get("recommended_actions", [])
        risk_level = analysis_data.get("risk_level", "low")

        # Assign priority based on risk
        if risk_level == "critical":
            plan["priority"] = "emergency"
        elif risk_level == "medium":
            plan["priority"] = "high"

        # Build action plan
        if "renew_svid" in recommended_actions:
            plan["actions"].append(
                {
                    "action_type": "renew_svid",
                    "description": "Renew SVID from SPIRE Agent",
                    "order": 1,
                    "timeout_seconds": 30,
                    "parameters": {
                        "renewal_threshold": self.renewal_threshold,
                        "timeout": 30,
                    },
                }
            )
            plan["estimated_duration_seconds"] += 30

        if "revoke_and_re_attest" in recommended_actions:
            plan["actions"].append(
                {
                    "action_type": "revoke_identity",
                    "description": "Revoke current identity",
                    "order": 2,
                    "timeout_seconds": 10,
                }
            )
            plan["actions"].append(
                {
                    "action_type": "re_attest",
                    "description": "Re-attest node identity with SPIRE",
                    "order": 3,
                    "timeout_seconds": 60,
                    "parameters": {
                        "attestation_strategy": "join_token"  # Override based on environment
                    },
                }
            )
            plan["estimated_duration_seconds"] += 70

        logger.info(
            f"📋 Plan created: {len(plan['actions'])} actions, priority={plan['priority']}"
        )
        return plan

    # === EXECUTE PHASE ===
    async def execute(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute identity recovery actions.

        Args:
            plan_data: Output from plan phase

        Returns:
            Execution results
        """
        logger.debug("EXECUTE: Running recovery actions...")

        results = {
            "phase": "EXECUTE",
            "actions_executed": 0,
            "actions_failed": 0,
            "results": [],
        }

        actions = list(plan_data.get("actions", []))
        plan_context = self._plan_context(plan_data, actions)
        self._publish_recovery_event(
            EventType.COORDINATION_REQUEST,
            stage="plan_received",
            context=plan_context,
        )

        for action in actions:
            action_type = str(action.get("action_type", "unknown_action"))
            try:
                logger.info(f"Executing: {action_type} - {action['description']}")

                policy_allowed, policy_decision, policy_reason = (
                    self._evaluate_action_policy(action_type)
                )
                if not policy_allowed:
                    result = {
                        "success": False,
                        "error": policy_reason,
                        "action_type": action_type,
                        "policy_required": True,
                        "matched_rules": self._policy_rules(policy_decision),
                    }
                    results["actions_failed"] += 1
                    results["results"].append(result)
                    self._publish_recovery_event(
                        EventType.TASK_BLOCKED,
                        stage="policy_denied",
                        action_type=action_type,
                        context={**plan_context, "action": action},
                        result=result,
                        reason=policy_reason,
                        policy_decision=policy_decision,
                    )
                    logger.warning("SPIFFE MAPE-K action blocked by policy: %s", action_type)
                    continue

                self._publish_recovery_event(
                    EventType.PIPELINE_STAGE_START,
                    stage="action_start",
                    action_type=action_type,
                    context={**plan_context, "action": action},
                    reason=policy_reason,
                    policy_decision=policy_decision,
                )

                if action_type == "renew_svid":
                    result = await self._renew_svid(action)
                elif action_type == "revoke_identity":
                    result = await self._revoke_identity(action)
                elif action_type == "re_attest":
                    result = await self._re_attest(action)
                else:
                    result = {
                        "success": False,
                        "error": f"Unknown action: {action_type}",
                    }

                result["action_type"] = action_type
                results["results"].append(result)
                self._publish_recovery_event(
                    EventType.PIPELINE_STAGE_END
                    if result.get("success", False)
                    else EventType.TASK_FAILED,
                    stage="action_completed"
                    if result.get("success", False)
                    else "action_failed",
                    action_type=action_type,
                    context={**plan_context, "action": action},
                    result=result,
                    reason=result.get("error", "") or policy_reason,
                    policy_decision=policy_decision,
                )

                if result.get("success", False):
                    results["actions_executed"] += 1
                else:
                    results["actions_failed"] += 1
                    logger.error(
                        f"Action failed: {result.get('error', 'unknown error')}"
                    )

            except Exception as e:
                logger.error(f"Execute error for {action_type}: {e}")
                results["actions_failed"] += 1
                result = {
                    "action_type": action_type,
                    "success": False,
                    "error": str(e),
                }
                results["results"].append(result)
                self._publish_recovery_event(
                    EventType.TASK_FAILED,
                    stage="action_error",
                    action_type=action_type,
                    context={**plan_context, "action": action},
                    result=result,
                    reason=str(e),
                )

        logger.info(
            f"✅ Execution complete: {results['actions_executed']} succeeded, {results['actions_failed']} failed"
        )
        return results

    async def _renew_svid(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Renew SVID from SPIRE Agent."""
        try:
            logger.info("Renewing SVID...")
            # This triggers automatic renewal in WorkloadAPIClient
            new_svid = self.spiffe_controller.get_current_x509_svid(force_renew=True)

            if new_svid and not new_svid.is_expired():
                logger.info(f"✅ SVID renewed: expires at {new_svid.expiry}")
                return {
                    "success": True,
                    "spiffe_id": new_svid.spiffe_id,
                    "new_expiry": new_svid.expiry.isoformat(),
                }
            else:
                return {"success": False, "error": "Failed to get valid SVID"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _entry_field(entry: Any, field: str) -> Any:
        if isinstance(entry, dict):
            return entry.get(field)
        return getattr(entry, field, None)

    def _resolve_revoke_spiffe_id(self, action: Dict[str, Any]) -> str:
        parameters = action.get("parameters") or {}
        explicit_id = parameters.get("spiffe_id") or parameters.get("target_spiffe_id")
        if explicit_id:
            return str(explicit_id)

        current_identity = getattr(self.spiffe_controller, "current_identity", None)
        current_id = getattr(current_identity, "spiffe_id", None)
        if current_id:
            return str(current_id)

        return str(self.identity.get("spiffe_id") or "")

    async def _revoke_identity(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Revoke a SPIFFE identity by deleting matching SPIRE entries."""
        target_spiffe_id = self._resolve_revoke_spiffe_id(action)
        if not target_spiffe_id:
            return {
                "success": False,
                "revoked": False,
                "error": "No target SPIFFE ID available for revocation",
            }

        controller_revoke = getattr(self.spiffe_controller, "revoke_identity", None)
        if callable(controller_revoke):
            revoked = bool(controller_revoke(target_spiffe_id))
            return {
                "success": revoked,
                "revoked": revoked,
                "spiffe_id": target_spiffe_id,
                "backend": "controller",
            }

        if hasattr(self.spiffe_controller, "list_registered_workloads"):
            entries = self.spiffe_controller.list_registered_workloads()
        else:
            server_client = getattr(self.spiffe_controller, "server_client", None)
            if server_client is None or not hasattr(server_client, "list_entries"):
                return {
                    "success": False,
                    "revoked": False,
                    "spiffe_id": target_spiffe_id,
                    "error": "SPIRE revocation backend is unavailable",
                }
            entries = server_client.list_entries()

        matches = [
            entry
            for entry in entries
            if self._entry_field(entry, "spiffe_id") == target_spiffe_id
        ]
        if not matches:
            return {
                "success": False,
                "revoked": False,
                "spiffe_id": target_spiffe_id,
                "error": "No matching SPIRE entry found for revocation",
            }

        server_client = getattr(self.spiffe_controller, "server_client", None)
        if server_client is None or not hasattr(server_client, "delete_entry"):
            return {
                "success": False,
                "revoked": False,
                "spiffe_id": target_spiffe_id,
                "error": "SPIRE entry delete backend is unavailable",
            }

        deleted_entry_ids: List[str] = []
        failed_entry_ids: List[str] = []
        for entry in matches:
            entry_id = self._entry_field(entry, "entry_id")
            if not entry_id:
                failed_entry_ids.append("<missing-entry-id>")
                continue
            if server_client.delete_entry(str(entry_id)):
                deleted_entry_ids.append(str(entry_id))
            else:
                failed_entry_ids.append(str(entry_id))

        success = bool(deleted_entry_ids) and not failed_entry_ids
        return {
            "success": success,
            "revoked": success,
            "spiffe_id": target_spiffe_id,
            "deleted_entry_ids": deleted_entry_ids,
            "failed_entry_ids": failed_entry_ids,
            "backend": "spire-server-entry-delete",
        }

    async def _re_attest(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Re-attest node identity with SPIRE."""
        try:
            logger.info("Re-attesting node identity...")
            # In production, use real attestation strategy
            import os

            join_token = os.getenv("X0TTA6BL4_SPIRE_JOIN_TOKEN")
            if join_token is None:
                logger.error(
                    "X0TTA6BL4_SPIRE_JOIN_TOKEN environment variable is not set. Cannot proceed without a valid join token."
                )
                raise RuntimeError(
                    "X0TTA6BL4_SPIRE_JOIN_TOKEN environment variable is required"
                )

            self.spiffe_controller.initialize(
                attestation_strategy=AttestationStrategy.JOIN_TOKEN, token=join_token
            )
            return {"success": True, "re_attested": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === KNOWLEDGE PHASE ===
    async def knowledge(self, execute_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update knowledge base with identity history and patterns.

        Args:
            execute_results: Output from execute phase

        Returns:
            Updated knowledge metrics
        """
        logger.debug("KNOWLEDGE: Updating identity knowledge base...")

        knowledge = {
            "phase": "KNOWLEDGE",
            "total_alerts": len(self.identity_history),
            "current_identities": len(self.current_identities),
            "trust_bundle_version": self.trust_bundle_version,
            "recent_anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.identity_history[-10:]  # Last 10 alerts
            ],
        }

        logger.info(
            f"📚 Knowledge: {knowledge['total_alerts']} total alerts, {knowledge['current_identities']} active identities"
        )
        return knowledge

    # === FULL CYCLE ===
    async def execute_cycle(self) -> Dict[str, Any]:
        """Execute one complete MAPE-K cycle."""
        logger.info("=" * 60)
        logger.info("Starting MAPE-K Identity Management Cycle")
        logger.info("=" * 60)

        try:
            # Monitor
            monitor_results = await self.monitor()
            logger.debug(f"Monitor results: {monitor_results}")

            # Analyze
            analysis_results = await self.analyze(monitor_results)
            logger.debug(f"Analysis results: {analysis_results}")

            # Plan
            plan_results = await self.plan(analysis_results)
            logger.debug(f"Plan results: {plan_results}")

            # Execute
            execute_results = await self.execute(plan_results)
            logger.debug(f"Execute results: {execute_results}")

            # Knowledge
            knowledge_results = await self.knowledge(execute_results)
            logger.debug(f"Knowledge results: {knowledge_results}")

            return {
                "monitor": monitor_results,
                "analyze": analysis_results,
                "plan": plan_results,
                "execute": execute_results,
                "knowledge": knowledge_results,
            }

        except Exception as e:
            logger.error(f"Cycle error: {e}")
            return {"error": str(e)}

    async def run_continuous(self):
        """Run MAPE-K loop continuously."""
        try:
            await self.initialize()

            while True:
                try:
                    await self.execute_cycle()
                    await asyncio.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"Cycle failed: {e}")
                    await asyncio.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("MAPE-K loop stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
