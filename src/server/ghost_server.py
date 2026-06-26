from __future__ import annotations
import sys
import os
sys.path.append("/mnt/projects")
sys.path.append("/mnt/projects/src")

import base64
import binascii
import fcntl
import struct
import socket
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from src.core.security.subprocess_validator import safe_run

# Manual import of GhostTransport to avoid any src issues
from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.network.transport.ghost_proto import GhostTransport
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger("ghost-server-l3")

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
_SERVICE_AGENT = "ghost-l3-server"
_MASTER_KEY_HEX_ENV = "GHOST_L3_MASTER_KEY_HEX"
_MASTER_KEY_B64_ENV = "GHOST_L3_MASTER_KEY_B64"
_MASTER_KEY_RAW_ENV = "GHOST_L3_MASTER_KEY"
GHOST_L3_CLAIM_BOUNDARY = (
    "Ghost L3 server runtime setup event only. It records local policy and safe "
    "actuator state for TUN/NAT setup; it is not production rollout evidence."
)


def _coerce_master_key(value: Union[bytes, str], source: str) -> bytes:
    key = value.encode("utf-8") if isinstance(value, str) else value
    if len(key) != 32:
        raise ValueError(f"{source} must decode to exactly 32 bytes, got {len(key)}")
    return key


def _load_master_key_from_env() -> bytes:
    hex_value = os.getenv(_MASTER_KEY_HEX_ENV)
    if hex_value:
        try:
            return _coerce_master_key(bytes.fromhex(hex_value.strip()), _MASTER_KEY_HEX_ENV)
        except ValueError as exc:
            raise ValueError(f"{_MASTER_KEY_HEX_ENV} must be 64 hex characters") from exc

    b64_value = os.getenv(_MASTER_KEY_B64_ENV)
    if b64_value:
        try:
            decoded = base64.b64decode(b64_value.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"{_MASTER_KEY_B64_ENV} must be valid base64") from exc
        return _coerce_master_key(decoded, _MASTER_KEY_B64_ENV)

    raw_value = os.getenv(_MASTER_KEY_RAW_ENV)
    if raw_value:
        return _coerce_master_key(raw_value, _MASTER_KEY_RAW_ENV)

    raise RuntimeError(
        "Ghost L3 master key is required. Set GHOST_L3_MASTER_KEY_HEX, "
        "GHOST_L3_MASTER_KEY_B64, or GHOST_L3_MASTER_KEY to a 32-byte key."
    )


class GhostL3Server:
    def __init__(
        self,
        host='127.0.0.1',
        port=8444,
        master_key: Optional[bytes] = None,
        node_id: str = "default-node",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
        tun_name: str = "x0t-srv0",
        tun_cidr: str = "10.8.0.1/24",
        nat_source_cidr: str = "10.8.0.0/24",
        egress_interface: str = "eth0",
    ):
        self.host = host
        self.port = port
        self.transport = GhostTransport(
            _coerce_master_key(master_key, "master_key")
            if master_key is not None
            else _load_master_key_from_env()
        )
        self.tun_fd = None
        self.client_addr = None
        self.tun_name = tun_name
        self.tun_cidr = tun_cidr
        self.nat_source_cidr = nat_source_cidr
        self.egress_interface = egress_interface
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_GHOST_L3_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="ghost-l3-server")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self.safe_actuator = safe_actuator or SafeActuator(self._setup_tun_internal)

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
            logger.error("Failed to initialize Ghost L3 EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize Ghost L3 policy engine: %s", exc)
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

    @staticmethod
    def _safe_context(context: Dict[str, Any]) -> Dict[str, Any]:
        blocked_fragments = ("secret", "password", "token", "key", "private")
        safe: Dict[str, Any] = {}
        for key, value in context.items():
            key_text = str(key)
            if any(fragment in key_text.lower() for fragment in blocked_fragments):
                safe[key_text] = "<redacted>"
            elif value is None or isinstance(value, (str, int, float, bool)):
                safe[key_text] = value
            else:
                safe[key_text] = str(value)
        return safe

    def _setup_context(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "tun_name": self.tun_name,
            "tun_cidr": self.tun_cidr,
            "nat_source_cidr": self.nat_source_cidr,
            "egress_interface": self.egress_interface,
        }

    def _publish_runtime_event(
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
            "component": "server.ghost_server",
            "stage": stage,
            "action_type": "setup_l3_tun",
            "resource": "server:ghost_l3:setup_tun",
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
            "claim_boundary": GHOST_L3_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish Ghost L3 runtime event: %s", exc)
            return None

    def _evaluate_setup_policy(self) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "Ghost L3 policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "Ghost L3 SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource="server:ghost_l3:setup_tun",
                workload_type="network-runtime",
            )
        except Exception as exc:
            return False, None, f"Ghost L3 policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "Ghost L3 policy denied setup"
        return True, decision, self._policy_reason(decision)

    def setup_tun(self):
        """Creates TUN interface and enables NAT on the server."""
        context = self._setup_context()
        self._publish_runtime_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            context=context,
        )
        policy_allowed, policy_decision, policy_reason = self._evaluate_setup_policy()
        if not policy_allowed:
            result = {
                "success": False,
                "reason": policy_reason,
                "policy_required": True,
                "matched_rules": self._policy_rules(policy_decision),
            }
            self._publish_runtime_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                context=context,
                result=result,
                reason=policy_reason,
                policy_decision=policy_decision,
            )
            logger.error("Ghost L3 TUN setup blocked: %s", policy_reason)
            return False

        self._publish_runtime_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )
        actuator_result = self.safe_actuator.execute("setup_l3_tun", context)
        if actuator_result.simulated:
            result = {
                "success": False,
                "reason": actuator_result.reason or "safe actuator returned simulated result",
                "simulated": True,
            }
            self._publish_runtime_event(
                EventType.TASK_FAILED,
                stage="actuator_simulated",
                context=context,
                result=result,
                reason=result["reason"],
                policy_decision=policy_decision,
            )
            return False

        result = {
            "success": actuator_result.success,
            "reason": actuator_result.reason,
            "simulated": actuator_result.simulated,
        }
        self._publish_runtime_event(
            EventType.PIPELINE_STAGE_END
            if actuator_result.success
            else EventType.TASK_FAILED,
            stage="actuator_completed" if actuator_result.success else "actuator_failed",
            context=context,
            result=result,
            reason=actuator_result.reason or policy_reason,
            policy_decision=policy_decision,
        )
        return actuator_result.success

    def _setup_tun_internal(
        self,
        _action: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        try:
            self.tun_fd = os.open('/dev/net/tun', os.O_RDWR)
            tun_name = str(context.get("tun_name", self.tun_name))
            ifr = struct.pack('16sH', tun_name.encode()[:15], IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.tun_fd, TUNSETIFF, ifr)
            safe_run(
                ["ip", "addr", "add", str(context.get("tun_cidr", self.tun_cidr)), "dev", tun_name],
                check=True,
            )
            safe_run(["ip", "link", "set", "dev", tun_name, "up"], check=True)
            self._enable_ip_forward()
            safe_run(
                [
                    "iptables",
                    "-t",
                    "nat",
                    "-A",
                    "POSTROUTING",
                    "-s",
                    str(context.get("nat_source_cidr", self.nat_source_cidr)),
                    "-o",
                    str(context.get("egress_interface", self.egress_interface)),
                    "-j",
                    "MASQUERADE",
                ],
                check=True,
            )
            logger.info("✅ Server L3 TUN configured.")
            return SafeActuatorResult(True)
        except Exception as e:
            logger.error(f"Failed to setup server TUN: {e}")
            return SafeActuatorResult(False, str(e))

    @staticmethod
    def _enable_ip_forward() -> None:
        with open("/proc/sys/net/ipv4/ip_forward", "w", encoding="utf-8") as handle:
            handle.write("1\n")

    async def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.setblocking(False)
        loop = asyncio.get_event_loop()

        async def tun_to_client():
            while True:
                try:
                    packet = await loop.run_in_executor(None, os.read, self.tun_fd, 4096)
                    if self.client_addr:
                        wrapped = self.transport.wrap_packet(packet)
                        sock.sendto(wrapped, self.client_addr)
                except Exception: break

        asyncio.create_task(tun_to_client())

        while True:
            data, addr = await loop.sock_recvfrom(sock, 4096)
            self.client_addr = addr
            unwrapped = self.transport.unwrap_packet(data)
            if unwrapped:
                os.write(self.tun_fd, unwrapped)

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    srv = GhostL3Server(master_key=_load_master_key_from_env())
    srv.setup_tun()
    asyncio.run(srv.run())


if __name__ == "__main__":
    main()

