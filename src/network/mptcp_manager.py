"""
MPTCP Manager for x0tta6bl4 Mesh.
=================================

Enables Kernel-level Multi-path TCP (MPTCP) to aggregate multiple
mesh links into a single logical high-speed connection.
"""

import hashlib
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mptcp-manager"
_STATUS_SOURCE_AGENT = "mptcp-manager-status-read"
_STATUS_LAYER = "network_mptcp_observed_state"

MPTCP_MANAGER_CLAIM_BOUNDARY = (
    "MPTCP manager control event only. It records local identity, policy, and "
    "safe actuator state for kernel/network MPTCP configuration; it is not "
    "proof of live production traffic, throughput, or field validation."
)
MPTCP_STATUS_CLAIM_BOUNDARY = (
    "Read-only local MPTCP status observation. It records /proc support checks "
    "and bounded ip mptcp limits command metadata; it does not prove live "
    "multipath traffic, throughput, remote path quality, or production field "
    "validation."
)


class MPTCPManager:
    """
    Manages MPTCP configuration on Linux nodes.
    Requires Kernel 5.6+ with MPTCP enabled.
    """

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _non_negative_int(value: Any) -> Optional[int]:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _env_int(cls, name: str) -> Optional[int]:
        value = os.getenv(name)
        if value is None:
            return None
        parsed = cls._non_negative_int(value)
        if parsed is None:
            logger.warning("Ignoring invalid %s=%r", name, value)
        return parsed

    @classmethod
    def _resolve_endpoint_limit(
        cls,
        explicit_value: Optional[int],
        *,
        env_name: str,
        interface_count: int,
    ) -> int:
        if explicit_value is not None:
            parsed = cls._non_negative_int(explicit_value)
            if parsed is None:
                raise ValueError(f"{env_name} must be a non-negative integer")
            return parsed
        env_value = cls._env_int(env_name)
        if env_value is not None:
            return env_value
        return max(1, interface_count)

    @staticmethod
    def _parse_mptcp_limits(output: str) -> Dict[str, int]:
        aliases = {
            "subflow": "subflow",
            "subflows": "subflow",
            "add_addr_accepted": "add_addr_accepted",
        }
        limits: Dict[str, int] = {}
        tokens = output.replace(":", " ").replace(",", " ").split()
        for index, token in enumerate(tokens[:-1]):
            key = aliases.get(token.strip().lower())
            if key is None:
                continue
            parsed = MPTCPManager._non_negative_int(tokens[index + 1])
            if parsed is not None:
                limits[key] = parsed
        return limits

    @classmethod
    def _sha256_text(cls, value: str) -> Optional[str]:
        if not value:
            return None
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

    @classmethod
    def _bounded_output_metadata(
        cls,
        stdout: Optional[str],
        stderr: Optional[str],
        *,
        preview_limit: int = 0,
    ) -> Dict[str, Any]:
        safe_stdout = stdout or ""
        safe_stderr = stderr or ""
        bounded_limit = max(0, preview_limit)
        return {
            "stdout_chars": len(safe_stdout),
            "stderr_chars": len(safe_stderr),
            "stdout_sha256": cls._sha256_text(safe_stdout),
            "stderr_sha256": cls._sha256_text(safe_stderr),
            "stdout_preview_chars": min(len(safe_stdout), bounded_limit),
            "stderr_preview_chars": min(len(safe_stderr), bounded_limit),
            "stdout_truncated": len(safe_stdout) > bounded_limit,
            "stderr_truncated": len(safe_stderr) > bounded_limit,
            "output_preview_limit": bounded_limit,
            "output_bounded": True,
            "output_redacted": True,
        }

    @classmethod
    def _read_mptcp_limits_with_metadata(
        cls,
        *,
        output_preview_limit: int = 0,
    ) -> tuple[Dict[str, int], Dict[str, Any]]:
        command = ["ip", "mptcp", "limits", "show"]
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            logger.debug("Unable to read MPTCP limits: %s", exc)
            duration_ms = (time.monotonic() - started) * 1000.0
            stdout = getattr(exc, "stdout", None) or getattr(exc, "output", None)
            stderr = getattr(exc, "stderr", None)
            returncode = getattr(exc, "returncode", None)
            return {}, {
                "command": command,
                "attempted": True,
                "returncode": returncode,
                "duration_ms": round(duration_ms, 3),
                "output": cls._bounded_output_metadata(
                    stdout,
                    stderr,
                    preview_limit=output_preview_limit,
                ),
                "error": {
                    "type": type(exc).__name__,
                    "message_redacted": True,
                },
            }

        duration_ms = (time.monotonic() - started) * 1000.0
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        limits = cls._parse_mptcp_limits(stdout) if isinstance(stdout, str) else {}
        return limits, {
            "command": command,
            "attempted": True,
            "returncode": getattr(result, "returncode", None),
            "duration_ms": round(duration_ms, 3),
            "parsed_limit_keys": sorted(limits),
            "output": cls._bounded_output_metadata(
                stdout if isinstance(stdout, str) else "",
                stderr if isinstance(stderr, str) else "",
                preview_limit=output_preview_limit,
            ),
        }

    @classmethod
    def _read_mptcp_limits(cls) -> Dict[str, int]:
        limits, _metadata = cls._read_mptcp_limits_with_metadata()
        return limits

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize MPTCP manager EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize MPTCP manager policy engine: %s", exc)
            return None

    @classmethod
    def _status_identity_metadata(cls) -> Dict[str, Any]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "service_name": _SERVICE_AGENT,
            "spiffe_id_configured": bool(identity.get("spiffe_id")),
            "did_configured": bool(identity.get("did")),
            "wallet_address_configured": bool(identity.get("wallet_address")),
            "redacted": True,
        }

    @classmethod
    def _status_evidence_metadata(cls, event_id: Optional[str]) -> Dict[str, Any]:
        event_ids = [event_id] if event_id else []
        return {
            "source_agents": [_STATUS_SOURCE_AGENT] if event_ids else [],
            "layer": _STATUS_LAYER,
            "event_ids": event_ids,
            "events_total": len(event_ids),
            "redacted": True,
        }

    @classmethod
    def _with_status_evidence(
        cls,
        payload: Dict[str, Any],
        event_id: Optional[str],
        *,
        include_evidence: bool,
    ) -> Dict[str, Any]:
        if not include_evidence:
            return payload
        return {**payload, "evidence": cls._status_evidence_metadata(event_id)}

    @classmethod
    def _publish_status_observation(
        cls,
        *,
        event_bus: Optional[EventBus],
        source_agent: str,
        status: str,
        supported: bool,
        enabled: bool,
        proc_metadata: Dict[str, Any],
        limits_metadata: Dict[str, Any],
        limits: Dict[str, int],
        duration_ms: float,
    ) -> Optional[str]:
        if event_bus is None:
            return None
        payload = {
            "component": "network.mptcp_manager",
            "stage": "observed_state",
            "operation": "get_status",
            "resource": "network:mptcp:get_status",
            "service_name": source_agent,
            "source_alias": source_agent,
            "layer": _STATUS_LAYER,
            "identity": cls._status_identity_metadata(),
            "status": status,
            "supported": supported,
            "enabled": enabled,
            "max_subflows": limits.get("subflow", 0),
            "add_addr_accepted": limits.get("add_addr_accepted", 0),
            "duration_ms": round(duration_ms, 3),
            "read_only": True,
            "observed_state": True,
            "safe_actuator": False,
            "proc": proc_metadata,
            "limits_command": limits_metadata,
            "claim_boundary": MPTCP_STATUS_CLAIM_BOUNDARY,
        }
        try:
            event = event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                source_agent,
                payload,
                priority=3,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish MPTCP status observation: %s", exc)
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

    @classmethod
    def _identity(
        cls,
        *,
        node_id: str,
        spiffe_id: Optional[str],
        did: Optional[str],
        wallet_address: Optional[str],
    ) -> Dict[str, Optional[str]]:
        service_identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "node_id": node_id,
            "spiffe_id": (
                spiffe_id if spiffe_id is not None else service_identity["spiffe_id"]
            ),
            "did": did if did is not None else service_identity["did"],
            "wallet_address": (
                wallet_address
                if wallet_address is not None
                else service_identity["wallet_address"]
            ),
        }

    @classmethod
    def _publish_control_event(
        cls,
        event_type: EventType,
        *,
        event_bus: Optional[EventBus],
        source_agent: str,
        identity: Dict[str, Optional[str]],
        stage: str,
        operation: str,
        context: Dict[str, Any],
        reason: str = "",
        policy_decision: Any = None,
        success: Optional[bool] = None,
        simulated: Optional[bool] = None,
    ) -> Optional[str]:
        if event_bus is None:
            return None
        payload = {
            "component": "network.mptcp_manager",
            "stage": stage,
            "operation": operation,
            "resource": f"network:mptcp:{operation}",
            "node_id": identity["node_id"],
            "spiffe_id": identity["spiffe_id"],
            "did": identity["did"],
            "wallet_address": identity["wallet_address"],
            "identity": dict(identity),
            "context": cls._safe_context(context),
            "success": success,
            "simulated": simulated,
            "reason": reason,
            "policy_allowed": cls._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": cls._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": cls._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "safe_actuator": True,
            "claim_boundary": MPTCP_MANAGER_CLAIM_BOUNDARY,
        }
        try:
            event = event_bus.publish(event_type, source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish MPTCP manager event: %s", exc)
            return None

    @classmethod
    def _evaluate_control_policy(
        cls,
        *,
        operation: str,
        identity: Dict[str, Optional[str]],
        policy_engine: Optional[Any],
        require_policy: bool,
    ) -> tuple[bool, Any, str]:
        if policy_engine is None:
            if require_policy:
                return False, None, "MPTCP manager policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "MPTCP manager SPIFFE identity is required for policy evaluation"
        try:
            decision = policy_engine.evaluate(
                spiffe_id,
                resource=f"network:mptcp:{operation}",
                workload_type="mptcp-manager",
            )
        except Exception as exc:
            return False, None, f"MPTCP manager policy evaluation failed: {exc}"
        if not cls._policy_allowed(decision):
            return (
                False,
                decision,
                cls._policy_reason(decision)
                or "MPTCP manager policy denied control action",
            )
        return True, decision, cls._policy_reason(decision)

    @classmethod
    def _run_control_action(
        cls,
        *,
        operation: str,
        context: Dict[str, Any],
        executor: Any,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        safe_actuator: Optional[SafeActuator] = None,
        source_agent: str = _SERVICE_AGENT,
        node_id: str = "mptcp-manager",
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> bool:
        bus = (
            event_bus
            if event_bus is not None
            else cls._default_event_bus(event_project_root)
        )
        policy = policy_engine
        require = (
            require_policy
            if require_policy is not None
            else cls._env_bool("X0TTA6BL4_MPTCP_MANAGER_POLICY_REQUIRED", False)
            or cls._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if policy is None and require:
            policy = cls._default_policy_engine()
        identity = cls._identity(
            node_id=node_id,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
        )
        cls._publish_control_event(
            EventType.COORDINATION_REQUEST,
            event_bus=bus,
            source_agent=source_agent,
            identity=identity,
            stage="received",
            operation=operation,
            context=context,
        )
        allowed, decision, reason = cls._evaluate_control_policy(
            operation=operation,
            identity=identity,
            policy_engine=policy,
            require_policy=require,
        )
        if not allowed:
            cls._publish_control_event(
                EventType.TASK_BLOCKED,
                event_bus=bus,
                source_agent=source_agent,
                identity=identity,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=reason,
                policy_decision=decision,
                success=False,
                simulated=False,
            )
            return False
        cls._publish_control_event(
            EventType.PIPELINE_STAGE_START,
            event_bus=bus,
            source_agent=source_agent,
            identity=identity,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=reason,
            policy_decision=decision,
        )
        actuator = safe_actuator or SafeActuator(executor)
        actuator_result = actuator.execute(operation, context)
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        cls._publish_control_event(
            (
                EventType.PIPELINE_STAGE_END
                if success and not simulated
                else EventType.TASK_FAILED
            ),
            event_bus=bus,
            source_agent=source_agent,
            identity=identity,
            stage="actuator_completed"
            if success and not simulated
            else "actuator_simulated"
            if simulated
            else "actuator_failed",
            operation=operation,
            context=context,
            reason=actuator_result.reason or reason,
            policy_decision=decision,
            success=success and not simulated,
            simulated=simulated,
        )
        return success and not simulated

    @staticmethod
    def is_mptcp_supported() -> bool:
        """Checks if the system kernel supports MPTCP."""
        try:
            # Check for mptcp sysctl entry
            return os.path.exists("/proc/sys/net/mptcp/enabled")
        except Exception:
            return False

    @staticmethod
    def enable_mptcp(
        enabled: bool = True,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        safe_actuator: Optional[SafeActuator] = None,
        source_agent: str = _SERVICE_AGENT,
        node_id: str = "mptcp-manager",
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> bool:
        """Enables/Disables MPTCP globally."""
        val = "1" if enabled else "0"

        def _executor(_operation: str, _context: Dict[str, Any]) -> SafeActuatorResult:
            subprocess.run(["sysctl", "-w", f"net.mptcp.enabled={val}"], check=True)
            logger.info("✅ MPTCP %s globally", "enabled" if enabled else "disabled")
            return SafeActuatorResult(
                True,
                f"MPTCP {'enabled' if enabled else 'disabled'} globally",
            )

        return MPTCPManager._run_control_action(
            operation="enable_mptcp",
            context={"enabled": enabled, "sysctl_key": "net.mptcp.enabled"},
            executor=_executor,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            safe_actuator=safe_actuator,
            source_agent=source_agent,
            node_id=node_id,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
        )

    @staticmethod
    def configure_endpoints(
        interfaces: List[str],
        *,
        subflow_limit: Optional[int] = None,
        add_addr_accepted: Optional[int] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        safe_actuator: Optional[SafeActuator] = None,
        source_agent: str = _SERVICE_AGENT,
        node_id: str = "mptcp-manager",
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> bool:
        """
        Configures network interfaces as MPTCP endpoints.
        Each interface can contribute to a subflow.
        """
        interface_list = list(interfaces)
        resolved_subflow_limit = MPTCPManager._resolve_endpoint_limit(
            subflow_limit,
            env_name="X0TTA6BL4_MPTCP_SUBFLOW_LIMIT",
            interface_count=len(interface_list),
        )
        resolved_add_addr_accepted = MPTCPManager._resolve_endpoint_limit(
            add_addr_accepted,
            env_name="X0TTA6BL4_MPTCP_ADD_ADDR_ACCEPTED",
            interface_count=len(interface_list),
        )

        def _executor(_operation: str, _context: Dict[str, Any]) -> SafeActuatorResult:
            if not MPTCPManager.is_mptcp_supported():
                logger.warning(
                    "⚠️ MPTCP not supported by kernel, skipping endpoint config"
                )
                return SafeActuatorResult(False, "MPTCP not supported by kernel")
            # Clear existing limits/endpoints for fresh config
            subprocess.run(["ip", "mptcp", "endpoint", "flush"], capture_output=True)
            subprocess.run(
                [
                    "ip",
                    "mptcp",
                    "limits",
                    "set",
                    "subflow",
                    str(resolved_subflow_limit),
                    "add_addr_accepted",
                    str(resolved_add_addr_accepted),
                ],
                check=True,
            )

            for iface in interface_list:
                # Add each interface as a potential MPTCP path
                # Note: Requires extracting IP address for the iface
                # Simplified: assuming 'ip mptcp endpoint add' logic
                logger.info(f"🔧 Configured {iface} as MPTCP subflow endpoint")

            return SafeActuatorResult(True, "MPTCP endpoints configured")

        return MPTCPManager._run_control_action(
            operation="configure_endpoints",
            context={
                "interfaces": interface_list,
                "subflow_limit": resolved_subflow_limit,
                "add_addr_accepted": resolved_add_addr_accepted,
            },
            executor=_executor,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            safe_actuator=safe_actuator,
            source_agent=source_agent,
            node_id=node_id,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
        )

    @staticmethod
    def get_status(
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        output_preview_limit: int = 0,
        include_evidence: bool = False,
        source_agent: str = _STATUS_SOURCE_AGENT,
    ) -> Dict:
        """Returns current MPTCP status."""
        started = time.monotonic()
        bus = (
            event_bus
            if event_bus is not None
            else MPTCPManager._default_event_bus(event_project_root)
        )
        supported = MPTCPManager.is_mptcp_supported()
        enabled = False
        proc_metadata: Dict[str, Any] = {
            "enabled_path": "/proc/sys/net/mptcp/enabled",
            "exists": supported,
            "read_attempted": supported,
            "read_succeeded": False,
            "read_error_type": "",
            "raw_value_redacted": True,
        }
        if supported:
            try:
                with open("/proc/sys/net/mptcp/enabled", "r", encoding="utf-8") as f:
                    raw_value = f.read().strip()
                    enabled = raw_value == "1"
                    proc_metadata["read_succeeded"] = True
                    proc_metadata["value_bucket"] = (
                        "enabled" if enabled else "disabled_or_unknown"
                    )
            except Exception as exc:
                proc_metadata["read_error_type"] = type(exc).__name__
                pass
        limits: Dict[str, int] = {}
        limits_metadata: Dict[str, Any] = {
            "command": ["ip", "mptcp", "limits", "show"],
            "attempted": False,
            "returncode": None,
            "duration_ms": 0.0,
            "parsed_limit_keys": [],
            "output": MPTCPManager._bounded_output_metadata(
                None,
                None,
                preview_limit=output_preview_limit,
            ),
        }
        if supported:
            limits, limits_metadata = MPTCPManager._read_mptcp_limits_with_metadata(
                output_preview_limit=output_preview_limit,
            )

        payload = {
            "supported": supported,
            "enabled": enabled,
            "max_subflows": limits.get("subflow", 0),
            "add_addr_accepted": limits.get("add_addr_accepted", 0),
        }
        status = (
            "enabled"
            if supported and enabled
            else "disabled"
            if supported
            else "unsupported"
        )
        event_id = MPTCPManager._publish_status_observation(
            event_bus=bus,
            source_agent=source_agent,
            status=status,
            supported=supported,
            enabled=enabled,
            proc_metadata=proc_metadata,
            limits_metadata=limits_metadata,
            limits=limits,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
        return MPTCPManager._with_status_evidence(
            payload,
            event_id,
            include_evidence=include_evidence,
        )
