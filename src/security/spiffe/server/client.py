"""
SPIRE Server Client

Production-ready client for SPIRE Server API:
- Entry management
- Registration
- Health checks
- Server status
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.security.subprocess_validator import safe_run
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "spire-server-client"

SPIRE_SERVER_CLIENT_CLAIM_BOUNDARY = (
    "SPIRE server client control event only. It records local identity, policy, "
    "and safe actuator state for SPIRE server CLI entry/status actions; it is "
    "not proof of live production SPIRE mTLS, workload traffic, or operator raw "
    "evidence."
)


@dataclass
class SPIREServerEntry:
    """SPIRE Server entry"""

    entry_id: str
    spiffe_id: str
    parent_id: str
    selectors: Dict[str, str]
    ttl: int
    admin: bool = False


class SPIREServerClient:
    """
    Client for SPIRE Server API.

    Provides production-ready integration with SPIRE Server:
    - Entry management (create, list, delete)
    - Registration operations
    - Health checks
    - Server status
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8081",
        server_socket: Optional[Path] = None,
        spire_server_bin: str = "spire-server",
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        safe_actuator: Optional[SafeActuator] = None,
        source_agent: str = _SERVICE_AGENT,
        node_id: str = "spire-server-client",
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ):
        """
        Initialize SPIRE Server client.

        Args:
            server_address: SPIRE Server address (host:port)
            server_socket: Path to SPIRE Server Unix socket (optional)
            spire_server_bin: Path to spire-server binary
        """
        self.server_address = server_address
        self.server_socket = server_socket
        self.spire_server_bin = spire_server_bin
        self.event_bus = (
            event_bus
            if event_bus is not None
            else self._default_event_bus(event_project_root)
        )
        self.event_project_root = event_project_root
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool(
                "X0TTA6BL4_SPIRE_SERVER_CLIENT_POLICY_REQUIRED",
                False,
            )
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name=_SERVICE_AGENT)
        self.source_agent = source_agent
        self.identity = {
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
        self.safe_actuator = safe_actuator

        logger.info(f"SPIRE Server Client initialized for {server_address}")

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
        except (ImportError, RuntimeError, OSError, ValueError) as exc:
            logger.error("Failed to initialize SPIRE server client EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except (ImportError, RuntimeError, ValueError, OSError) as exc:
            logger.error(
                "Failed to initialize SPIRE server client policy engine: %s",
                exc,
            )
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
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(
                    str(child_key),
                    child_value,
                    depth + 1,
                )
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

    def _publish_control_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        operation: str,
        context: Dict[str, Any],
        reason: str = "",
        policy_decision: Any = None,
        success: Optional[bool] = None,
        simulated: Optional[bool] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "security.spiffe.server.client",
            "stage": stage,
            "operation": operation,
            "resource": f"identity:spire_server:{operation}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "success": success,
            "simulated": simulated,
            "reason": reason,
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
            "policy_required": self.require_policy or self.policy_engine is not None,
            "claim_boundary": SPIRE_SERVER_CLIENT_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(
                event_type,
                self.source_agent,
                payload,
                priority=7,
            )
            return event.event_id
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            logger.error("Failed to publish SPIRE server manager event: %s", exc)
            return None

    def _evaluate_control_policy(self, operation: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return (
                    False,
                    None,
                    "SPIRE server client policy engine is required but unavailable",
                )
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return (
                False,
                None,
                "SPIRE server client SPIFFE identity is required for policy evaluation",
            )
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"identity:spire_server:{operation}",
                workload_type="spire-server-client",
            )
        except (ValueError, KeyError, RuntimeError, OSError) as exc:
            return (False, f"SPIRE server policy evaluation failed: {exc}")
        if not self._policy_allowed(decision):
            return (
                False,
                decision,
                self._policy_reason(decision)
                or "SPIRE server client policy denied control action",
            )
        return True, decision, self._policy_reason(decision)

    def _run_control_action(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        executor: Any,
    ) -> SafeActuatorResult:
        self._publish_control_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            operation=operation,
            context=context,
        )
        allowed, decision, reason = self._evaluate_control_policy(operation)
        if not allowed:
            self._publish_control_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=reason,
                policy_decision=decision,
                success=False,
                simulated=False,
            )
            return SafeActuatorResult(False, reason)

        self._publish_control_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=reason,
            policy_decision=decision,
        )
        actuator = self.safe_actuator or SafeActuator(executor)
        actuator_result = actuator.execute(operation, context)
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        self._publish_control_event(
            (
                EventType.PIPELINE_STAGE_END
                if success and not simulated
                else EventType.TASK_FAILED
            ),
            stage=(
                "actuator_completed"
                if success and not simulated
                else "actuator_simulated"
                if simulated
                else "actuator_failed"
            ),
            operation=operation,
            context=context,
            reason=actuator_result.reason or reason,
            policy_decision=decision,
            success=success and not simulated,
            simulated=simulated,
        )
        return actuator_result

    def health_check(self) -> bool:
        """
        Check SPIRE Server health.

        Returns:
            True if server is healthy
        """
        result = self._run_control_action(
            operation="health_check",
            context={"server_address": self.server_address},
            executor=self._health_check_internal,
        )
        return bool(result.success) and not bool(result.simulated)

    def _health_check_internal(
        self,
        _operation: str,
        _context: Dict[str, Any],
    ) -> SafeActuatorResult:
        try:
            result = safe_run(
                [self.spire_server_bin, "healthcheck"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return SafeActuatorResult(
                result.returncode == 0,
                "SPIRE server healthcheck passed"
                if result.returncode == 0
                else "SPIRE server healthcheck returned non-zero",
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"SPIRE Server health check failed: {e}")
            return SafeActuatorResult(
                False,
                f"SPIRE server health check failed: {e}",
            )

    def create_entry(
        self,
        spiffe_id: str,
        parent_id: str,
        selectors: Dict[str, str],
        ttl: int = 3600,
        admin: bool = False,
    ) -> Optional[str]:
        """
        Create a new entry in SPIRE Server.

        Args:
            spiffe_id: SPIFFE ID for the entry
            parent_id: Parent SPIFFE ID
            selectors: Workload selectors (e.g., {"unix:uid": "1000"})
            ttl: SVID time-to-live in seconds
            admin: Whether entry has admin privileges

        Returns:
            Entry ID if successful, None otherwise
        """
        holder: Dict[str, Optional[str]] = {"entry_id": None}
        result = self._run_control_action(
            operation="create_entry",
            context={
                "spiffe_id": spiffe_id,
                "parent_id": parent_id,
                "selectors": dict(selectors),
                "ttl": ttl,
                "admin": admin,
            },
            executor=lambda _operation, _context: self._create_entry_internal(
                spiffe_id,
                parent_id,
                selectors,
                ttl,
                admin,
                holder,
            ),
        )
        if bool(result.success) and not bool(result.simulated):
            return holder["entry_id"]
        return None

    def _create_entry_internal(
        self,
        spiffe_id: str,
        parent_id: str,
        selectors: Dict[str, str],
        ttl: int,
        admin: bool,
        holder: Dict[str, Optional[str]],
    ) -> SafeActuatorResult:
        try:
            selector_str = ",".join([f"{k}:{v}" for k, v in selectors.items()])
            cmd = [
                self.spire_server_bin,
                "entry",
                "create",
                "-spiffeID",
                spiffe_id,
                "-parentID",
                parent_id,
                "-selector",
                selector_str,
                "-ttl",
                str(ttl),
            ]

            if admin:
                cmd.append("-admin")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                entry_id = (
                    result.stdout.strip().split()[-1] if result.stdout else None
                )
                holder["entry_id"] = entry_id
                logger.info(f"Created SPIRE entry: {spiffe_id} (ID: {entry_id})")
                return SafeActuatorResult(True, "SPIRE entry created")
            logger.error(f"Failed to create entry: {result.stderr}")
            return SafeActuatorResult(False, "SPIRE entry creation failed")
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            logger.error(f"Error creating SPIRE entry: {e}")
            return SafeActuatorResult(False, f"Error creating SPIRE entry: {e}")

    def list_entries(self) -> List[SPIREServerEntry]:
        """
        List all entries in SPIRE Server.

        Returns:
            List of SPIREServerEntry objects
        """
        holder: Dict[str, List[SPIREServerEntry]] = {"entries": []}
        result = self._run_control_action(
            operation="list_entries",
            context={"server_address": self.server_address},
            executor=lambda _operation, _context: self._list_entries_internal(
                holder
            ),
        )
        if bool(result.success) and not bool(result.simulated):
            return holder["entries"]
        return []

    def _list_entries_internal(
        self,
        holder: Dict[str, List[SPIREServerEntry]],
    ) -> SafeActuatorResult:
        try:
            result = safe_run(
                [self.spire_server_bin, "entry", "show"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to list entries: {result.stderr}")
                return SafeActuatorResult(False, "SPIRE entry list failed")

            entries = []
            current_entry = {}

            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    if current_entry:
                        entries.append(self._parse_entry(current_entry))
                        current_entry = {}
                    continue

                if ":" in line:
                    key, value = line.split(":", 1)
                    current_entry[key.strip()] = value.strip()

            if current_entry:
                entries.append(self._parse_entry(current_entry))

            holder["entries"] = entries
            logger.info(f"Listed {len(entries)} SPIRE entries")
            return SafeActuatorResult(True, "SPIRE entries listed")
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            logger.error(f"Error listing SPIRE entries: {e}")
            return SafeActuatorResult(False, f"Error listing SPIRE entries: {e}")

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete an entry from SPIRE Server.

        Args:
            entry_id: Entry ID to delete

        Returns:
            True if deletion successful
        """
        result = self._run_control_action(
            operation="delete_entry",
            context={"entry_id": entry_id},
            executor=lambda _operation, _context: self._delete_entry_internal(
                entry_id
            ),
        )
        return bool(result.success) and not bool(result.simulated)

    def _delete_entry_internal(self, entry_id: str) -> SafeActuatorResult:
        try:
            result = safe_run(
                [self.spire_server_bin, "entry", "delete", "-entryID", entry_id],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logger.info(f"Deleted SPIRE entry: {entry_id}")
                return SafeActuatorResult(True, "SPIRE entry deleted")
            logger.error(f"Failed to delete entry: {result.stderr}")
            return SafeActuatorResult(False, "SPIRE entry deletion failed")
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            logger.error(f"Error deleting SPIRE entry: {e}")
            return SafeActuatorResult(False, f"Error deleting SPIRE entry: {e}")

    def _parse_entry(self, entry_dict: Dict[str, str]) -> SPIREServerEntry:
        """Parse entry dictionary into SPIREServerEntry"""
        selectors = {}
        selectors_str = entry_dict.get("Selectors", "")
        if selectors_str:
            for s in selectors_str.split(","):
                if ":" in s:
                    parts = s.split(":", 1)
                    if len(parts) == 2:
                        selectors[parts[0].strip()] = parts[1].strip()

        return SPIREServerEntry(
            entry_id=entry_dict.get("Entry ID", ""),
            spiffe_id=entry_dict.get("SPIFFE ID", ""),
            parent_id=entry_dict.get("Parent ID", ""),
            selectors=selectors,
            ttl=int(entry_dict.get("TTL", "3600")),
            admin=entry_dict.get("Admin", "false").lower() == "true",
        )

    def get_server_status(self) -> Dict[str, Any]:
        """
        Get SPIRE Server status.

        Returns:
            Dictionary with server status information
        """
        holder: Dict[str, Dict[str, Any]] = {"status": {}}
        result = self._run_control_action(
            operation="get_server_status",
            context={"server_address": self.server_address},
            executor=lambda _operation, _context: self._get_server_status_internal(
                holder
            ),
        )
        if holder["status"] and not bool(result.simulated):
            return holder["status"]
        return {
            "healthy": False,
            "address": self.server_address,
            "error": result.reason,
            "simulated": bool(result.simulated),
        }

    def _get_server_status_internal(
        self,
        holder: Dict[str, Dict[str, Any]],
    ) -> SafeActuatorResult:
        try:
            result = safe_run(
                [self.spire_server_bin, "healthcheck", "-shallow"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            holder["status"] = {
                "healthy": result.returncode == 0,
                "address": self.server_address,
                "output": (
                    result.stdout.strip()
                    if result.returncode == 0
                    else result.stderr.strip()
                ),
            }
            return SafeActuatorResult(
                result.returncode == 0,
                "SPIRE server shallow healthcheck passed"
                if result.returncode == 0
                else "SPIRE server shallow healthcheck returned non-zero",
            )
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error(f"Error getting server status: {e}")
            holder["status"] = {
                "healthy": False,
                "address": self.server_address,
                "error": str(e),
            }
            return SafeActuatorResult(False, f"Error getting server status: {e}")
