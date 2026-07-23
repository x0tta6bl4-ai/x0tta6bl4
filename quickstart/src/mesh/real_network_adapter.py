"""
Адаптер для реальных mesh-протоколов (batman-adv, yggdrasil)
Заменяет моки на реальные метрики
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.core.security.subprocess_validator import validate_command
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "real-network-adapter"
_SERVICE_LAYER = "mesh_real_network_observed_state"
_REAL_NETWORK_RESOURCES = {
    "batman_originators": "mesh:batman_adv:originators",
    "batman_throughput": "mesh:batman_adv:throughput",
    "yggdrasil_admin_request": "mesh:yggdrasil:admin_api",
    "dataplane_ping_probe": "mesh:dataplane:ping_probe",
}
REAL_NETWORK_OBSERVED_STATE_CLAIM_BOUNDARY = (
    "Read-only local batctl/yggdrasilctl observation. EventBus evidence records "
    "service identity presence, command metadata, return code, duration, parsed "
    "summary, and bounded output hashes; it does not expose raw mesh stdout/stderr, "
    "MAC addresses, peer addresses, or prove remote peer authenticity, route "
    "quality, or live packet reachability."
)
YGGDRASIL_PEER_METRIC_ESTIMATE_CLAIM_BOUNDARY = (
    "Derived local estimate from Yggdrasil admin peer fields only. Coordinates "
    "can suggest relative route distance and byte counters can estimate throughput "
    "over uptime; this is not direct RTT, packet-loss, or live reachability proof."
)
DATAPLANE_PING_PROBE_CLAIM_BOUNDARY = (
    "Local ICMP ping dataplane probe only. It records bounded command metadata, "
    "return code, duration, parsed RTT/loss summary, and output hashes for one "
    "redacted target; it does not prove application traffic delivery, remote peer "
    "identity, or sustained mesh quality."
)


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


def _decode_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


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


def _event_bus_or_none(
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return EventBus(project_root=event_project_root)
    except Exception as exc:
        logger.error(
            "Failed to initialize real-network observed-state EventBus: %s", exc
        )
        return None


def _redacted_command(
    command: List[str],
    *,
    redacted_indices: Optional[set[int]] = None,
) -> List[str]:
    redacted_indices = redacted_indices or set()
    safe_command: List[str] = []
    for index, arg in enumerate(command):
        if index == 0:
            safe_command.append(os.path.basename(str(arg)))
        elif index in redacted_indices:
            safe_command.append("[redacted]")
        else:
            safe_command.append(str(arg))
    return safe_command


def _redacted_target_metadata(kind: str, value: Any) -> Dict[str, Any]:
    value_text = str(value or "")
    return {
        "kind": kind,
        "value_present": bool(value_text),
        "sha256": _sha256_text(value_text.lower()),
        "redacted": True,
    }


def _safe_probe_target(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or len(text) > 255:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:%-]+", text):
        return None
    return text


def _request_metadata(request: Dict[str, Any]) -> Dict[str, Any]:
    request_type = str(request.get("request") or "unknown")
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", request_type):
        return {
            "type": request_type,
            "type_redacted": False,
            "payload_redacted": True,
        }
    return {
        "type": "[redacted]",
        "type_sha256": _sha256_text(request_type),
        "type_redacted": True,
        "payload_redacted": True,
    }


def _count_items(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _parse_ping_output(stdout: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "latency_ms": None,
        "packet_loss_percent": None,
        "jitter_ms": None,
        "packets_transmitted": None,
        "packets_received": None,
        "parsed": False,
    }
    loss_match = re.search(
        r"(?P<tx>\d+)\s+packets transmitted,\s+"
        r"(?P<rx>\d+)\s+(?:packets\s+)?received,.*?"
        r"(?P<loss>\d+(?:\.\d+)?)%\s+packet loss",
        stdout,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loss_match:
        summary["packets_transmitted"] = int(loss_match.group("tx"))
        summary["packets_received"] = int(loss_match.group("rx"))
        summary["packet_loss_percent"] = float(loss_match.group("loss"))
        summary["parsed"] = True

    rtt_match = re.search(
        r"(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*"
        r"(?P<min>\d+(?:\.\d+)?)/(?P<avg>\d+(?:\.\d+)?)/"
        r"(?P<max>\d+(?:\.\d+)?)/(?P<mdev>\d+(?:\.\d+)?)\s*ms",
        stdout,
        flags=re.IGNORECASE,
    )
    if rtt_match:
        summary["latency_ms"] = float(rtt_match.group("avg"))
        summary["jitter_ms"] = float(rtt_match.group("mdev"))
        summary["parsed"] = True

    return summary


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
        return candidate if math.isfinite(candidate) else None
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.strip())
        if not match:
            return None
        candidate = float(match.group(0))
        return candidate if math.isfinite(candidate) else None
    return None


def estimate_yggdrasil_peer_metrics(peer: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate peer metrics from Yggdrasil admin fields without exposing peer IDs."""
    coords_value = peer.get("coords")
    coords: List[float] = []
    if isinstance(coords_value, list):
        coords = [
            value
            for item in coords_value
            if (value := _safe_float(item)) is not None
        ]

    latency_ms = None
    if coords:
        latency_ms = sum(abs(item) for item in coords) / len(coords) * 10.0

    bytes_sent = _safe_float(peer.get("bytes_sent"))
    bytes_recvd = _safe_float(peer.get("bytes_recvd"))
    uptime = _safe_float(peer.get("uptime"))
    bandwidth_mbps = None
    if (
        bytes_sent is not None
        and bytes_recvd is not None
        and uptime is not None
        and uptime > 0
    ):
        bandwidth_mbps = (bytes_sent + bytes_recvd) / uptime / 1024 / 1024 * 8

    return {
        "latency_ms": latency_ms,
        "bandwidth_mbps": bandwidth_mbps,
        "sources": {
            "latency_ms": {
                "source": "admin_estimate" if latency_ms is not None else "missing",
                "field": "coords" if latency_ms is not None else None,
            },
            "bandwidth_mbps": {
                "source": (
                    "admin_estimate" if bandwidth_mbps is not None else "missing"
                ),
                "field": (
                    "bytes_sent+bytes_recvd/uptime"
                    if bandwidth_mbps is not None
                    else None
                ),
            },
        },
        "basis": {
            "coords_present": bool(coords),
            "coords_count": len(coords),
            "traffic_counters_present": (
                bytes_sent is not None and bytes_recvd is not None
            ),
            "uptime_present": uptime is not None,
            "claim_boundary": YGGDRASIL_PEER_METRIC_ESTIMATE_CLAIM_BOUNDARY,
            "values_redacted": True,
        },
    }


async def probe_peer_dataplane_ping(
    target: str,
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
    count: int = 2,
    timeout_seconds: int = 1,
    output_preview_limit: int = 0,
) -> Dict[str, Any]:
    """Run a bounded ICMP ping probe and return redacted dataplane metrics."""
    safe_target = _safe_probe_target(target)
    if safe_target is None:
        _publish_real_network_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="dataplane_ping_probe",
            command=["ping", "-c", "<count>", "-W", "<seconds>", "[redacted]"],
            status="failed",
            source_mode="validation",
            returncode=None,
            duration_ms=0.0,
            parsed_summary={"status": "invalid_target", "target_valid": False},
            target_metadata=_redacted_target_metadata("dataplane_ping_target", target),
            error_type="ValueError",
            output_preview_limit=output_preview_limit,
        )
        return {
            "status": "error",
            "error": "invalid_target",
            "latency_ms": None,
            "packet_loss_percent": None,
            "jitter_ms": None,
            "sources": {},
            "redacted": True,
        }

    safe_count = max(1, min(int(count), 5))
    safe_timeout = max(1, min(int(timeout_seconds), 5))
    command = [
        "ping",
        "-c",
        str(safe_count),
        "-W",
        str(safe_timeout),
        "-q",
        safe_target,
    ]
    start = time.monotonic()
    proc = None
    stdout_text = ""
    stderr_text = ""
    try:
        validate_command(command)
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=safe_timeout * safe_count + 2,
        )
        duration_ms = (time.monotonic() - start) * 1000
        stdout_text = _decode_output(stdout)
        stderr_text = _decode_output(stderr)
        parsed = _parse_ping_output(stdout_text)
        status = "success" if parsed["parsed"] and proc.returncode == 0 else "failed"
        event_id = _publish_real_network_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="dataplane_ping_probe",
            command=command,
            status=status,
            source_mode="ping",
            returncode=proc.returncode,
            duration_ms=duration_ms,
            stdout=stdout_text,
            stderr=stderr_text,
            parsed_summary={
                "status": status,
                "latency_ms": parsed["latency_ms"],
                "packet_loss_percent": parsed["packet_loss_percent"],
                "jitter_ms": parsed["jitter_ms"],
                "packets_transmitted": parsed["packets_transmitted"],
                "packets_received": parsed["packets_received"],
            },
            target_metadata=_redacted_target_metadata(
                "dataplane_ping_target",
                safe_target,
            ),
            output_preview_limit=output_preview_limit,
            redacted_command_indices={6},
        )
        return {
            "status": "ok" if status == "success" else "error",
            "latency_ms": parsed["latency_ms"],
            "packet_loss_percent": parsed["packet_loss_percent"],
            "jitter_ms": parsed["jitter_ms"],
            "sources": {
                "latency_ms": {
                    "source": "dataplane_probe",
                    "field": "ping_avg_rtt_ms",
                },
                "packet_loss_percent": {
                    "source": "dataplane_probe",
                    "field": "ping_packet_loss_percent",
                },
                "jitter_ms": {
                    "source": "dataplane_probe",
                    "field": "ping_mdev_ms",
                },
            },
            "evidence": {
                "source_agents": [_SERVICE_AGENT] if event_id else [],
                "event_ids": [event_id] if event_id else [],
                "events_total": 1 if event_id else 0,
                "redacted": True,
            },
            "claim_boundary": DATAPLANE_PING_PROBE_CLAIM_BOUNDARY,
            "redacted": True,
        }
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        event_id = _publish_real_network_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            operation="dataplane_ping_probe",
            command=command,
            status="failed",
            source_mode="ping",
            returncode=getattr(proc, "returncode", None),
            duration_ms=duration_ms,
            stdout=stdout_text,
            stderr=stderr_text,
            parsed_summary={"status": "failed"},
            target_metadata=_redacted_target_metadata(
                "dataplane_ping_target",
                safe_target,
            ),
            error_type=type(exc).__name__,
            output_preview_limit=output_preview_limit,
            redacted_command_indices={6},
        )
        return {
            "status": "error",
            "error": type(exc).__name__,
            "latency_ms": None,
            "packet_loss_percent": None,
            "jitter_ms": None,
            "sources": {},
            "evidence": {
                "source_agents": [_SERVICE_AGENT] if event_id else [],
                "event_ids": [event_id] if event_id else [],
                "events_total": 1 if event_id else 0,
                "redacted": True,
            },
            "claim_boundary": DATAPLANE_PING_PROBE_CLAIM_BOUNDARY,
            "redacted": True,
        }


def _summarize_yggdrasil_response(
    request_meta: Dict[str, Any],
    response: Dict[str, Any],
) -> Dict[str, Any]:
    request_type = request_meta["type"]
    body = response.get("response", {}) if isinstance(response, dict) else {}
    summary: Dict[str, Any] = {
        "request_type": request_type,
        "request_type_redacted": request_meta["type_redacted"],
    }

    if request_type == "getPeers" and isinstance(body, dict):
        summary["peer_count"] = _count_items(body.get("peers", {}))
    elif request_type == "getDHT" and isinstance(body, dict):
        summary["dht_entries"] = _count_items(body.get("dht", body))
    else:
        summary["response_items"] = _count_items(body)

    return summary


def _publish_real_network_observation(
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
    target_metadata: Optional[Dict[str, Any]] = None,
    request_metadata: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    output_preview_limit: int = 0,
    redacted_command_indices: Optional[set[int]] = None,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    payload: Dict[str, Any] = {
        "component": "mesh.real_network_adapter",
        "stage": "observed_state",
        "operation": operation,
        "resource": _REAL_NETWORK_RESOURCES[operation],
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": _identity_metadata(),
        "command": _redacted_command(
            command,
            redacted_indices=redacted_command_indices,
        ),
        "status": status,
        "source_mode": source_mode,
        "returncode": returncode,
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
        "claim_boundary": REAL_NETWORK_OBSERVED_STATE_CLAIM_BOUNDARY,
    }
    if target_metadata:
        payload["target"] = target_metadata
    if request_metadata:
        payload["request"] = request_metadata
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
        logger.error("Failed to publish real-network observed-state event: %s", exc)
        return None


class BatmanAdvAdapter:
    """
    Интерфейс к batman-adv через batctl
    """

    def __init__(
        self,
        interface: str = "bat0",
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        output_preview_limit: int = 0,
    ) -> None:
        self.interface = interface
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.output_preview_limit = output_preview_limit

    async def get_originators(self) -> List[Dict[str, Any]]:
        """
        Получить список originator'ов (mesh-узлов)

        Выполняет: batctl o
        Парсит вывод в структурированные данные
        """
        command = ["batctl", "o"]
        start = time.monotonic()
        stdout_text = ""
        stderr_text = ""
        try:
            validate_command(command)
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            duration_ms = (time.monotonic() - start) * 1000
            stdout_text = _decode_output(stdout)
            stderr_text = _decode_output(stderr)

            if proc.returncode != 0:
                logger.warning(
                    "batctl originator read failed; stderr is redacted in EventBus evidence"
                )
                _publish_real_network_observation(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    operation="batman_originators",
                    command=command,
                    status="failed",
                    source_mode="real_command",
                    returncode=proc.returncode,
                    duration_ms=duration_ms,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    parsed_summary={"originator_count": 0},
                    output_preview_limit=self.output_preview_limit,
                )
                return []

            # Парсинг вывода batctl
            # Формат: [B.A.T.M.A.N. adv openwrt-2021.0, MainIF/MAC: wlan0/...]
            # ff:ff:ff:ff:ff:ff    0.020s   (255) fe:ff:ff:ff:ff:ff [wlan0]

            originators = []
            lines = stdout_text.strip().split("\n")
            if len(lines) > 2:
                lines = lines[2:]  # Skip header

            for line in lines:
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 3:
                    originators.append(
                        {
                            "mac": parts[0],
                            "last_seen": self._parse_time(parts[1]),
                            "tq": int(parts[2].strip("()")),  # Transmission Quality
                            "nexthop": parts[3] if len(parts) > 3 else None,
                        }
                    )

            _publish_real_network_observation(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                operation="batman_originators",
                command=command,
                status="success",
                source_mode="real_command",
                returncode=proc.returncode,
                duration_ms=duration_ms,
                stdout=stdout_text,
                stderr=stderr_text,
                parsed_summary={
                    "originator_count": len(originators),
                    "avg_tq": (
                        round(
                            sum(item["tq"] for item in originators) / len(originators),
                            3,
                        )
                        if originators
                        else 0
                    ),
                },
                output_preview_limit=self.output_preview_limit,
            )
            return originators

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            _publish_real_network_observation(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                operation="batman_originators",
                command=command,
                status="failed",
                source_mode="exception",
                duration_ms=duration_ms,
                stdout=stdout_text,
                stderr=stderr_text or str(e),
                parsed_summary={"originator_count": 0},
                error_type=type(e).__name__,
                output_preview_limit=self.output_preview_limit,
            )
            logger.error(
                "Failed to get batman-adv originators; details are redacted in EventBus evidence"
            )
            return []

    async def get_throughput(self) -> Dict[str, float]:
        """
        Получить throughput между узлами

        Выполняет: batctl tp -m <mac>
        """
        throughput_map = {}
        originators = await self.get_originators()

        for orig in originators[:5]:  # Ограничиваем для производительности
            mac = orig.get("mac", "")
            command = ["batctl", "tp", "-m", str(mac)]
            target_metadata = _redacted_target_metadata("batman_originator_mac", mac)
            start = time.monotonic()
            stdout_text = ""
            stderr_text = ""
            try:
                validate_command(command)
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Use wait_for for timeout
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.warning(
                        "Throughput test to redacted batman-adv originator timed out"
                    )
                    if proc.returncode is None and hasattr(proc, "terminate"):
                        proc.terminate()
                    _publish_real_network_observation(
                        event_bus=self.event_bus,
                        event_project_root=self.event_project_root,
                        operation="batman_throughput",
                        command=command,
                        status="failed",
                        source_mode="timeout",
                        returncode=proc.returncode,
                        duration_ms=duration_ms,
                        parsed_summary={"measurement_found": False},
                        target_metadata=target_metadata,
                        error_type="TimeoutError",
                        output_preview_limit=self.output_preview_limit,
                        redacted_command_indices={3},
                    )
                    continue
                duration_ms = (time.monotonic() - start) * 1000
                stdout_text = _decode_output(stdout)
                stderr_text = _decode_output(stderr)

                if proc.returncode != 0:
                    logger.warning(
                        "batctl throughput read failed; stderr is redacted in EventBus evidence"
                    )
                    _publish_real_network_observation(
                        event_bus=self.event_bus,
                        event_project_root=self.event_project_root,
                        operation="batman_throughput",
                        command=command,
                        status="failed",
                        source_mode="real_command",
                        returncode=proc.returncode,
                        duration_ms=duration_ms,
                        stdout=stdout_text,
                        stderr=stderr_text,
                        parsed_summary={"measurement_found": False},
                        target_metadata=target_metadata,
                        output_preview_limit=self.output_preview_limit,
                        redacted_command_indices={3},
                    )
                    continue

                # Парсинг вывода throughput теста
                match = re.search(r"(\d+\.\d+)\s*Mbits/sec", stdout_text)
                throughput_mbps = None
                if match:
                    throughput_mbps = float(match.group(1))
                    throughput_map[str(mac)] = throughput_mbps

                _publish_real_network_observation(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    operation="batman_throughput",
                    command=command,
                    status="success",
                    source_mode="real_command",
                    returncode=proc.returncode,
                    duration_ms=duration_ms,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    parsed_summary={
                        "measurement_found": throughput_mbps is not None,
                        "throughput_mbps": throughput_mbps,
                    },
                    target_metadata=target_metadata,
                    output_preview_limit=self.output_preview_limit,
                    redacted_command_indices={3},
                )

            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000
                _publish_real_network_observation(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    operation="batman_throughput",
                    command=command,
                    status="failed",
                    source_mode="exception",
                    duration_ms=duration_ms,
                    stdout=stdout_text,
                    stderr=stderr_text or str(e),
                    parsed_summary={"measurement_found": False},
                    target_metadata=target_metadata,
                    error_type=type(e).__name__,
                    output_preview_limit=self.output_preview_limit,
                    redacted_command_indices={3},
                )
                logger.warning(
                    "Throughput test error; details are redacted in EventBus evidence"
                )
                continue

        return throughput_map

    async def get_statistics(self) -> Dict[str, float]:
        """
        Агрегированная статистика mesh-сети
        """
        originators = await self.get_originators()
        throughput = await self.get_throughput()

        if not originators:
            return {
                "active_peers": 0,
                "avg_latency_ms": 1000,
                "packet_loss_percent": 100,
                "mttr_minutes": 10.0,
            }

        # Transmission Quality как показатель здоровья канала
        avg_tq = sum(o["tq"] for o in originators) / len(originators)

        # Latency оценивается из last_seen (чем меньше, тем лучше)
        avg_last_seen = sum(o["last_seen"] for o in originators) / len(originators)
        estimated_latency = avg_last_seen * 1000  # Convert to ms

        # Packet loss из TQ (TQ=255 = 100% качество)
        packet_loss = 100 * (1 - (avg_tq / 255.0))

        # Средний throughput
        avg_throughput = sum(throughput.values()) / len(throughput) if throughput else 0

        return {
            "active_peers": len(originators),
            "avg_latency_ms": estimated_latency,
            "packet_loss_percent": max(0, packet_loss),
            "avg_throughput_mbps": avg_throughput,
            "mttr_minutes": 3.5,  # Будет рассчитываться из исторических данных
        }

    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Парсит время вида '0.020s' в секунды"""
        return float(time_str.rstrip("s"))


class YggdrasilAdapter:
    """
    Интерфейс к Yggdrasil через Admin API
    """

    def __init__(
        self,
        admin_socket: str = "/var/run/yggdrasil.sock",
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        output_preview_limit: int = 0,
    ):
        self.admin_socket = admin_socket
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.output_preview_limit = output_preview_limit

    async def _send_command(self, request: Dict) -> Dict:
        """
        Отправить команду в Yggdrasil Admin API
        """
        command = ["yggdrasilctl", "-json", "-v"]
        request_meta = _request_metadata(request)
        start = time.monotonic()
        proc = None
        stdout_text = ""
        stderr_text = ""
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            request_json = json.dumps(request).encode()
            stdout, stderr = await proc.communicate(input=request_json)
            duration_ms = (time.monotonic() - start) * 1000
            stdout_text = _decode_output(stdout)
            stderr_text = _decode_output(stderr)

            if proc.returncode != 0:
                logger.warning(
                    "yggdrasilctl admin request failed; stderr is redacted in EventBus evidence"
                )
                _publish_real_network_observation(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    operation="yggdrasil_admin_request",
                    command=command,
                    status="failed",
                    source_mode="real_command",
                    returncode=proc.returncode,
                    duration_ms=duration_ms,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    parsed_summary={
                        "request_type": request_meta["type"],
                        "request_type_redacted": request_meta["type_redacted"],
                    },
                    request_metadata=request_meta,
                    output_preview_limit=self.output_preview_limit,
                )
                return {}

            response = json.loads(stdout_text)
            _publish_real_network_observation(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                operation="yggdrasil_admin_request",
                command=command,
                status="success",
                source_mode="real_command",
                returncode=proc.returncode,
                duration_ms=duration_ms,
                stdout=stdout_text,
                stderr=stderr_text,
                parsed_summary=_summarize_yggdrasil_response(request_meta, response),
                request_metadata=request_meta,
                output_preview_limit=self.output_preview_limit,
            )
            return response

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            _publish_real_network_observation(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                operation="yggdrasil_admin_request",
                command=command,
                status="failed",
                source_mode="exception",
                returncode=getattr(proc, "returncode", None),
                duration_ms=duration_ms,
                stdout=stdout_text,
                stderr=stderr_text or str(e),
                parsed_summary={
                    "request_type": request_meta["type"],
                    "request_type_redacted": request_meta["type_redacted"],
                },
                request_metadata=request_meta,
                error_type=type(e).__name__,
                output_preview_limit=self.output_preview_limit,
            )
            logger.error(
                "Yggdrasil admin command failed; details are redacted in EventBus evidence"
            )
            return {}

    async def get_peers(self) -> List[Dict]:
        """
        Получить список peer'ов
        """
        response = await self._send_command({"request": "getPeers"})
        peers_data = response.get("response", {}).get("peers", {})

        peers = []
        for peer_addr, peer_info in peers_data.items():
            peers.append(
                {
                    "address": peer_addr,
                    "port": peer_info.get("port"),
                    "coords": peer_info.get("coords"),
                    "bytes_sent": peer_info.get("bytes_sent", 0),
                    "bytes_recvd": peer_info.get("bytes_recvd", 0),
                    "uptime": peer_info.get("uptime", 0),
                    "estimated_metrics": estimate_yggdrasil_peer_metrics(peer_info),
                }
            )

        return peers

    async def get_dht(self) -> Dict:
        """
        Получить информацию о DHT
        """
        response = await self._send_command({"request": "getDHT"})
        return response.get("response", {})

    async def get_statistics(self) -> Dict[str, float]:
        """
        Агрегированная статистика Yggdrasil
        """
        peers = await self.get_peers()
        dht = await self.get_dht()

        if not peers:
            return {
                "active_peers": 0,
                "avg_latency_ms": 1000,
                "packet_loss_percent": 100,
                "mttr_minutes": 10.0,
            }

        # Оценка latency из координат (расстояние в графе)
        avg_coords = []
        for peer in peers:
            if peer.get("coords"):
                coords = peer["coords"]
                avg_coords.append(sum(coords) / len(coords) if coords else 0)

        estimated_latency = (
            sum(avg_coords)
            / len(avg_coords)
            * 10  # Heuristic: coord distance ~ latency
            if avg_coords
            else 100
        )

        # Throughput из переданных/принятых байт
        total_traffic = sum(p["bytes_sent"] + p["bytes_recvd"] for p in peers)
        avg_uptime = sum(p["uptime"] for p in peers) / len(peers) if peers else 1
        avg_throughput_mbps = (
            (total_traffic / avg_uptime / 1024 / 1024 * 8) if avg_uptime > 0 else 0
        )

        return {
            "active_peers": len(peers),
            "avg_latency_ms": estimated_latency,
            "packet_loss_percent": 0.5,  # Yggdrasil обычно очень надежен
            "avg_throughput_mbps": avg_throughput_mbps,
            "dht_size": len(dht.get("dht", {})),
            "mttr_minutes": 2.5,
        }


class UnifiedMeshAdapter:
    """
    Унифицированный адаптер, который может работать с любым backend'ом
    """

    def __init__(
        self,
        backend: str = "auto",
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        output_preview_limit: int = 0,
    ):
        self.backend = backend
        self._adapter = None
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.output_preview_limit = output_preview_limit

    async def initialize(self):
        """
        Автоматически определяет доступный mesh-backend
        """
        if self.backend == "auto":
            # Проверяем наличие batman-adv
            if await self._check_command("batctl"):
                self._adapter = BatmanAdvAdapter(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    output_preview_limit=self.output_preview_limit,
                )
                self.backend = "batman-adv"
                logger.info("Using batman-adv backend")
                return

            # Проверяем наличие yggdrasil
            if await self._check_command("yggdrasilctl"):
                self._adapter = YggdrasilAdapter(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    output_preview_limit=self.output_preview_limit,
                )
                self.backend = "yggdrasil"
                logger.info("Using yggdrasil backend")
                return

            # Fallback to simulation
            logger.warning("No mesh backend found, using simulation mode")
            # Import here to avoid circular imports if possible, or assume mock_network exists
            # For now, we'll implement a simple mock inline or fail gracefully
            self._adapter = MockMeshAdapter()
            self.backend = "simulation"

        elif self.backend == "batman-adv":
            self._adapter = BatmanAdvAdapter(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                output_preview_limit=self.output_preview_limit,
            )
        elif self.backend == "yggdrasil":
            self._adapter = YggdrasilAdapter(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                output_preview_limit=self.output_preview_limit,
            )
        elif self.backend == "simulation":
            self._adapter = MockMeshAdapter()
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    async def get_statistics(self) -> Dict[str, float]:
        """
        Получить статистику от активного адаптера
        """
        if not self._adapter:
            await self.initialize()

        return await self._adapter.get_statistics()

    @staticmethod
    async def _check_command(cmd: str) -> bool:
        """
        Проверить наличие команды в системе
        """
        try:
            validate_command(["which", cmd])
            proc = await asyncio.create_subprocess_exec(
                "which",
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False


class MockMeshAdapter:
    """
    Mock adapter for simulation
    """

    async def get_statistics(self) -> Dict[str, float]:
        stats = {
            "active_peers": random.randint(3, 15),
            "avg_latency_ms": random.uniform(20.0, 150.0),
            "packet_loss_percent": random.uniform(0.0, 5.0),
            "mttr_minutes": random.uniform(2.0, 15.0),
            "avg_throughput_mbps": random.uniform(5.0, 50.0),
        }
        return {k: round(v, 4) for k, v in stats.items()}

