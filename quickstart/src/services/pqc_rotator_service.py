from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import AsyncSafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

# Configuration
PQC_ID_FILE = Path(".tmp/pqc_identity.txt")
ROTATION_INTERVAL = 3600  # 1 hour for high-security MVP

_SERVICE_AGENT = "pqc-rotator"

PQC_ROTATOR_CLAIM_BOUNDARY = (
    "PQC identity rotation event only. It records local identity, policy, "
    "safe actuator, key-generation, and report-signing state; it is not "
    "external settlement evidence or proof of production rollout."
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pqc-rotator")


def _generate_report_lazy() -> Any:
    try:
        from src.services.generate_partisan_report import generate_report
    except BaseException as exc:
        raise RuntimeError(f"PQC report generator import failed: {exc}") from exc

    try:
        return generate_report()
    except BaseException as exc:
        raise RuntimeError(f"PQC report generator failed: {exc}") from exc


class PQCRotatorService:
    """Policy-gated service wrapper for PQC identity rotation."""

    def __init__(
        self,
        *,
        identity_file: Path = PQC_ID_FILE,
        temp_identity_file: Optional[Path] = None,
        rotation_interval: int = ROTATION_INTERVAL,
        signer_cmd: Optional[Sequence[str]] = None,
        process_factory: Optional[Callable[..., Any]] = None,
        report_generator: Optional[Callable[[], Any]] = _generate_report_lazy,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[Any] = None,
    ):
        self.identity_file = Path(identity_file)
        self.temp_identity_file = (
            Path(temp_identity_file)
            if temp_identity_file is not None
            else self.identity_file.with_suffix(".new")
        )
        self.rotation_interval = rotation_interval
        self.signer_cmd = tuple(
            signer_cmd
            or ("./venv/bin/python3", "pqc_signer.py", "--algorithm", "ML-DSA-65", "generate-keys")
        )
        self.process_factory = process_factory or asyncio.create_subprocess_exec
        self.report_generator = report_generator
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_PQC_ROTATOR_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="pqc-rotator")
        self.identity = {
            "node_id": "pqc-rotator",
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self.safe_actuator = safe_actuator or AsyncSafeActuator(self._rotate_identity_internal)

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
            logger.error("Failed to initialize PQC rotator EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize PQC rotator policy engine: %s", exc)
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
        if isinstance(value, (list, tuple)) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    def _rotation_context(self) -> Dict[str, Any]:
        return {
            "identity_file": str(self.identity_file),
            "temp_identity_file": str(self.temp_identity_file),
            "signer_command": self.signer_cmd[0] if self.signer_cmd else "",
            "signer_args_count": max(len(self.signer_cmd) - 1, 0),
            "report_generator": bool(self.report_generator),
        }

    def _publish_rotation_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "services.pqc_rotator_service",
            "stage": stage,
            "action_type": "rotate_identity",
            "resource": "services:pqc_rotator:rotate_identity",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
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
            "safe_actuator": True,
            "claim_boundary": PQC_ROTATOR_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish PQC rotator event: %s", exc)
            return None

    def _evaluate_policy(self) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "PQC rotator policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "PQC rotator SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource="services:pqc_rotator:rotate_identity",
                workload_type="pqc-rotator",
            )
        except Exception as exc:
            return False, None, f"PQC rotator policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "PQC rotator policy denied rotation"
        return True, decision, self._policy_reason(decision)

    async def rotate_once(self) -> Dict[str, Any]:
        """Run one fail-closed PQC identity rotation attempt."""
        context = self._rotation_context()
        result = {
            "success": False,
            "action_type": "rotate_identity",
            "identity_file": str(self.identity_file),
            "safe_actuator": True,
        }
        self._publish_rotation_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            context=context,
        )

        policy_allowed, policy_decision, policy_reason = self._evaluate_policy()
        if not policy_allowed:
            result.update({
                "error": policy_reason,
                "policy_required": True,
                "matched_rules": self._policy_rules(policy_decision),
            })
            self._publish_rotation_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                context=context,
                result=result,
                reason=policy_reason,
                policy_decision=policy_decision,
            )
            return result

        self._publish_rotation_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )

        actuator_result = await self.safe_actuator.execute("rotate_identity", context)
        if actuator_result.simulated:
            reason = actuator_result.reason or "safe actuator returned simulated result"
            result.update({"error": reason, "simulated": True})
            self._publish_rotation_event(
                EventType.TASK_FAILED,
                stage="actuator_simulated",
                context=context,
                result=result,
                reason=reason,
                policy_decision=policy_decision,
            )
            return result

        if actuator_result.success:
            result.update({
                "success": True,
                "reason": actuator_result.reason or policy_reason,
                "simulated": actuator_result.simulated,
            })
            self._publish_rotation_event(
                EventType.PIPELINE_STAGE_END,
                stage="actuator_completed",
                context=context,
                result=result,
                reason=actuator_result.reason or policy_reason,
                policy_decision=policy_decision,
            )
            return result

        reason = actuator_result.reason or "PQC rotator safe actuator failed"
        result.update({"error": reason, "simulated": actuator_result.simulated})
        self._publish_rotation_event(
            EventType.TASK_FAILED,
            stage="actuator_failed",
            context=context,
            result=result,
            reason=reason,
            policy_decision=policy_decision,
        )
        return result

    async def _rotate_identity_internal(
        self,
        action: str,
        _context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if action != "rotate_identity":
            return SafeActuatorResult(False, f"unknown PQC rotator action: {action}")
        if not self.signer_cmd:
            return SafeActuatorResult(False, "PQC signer command is not configured")

        self.temp_identity_file.parent.mkdir(parents=True, exist_ok=True)
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.temp_identity_file, "wb") as stdout:
                proc = await self.process_factory(
                    *self.signer_cmd,
                    stdout=stdout,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                returncode = await proc.wait()
        except Exception as exc:
            self.temp_identity_file.unlink(missing_ok=True)
            return SafeActuatorResult(False, f"PQC signer execution failed: {exc}")

        if returncode != 0:
            self.temp_identity_file.unlink(missing_ok=True)
            return SafeActuatorResult(False, f"PQC signer exited with code {returncode}")

        self.temp_identity_file.replace(self.identity_file)

        try:
            if self.report_generator is not None:
                maybe_result = self.report_generator()
                if asyncio.iscoroutine(maybe_result):
                    await maybe_result
        except Exception as exc:
            return SafeActuatorResult(False, f"PQC report generation failed: {exc}")

        return SafeActuatorResult(True, "PQC identity rotated and report regenerated")

    async def run_forever(self) -> None:
        logger.info("Starting PQC identity rotation service")
        while True:
            result = await self.rotate_once()
            if result.get("success"):
                logger.info("PQC identity rotation completed")
            else:
                logger.error("PQC identity rotation failed: %s", result.get("error", "unknown error"))
            await asyncio.sleep(self.rotation_interval)


async def rotate_identity(service: Optional[PQCRotatorService] = None) -> None:
    rotator = service or PQCRotatorService()
    await rotator.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(rotate_identity())
    except KeyboardInterrupt:
        pass

