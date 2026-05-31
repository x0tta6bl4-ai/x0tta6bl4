import asyncio
import hashlib
import logging
import math
import os
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.coordination.events import EventBus, EventType, get_event_bus
from src.mesh.real_network_adapter import (
    DATAPLANE_PING_PROBE_CLAIM_BOUNDARY,
    YGGDRASIL_PEER_METRIC_ESTIMATE_CLAIM_BOUNDARY,
    YggdrasilAdapter,
    estimate_yggdrasil_peer_metrics,
    probe_peer_dataplane_ping,
)
from src.mesh.yggdrasil_optimizer import get_optimizer, RouteMetrics
from src.network.yggdrasil_client import get_yggdrasil_peers, get_yggdrasil_status
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)


_SERVICE_AGENT = "mesh-telemetry-collector"
_SERVICE_LAYER = "mesh_telemetry_collector_observed_state"
_REAL_NETWORK_AGENT = "real-network-adapter"
_OPTIMIZER_AGENT = "mesh-yggdrasil-optimizer"
_RESOURCE = "mesh:telemetry_collector:collect_once"
_HASH_LIMIT = 20
_CLAIM_BOUNDARY_LIMIT = 8
_CLAIM_BOUNDARY_TEXT_LIMIT = 400
_CLAIM_GATE_LIMIT = 8
_CLAIM_GATE_BLOCKER_LIMIT = 10
_DEFAULT_LATENCY_MS = 50.0
_DEFAULT_PACKET_LOSS_PERCENT = 0.0
_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")

MESH_TELEMETRY_COLLECTOR_CLAIM_BOUNDARY = (
    "Local mesh telemetry collector evidence only. It links Yggdrasil peer "
    "observations to local optimizer route-metric updates with redacted peer "
    "hashes, metric-source counts, fallback/default counters, and downstream "
    "Yggdrasil/real-network-adapter evidence event IDs; optional admin API "
    "metric enrichment is marked as an estimate, not direct RTT/loss proof. "
    "It does not expose raw peer URIs, route tables, or prove live packet "
    "reachability."
)


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int, minimum: int = 0, maximum: int = 100) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "service_name": _SERVICE_AGENT,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _event_bus_or_none(
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return get_event_bus(event_project_root)
    except Exception as exc:
        logger.error(
            "Failed to initialize mesh-telemetry-collector EventBus: %s",
            exc,
        )
        return None


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _event_ids(
    bus: Optional[EventBus],
    *,
    source_agent: str,
) -> set[str]:
    if bus is None:
        return set()
    return {
        event.event_id
        for event in bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=1000,
        )
    }


def _safe_evidence_ids(peers_data: Dict[str, Any]) -> List[str]:
    evidence = peers_data.get("evidence")
    if not isinstance(evidence, dict):
        return []
    return [
        str(event_id)
        for event_id in evidence.get("event_ids", [])
        if str(event_id)
    ]


def _safe_claim_boundary(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:_CLAIM_BOUNDARY_TEXT_LIMIT]


def _safe_evidence_claim_boundaries(value: Dict[str, Any]) -> List[str]:
    evidence = value.get("evidence") if isinstance(value, dict) else None
    if not isinstance(evidence, dict):
        return []
    boundaries: List[str] = []
    direct_boundary = _safe_claim_boundary(evidence.get("claim_boundary"))
    if direct_boundary:
        boundaries.append(direct_boundary)
    if isinstance(evidence.get("claim_boundaries"), list):
        for item in evidence["claim_boundaries"]:
            boundary = _safe_claim_boundary(item)
            if boundary:
                boundaries.append(boundary)
    return sorted(set(boundaries))[:_CLAIM_BOUNDARY_LIMIT]


def _safe_downstream_claim_gate(
    gate: Any,
    *,
    source_agent: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(gate, dict):
        return None

    flags = {
        str(key): bool(value)
        for key, value in gate.items()
        if isinstance(value, bool)
        and key.endswith(("_allowed", "_observed", "_confirmed", "_mode"))
    }
    all_blockers = [
        str(blocker)
        for blocker in gate.get("blockers", [])
        if str(blocker).strip()
    ]
    return {
        "source_agent": str(source_agent),
        "schema": str(gate.get("schema", "")),
        "decision": str(gate.get("decision", "")),
        "flags": flags,
        "blockers": all_blockers[:_CLAIM_GATE_BLOCKER_LIMIT],
        "blockers_total": len(all_blockers),
        "claim_boundary": _safe_claim_boundary(gate.get("claim_boundary")) or "",
        "redacted": gate.get("redacted") is True,
    }


def _downstream_claim_gate_summary(
    bus: Optional[EventBus],
    *,
    event_ids: List[str],
    source_agents: List[str],
) -> Dict[str, Any]:
    wanted = {str(event_id) for event_id in event_ids if str(event_id)}
    if bus is None or not wanted:
        return {
            "present": False,
            "claim_gates": [],
            "claim_gates_total": 0,
            "claim_gates_truncated": False,
            "redacted": True,
        }

    gates: List[Dict[str, Any]] = []
    for source_agent in sorted(set(source_agents)):
        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=1000,
        )
        for event in events:
            if event.event_id not in wanted or not isinstance(event.data, dict):
                continue
            gate = _safe_downstream_claim_gate(
                event.data.get("claim_gate"),
                source_agent=source_agent,
            )
            if gate is not None:
                gates.append(gate)

    return {
        "present": bool(gates),
        "claim_gates": gates[:_CLAIM_GATE_LIMIT],
        "claim_gates_total": len(gates),
        "claim_gates_truncated": len(gates) > _CLAIM_GATE_LIMIT,
        "redacted": True,
    }


def _peer_hashes(peer_ids: List[str]) -> Dict[str, Any]:
    hashes = [_sha256_text(peer_id) for peer_id in peer_ids if peer_id]
    safe_hashes = [value for value in hashes if value]
    return {
        "peer_uri_hashes": safe_hashes[-_HASH_LIMIT:],
        "peer_uri_hashes_total": len(safe_hashes),
        "peer_uri_hashes_limit": _HASH_LIMIT,
        "peer_uri_hashes_truncated": len(safe_hashes) > _HASH_LIMIT,
        "peer_values_redacted": True,
    }


def _peer_match_keys(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    keys = {text}
    parsed = urlparse(text)
    if parsed.hostname:
        keys.add(parsed.hostname)
    return keys


def _peer_probe_target(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    target = parsed.hostname or text
    if not re.fullmatch(r"[A-Za-z0-9_.:%-]{1,255}", target):
        return None
    return target


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
        return candidate if math.isfinite(candidate) else None
    if isinstance(value, str):
        match = _NUMERIC_RE.search(value.strip())
        if not match:
            return None
        candidate = float(match.group(0))
        return candidate if math.isfinite(candidate) else None
    return None


def _first_peer_metric(
    peer: Dict[str, Any],
    keys: List[str],
) -> tuple[Optional[float], Optional[str]]:
    for key in keys:
        value = _safe_float(peer.get(key))
        if value is not None:
            return value, key
    return None, None


def _estimated_source(
    estimated_metrics: Dict[str, Any],
    metric_name: str,
) -> Dict[str, Any]:
    sources = estimated_metrics.get("sources")
    if isinstance(sources, dict) and isinstance(sources.get(metric_name), dict):
        return sources[metric_name]
    return {"source": "admin_estimate", "field": None}


def _peer_optimizer_metrics(
    peer: Dict[str, Any],
    estimated_metrics: Optional[Dict[str, Any]] = None,
    dataplane_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    estimated_metrics = estimated_metrics or {}
    dataplane_metrics = dataplane_metrics or {}
    latency_ms, latency_field = _first_peer_metric(
        peer,
        ["latency_ms", "rtt_ms", "round_trip_ms"],
    )
    packet_loss, packet_loss_field = _first_peer_metric(
        peer,
        ["packet_loss_percent", "packet_loss_pct", "loss_percent", "loss_pct"],
    )
    if packet_loss is None:
        packet_loss, packet_loss_field = _first_peer_metric(peer, ["packet_loss"])
    packet_loss_ratio, ratio_field = _first_peer_metric(peer, ["packet_loss_ratio"])
    if packet_loss is None and packet_loss_ratio is not None:
        packet_loss = packet_loss_ratio * 100.0
        packet_loss_field = ratio_field

    jitter_ms, jitter_field = _first_peer_metric(peer, ["jitter_ms"])
    bandwidth_mbps, bandwidth_field = _first_peer_metric(
        peer,
        ["bandwidth_mbps", "throughput_mbps"],
    )
    hop_count, hop_count_field = _first_peer_metric(peer, ["hop_count", "hops"])
    estimated_latency = _safe_float(estimated_metrics.get("latency_ms"))
    estimated_bandwidth = _safe_float(estimated_metrics.get("bandwidth_mbps"))
    dataplane_latency = _safe_float(dataplane_metrics.get("latency_ms"))
    dataplane_packet_loss = _safe_float(
        dataplane_metrics.get("packet_loss_percent")
    )
    dataplane_jitter = _safe_float(dataplane_metrics.get("jitter_ms"))

    latency_observed = latency_ms is not None
    packet_loss_observed = packet_loss is not None
    latency_probed = not latency_observed and dataplane_latency is not None
    latency_estimated = not latency_observed and estimated_latency is not None
    bandwidth_estimated = bandwidth_mbps is None and estimated_bandwidth is not None
    if latency_observed:
        latency_source = {"source": "peer_field", "field": latency_field}
    elif latency_probed:
        latency_ms = dataplane_latency
        latency_source = _estimated_source(dataplane_metrics, "latency_ms")
    elif latency_estimated:
        latency_ms = estimated_latency
        latency_source = _estimated_source(estimated_metrics, "latency_ms")
    else:
        latency_ms = _DEFAULT_LATENCY_MS
        latency_source = {"source": "default_baseline", "field": None}

    if bandwidth_estimated:
        bandwidth_mbps = estimated_bandwidth
        bandwidth_source = _estimated_source(estimated_metrics, "bandwidth_mbps")
    else:
        bandwidth_source = {
            "source": "peer_field" if bandwidth_mbps is not None else "missing",
            "field": bandwidth_field,
        }

    packet_loss_probed = (
        not packet_loss_observed and dataplane_packet_loss is not None
    )
    if packet_loss_observed:
        packet_loss_source = {"source": "peer_field", "field": packet_loss_field}
    elif packet_loss_probed:
        packet_loss = dataplane_packet_loss
        packet_loss_source = _estimated_source(
            dataplane_metrics,
            "packet_loss_percent",
        )
    else:
        packet_loss = _DEFAULT_PACKET_LOSS_PERCENT
        packet_loss_source = {"source": "default_baseline", "field": None}

    jitter_probed = jitter_ms is None and dataplane_jitter is not None
    if jitter_probed:
        jitter_ms = dataplane_jitter
        jitter_source = _estimated_source(dataplane_metrics, "jitter_ms")
    else:
        jitter_source = {
            "source": "peer_field" if jitter_ms is not None else "missing",
            "field": jitter_field,
        }

    return {
        "latency_ms": latency_ms,
        "packet_loss": packet_loss,
        "jitter_ms": jitter_ms,
        "bandwidth_mbps": bandwidth_mbps,
        "hop_count": int(hop_count) if hop_count is not None else 1,
        "sources": {
            "latency_ms": latency_source,
            "packet_loss_percent": packet_loss_source,
            "jitter_ms": jitter_source,
            "bandwidth_mbps": bandwidth_source,
            "hop_count": {
                "source": "peer_field" if hop_count is not None else "default_direct",
                "field": hop_count_field,
            },
        },
    }


def _metric_source_summary(metric_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "peer_metric_samples": len(metric_sources),
        "defaults": {
            "latency_ms": _DEFAULT_LATENCY_MS,
            "packet_loss_percent": _DEFAULT_PACKET_LOSS_PERCENT,
        },
        "values_redacted": True,
    }
    fallback_used = False
    for metric_name in (
        "latency_ms",
        "packet_loss_percent",
        "jitter_ms",
        "bandwidth_mbps",
        "hop_count",
    ):
        sources = [source.get(metric_name, {}) for source in metric_sources]
        source_counts = Counter(
            str(item.get("source", "missing")) for item in sources
        )
        fields = sorted(
            {
                str(item["field"])
                for item in sources
                if item.get("field")
            }
        )
        if source_counts.get("default_baseline", 0):
            fallback_used = True
        summary[metric_name] = {
            "source_counts": dict(sorted(source_counts.items())),
            "observed": int(source_counts.get("peer_field", 0)),
            "probed": int(source_counts.get("dataplane_probe", 0)),
            "estimated": int(source_counts.get("admin_estimate", 0)),
            "fallback_default": int(source_counts.get("default_baseline", 0)),
            "fields": fields,
        }
    summary["fallback_values_used"] = fallback_used
    return summary


def _recommendation_summary(report: Any) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return {
            "recommendation_count": 0,
            "action_counts": {},
            "values_redacted": True,
        }
    recommendations = report.get("recommendations", []) or []
    action_counts = Counter()
    for recommendation in recommendations:
        if isinstance(recommendation, dict):
            action_counts[str(recommendation.get("action", "unknown"))] += 1
        else:
            action_counts["invalid"] += 1
    return {
        "recommendation_count": len(recommendations),
        "action_counts": dict(sorted(action_counts.items())),
        "values_redacted": True,
    }


def _publish_collector_event(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    status: str,
    duration_ms: float,
    peers_status: str,
    peer_count: int = 0,
    peer_ids: Optional[List[str]] = None,
    route_update_attempts: int = 0,
    routes_updated: int = 0,
    routes_registered: int = 0,
    metric_sources: Optional[List[Dict[str, Any]]] = None,
    metric_enrichment: Optional[Dict[str, Any]] = None,
    dataplane_probe: Optional[Dict[str, Any]] = None,
    report: Any = None,
    downstream_event_ids: Optional[List[str]] = None,
    downstream_source_agents: Optional[List[str]] = None,
    downstream_claim_boundaries: Optional[List[str]] = None,
    error_type: Optional[str] = None,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    evidence_ids = sorted(
        set(str(event_id) for event_id in downstream_event_ids or [])
    )
    source_agents = sorted(
        {str(agent) for agent in downstream_source_agents or [] if str(agent)}
    )
    claim_boundaries = sorted(
        {
            boundary
            for boundary in (
                _safe_claim_boundary(item)
                for item in downstream_claim_boundaries or []
            )
            if boundary
        }
    )[:_CLAIM_BOUNDARY_LIMIT]
    payload: Dict[str, Any] = {
        "component": "mesh.telemetry_collector",
        "stage": "observed_state",
        "operation": "collect_once",
        "resource": _RESOURCE,
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "read_only": False,
        "observed_state": True,
        "control_action": False,
        "safe_actuator": False,
        "source_mode": "yggdrasil_peer_observation_to_optimizer",
        "yggdrasil": {
            "status": peers_status,
            "peer_count": int(peer_count),
            **_peer_hashes(peer_ids or []),
        },
        "optimizer": {
            "route_update_attempts": int(route_update_attempts),
            "routes_updated": int(routes_updated),
            "routes_registered": int(routes_registered),
            "metric_sources": _metric_source_summary(metric_sources or []),
            "metric_enrichment": metric_enrichment or {
                "status": "disabled",
                "source": "none",
                "values_redacted": True,
            },
            "dataplane_probe": dataplane_probe or {
                "status": "disabled",
                "source": "none",
                "values_redacted": True,
            },
            "recommendations": _recommendation_summary(report),
            "values_redacted": True,
        },
        "downstream_evidence": {
            "source_agents": source_agents,
            "event_ids": evidence_ids,
            "events_total": len(evidence_ids),
            "claim_boundaries": claim_boundaries,
            "claim_boundaries_total": len(claim_boundaries),
            "claim_boundaries_truncated": len(
                set(downstream_claim_boundaries or [])
            )
            > len(claim_boundaries),
            "redacted": True,
        },
        "downstream_claim_gates": _downstream_claim_gate_summary(
            bus,
            event_ids=evidence_ids,
            source_agents=source_agents,
        ),
        "claim_boundary": MESH_TELEMETRY_COLLECTOR_CLAIM_BOUNDARY,
    }
    if error_type:
        payload["error"] = {"type": error_type, "message_redacted": True}

    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SERVICE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish mesh-telemetry-collector event: %s", exc)
        return None


class MeshTelemetryCollector:
    """
    Bridge between raw Yggdrasil data and the YggdrasilOptimizer.
    Periodically polls yggdrasilctl and updates route metrics.
    """

    def __init__(
        self,
        interval_seconds: int = 15,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        enable_admin_metric_enrichment: Optional[bool] = None,
        admin_metric_provider: Optional[Any] = None,
        enable_dataplane_probe: Optional[bool] = None,
        dataplane_probe_provider: Optional[Any] = None,
        max_dataplane_probe_peers: Optional[int] = None,
    ):
        self.interval = interval_seconds
        self.optimizer = get_optimizer()
        self._running = False
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.enable_admin_metric_enrichment = (
            _env_flag("X0TTA6BL4_MESH_TELEMETRY_ADMIN_METRICS")
            if enable_admin_metric_enrichment is None
            else bool(enable_admin_metric_enrichment)
        )
        self.admin_metric_provider = admin_metric_provider
        self.enable_dataplane_probe = (
            _env_flag("X0TTA6BL4_MESH_TELEMETRY_DATAPLANE_PROBE")
            if enable_dataplane_probe is None
            else bool(enable_dataplane_probe)
        )
        self.dataplane_probe_provider = dataplane_probe_provider
        self.max_dataplane_probe_peers = (
            _env_int(
                "X0TTA6BL4_MESH_TELEMETRY_DATAPLANE_PROBES_MAX",
                default=3,
                minimum=0,
                maximum=20,
            )
            if max_dataplane_probe_peers is None
            else max(0, min(int(max_dataplane_probe_peers), 20))
        )

    async def start(self):
        self._running = True
        logger.info(
            "Mesh Telemetry Collector started (Interval: %ss)",
            self.interval,
        )
        while self._running:
            try:
                await self._collect_once()
            except Exception as e:
                logger.error(f"Telemetry collection error: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False

    async def _collect_admin_metric_estimates(
        self,
        bus: Optional[EventBus],
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any], List[str]]:
        if not self.enable_admin_metric_enrichment:
            return (
                {},
                {
                    "status": "disabled",
                    "source": "none",
                    "values_redacted": True,
                },
                [],
            )

        real_network_events_before = _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
        provider = self.admin_metric_provider or YggdrasilAdapter(
            event_bus=bus,
            event_project_root=self.event_project_root,
        )
        try:
            admin_peers = await provider.get_peers()
        except Exception as exc:
            event_ids = sorted(
                _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
                - real_network_events_before
            )
            return (
                {},
                {
                    "status": "failed",
                    "source": "yggdrasil_admin_api",
                    "error": {
                        "type": type(exc).__name__,
                        "message_redacted": True,
                    },
                    "event_ids": event_ids,
                    "events_total": len(event_ids),
                    "claim_boundary": (
                        YGGDRASIL_PEER_METRIC_ESTIMATE_CLAIM_BOUNDARY
                    ),
                    "values_redacted": True,
                },
                event_ids,
            )

        estimates: Dict[str, Dict[str, Any]] = {}
        estimated_peer_count = 0
        for admin_peer in admin_peers or []:
            if not isinstance(admin_peer, dict):
                continue
            metrics = admin_peer.get("estimated_metrics")
            if not isinstance(metrics, dict):
                metrics = estimate_yggdrasil_peer_metrics(admin_peer)
            if _safe_float(metrics.get("latency_ms")) is not None or _safe_float(
                metrics.get("bandwidth_mbps")
            ) is not None:
                estimated_peer_count += 1
            for key_name in ("address", "remote", "uri"):
                for key in _peer_match_keys(admin_peer.get(key_name)):
                    estimates[key] = metrics

        event_ids = sorted(
            _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
            - real_network_events_before
        )
        return (
            estimates,
            {
                "status": "success",
                "source": "yggdrasil_admin_api",
                "admin_peer_count": len(admin_peers or []),
                "estimated_peer_count": estimated_peer_count,
                "matched_peer_count": 0,
                "event_ids": event_ids,
                "events_total": len(event_ids),
                "claim_boundary": YGGDRASIL_PEER_METRIC_ESTIMATE_CLAIM_BOUNDARY,
                "values_redacted": True,
            },
            event_ids,
        )

    async def _probe_peer_dataplane(
        self,
        peer_target: str,
        bus: Optional[EventBus],
    ) -> tuple[Dict[str, Any], List[str]]:
        real_network_events_before = _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
        provider = self.dataplane_probe_provider
        try:
            if provider is not None:
                metrics = await provider.probe_peer(peer_target)
            else:
                metrics = await probe_peer_dataplane_ping(
                    peer_target,
                    event_bus=bus,
                    event_project_root=self.event_project_root,
                )
        except Exception as exc:
            event_ids = sorted(
                _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
                - real_network_events_before
            )
            return (
                {
                    "status": "error",
                    "error": {
                        "type": type(exc).__name__,
                        "message_redacted": True,
                    },
                    "redacted": True,
                },
                event_ids,
            )

        evidence = metrics.get("evidence") if isinstance(metrics, dict) else None
        if isinstance(evidence, dict):
            event_ids = [
                str(event_id)
                for event_id in evidence.get("event_ids", [])
                if str(event_id)
            ]
        else:
            event_ids = sorted(
                _event_ids(bus, source_agent=_REAL_NETWORK_AGENT)
                - real_network_events_before
            )
        return (metrics if isinstance(metrics, dict) else {}, event_ids)

    async def _collect_once(self):
        started = time.monotonic()
        bus = _event_bus_or_none(self.event_bus, self.event_project_root)
        yggdrasil_events_before = _event_ids(bus, source_agent="yggdrasil-client")

        # 1. Get peers from Yggdrasil
        try:
            try:
                peers_data = get_yggdrasil_peers(
                    event_bus=bus,
                    event_project_root=self.event_project_root,
                    include_evidence=True,
                )
            except TypeError as exc:
                if "unexpected keyword" not in str(exc):
                    raise
                peers_data = get_yggdrasil_peers()
        except Exception as exc:
            duration_ms = (time.monotonic() - started) * 1000
            failure_event_ids = sorted(
                _event_ids(bus, source_agent="yggdrasil-client")
                - yggdrasil_events_before
            )
            _publish_collector_event(
                event_bus=bus,
                event_project_root=self.event_project_root,
                status="failed",
                duration_ms=duration_ms,
                peers_status="failed",
                downstream_event_ids=failure_event_ids,
                downstream_source_agents=(
                    ["yggdrasil-client"] if failure_event_ids else []
                ),
                error_type=type(exc).__name__,
            )
            raise

        downstream_event_ids = sorted(
            set(_safe_evidence_ids(peers_data))
            | (
                _event_ids(bus, source_agent="yggdrasil-client")
                - yggdrasil_events_before
            )
        )
        downstream_claim_boundaries = _safe_evidence_claim_boundaries(peers_data)
        if peers_data.get("status") != "ok":
            duration_ms = (time.monotonic() - started) * 1000
            _publish_collector_event(
                event_bus=bus,
                event_project_root=self.event_project_root,
                status="skipped",
                duration_ms=duration_ms,
                peers_status=str(peers_data.get("status", "unknown")),
                peer_count=int(peers_data.get("count", 0) or 0),
                downstream_event_ids=downstream_event_ids,
                downstream_source_agents=(
                    ["yggdrasil-client"] if downstream_event_ids else []
                ),
                downstream_claim_boundaries=downstream_claim_boundaries,
            )
            return

        (
            admin_metric_estimates,
            metric_enrichment,
            admin_event_ids,
        ) = await self._collect_admin_metric_estimates(bus)
        downstream_event_ids = sorted(set(downstream_event_ids) | set(admin_event_ids))
        downstream_source_agents = []
        if _safe_evidence_ids(peers_data) or (
            _event_ids(bus, source_agent="yggdrasil-client")
            - yggdrasil_events_before
        ):
            downstream_source_agents.append("yggdrasil-client")
        if admin_event_ids:
            downstream_source_agents.append(_REAL_NETWORK_AGENT)

        peer_ids: List[str] = []
        route_update_attempts = 0
        routes_updated = 0
        routes_registered = 0
        metric_sources: List[Dict[str, Any]] = []
        admin_estimate_matches = 0
        dataplane_probe_event_ids: List[str] = []
        dataplane_probe_attempts = 0
        dataplane_probe_successes = 0
        dataplane_probe_matches = 0
        for peer in peers_data.get("peers", []):
            if not isinstance(peer, dict):
                continue
            peer_id = peer.get("remote")
            if not peer_id:
                continue
            peer_ids.append(str(peer_id))
            estimated_metrics = None
            for key in _peer_match_keys(peer_id):
                if key in admin_metric_estimates:
                    estimated_metrics = admin_metric_estimates[key]
                    admin_estimate_matches += 1
                    break
            dataplane_metrics = None
            probe_target = _peer_probe_target(peer_id)
            if (
                self.enable_dataplane_probe
                and probe_target
                and dataplane_probe_attempts < self.max_dataplane_probe_peers
            ):
                dataplane_probe_attempts += 1
                dataplane_metrics, probe_event_ids = await self._probe_peer_dataplane(
                    probe_target,
                    bus,
                )
                dataplane_probe_event_ids.extend(probe_event_ids)
                if (
                    _safe_float(dataplane_metrics.get("latency_ms")) is not None
                    or _safe_float(
                        dataplane_metrics.get("packet_loss_percent")
                    ) is not None
                ):
                    dataplane_probe_successes += 1
                    dataplane_probe_matches += 1
            optimizer_metrics = _peer_optimizer_metrics(
                peer,
                estimated_metrics,
                dataplane_metrics,
            )
            metric_sources.append(optimizer_metrics["sources"])

            # 2. Register/Update route in optimizer
            # Note: We use peer_id as both destination and next_hop for direct peers
            route_id = f"direct-{peer_id}"

            route_update_attempts += 1
            updated_route = self.optimizer.update_route_metrics(
                route_id=route_id,
                latency_ms=optimizer_metrics["latency_ms"],
                packet_loss=optimizer_metrics["packet_loss"],
                bandwidth_mbps=optimizer_metrics["bandwidth_mbps"],
                jitter_ms=optimizer_metrics["jitter_ms"],
            )
            if updated_route is not None:
                routes_updated += 1

            # If new, register it
            if route_id not in self.optimizer._routes:
                self.optimizer.register_route(
                    RouteMetrics(
                        route_id=route_id,
                        destination=peer_id,
                        next_hop=peer_id,
                        latency_ms=optimizer_metrics["latency_ms"],
                        jitter_ms=optimizer_metrics["jitter_ms"] or 0.0,
                        packet_loss=optimizer_metrics["packet_loss"],
                        bandwidth_mbps=optimizer_metrics["bandwidth_mbps"] or 0.0,
                        hop_count=optimizer_metrics["hop_count"],
                    )
                )
                routes_registered += 1

        # 3. Trigger optimization cycle
        try:
            report = self.optimizer.optimize_routes(
                event_bus=bus,
                event_project_root=self.event_project_root,
                include_evidence=True,
            )
        except TypeError as exc:
            if "unexpected keyword" not in str(exc):
                raise
            report = self.optimizer.optimize_routes()
        optimizer_event_ids = _safe_evidence_ids(report)
        if optimizer_event_ids:
            downstream_event_ids = sorted(
                set(downstream_event_ids) | set(optimizer_event_ids)
            )
            downstream_source_agents.append(_OPTIMIZER_AGENT)
            downstream_claim_boundaries = sorted(
                set(downstream_claim_boundaries)
                | set(_safe_evidence_claim_boundaries(report))
            )
        if report.get("recommendations"):
            logger.info(
                "Mesh Optimizer: %s recommendations generated.",
                len(report["recommendations"]),
            )
        duration_ms = (time.monotonic() - started) * 1000
        metric_enrichment["matched_peer_count"] = admin_estimate_matches
        downstream_event_ids = sorted(
            set(downstream_event_ids) | set(dataplane_probe_event_ids)
        )
        if dataplane_probe_event_ids and _REAL_NETWORK_AGENT not in downstream_source_agents:
            downstream_source_agents.append(_REAL_NETWORK_AGENT)
        if dataplane_probe_event_ids:
            downstream_claim_boundaries = sorted(
                set(downstream_claim_boundaries)
                | {DATAPLANE_PING_PROBE_CLAIM_BOUNDARY}
            )
        dataplane_probe_summary = {
            "status": "success" if dataplane_probe_attempts else (
                "disabled" if not self.enable_dataplane_probe else "skipped"
            ),
            "source": (
                "icmp_ping"
                if self.enable_dataplane_probe
                else "none"
            ),
            "attempts": dataplane_probe_attempts,
            "successes": dataplane_probe_successes,
            "matched_peer_count": dataplane_probe_matches,
            "max_probe_peers": self.max_dataplane_probe_peers,
            "event_ids": sorted(set(dataplane_probe_event_ids)),
            "events_total": len(set(dataplane_probe_event_ids)),
            "claim_boundary": DATAPLANE_PING_PROBE_CLAIM_BOUNDARY,
            "values_redacted": True,
        }
        _publish_collector_event(
            event_bus=bus,
            event_project_root=self.event_project_root,
            status="success",
            duration_ms=duration_ms,
            peers_status=str(peers_data.get("status", "unknown")),
            peer_count=int(peers_data.get("count", len(peer_ids)) or 0),
            peer_ids=peer_ids,
            route_update_attempts=route_update_attempts,
            routes_updated=routes_updated,
            routes_registered=routes_registered,
            metric_sources=metric_sources,
            metric_enrichment=metric_enrichment,
            dataplane_probe=dataplane_probe_summary,
            report=report,
            downstream_event_ids=downstream_event_ids,
            downstream_source_agents=downstream_source_agents,
            downstream_claim_boundaries=downstream_claim_boundaries,
        )

mesh_telemetry_collector = MeshTelemetryCollector()
