#!/usr/bin/env python3
"""
x0tta6bl4 Self-Healing Daemon
Monitors singbox_tun latency AND VPN proxy health.
Triggers healing when latency exceeds 150ms, packet loss occurs, or proxy is unhealthy.
"""

import os
import signal
import socket
import subprocess
import sys
import time
import logging
import hashlib
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

DEFAULT_SOCKS_PORT_CANDIDATES = (10818, 10918, 10808, 10809, 10924, 40467, 1080)
NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME = "network-self-healing-daemon"
NETWORK_SELF_HEALING_DAEMON_LAYER = "network_self_healing_daemon_observed_state"
NETWORK_SELF_HEALING_DAEMON_CLAIM_BOUNDARY = (
    "Local VPN self-healing daemon evidence only. Events record local ping, SOCKS, "
    "ss, pgrep, SIGHUP, heal-script, provider-guard, and optional rotation outcomes "
    "with return codes, duration, and redacted selector/output metadata; they do "
    "not prove provider health, external reachability, successful remote recovery, "
    "or production traffic forwarding."
)
_EVENT_BUS: Optional[EventBus] = None
_EVENT_PROJECT_ROOT = os.getenv("X0TTA6BL4_EVENT_PROJECT_ROOT", ".")
_SOURCE_AGENT = NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME


def configure_event_bus(
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
    source_agent: Optional[str] = None,
) -> None:
    """Configure EventBus injection for tests or embedding processes."""
    global _EVENT_BUS, _EVENT_PROJECT_ROOT, _SOURCE_AGENT
    _EVENT_BUS = event_bus
    if event_project_root is not None:
        _EVENT_PROJECT_ROOT = event_project_root
    if source_agent is not None:
        _SOURCE_AGENT = source_agent


def _event_bus_or_none() -> Optional[EventBus]:
    global _EVENT_BUS
    if _EVENT_BUS is not None:
        return _EVENT_BUS
    try:
        _EVENT_BUS = get_event_bus(_EVENT_PROJECT_ROOT)
        return _EVENT_BUS
    except Exception as exc:
        logging.error("Failed to initialize network self-healing EventBus: %s", exc)
        return None


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


def _output_metadata(value: Any, limit: int = 512) -> dict[str, Any]:
    if value is None:
        encoded = b""
    elif isinstance(value, bytes):
        encoded = value
    else:
        encoded = str(value).encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest() if encoded else None,
        "sample_limit": limit,
        "sample_redacted": True,
        "truncated": len(encoded) > limit,
    }


def _identity_metadata() -> dict[str, Any]:
    identity = service_event_identity(
        service_name=NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME
    )
    return {
        "service_name": NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME,
        "layer": NETWORK_SELF_HEALING_DAEMON_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _selector_metadata(
    *,
    target: Optional[str] = None,
    interface: Optional[str] = None,
    vpn_server: Optional[str] = None,
    socks_host: Optional[str] = None,
    socks_port: Optional[int] = None,
    state: Optional[str] = None,
    script_path: Optional[str] = None,
    pid: Optional[str | int] = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if target is not None:
        metadata["target_hash"] = _hash_value(target)
        metadata["target_redacted"] = True
    if interface is not None:
        metadata["interface_hash"] = _hash_value(interface)
        metadata["interface_redacted"] = True
    if vpn_server is not None:
        metadata["vpn_server_hash"] = _hash_value(vpn_server)
        metadata["vpn_server_redacted"] = True
    if socks_host is not None:
        metadata["socks_host_hash"] = _hash_value(socks_host)
        metadata["socks_host_redacted"] = True
    if socks_port is not None:
        metadata["socks_port_hash"] = _hash_value(socks_port)
        metadata["socks_port_redacted"] = True
    if state is not None:
        metadata["tcp_state"] = state
    if script_path is not None:
        metadata["script_path_hash"] = _hash_value(script_path)
        metadata["script_path_redacted"] = True
    if pid is not None:
        metadata["pid_hash"] = _hash_value(pid)
        metadata["pid_redacted"] = True
    return metadata


def _reason_metadata(reason: str) -> dict[str, Any]:
    return {
        "reason_hash": _hash_value(reason),
        "reason_length": len(reason),
        "reason_redacted": True,
    }


def _publish_observation(
    *,
    stage: str,
    operation: str,
    status: str,
    source_mode: str,
    start: float,
    returncode: Optional[int] = None,
    read_only: bool = True,
    control_action: bool = False,
    parsed_summary: Optional[dict[str, Any]] = None,
    error: Optional[BaseException] = None,
    extra: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    bus = _event_bus_or_none()
    if bus is None:
        return None

    payload: dict[str, Any] = {
        "component": "network.self_healing_daemon",
        "stage": stage,
        "operation": operation,
        "operation_resource": f"network:self_healing_daemon:{operation}",
        "service_name": _SOURCE_AGENT,
        "layer": NETWORK_SELF_HEALING_DAEMON_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "source_mode": source_mode,
        "returncode": returncode,
        "duration_ms": round((time.monotonic() - start) * 1000, 3),
        "read_only": read_only,
        "observed_state": True,
        "control_action": control_action,
        "local_actuator": control_action,
        "safe_actuator": False,
        "payloads_redacted": True,
        "parsed_summary": parsed_summary or {},
        "claim_boundary": NETWORK_SELF_HEALING_DAEMON_CLAIM_BOUNDARY,
    }
    if error is not None:
        payload["error"] = {
            "type": type(error).__name__,
            "message_hash": _hash_value(str(error)),
            "message_redacted": True,
        }
    if extra:
        payload.update(extra)

    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception:
        logging.exception("Failed to publish network self-healing evidence")
        return None


def _run_observed_command(
    command: list[str],
    *,
    command_shape: list[str],
    operation: str,
    success_stage: str,
    failure_stage: str,
    missing_stage: str,
    timeout_stage: str,
    parsed_summary: dict[str, Any],
    selector_metadata: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
    text: bool = True,
    read_only: bool = True,
    control_action: bool = False,
    raise_on_exception: bool = False,
) -> Optional[subprocess.CompletedProcess[Any]]:
    start = time.monotonic()
    extra = {
        "command_shape": command_shape,
        "command_hash": _hash_value(" ".join(command)),
        **(selector_metadata or {}),
    }
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=text,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        _publish_observation(
            stage=missing_stage,
            operation=operation,
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=127,
            read_only=read_only,
            control_action=control_action,
            parsed_summary={**parsed_summary, "command_available": False},
            error=exc,
            extra={
                **extra,
                "stdout_metadata": _output_metadata(None),
                "stderr_metadata": _output_metadata(None),
            },
        )
        if raise_on_exception:
            raise
        return None
    except subprocess.TimeoutExpired as exc:
        _publish_observation(
            stage=timeout_stage,
            operation=operation,
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=124,
            read_only=read_only,
            control_action=control_action,
            parsed_summary={**parsed_summary, "command_timed_out": True},
            error=exc,
            extra={
                **extra,
                "stdout_metadata": _output_metadata(exc.stdout),
                "stderr_metadata": _output_metadata(exc.stderr),
            },
        )
        if raise_on_exception:
            raise
        return None
    except OSError as exc:
        _publish_observation(
            stage=failure_stage,
            operation=operation,
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=1,
            read_only=read_only,
            control_action=control_action,
            parsed_summary=parsed_summary,
            error=exc,
            extra={
                **extra,
                "stdout_metadata": _output_metadata(None),
                "stderr_metadata": _output_metadata(None),
            },
        )
        if raise_on_exception:
            raise
        return None

    successful = result.returncode == 0
    _publish_observation(
        stage=success_stage if successful else failure_stage,
        operation=operation,
        status="success" if successful else "failure",
        source_mode="subprocess",
        start=start,
        returncode=result.returncode,
        read_only=read_only,
        control_action=control_action,
        parsed_summary={**parsed_summary, "command_returned": True},
        extra={
            **extra,
            "stdout_metadata": _output_metadata(result.stdout),
            "stderr_metadata": _output_metadata(result.stderr),
        },
    )
    return result


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_ports(*values: str | None) -> tuple[int, ...]:
    ports: list[int] = []
    for value in values:
        if not value:
            continue
        for raw in value.replace(";", ",").split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                port = int(raw)
            except ValueError:
                continue
            if 0 < port < 65536 and port not in ports:
                ports.append(port)
    for port in DEFAULT_SOCKS_PORT_CANDIDATES:
        if port not in ports:
            ports.append(port)
    return tuple(ports)


def _socks_handshake(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.send(b"\x05\x01\x00")
            return s.recv(2) == b"\x05\x00"
    except OSError:
        return False


def discover_socks_port() -> int | None:
    for port in SOCKS_PORT_CANDIDATES:
        if _socks_handshake(SOCKS_HOST, port):
            return port
    return None


# Configuration
INTERFACE = os.getenv("INTERFACE", "singbox_tun")
TEST_TARGET = os.getenv("TEST_TARGET", "8.8.8.8")
MAX_LATENCY_MS = float(os.getenv("MAX_LATENCY_MS", "150.0"))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "5"))
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
SOCKS_HOST = os.getenv("VPN_SOCKS_HOST", os.getenv("SOCKS_HOST", "127.0.0.1"))
SOCKS_PORT_CANDIDATES = _parse_ports(
    os.getenv("VPN_SOCKS_PORT"),
    os.getenv("SOCKS_PORT"),
    os.getenv("VPN_SOCKS_PORT_CANDIDATES"),
)
SOCKS_PORT = SOCKS_PORT_CANDIDATES[0]
ENABLE_REALITY_ROTATION = _truthy(os.getenv("VPN_ENABLE_REALITY_ROTATION"))
ENABLE_PULSE_SHIFT = _truthy(os.getenv("VPN_ENABLE_PULSE_SHIFT"))
ENABLE_HEAL = _truthy(os.getenv("VPN_SELF_HEAL_ENABLE"))
PACKET_LOSS_HEAL_FAILURES = int(os.getenv("VPN_PACKET_LOSS_HEAL_FAILURES", "3"))
LATENCY_HEAL_FAILURES = int(os.getenv("VPN_LATENCY_HEAL_FAILURES", "3"))
PROXY_HEAL_FAILURES = int(os.getenv("VPN_PROXY_HEAL_FAILURES", "3"))
FIN_WAIT2_HEAL_FAILURES = int(os.getenv("VPN_FIN_WAIT2_HEAL_FAILURES", "2"))
PROVIDER_GUARD_SCRIPT = os.getenv("VPN_PROVIDER_GUARD_SCRIPT", "/mnt/projects/scripts/vpn_provider_guard.py")
PROVIDER_GUARD_DISABLED = _truthy(os.getenv("VPN_PROVIDER_GUARD_DISABLE"))
PROVIDER_GUARD_REQUIRE_FRESH = _truthy(os.getenv("VPN_PROVIDER_GUARD_REQUIRE_FRESH"))
PROVIDER_GUARD_MAX_AGE_SECONDS = int(os.getenv("VPN_PROVIDER_GUARD_MAX_AGE_SECONDS", "3600"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MAPE-K Self-Healing] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/tmp/healing.log"),
        logging.StreamHandler()
    ]
)

_consecutive_failures = 0
_consecutive_latency_failures = 0
_consecutive_proxy_failures = 0
_consecutive_fin_wait2_failures = 0
_healing_attempts_count = 0
_last_heal_time = 0.0
_HEAL_COOLDOWN = int(os.getenv("VPN_HEAL_COOLDOWN_SEC", os.getenv("VPN_SELF_HEAL_COOLDOWN_SEC", "1800")))


def provider_guard_allows_heal() -> tuple[bool, str]:
    start = time.monotonic()
    if PROVIDER_GUARD_DISABLED:
        if PROVIDER_GUARD_REQUIRE_FRESH:
            _publish_observation(
                stage="network_self_healing_provider_guard_disabled_blocked",
                operation="provider_guard",
                status="blocked",
                source_mode="config",
                start=start,
                returncode=1,
                parsed_summary={
                    "provider_guard_disabled": True,
                    "require_fresh": True,
                    "allowed": False,
                },
            )
            return False, "provider guard disabled; fresh snapshot required"
        _publish_observation(
            stage="network_self_healing_provider_guard_disabled_allowed",
            operation="provider_guard",
            status="skipped",
            source_mode="config",
            start=start,
            returncode=0,
            parsed_summary={
                "provider_guard_disabled": True,
                "require_fresh": False,
                "allowed": True,
            },
        )
        return True, "provider guard disabled"
    if not os.path.exists(PROVIDER_GUARD_SCRIPT):
        if PROVIDER_GUARD_REQUIRE_FRESH:
            _publish_observation(
                stage="network_self_healing_provider_guard_unavailable_blocked",
                operation="provider_guard",
                status="blocked",
                source_mode="filesystem",
                start=start,
                returncode=1,
                parsed_summary={
                    "provider_guard_script_present": False,
                    "require_fresh": True,
                    "allowed": False,
                },
                extra=_selector_metadata(script_path=PROVIDER_GUARD_SCRIPT),
            )
            return False, "provider guard unavailable; fresh snapshot required"
        _publish_observation(
            stage="network_self_healing_provider_guard_unavailable_allowed",
            operation="provider_guard",
            status="skipped",
            source_mode="filesystem",
            start=start,
            returncode=0,
            parsed_summary={
                "provider_guard_script_present": False,
                "require_fresh": False,
                "allowed": True,
            },
            extra=_selector_metadata(script_path=PROVIDER_GUARD_SCRIPT),
        )
        return True, "provider guard unavailable"
    cmd = [
        sys.executable,
        PROVIDER_GUARD_SCRIPT,
        "--check",
        "--max-age-seconds",
        str(PROVIDER_GUARD_MAX_AGE_SECONDS),
    ]
    if PROVIDER_GUARD_REQUIRE_FRESH:
        cmd.append("--require-fresh")
    command_shape = [
        "<python>",
        "<provider_guard_script>",
        "--check",
        "--max-age-seconds",
        "<seconds>",
    ]
    if PROVIDER_GUARD_REQUIRE_FRESH:
        command_shape.append("--require-fresh")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _publish_observation(
            stage="network_self_healing_provider_guard_inconclusive_error",
            operation="provider_guard",
            status="blocked" if PROVIDER_GUARD_REQUIRE_FRESH else "warning",
            source_mode="subprocess",
            start=start,
            returncode=124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
            parsed_summary={
                "provider_guard_script_present": True,
                "require_fresh": PROVIDER_GUARD_REQUIRE_FRESH,
                "allowed": not PROVIDER_GUARD_REQUIRE_FRESH,
                "inconclusive": True,
            },
            error=exc,
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **_selector_metadata(script_path=PROVIDER_GUARD_SCRIPT),
                "stdout_metadata": _output_metadata(
                    getattr(exc, "stdout", None)
                ),
                "stderr_metadata": _output_metadata(
                    getattr(exc, "stderr", None)
                ),
            },
        )
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, f"provider guard inconclusive while fresh snapshot is required: {exc}"
        return True, f"provider guard inconclusive: {exc}"
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 10:
        stage = "network_self_healing_provider_guard_blocked"
        status = "blocked"
        allowed = False
        inconclusive = False
    elif result.returncode != 0:
        stage = (
            "network_self_healing_provider_guard_inconclusive_blocked"
            if PROVIDER_GUARD_REQUIRE_FRESH
            else "network_self_healing_provider_guard_inconclusive_allowed"
        )
        status = "blocked" if PROVIDER_GUARD_REQUIRE_FRESH else "warning"
        allowed = not PROVIDER_GUARD_REQUIRE_FRESH
        inconclusive = True
    else:
        stage = "network_self_healing_provider_guard_allowed"
        status = "success"
        allowed = True
        inconclusive = False

    _publish_observation(
        stage=stage,
        operation="provider_guard",
        status=status,
        source_mode="subprocess",
        start=start,
        returncode=result.returncode,
        parsed_summary={
            "provider_guard_script_present": True,
            "require_fresh": PROVIDER_GUARD_REQUIRE_FRESH,
            "allowed": allowed,
            "inconclusive": inconclusive,
            "output_present": bool(output),
        },
        extra={
            "command_shape": command_shape,
            "command_hash": _hash_value(" ".join(cmd)),
            **_selector_metadata(script_path=PROVIDER_GUARD_SCRIPT),
            "stdout_metadata": _output_metadata(result.stdout),
            "stderr_metadata": _output_metadata(result.stderr),
        },
    )
    if result.returncode == 10:
        return False, output or "provider guard blocked local heal"
    if result.returncode != 0:
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, f"provider guard inconclusive while fresh snapshot is required rc={result.returncode}: {output}"
        return True, f"provider guard inconclusive rc={result.returncode}: {output}"
    return True, output or "provider guard allowed local heal"


def ping_target(target, interface):
    """Ping target through interface, return latency in ms or inf on failure."""
    start = time.monotonic()
    cmd = ["ping", "-I", interface, "-c", "1", "-W", "1", target]
    command_shape = [
        "ping",
        "-I",
        "<interface>",
        "-c",
        "1",
        "-W",
        "1",
        "<target>",
    ]
    selector_metadata = _selector_metadata(target=target, interface=interface)
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in output.splitlines():
            if "time=" in line:
                latency_str = line.split("time=")[1].split(" ")[0]
                latency = float(latency_str)
                _publish_observation(
                    stage="network_self_healing_ping_succeeded",
                    operation="ping_target",
                    status="success",
                    source_mode="subprocess",
                    start=start,
                    returncode=0,
                    parsed_summary={
                        "latency_ms": latency,
                        "packet_loss": False,
                    },
                    extra={
                        "command_shape": command_shape,
                        "command_hash": _hash_value(" ".join(cmd)),
                        **selector_metadata,
                        "stdout_metadata": _output_metadata(output),
                        "stderr_metadata": _output_metadata(None),
                    },
                )
                return latency
        _publish_observation(
            stage="network_self_healing_ping_unparsed",
            operation="ping_target",
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=0,
            parsed_summary={"latency_ms": None, "packet_loss": True},
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **selector_metadata,
                "stdout_metadata": _output_metadata(output),
                "stderr_metadata": _output_metadata(None),
            },
        )
        return float('inf')
    except subprocess.CalledProcessError as exc:
        _publish_observation(
            stage="network_self_healing_ping_failed",
            operation="ping_target",
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=exc.returncode,
            parsed_summary={"latency_ms": None, "packet_loss": True},
            error=exc,
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **selector_metadata,
                "stdout_metadata": _output_metadata(exc.output),
                "stderr_metadata": _output_metadata(None),
            },
        )
        return float('inf')
    except OSError as exc:
        _publish_observation(
            stage="network_self_healing_ping_command_error",
            operation="ping_target",
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=127 if isinstance(exc, FileNotFoundError) else 1,
            parsed_summary={"latency_ms": None, "packet_loss": True},
            error=exc,
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **selector_metadata,
                "stdout_metadata": _output_metadata(None),
                "stderr_metadata": _output_metadata(None),
            },
        )
        return float('inf')


def check_proxy_health() -> bool:
    """Quick TCP check that SOCKS5 proxy is alive."""
    global SOCKS_PORT

    start = time.monotonic()
    previous_port = SOCKS_PORT
    port = discover_socks_port()
    if port is None:
        _publish_observation(
            stage="network_self_healing_proxy_unavailable",
            operation="check_proxy_health",
            status="failure",
            source_mode="socket",
            start=start,
            returncode=1,
            parsed_summary={
                "proxy_ok": False,
                "candidates_total": len(SOCKS_PORT_CANDIDATES),
                "port_changed": False,
            },
            extra=_selector_metadata(
                socks_host=SOCKS_HOST,
                socks_port=previous_port,
            ),
        )
        return False

    if port != SOCKS_PORT:
        logging.info("Detected active SOCKS5 proxy on configured host")
        SOCKS_PORT = port
    _publish_observation(
        stage="network_self_healing_proxy_available",
        operation="check_proxy_health",
        status="success",
        source_mode="socket",
        start=start,
        returncode=0,
        parsed_summary={
            "proxy_ok": True,
            "candidates_total": len(SOCKS_PORT_CANDIDATES),
            "port_changed": port != previous_port,
        },
        extra={
            **_selector_metadata(socks_host=SOCKS_HOST, socks_port=port),
            "previous_socks_port_hash": _hash_value(previous_port),
            "previous_socks_port_redacted": True,
        },
    )
    return True


def get_fin_wait2_count() -> int:
    """Count FIN-WAIT-2 connections to VPN server."""
    start = time.monotonic()
    cmd = ["ss", "-tn", "dst", VPN_SERVER]
    command_shape = ["ss", "-tn", "dst", "<vpn_server>"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        count = sum(1 for line in result.stdout.splitlines() if "FIN-WAIT-2" in line)
        _publish_observation(
            stage=(
                "network_self_healing_fin_wait2_observed"
                if result.returncode == 0
                else "network_self_healing_fin_wait2_failed"
            ),
            operation="get_fin_wait2_count",
            status="success" if result.returncode == 0 else "failure",
            source_mode="subprocess",
            start=start,
            returncode=result.returncode,
            parsed_summary={"fin_wait2_count": count},
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **_selector_metadata(vpn_server=VPN_SERVER),
                "stdout_metadata": _output_metadata(result.stdout),
                "stderr_metadata": _output_metadata(result.stderr),
            },
        )
        return count
    except Exception as exc:
        _publish_observation(
            stage="network_self_healing_fin_wait2_error",
            operation="get_fin_wait2_count",
            status="failure",
            source_mode="subprocess",
            start=start,
            returncode=124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
            parsed_summary={"fin_wait2_count": 0},
            error=exc,
            extra={
                "command_shape": command_shape,
                "command_hash": _hash_value(" ".join(cmd)),
                **_selector_metadata(vpn_server=VPN_SERVER),
                "stdout_metadata": _output_metadata(getattr(exc, "stdout", None)),
                "stderr_metadata": _output_metadata(getattr(exc, "stderr", None)),
            },
        )
        return 0


def trigger_healing(reason: str):
    """Multi-stage healing: force-close stale connections, SIGHUP, then Rotate Keys."""
    global _last_heal_time, _healing_attempts_count

    op_start = time.monotonic()
    if not ENABLE_HEAL:
        _publish_observation(
            stage="network_self_healing_trigger_disabled",
            operation="trigger_healing",
            status="skipped",
            source_mode="config",
            start=op_start,
            returncode=0,
            read_only=False,
            control_action=False,
            parsed_summary={"heal_enabled": False},
            extra=_reason_metadata(reason),
        )
        logging.warning(f"Healing disabled by VPN_SELF_HEAL_ENABLE=false: {reason}")
        return

    guard_ok, guard_reason = provider_guard_allows_heal()
    if not guard_ok:
        _publish_observation(
            stage="network_self_healing_trigger_provider_blocked",
            operation="trigger_healing",
            status="blocked",
            source_mode="provider_guard",
            start=op_start,
            returncode=1,
            read_only=False,
            control_action=False,
            parsed_summary={"heal_enabled": True, "provider_guard_allowed": False},
            extra={
                **_reason_metadata(reason),
                "guard_reason_hash": _hash_value(guard_reason),
                "guard_reason_redacted": True,
            },
        )
        logging.warning(f"Healing blocked by provider guard: {guard_reason}; reason={reason}")
        return

    now = time.monotonic()
    if (now - _last_heal_time) < _HEAL_COOLDOWN:
        _publish_observation(
            stage="network_self_healing_trigger_cooldown_skipped",
            operation="trigger_healing",
            status="skipped",
            source_mode="cooldown",
            start=op_start,
            returncode=0,
            read_only=False,
            control_action=False,
            parsed_summary={
                "heal_enabled": True,
                "provider_guard_allowed": True,
                "cooldown_seconds": _HEAL_COOLDOWN,
            },
            extra=_reason_metadata(reason),
        )
        logging.warning(f"Healing skipped (cooldown): {reason}")
        return

    logging.warning(f"=== Triggering healing Stage {min(_healing_attempts_count + 1, 5)}: {reason} ===")
    _last_heal_time = now
    _healing_attempts_count += 1
    current_stage = min(_healing_attempts_count, 5)
    _publish_observation(
        stage="network_self_healing_trigger_started",
        operation="trigger_healing",
        status="started",
        source_mode="daemon",
        start=op_start,
        returncode=0,
        read_only=False,
        control_action=True,
        parsed_summary={
            "heal_enabled": True,
            "provider_guard_allowed": True,
            "healing_stage": current_stage,
        },
        extra=_reason_metadata(reason),
    )

    # Stage 0: optional pulse adaptation. Disabled by default because VPN
    # recovery must not mutate traffic profiles on a single local symptom.
    if _healing_attempts_count == 1 and ENABLE_PULSE_SHIFT:
        logging.info("🧠 MAPE-K: Phase 0 - Transitioning x0tta6bl4_pulse mimicry profile (Dynamic Pulse Shift)...")
        pulse_start = time.monotonic()
        try:
            import json
            cmd_file = "/mnt/projects/.tmp/pulse_cmd.json"
            os.makedirs(os.path.dirname(cmd_file), exist_ok=True)
            with open(cmd_file, "w") as f:
                json.dump({"action": "switch_profile", "target": "vk", "reason": reason}, f)
            _publish_observation(
                stage="network_self_healing_pulse_shift_requested",
                operation="trigger_healing",
                status="started",
                source_mode="filesystem",
                start=pulse_start,
                returncode=0,
                read_only=False,
                control_action=True,
                parsed_summary={"pulse_shift_enabled": True},
                extra={
                    **_reason_metadata(reason),
                    "command_file_hash": _hash_value(cmd_file),
                    "command_file_redacted": True,
                },
            )
            logging.info("✅ Pulse shift command issued to mesh daemon.")
            time.sleep(5)
            # Check if pulse shift fixed it
            if ping_target(TEST_TARGET, INTERFACE) != float('inf'):
                _publish_observation(
                    stage="network_self_healing_pulse_shift_succeeded",
                    operation="trigger_healing",
                    status="success",
                    source_mode="daemon",
                    start=pulse_start,
                    returncode=0,
                    read_only=False,
                    control_action=True,
                    parsed_summary={"pulse_shift_enabled": True},
                    extra=_reason_metadata(reason),
                )
                logging.info("💪 Pulse Shift SUCCESSFUL. Latency restored via VK-Mimicry.")
                return
        except Exception as e:
            _publish_observation(
                stage="network_self_healing_pulse_shift_failed",
                operation="trigger_healing",
                status="failure",
                source_mode="filesystem",
                start=pulse_start,
                returncode=1,
                read_only=False,
                control_action=True,
                parsed_summary={"pulse_shift_enabled": True},
                error=e,
                extra=_reason_metadata(reason),
            )
            logging.error(f"Pulse shift failed: {e}")
    elif _healing_attempts_count == 1:
        _publish_observation(
            stage="network_self_healing_pulse_shift_skipped",
            operation="trigger_healing",
            status="skipped",
            source_mode="config",
            start=op_start,
            returncode=0,
            read_only=False,
            control_action=False,
            parsed_summary={"pulse_shift_enabled": False},
            extra=_reason_metadata(reason),
        )
        logging.info("Pulse shift skipped; set VPN_ENABLE_PULSE_SHIFT=true to allow it.")

    # Stage 1: force-close stale TCP connections
    for state in ("fin-wait-2", "close-wait"):
        _run_observed_command(
            ["ss", "-K", "dst", VPN_SERVER, "state", state],
            command_shape=[
                "ss",
                "-K",
                "dst",
                "<vpn_server>",
                "state",
                state,
            ],
            operation="force_close_stale",
            success_stage="network_self_healing_force_close_completed",
            failure_stage="network_self_healing_force_close_failed",
            missing_stage="network_self_healing_force_close_command_missing",
            timeout_stage="network_self_healing_force_close_timeout",
            parsed_summary={"healing_stage": current_stage},
            selector_metadata=_selector_metadata(vpn_server=VPN_SERVER, state=state),
            timeout=5,
            text=False,
            read_only=False,
            control_action=True,
            raise_on_exception=True,
        )

    # Stage 2: SIGHUP xray (graceful reload)
    if _healing_attempts_count == 2:
        sighup_start = time.monotonic()
        try:
            result = _run_observed_command(
                ["pgrep", "-f", "xray run"],
                command_shape=["pgrep", "-f", "<process_pattern>"],
                operation="find_xray_process",
                success_stage="network_self_healing_xray_pgrep_completed",
                failure_stage="network_self_healing_xray_pgrep_failed",
                missing_stage="network_self_healing_xray_pgrep_command_missing",
                timeout_stage="network_self_healing_xray_pgrep_timeout",
                parsed_summary={"healing_stage": current_stage},
                timeout=None,
                text=True,
                read_only=True,
                control_action=False,
                raise_on_exception=False,
            )
            stdout = result.stdout if result is not None else ""
            pid = stdout.strip().split()[0] if stdout.strip() else None
            if pid:
                os.kill(int(pid), signal.SIGHUP)
                _publish_observation(
                    stage="network_self_healing_xray_sighup_sent",
                    operation="sighup_xray",
                    status="success",
                    source_mode="signal",
                    start=sighup_start,
                    returncode=0,
                    read_only=False,
                    control_action=True,
                    parsed_summary={"healing_stage": current_stage},
                    extra=_selector_metadata(pid=pid),
                )
                logging.info("Sent SIGHUP to xray process")
                time.sleep(3)
            else:
                _publish_observation(
                    stage="network_self_healing_xray_sighup_no_pid",
                    operation="sighup_xray",
                    status="skipped",
                    source_mode="process_scan",
                    start=sighup_start,
                    returncode=0,
                    read_only=False,
                    control_action=False,
                    parsed_summary={"healing_stage": current_stage, "pid_found": False},
                )
        except Exception as e:
            _publish_observation(
                stage="network_self_healing_xray_sighup_failed",
                operation="sighup_xray",
                status="failure",
                source_mode="signal",
                start=sighup_start,
                returncode=1,
                read_only=False,
                control_action=True,
                parsed_summary={"healing_stage": current_stage},
                error=e,
            )
            logging.error(f"SIGHUP failed: {e}")

    # Stage 3: run project heal script
    if _healing_attempts_count == 3:
        heal_script = "/mnt/projects/heal_now.py"
        if os.path.exists(heal_script):
            _run_observed_command(
                ["python3", heal_script],
                command_shape=["python3", "<heal_script>"],
                operation="run_heal_script",
                success_stage="network_self_healing_heal_script_completed",
                failure_stage="network_self_healing_heal_script_failed",
                missing_stage="network_self_healing_heal_script_command_missing",
                timeout_stage="network_self_healing_heal_script_timeout",
                parsed_summary={"healing_stage": current_stage},
                selector_metadata=_selector_metadata(script_path=heal_script),
                timeout=None,
                text=True,
                read_only=False,
                control_action=True,
                raise_on_exception=True,
            )
        else:
            _publish_observation(
                stage="network_self_healing_heal_script_missing",
                operation="run_heal_script",
                status="skipped",
                source_mode="filesystem",
                start=op_start,
                returncode=0,
                read_only=False,
                control_action=False,
                parsed_summary={"healing_stage": current_stage, "script_present": False},
                extra=_selector_metadata(script_path=heal_script),
            )

    # Stage 4: CRITICAL - Rotate Reality Keys (Possible IP blocking/GFW detection)
    if _healing_attempts_count >= 4:
        if not ENABLE_REALITY_ROTATION:
            _publish_observation(
                stage="network_self_healing_reality_rotation_skipped",
                operation="rotate_reality_credentials",
                status="skipped",
                source_mode="config",
                start=op_start,
                returncode=0,
                read_only=False,
                control_action=False,
                parsed_summary={
                    "healing_stage": current_stage,
                    "reality_rotation_enabled": False,
                },
                extra=_reason_metadata(reason),
            )
            logging.error(
                "Reality key rotation skipped; set VPN_ENABLE_REALITY_ROTATION=true "
                "to allow this destructive recovery step."
            )
            logging.info("Healing iteration complete. Waiting for stabilization.")
            time.sleep(10)
            return

        logging.critical("🚨 Stage 4: Initiating Reality Key Rotation (Self-Healing)")
        rotation_start = time.monotonic()
        try:
            from vpn_config_generator import XUIAPIClient
            xui = XUIAPIClient()
            xui.rotate_reality_credentials()
            logging.info("✅ Reality keys rotated and x-ui restarted.")
            _healing_attempts_count = 0 # Reset after deep healing
            _publish_observation(
                stage="network_self_healing_reality_rotation_completed",
                operation="rotate_reality_credentials",
                status="success",
                source_mode="xui_api",
                start=rotation_start,
                returncode=0,
                read_only=False,
                control_action=True,
                parsed_summary={"reality_rotation_enabled": True},
                extra=_reason_metadata(reason),
            )
        except Exception as e:
            _publish_observation(
                stage="network_self_healing_reality_rotation_failed",
                operation="rotate_reality_credentials",
                status="failure",
                source_mode="xui_api",
                start=rotation_start,
                returncode=1,
                read_only=False,
                control_action=True,
                parsed_summary={"reality_rotation_enabled": True},
                error=e,
                extra=_reason_metadata(reason),
            )
            logging.error(f"❌ Critical rotation failed: {e}")

    _publish_observation(
        stage="network_self_healing_trigger_completed",
        operation="trigger_healing",
        status="completed",
        source_mode="daemon",
        start=op_start,
        returncode=0,
        read_only=False,
        control_action=True,
        parsed_summary={
            "healing_stage": current_stage,
            "healing_attempts_count": _healing_attempts_count,
        },
        extra=_reason_metadata(reason),
    )
    logging.info("Healing iteration complete. Waiting for stabilization.")
    time.sleep(10)


def check_once():
    """Run one monitoring iteration. Kept separate so thresholds are testable."""
    global _consecutive_failures
    global _consecutive_latency_failures
    global _consecutive_proxy_failures
    global _consecutive_fin_wait2_failures

    check_start = time.monotonic()
    latency = ping_target(TEST_TARGET, INTERFACE)
    proxy_ok = check_proxy_health()
    fw2 = get_fin_wait2_count()

    if latency == float('inf'):
        _consecutive_failures += 1
        _consecutive_latency_failures = 0
        logging.error(f"Packet loss detected! (failure #{_consecutive_failures})")
        if _consecutive_failures >= PACKET_LOSS_HEAL_FAILURES:
            trigger_healing(
                f"Sustained packet loss for {_consecutive_failures} checks"
            )
    elif latency > MAX_LATENCY_MS:
        _consecutive_latency_failures += 1
        logging.warning(f"High latency: {latency}ms (limit: {MAX_LATENCY_MS}ms)")
        if _consecutive_latency_failures >= LATENCY_HEAL_FAILURES:
            trigger_healing(
                f"Latency {latency:.0f}ms > {MAX_LATENCY_MS}ms "
                f"for {_consecutive_latency_failures} checks"
            )
        _consecutive_failures = 0
    else:
        _consecutive_failures = 0
        _consecutive_latency_failures = 0
        logging.info(f"Network OK | latency={latency:.1f}ms | proxy={'OK' if proxy_ok else 'FAIL'} | FIN-WAIT-2={fw2}")

    if not proxy_ok:
        _consecutive_proxy_failures += 1
        logging.error(
            f"SOCKS5 proxy health check failed "
            f"({_consecutive_proxy_failures}/{PROXY_HEAL_FAILURES})"
        )
        if _consecutive_proxy_failures >= PROXY_HEAL_FAILURES:
            trigger_healing(
                f"SOCKS5 proxy health check failed for {_consecutive_proxy_failures} checks"
            )
    else:
        _consecutive_proxy_failures = 0

    if fw2 >= 50:
        _consecutive_fin_wait2_failures += 1
        if _consecutive_fin_wait2_failures >= FIN_WAIT2_HEAL_FAILURES:
            trigger_healing(
                f"FIN-WAIT-2 spike: {fw2} connections for "
                f"{_consecutive_fin_wait2_failures} checks"
            )
    else:
        _consecutive_fin_wait2_failures = 0

    _publish_observation(
        stage=(
            "network_self_healing_check_ok"
            if latency != float("inf") and latency <= MAX_LATENCY_MS and proxy_ok and fw2 < 50
            else "network_self_healing_check_degraded"
        ),
        operation="check_once",
        status=(
            "success"
            if latency != float("inf") and latency <= MAX_LATENCY_MS and proxy_ok and fw2 < 50
            else "warning"
        ),
        source_mode="daemon",
        start=check_start,
        returncode=0,
        parsed_summary={
            "latency_ms": None if latency == float("inf") else latency,
            "packet_loss": latency == float("inf"),
            "max_latency_ms": MAX_LATENCY_MS,
            "proxy_ok": proxy_ok,
            "fin_wait2_count": fw2,
            "packet_loss_failures": _consecutive_failures,
            "latency_failures": _consecutive_latency_failures,
            "proxy_failures": _consecutive_proxy_failures,
            "fin_wait2_failures": _consecutive_fin_wait2_failures,
        },
        extra=_selector_metadata(
            target=TEST_TARGET,
            interface=INTERFACE,
            vpn_server=VPN_SERVER,
            socks_host=SOCKS_HOST,
            socks_port=SOCKS_PORT,
        ),
    )


def run_daemon():
    logging.info(
        f"Started monitoring interface {INTERFACE} → target {TEST_TARGET} "
        f"| socks={SOCKS_HOST}:{SOCKS_PORT} candidates={SOCKS_PORT_CANDIDATES} "
        f"| heal_enabled={ENABLE_HEAL}"
    )

    # Do not create recovery scripts implicitly in production. Missing
    # recovery scripts are reported when that later recovery stage is reached.
    heal_script = "/mnt/projects/heal_now.py"
    if not os.path.exists(heal_script):
        logging.info("Optional heal_now.py script is absent; stage 3 will be skipped if reached.")

    while True:
        check_once()
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    run_daemon()
