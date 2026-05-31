"""Yggdrasil mesh network client (Strict Production Edition)."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "yggdrasil-client"
_SERVICE_LAYER = "network_yggdrasil_observed_state"
_YGGDRASIL_RESOURCES = {
    "get_self": "network:yggdrasil:get_self",
    "get_peers": "network:yggdrasil:get_peers",
    "get_routes": "network:yggdrasil:get_routes",
}
YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY = (
    "Read-only local yggdrasilctl observation. EventBus evidence records command "
    "metadata, return code, duration, parsed summary, and bounded output hashes; "
    "it does not expose raw mesh stdout/stderr or prove remote peer authenticity, "
    "route quality, or live packet reachability."
)
YGGDRASIL_OBSERVED_STATE_CLAIM_GATE_SCHEMA = (
    "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1"
)
_YGGDRASIL_OUTPUT_FAILURE_MARKERS = (
    "fatal error:",
    "panic:",
)
_YGGDRASIL_OUTPUT_FAILURE_ERROR = "yggdrasilctl reported fatal error"


class YggdrasilCommandOutputError(RuntimeError):
    """Raised when yggdrasilctl reports failure text despite a zero return code."""


def _has_yggdrasil_output_failure(*streams: Optional[str]) -> bool:
    combined = "\n".join(stream or "" for stream in streams).lower()
    return any(marker in combined for marker in _YGGDRASIL_OUTPUT_FAILURE_MARKERS)


def _evidence_metadata(event_id: Optional[str]) -> Dict[str, Any]:
    event_ids = [event_id] if event_id else []
    return {
        "source_agents": [_SERVICE_AGENT] if event_ids else [],
        "layer": _SERVICE_LAYER,
        "event_ids": event_ids,
        "events_total": len(event_ids),
        "event_ids_limit": 1,
        "event_ids_truncated": False,
        "payloads_redacted": True,
        "redacted": True,
        "claim_boundary": YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
    }


def _with_evidence(
    payload: Dict[str, Any],
    event_id: Optional[str],
    *,
    include_evidence: bool,
) -> Dict[str, Any]:
    if not include_evidence:
        return payload
    return {**payload, "evidence": _evidence_metadata(event_id)}


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "service_name": _SERVICE_AGENT,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _bounded_output_metadata(
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
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "stdout_preview_chars": min(len(safe_stdout), bounded_limit),
        "stderr_preview_chars": min(len(safe_stderr), bounded_limit),
        "stdout_truncated": len(safe_stdout) > bounded_limit,
        "stderr_truncated": len(safe_stderr) > bounded_limit,
        "output_preview_limit": bounded_limit,
        "output_bounded": True,
        "output_redacted": True,
    }


def _observation_claim_gate(
    *,
    status: str,
    source_mode: str,
    returncode: Optional[int],
) -> Dict[str, Any]:
    real_command_succeeded = (
        status == "succeeded"
        and source_mode == "real_command"
        and returncode == 0
    )
    mock_observation = source_mode == "mock"
    local_observed_state_allowed = real_command_succeeded or mock_observation
    blockers: List[str] = []
    if not local_observed_state_allowed:
        blockers.append("yggdrasil_observed_state_not_confirmed")
    if mock_observation:
        blockers.append("mock_source_mode_not_live_mesh_evidence")

    return {
        "schema": YGGDRASIL_OBSERVED_STATE_CLAIM_GATE_SCHEMA,
        "decision": (
            "LOCAL_YGGDRASIL_OBSERVED_STATE_ONLY"
            if local_observed_state_allowed
            else "YGGDRASIL_OBSERVED_STATE_UNPROVEN"
        ),
        "local_observed_state_claim_allowed": local_observed_state_allowed,
        "real_yggdrasil_daemon_observed": real_command_succeeded,
        "mock_source_mode": mock_observation,
        "return_code_observed": returncode is not None,
        "remote_peer_authenticity_claim_allowed": False,
        "route_quality_claim_allowed": False,
        "live_packet_reachability_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": blockers,
        "claim_boundary": YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
        "redacted": True,
    }


def _event_bus_or_none(
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return EventBus(project_root=event_project_root)
    except Exception as exc:
        logger.error("Failed to initialize Yggdrasil observed-state EventBus: %s", exc)
        return None


def _publish_yggdrasil_observation(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    operation: str,
    command: List[str],
    status: str,
    source_mode: str,
    returncode: Optional[int] = None,
    duration_ms: Optional[float] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    parsed_summary: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    output_preview_limit: int = 0,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    identity = _identity_metadata()
    payload: Dict[str, Any] = {
        "component": "network.yggdrasil_client",
        "stage": "observed_state",
        "operation": operation,
        "resource": _YGGDRASIL_RESOURCES[operation],
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": identity,
        "command": [os.path.basename(command[0]), *command[1:]] if command else [],
        "status": status,
        "source_mode": source_mode,
        "returncode": returncode,
        "return_code": returncode,
        "duration_ms": round(duration_ms or 0.0, 3),
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "parsed_summary": parsed_summary or {},
        "output": _bounded_output_metadata(
            stdout,
            stderr,
            preview_limit=output_preview_limit,
        ),
        "claim_gate": _observation_claim_gate(
            status=status,
            source_mode=source_mode,
            returncode=returncode,
        ),
        "service_identity": identity,
        "raw_values_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
    }
    if error_type:
        payload["error"] = {
            "type": error_type,
            "message_redacted": True,
        }

    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SERVICE_AGENT,
            payload,
            priority=3,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish Yggdrasil observed-state event: %s", exc)
        return None


def _exception_output(
    exc: BaseException,
    result: Optional[subprocess.CompletedProcess[str]],
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    stdout = getattr(exc, "stdout", None) or getattr(exc, "output", None)
    stderr = getattr(exc, "stderr", None)
    returncode = getattr(exc, "returncode", None)
    if result is not None:
        stdout = stdout if stdout is not None else result.stdout
        stderr = stderr if stderr is not None else result.stderr
        returncode = returncode if returncode is not None else result.returncode
    return returncode, stdout, stderr


def _find_yggdrasilctl() -> Optional[str]:
    """Find yggdrasilctl binary in standard locations."""
    locations: List[str] = [
        "yggdrasilctl",
        "/usr/local/bin/yggdrasilctl",
        "/usr/bin/yggdrasilctl",
        "/usr/sbin/yggdrasilctl",
        "/sbin/yggdrasilctl",
    ]
    for loc in locations:
        if shutil.which(loc) or os.path.exists(loc):
            return loc
    return None


def _is_mock_enabled() -> bool:
    testing = os.getenv("X0TTA6BL4_TESTING", "false").lower() == "true"
    force_mock = os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}
    return testing or force_mock


def get_yggdrasil_status(
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> Dict[str, Any]:
    """Get Yggdrasil node status. Requires real binary unless TESTING is set."""
    if _is_mock_enabled():
        status = {
            "address": "fd00::mock",
            "subnet": "fd00::/8",
            "status": "mock",
        }
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=["yggdrasilctl", "getSelf"],
            status="mock",
            source_mode="mock",
            returncode=0,
            duration_ms=0.0,
            parsed_summary={"status": "mock", "node_fields": ["address", "subnet"]},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(status, event_id, include_evidence=include_evidence)

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=["yggdrasilctl", "getSelf"],
            status="failed",
            source_mode="missing_binary",
            returncode=None,
            duration_ms=0.0,
            error_type="RuntimeError",
            output_preview_limit=output_preview_limit,
        )
        raise RuntimeError("yggdrasilctl not found. Mesh networking unavailable.")

    command = [yggdrasilctl_path, "getSelf"]
    started = time.monotonic()
    result: Optional[subprocess.CompletedProcess[str]] = None
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        duration_ms = (time.monotonic() - started) * 1000.0
        if _has_yggdrasil_output_failure(result.stdout, result.stderr):
            event_id = _publish_yggdrasil_observation(
                event_bus=event_bus,
                event_project_root=event_project_root,
                operation="get_self",
                command=command,
                status="failed",
                source_mode="real_command",
                returncode=result.returncode,
                duration_ms=duration_ms,
                stdout=result.stdout,
                stderr=result.stderr,
                parsed_summary={"status": "failed", "output_failure": True},
                error_type=YggdrasilCommandOutputError.__name__,
                output_preview_limit=output_preview_limit,
            )
            return _with_evidence(
                {"status": "offline", "error": _YGGDRASIL_OUTPUT_FAILURE_ERROR},
                event_id,
                include_evidence=include_evidence,
            )
        status = {}
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                status[key] = value.strip()
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="succeeded",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={
                "status": "online",
                "node_field_count": len(status),
                "node_fields": sorted(status),
            },
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "online", "node": status},
            event_id,
            include_evidence=include_evidence,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        returncode, stdout, stderr = _exception_output(exc, result)
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "offline", "error": str(exc)},
            event_id,
            include_evidence=include_evidence,
        )


def get_yggdrasil_peers(
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> Dict[str, Any]:
    """Get list of connected peers."""
    if _is_mock_enabled():
        peers = {"status": "ok", "peers": [], "count": 0}
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=["yggdrasilctl", "getPeers"],
            status="mock",
            source_mode="mock",
            returncode=0,
            duration_ms=0.0,
            parsed_summary={"status": "ok", "peer_count": 0},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(peers, event_id, include_evidence=include_evidence)

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=["yggdrasilctl", "getPeers"],
            status="failed",
            source_mode="missing_binary",
            returncode=None,
            duration_ms=0.0,
            error_type="RuntimeError",
            output_preview_limit=output_preview_limit,
        )
        raise RuntimeError("yggdrasilctl not found")

    command = [yggdrasilctl_path, "getPeers"]
    started = time.monotonic()
    result: Optional[subprocess.CompletedProcess[str]] = None
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        duration_ms = (time.monotonic() - started) * 1000.0
        if _has_yggdrasil_output_failure(result.stdout, result.stderr):
            event_id = _publish_yggdrasil_observation(
                event_bus=event_bus,
                event_project_root=event_project_root,
                operation="get_peers",
                command=command,
                status="failed",
                source_mode="real_command",
                returncode=result.returncode,
                duration_ms=duration_ms,
                stdout=result.stdout,
                stderr=result.stderr,
                parsed_summary={"status": "failed", "output_failure": True},
                error_type=YggdrasilCommandOutputError.__name__,
                output_preview_limit=output_preview_limit,
            )
            return _with_evidence(
                {
                    "status": "error",
                    "error": _YGGDRASIL_OUTPUT_FAILURE_ERROR,
                    "peers": [],
                    "count": 0,
                },
                event_id,
                include_evidence=include_evidence,
            )
        peers = []
        for line in result.stdout.strip().split("\n"):
            if line.strip() and not line.startswith("Peer"):
                parts = line.split()
                if len(parts) >= 3:
                    peers.append(
                        {"port": parts[0], "protocol": parts[1], "remote": parts[2]}
                    )
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="succeeded",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={
                "status": "ok",
                "peer_count": len(peers),
                "protocols": sorted({str(peer["protocol"]) for peer in peers}),
            },
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "ok", "peers": peers, "count": len(peers)},
            event_id,
            include_evidence=include_evidence,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        returncode, stdout, stderr = _exception_output(exc, result)
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": str(exc), "peers": [], "count": 0},
            event_id,
            include_evidence=include_evidence,
        )


def get_yggdrasil_routes(
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> Dict[str, Any]:
    """Get routing table information."""
    if _is_mock_enabled():
        routes = {"status": "ok", "routing_table_size": 0}
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=["yggdrasilctl", "getSelf"],
            status="mock",
            source_mode="mock",
            returncode=0,
            duration_ms=0.0,
            parsed_summary={"status": "ok", "routing_table_size": 0},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(routes, event_id, include_evidence=include_evidence)

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=["yggdrasilctl", "getSelf"],
            status="failed",
            source_mode="missing_binary",
            returncode=None,
            duration_ms=0.0,
            error_type="RuntimeError",
            output_preview_limit=output_preview_limit,
        )
        raise RuntimeError("yggdrasilctl not found")

    command = [yggdrasilctl_path, "getSelf"]
    started = time.monotonic()
    result: Optional[subprocess.CompletedProcess[str]] = None
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        duration_ms = (time.monotonic() - started) * 1000.0
        if _has_yggdrasil_output_failure(result.stdout, result.stderr):
            event_id = _publish_yggdrasil_observation(
                event_bus=event_bus,
                event_project_root=event_project_root,
                operation="get_routes",
                command=command,
                status="failed",
                source_mode="real_command",
                returncode=result.returncode,
                duration_ms=duration_ms,
                stdout=result.stdout,
                stderr=result.stderr,
                parsed_summary={"status": "failed", "output_failure": True},
                error_type=YggdrasilCommandOutputError.__name__,
                output_preview_limit=output_preview_limit,
            )
            return _with_evidence(
                {
                    "status": "error",
                    "error": _YGGDRASIL_OUTPUT_FAILURE_ERROR,
                    "routing_table_size": 0,
                },
                event_id,
                include_evidence=include_evidence,
            )
        routing_size = 0
        for line in result.stdout.strip().split("\n"):
            if "Routing table size" in line:
                _, value = line.split(":", 1)
                routing_size = int(value.strip())
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=command,
            status="succeeded",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={"status": "ok", "routing_table_size": routing_size},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "ok", "routing_table_size": routing_size},
            event_id,
            include_evidence=include_evidence,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        returncode, stdout, stderr = _exception_output(exc, result)
        event_id = _publish_yggdrasil_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": str(exc), "routing_table_size": 0},
            event_id,
            include_evidence=include_evidence,
        )
