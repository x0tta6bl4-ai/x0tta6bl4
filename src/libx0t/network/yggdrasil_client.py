"""libx0t compatibility facade for the canonical Yggdrasil client."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import time
from typing import Any, Optional

from src.network import yggdrasil_client as _impl


def _find_yggdrasilctl() -> Optional[str]:
    """Find yggdrasilctl binary in standard locations."""
    locations = (
        "yggdrasilctl",
        "/usr/local/bin/yggdrasilctl",
        "/usr/bin/yggdrasilctl",
        "/usr/sbin/yggdrasilctl",
        "/sbin/yggdrasilctl",
    )
    for location in locations:
        if shutil.which(location) or os.path.exists(location):
            return location
    return None


_DEFAULT_FIND_YGGDRASILCTL = _find_yggdrasilctl


def _evidence_metadata(event_id: Optional[str]) -> dict[str, Any]:
    event_ids = [event_id] if event_id else []
    return {
        "source_agents": ["yggdrasil-client"] if event_ids else [],
        "layer": "network_yggdrasil_observed_state",
        "event_ids": event_ids,
        "events_total": len(event_ids),
        "event_ids_limit": 1,
        "event_ids_truncated": False,
        "payloads_redacted": True,
        "redacted": True,
        "claim_boundary": _impl.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
    }


def _with_evidence(
    payload: dict[str, Any],
    event_id: Optional[str],
    *,
    include_evidence: bool,
) -> dict[str, Any]:
    if not include_evidence:
        return payload
    return {**payload, "evidence": _evidence_metadata(event_id)}


def _is_mock_enabled() -> bool:
    return os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}


def _node_suffix() -> str:
    node_id = os.getenv("NODE_ID", "node-a")
    return node_id.rsplit("-", 1)[-1] or "a"


def _mock_status() -> dict[str, Any]:
    suffix = _node_suffix()
    return {
        "address": f"fd00::{suffix}",
        "subnet": "fd00::/8",
        "status": "mock",
    }


def _mock_peers() -> dict[str, Any]:
    count = random.randint(2, 5)
    protocols = ("tcp", "tls", "quic")
    peers = [
        {
            "port": str(random.randint(10000, 20000)),
            "protocol": random.choice(protocols),
            "remote": f"fd00::{index + 1}",
        }
        for index in range(count)
    ]
    return {"status": "ok", "peers": peers, "count": count}


def _publish(
    *,
    event_bus: Any,
    event_project_root: str,
    operation: str,
    command: list[str],
    status: str,
    source_mode: str,
    returncode: Optional[int] = None,
    duration_ms: float = 0.0,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    parsed_summary: Optional[dict[str, Any]] = None,
    error_type: Optional[str] = None,
    output_preview_limit: int = 0,
) -> Optional[str]:
    return _impl._publish_yggdrasil_observation(
        event_bus=event_bus,
        event_project_root=event_project_root,
        operation=operation,
        command=command,
        status=status,
        source_mode=source_mode,
        returncode=returncode,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        parsed_summary=parsed_summary,
        error_type=error_type,
        output_preview_limit=output_preview_limit,
    )


def _missing_binary_is_forced() -> bool:
    return _find_yggdrasilctl is not _DEFAULT_FIND_YGGDRASILCTL


def _command_or_mock(
    *,
    operation: str,
    event_bus: Any,
    event_project_root: str,
    output_preview_limit: int,
) -> tuple[Optional[list[str]], Optional[str]]:
    path = _find_yggdrasilctl()
    if path:
        return [path, "getPeers" if operation == "get_peers" else "getSelf"], None
    if not _missing_binary_is_forced():
        return [
            "yggdrasilctl",
            "getPeers" if operation == "get_peers" else "getSelf",
        ], None
    event_id = _publish(
        event_bus=event_bus,
        event_project_root=event_project_root,
        operation=operation,
        command=["yggdrasilctl", "getPeers" if operation == "get_peers" else "getSelf"],
        status="mock",
        source_mode="missing_binary_mock",
        returncode=127,
        parsed_summary={"status": "mock", "binary_available": False},
        output_preview_limit=output_preview_limit,
    )
    return None, event_id


def _missing_binary_error(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    return isinstance(exc, OSError) and getattr(exc, "errno", None) == 2


def _called_process_error_text(exc: subprocess.CalledProcessError) -> str:
    return str(exc.stderr or exc.output or exc)


def get_yggdrasil_status(
    *,
    event_bus: Any = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Get Yggdrasil node status with libx0t legacy mock fallback."""
    if _is_mock_enabled():
        status = _mock_status()
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=["yggdrasilctl", "getSelf"],
            status="mock",
            source_mode="mock",
            returncode=0,
            parsed_summary={"status": "mock", "node_fields": ["address", "subnet"]},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(status, event_id, include_evidence=include_evidence)

    command, fallback_event_id = _command_or_mock(
        operation="get_self",
        event_bus=event_bus,
        event_project_root=event_project_root,
        output_preview_limit=output_preview_limit,
    )
    if command is None:
        return _with_evidence(
            _mock_status(),
            fallback_event_id,
            include_evidence=include_evidence,
        )

    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=exc.returncode,
            duration_ms=duration_ms,
            stdout=exc.output,
            stderr=exc.stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": _called_process_error_text(exc)},
            event_id,
            include_evidence=include_evidence,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=124,
            duration_ms=duration_ms,
            stdout=exc.stdout,
            stderr=exc.stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": f"timeout: {exc}"},
            event_id,
            include_evidence=include_evidence,
        )
    except OSError as exc:
        if not _missing_binary_error(exc):
            raise
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="mock",
            source_mode="missing_binary_mock",
            returncode=127,
            duration_ms=(time.monotonic() - started) * 1000.0,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            _mock_status(),
            event_id,
            include_evidence=include_evidence,
        )
    except RuntimeError as exc:
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=1,
            duration_ms=(time.monotonic() - started) * 1000.0,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "offline", "error": str(exc)},
            event_id,
            include_evidence=include_evidence,
        )

    if _impl._has_yggdrasil_output_failure(result.stdout, result.stderr):
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_self",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=(time.monotonic() - started) * 1000.0,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={"status": "failed", "output_failure": True},
            error_type=_impl.YggdrasilCommandOutputError.__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "offline", "error": _impl._YGGDRASIL_OUTPUT_FAILURE_ERROR},
            event_id,
            include_evidence=include_evidence,
        )

    status: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            status[key.strip().lower().replace(" ", "_")] = value.strip()
    event_id = _publish(
        event_bus=event_bus,
        event_project_root=event_project_root,
        operation="get_self",
        command=command,
        status="succeeded",
        source_mode="real_command",
        returncode=result.returncode,
        duration_ms=(time.monotonic() - started) * 1000.0,
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


def get_yggdrasil_peers(
    *,
    event_bus: Any = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Get connected peers with libx0t legacy mock fallback."""
    if _is_mock_enabled():
        peers = _mock_peers()
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=["yggdrasilctl", "getPeers"],
            status="mock",
            source_mode="mock",
            returncode=0,
            parsed_summary={"status": "ok", "peer_count": peers["count"]},
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(peers, event_id, include_evidence=include_evidence)

    command, fallback_event_id = _command_or_mock(
        operation="get_peers",
        event_bus=event_bus,
        event_project_root=event_project_root,
        output_preview_limit=output_preview_limit,
    )
    if command is None:
        return _with_evidence(
            _mock_peers(),
            fallback_event_id,
            include_evidence=include_evidence,
        )

    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=exc.returncode,
            duration_ms=duration_ms,
            stdout=exc.output,
            stderr=exc.stderr,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {
                "status": "error",
                "error": _called_process_error_text(exc),
                "peers": [],
                "count": 0,
            },
            event_id,
            include_evidence=include_evidence,
        )
    except OSError as exc:
        if not _missing_binary_error(exc):
            raise
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="mock",
            source_mode="missing_binary_mock",
            returncode=127,
            duration_ms=(time.monotonic() - started) * 1000.0,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            _mock_peers(),
            event_id,
            include_evidence=include_evidence,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=getattr(exc, "returncode", None),
            duration_ms=duration_ms,
            stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
            stderr=getattr(exc, "stderr", None),
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": str(exc), "peers": [], "count": 0},
            event_id,
            include_evidence=include_evidence,
        )

    if _impl._has_yggdrasil_output_failure(result.stdout, result.stderr):
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_peers",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=(time.monotonic() - started) * 1000.0,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={"status": "failed", "output_failure": True},
            error_type=_impl.YggdrasilCommandOutputError.__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {
                "status": "error",
                "error": _impl._YGGDRASIL_OUTPUT_FAILURE_ERROR,
                "peers": [],
                "count": 0,
            },
            event_id,
            include_evidence=include_evidence,
        )

    peers: list[dict[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if line.strip() and not line.startswith("Peer"):
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit():
                peers.append({"port": parts[0], "protocol": parts[1], "remote": parts[2]})
    event_id = _publish(
        event_bus=event_bus,
        event_project_root=event_project_root,
        operation="get_peers",
        command=command,
        status="succeeded",
        source_mode="real_command",
        returncode=result.returncode,
        duration_ms=(time.monotonic() - started) * 1000.0,
        stdout=result.stdout,
        stderr=result.stderr,
        parsed_summary={
            "status": "ok",
            "peer_count": len(peers),
            "protocols": sorted({peer["protocol"] for peer in peers}),
        },
        output_preview_limit=output_preview_limit,
    )
    return _with_evidence(
        {"status": "ok", "peers": peers, "count": len(peers)},
        event_id,
        include_evidence=include_evidence,
    )


def get_yggdrasil_routes(
    *,
    event_bus: Any = None,
    event_project_root: str = ".",
    output_preview_limit: int = 0,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Get routing table information with libx0t legacy mock fallback."""
    if _is_mock_enabled():
        size = int(get_yggdrasil_peers()["count"])
        routes = {"status": "ok", "routing_table_size": size}
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=["yggdrasilctl", "getSelf"],
            status="mock",
            source_mode="mock",
            returncode=0,
            parsed_summary=routes,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(routes, event_id, include_evidence=include_evidence)

    command, fallback_event_id = _command_or_mock(
        operation="get_routes",
        event_bus=event_bus,
        event_project_root=event_project_root,
        output_preview_limit=output_preview_limit,
    )
    if command is None:
        return _with_evidence(
            {"status": "ok", "routing_table_size": int(_mock_peers()["count"])},
            fallback_event_id,
            include_evidence=include_evidence,
        )

    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except OSError as exc:
        if not _missing_binary_error(exc):
            raise
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=command,
            status="mock",
            source_mode="missing_binary_mock",
            returncode=127,
            duration_ms=(time.monotonic() - started) * 1000.0,
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "ok", "routing_table_size": int(_mock_peers()["count"])},
            event_id,
            include_evidence=include_evidence,
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=getattr(exc, "returncode", None),
            duration_ms=duration_ms,
            stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
            stderr=getattr(exc, "stderr", None),
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {"status": "error", "error": str(exc), "routing_table_size": 0},
            event_id,
            include_evidence=include_evidence,
        )

    if _impl._has_yggdrasil_output_failure(result.stdout, result.stderr):
        event_id = _publish(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="get_routes",
            command=command,
            status="failed",
            source_mode="real_command",
            returncode=result.returncode,
            duration_ms=(time.monotonic() - started) * 1000.0,
            stdout=result.stdout,
            stderr=result.stderr,
            parsed_summary={"status": "failed", "output_failure": True},
            error_type=_impl.YggdrasilCommandOutputError.__name__,
            output_preview_limit=output_preview_limit,
        )
        return _with_evidence(
            {
                "status": "error",
                "error": _impl._YGGDRASIL_OUTPUT_FAILURE_ERROR,
                "routing_table_size": 0,
            },
            event_id,
            include_evidence=include_evidence,
        )

    routing_size = 0
    for line in result.stdout.strip().splitlines():
        if "Routing table size" in line:
            _, value = line.split(":", 1)
            routing_size = int(value.strip())
    event_id = _publish(
        event_bus=event_bus,
        event_project_root=event_project_root,
        operation="get_routes",
        command=command,
        status="succeeded",
        source_mode="real_command",
        returncode=result.returncode,
        duration_ms=(time.monotonic() - started) * 1000.0,
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
