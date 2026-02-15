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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.security.spiffe import AttestationStrategy, SPIFFEController
from src.security.spiffe.workload import JWTSVID, X509SVID

logger = logging.getLogger(__name__)


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

        self.spiffe_controller = SPIFFEController(trust_domain=trust_domain)

        # State tracking
        self.current_identities: Dict[str, Dict[str, Any]] = {}
        self.identity_history: List[IdentityAnomalyAlert] = []
        self.trust_bundle_version = 0

        logger.info(f"✅ SPIFFE MAPE-K loop initialized (domain: {trust_domain})")

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

        for action in plan_data.get("actions", []):
            try:
                action_type = action["action_type"]
                logger.info(f"Executing: {action_type} - {action['description']}")

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

                if result.get("success", False):
                    results["actions_executed"] += 1
                else:
                    results["actions_failed"] += 1
                    logger.error(
                        f"Action failed: {result.get('error', 'unknown error')}"
                    )

            except Exception as e:
                logger.error(f"Execute error for {action['action_type']}: {e}")
                results["actions_failed"] += 1
                results["results"].append(
                    {
                        "action_type": action["action_type"],
                        "success": False,
                        "error": str(e),
                    }
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

    async def _revoke_identity(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Revoke current identity (placeholder)."""
        logger.warning("Revoking identity (placeholder implementation)")
        return {"success": True, "revoked": True}

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
