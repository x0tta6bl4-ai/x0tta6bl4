#!/usr/bin/env python3
"""Verify MaaS heal can surface bounded post-action dataplane probe evidence.

This is a local lab verifier. It uses a synthetic stale route to make
MeshNetworkManager perform one local healing action, then runs the configured
bounded post-heal dataplane probe against a redacted target. By default the
EventBus writes to a temporary directory, not the repository event log.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.maas.nodes import healing as maas_healing
from src.coordination.events import EventType, get_event_bus
from src.mesh.network_manager import MeshNetworkManager


SCHEMA = "x0tta6bl4.maas_heal_post_action_dataplane_probe_verifier.v1"
CLAIM_BOUNDARY = (
    "Local verifier only. It proves a bounded post-action dataplane probe can be "
    "attached to a local mesh-network-manager healing event and surfaced by the "
    "MaaS heal evidence adapter. It does not prove customer traffic delivery, "
    "external reachability, sustained mesh quality, production SLOs, or production "
    "readiness."
)

ProbeFunc = Callable[..., Mapping[str, Any] | Awaitable[Mapping[str, Any]]]


class _StaleRoute:
    age = 49.0


class _LabRouter:
    ROUTE_TIMEOUT = 60.0

    def __init__(self) -> None:
        self.discovery_attempts = 0

    def get_routes(self) -> dict[str, list[_StaleRoute]]:
        return {"redacted-lab-destination": [_StaleRoute()]}

    async def _discover_route(self, _destination: str) -> None:
        self.discovery_attempts += 1


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _safe_bool(mapping: Mapping[str, Any], key: str) -> bool:
    return mapping.get(key) is True


def _latest_mesh_heal_event(event_bus: Any) -> Any | None:
    events = event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mesh-network-manager",
        limit=100,
    )
    candidates = [
        event
        for event in events
        if isinstance(getattr(event, "data", None), dict)
        and event.data.get("operation") == "trigger_aggressive_healing"
    ]
    return candidates[-1] if candidates else None


async def run_verification(
    *,
    target: str = "127.0.0.1",
    event_project_root: str,
    count: int = 1,
    timeout_seconds: int = 1,
    probe_func: ProbeFunc | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    event_bus = get_event_bus(event_project_root)
    router = _LabRouter()

    provider = None
    if probe_func is not None:

        class _Provider:
            def probe_peer(self, peer_target: str) -> Mapping[str, Any] | Awaitable[Mapping[str, Any]]:
                return probe_func(
                    peer_target,
                    event_bus=event_bus,
                    event_project_root=event_project_root,
                    count=count,
                    timeout_seconds=timeout_seconds,
                    output_preview_limit=0,
                )

        provider = _Provider()

    manager = MeshNetworkManager(
        event_bus=event_bus,
        event_project_root=event_project_root,
        enable_post_heal_dataplane_probe=True,
        post_heal_dataplane_probe_provider=provider,
        enable_database_node_healing=False,
    )
    manager._router = router

    healed = await manager.trigger_aggressive_healing(
        post_action_dataplane_probe_target=target
    )
    action_event = _latest_mesh_heal_event(event_bus)
    action_data = action_event.data if action_event is not None else {}
    manager_revalidation = action_data.get("post_action_dataplane_revalidation", {})
    manager_gate = manager_revalidation.get("claim_gate", {})

    control_evidence = maas_healing._mesh_healing_control_plane_evidence(
        event_bus,
        evidence_before=[],
    )
    maas_revalidation = maas_healing._mesh_healing_post_action_revalidation(
        healed=healed,
        control_plane_evidence=control_evidence,
        event_bus=event_bus,
    )

    ready = (
        int(healed) > 0
        and router.discovery_attempts > 0
        and _safe_bool(manager_revalidation, "dataplane_confirmed")
        and _safe_bool(manager_revalidation, "post_action_dataplane_revalidated")
        and _safe_bool(manager_gate, "restored_dataplane_claim_allowed")
        and _safe_bool(maas_revalidation, "dataplane_confirmed")
        and _safe_bool(maas_revalidation, "post_action_dataplane_revalidated")
        and _safe_bool(maas_revalidation, "restored_dataplane_claim_allowed")
        and maas_revalidation.get("traffic_delivery_claim_allowed") is False
        and maas_revalidation.get("customer_traffic_claim_allowed") is False
        and maas_revalidation.get("production_readiness_claim_allowed") is False
    )

    return {
        "schema": SCHEMA,
        "decision": (
            "MAAS_HEAL_POST_ACTION_DATAPLANE_PROBE_READY"
            if ready
            else "MAAS_HEAL_POST_ACTION_DATAPLANE_PROBE_BLOCKED"
        ),
        "ready": ready,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "target": {
            "sha256": _sha256_text(target),
            "raw_target_redacted": True,
            "loopback_lab_target": target in {"127.0.0.1", "::1", "localhost"},
        },
        "local_healing": {
            "healed": int(healed),
            "route_discovery_attempts": router.discovery_attempts,
        },
        "mesh_network_manager": {
            "event_id": getattr(action_event, "event_id", None),
            "dataplane_confirmed": _safe_bool(
                manager_revalidation,
                "dataplane_confirmed",
            ),
            "post_action_dataplane_revalidated": _safe_bool(
                manager_revalidation,
                "post_action_dataplane_revalidated",
            ),
            "restored_dataplane_claim_allowed": _safe_bool(
                manager_gate,
                "restored_dataplane_claim_allowed",
            ),
            "claim_gate_decision": str(manager_gate.get("decision") or ""),
            "blockers": list(manager_gate.get("blockers") or []),
        },
        "maas_heal_surface": {
            "status": maas_revalidation.get("status"),
            "reason": maas_revalidation.get("reason"),
            "dataplane_confirmed": _safe_bool(
                maas_revalidation,
                "dataplane_confirmed",
            ),
            "post_action_dataplane_revalidated": _safe_bool(
                maas_revalidation,
                "post_action_dataplane_revalidated",
            ),
            "restored_dataplane_claim_allowed": _safe_bool(
                maas_revalidation,
                "restored_dataplane_claim_allowed",
            ),
            "traffic_delivery_claim_allowed": maas_revalidation.get(
                "traffic_delivery_claim_allowed"
            )
            is True,
            "customer_traffic_claim_allowed": maas_revalidation.get(
                "customer_traffic_claim_allowed"
            )
            is True,
            "production_readiness_claim_allowed": maas_revalidation.get(
                "production_readiness_claim_allowed"
            )
            is True,
            "evidence": maas_revalidation.get("evidence", {}),
        },
        "event_project_root": event_project_root,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="127.0.0.1")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=1)
    parser.add_argument(
        "--event-project-root",
        default="",
        help=(
            "Where EventBus should write .agent_coordination/events.log. "
            "Defaults to a temporary directory."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.event_project_root:
        event_project_root = args.event_project_root
        Path(event_project_root).mkdir(parents=True, exist_ok=True)
        report = asyncio.run(
            run_verification(
                target=args.target,
                event_project_root=event_project_root,
                count=args.count,
                timeout_seconds=args.timeout_seconds,
            )
        )
    else:
        with tempfile.TemporaryDirectory(prefix="maas-heal-probe-") as tmpdir:
            report = asyncio.run(
                run_verification(
                    target=args.target,
                    event_project_root=tmpdir,
                    count=args.count,
                    timeout_seconds=args.timeout_seconds,
                )
            )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
