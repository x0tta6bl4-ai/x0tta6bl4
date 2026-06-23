"""Small API helper for fail-closed cross-plane claim-gate metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from scripts.ops.run_cross_plane_proof_gate import (
        build_report as build_cross_plane_proof_gate_report,
    )
except Exception:  # pragma: no cover - fail closed if scripts are unavailable in a runtime image
    build_cross_plane_proof_gate_report = None


SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
DEFAULT_ROOT = Path(".")
DEFAULT_READINESS_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "trust_finality",
    "settlement_finality",
    "dpi_bypass",
)


def _unique_claims(claims: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(claim) for claim in claims if str(claim).strip()))


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _safe_plane_claims(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}

    plane_claims: dict[str, list[str]] = {}
    for plane, claims in value.items():
        plane_id = str(plane)
        claim_ids = _safe_string_list(claims)
        if plane_id and claim_ids:
            plane_claims[plane_id] = claim_ids
    return plane_claims


def _safe_next_actions_by_plane(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return {}

    next_actions: dict[str, list[dict[str, Any]]] = {}
    for plane, actions in value.items():
        plane_id = str(plane)
        if not plane_id or not isinstance(actions, list):
            continue
        plane_actions = [
            dict(action)
            for action in actions
            if isinstance(action, Mapping)
        ]
        if plane_actions:
            next_actions[plane_id] = plane_actions
    return next_actions


def _safe_next_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        dict(action)
        for action in value
        if isinstance(action, Mapping)
    ]


def _safe_proof_dependency_graph(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    graph: dict[str, dict[str, Any]] = {}
    for claim_id, dependency in value.items():
        if isinstance(dependency, Mapping) and str(claim_id):
            graph[str(claim_id)] = dict(dependency)
    return graph


def _claim_plane_summary(
    claim_results: Any,
    *,
    report_plane_claims: Any = None,
    report_plane_blockers: Any = None,
    report_allowed_plane_ids: Any = None,
    report_blocked_plane_ids: Any = None,
) -> dict[str, Any]:
    plane_claims = _safe_plane_claims(report_plane_claims)
    has_report_plane_claims = bool(plane_claims)
    plane_blockers = _safe_plane_claims(report_plane_blockers)
    has_report_plane_blockers = bool(plane_blockers)
    claim_planes: dict[str, list[str]] = {}

    for plane, claim_ids in plane_claims.items():
        for claim_id in claim_ids:
            claim_planes.setdefault(claim_id, []).append(plane)

    if isinstance(claim_results, list):
        for item in claim_results:
            if not isinstance(item, Mapping):
                continue
            claim_id = str(item.get("claim_id") or "")
            if not claim_id:
                continue
            planes = _safe_string_list(item.get("claim_planes"))
            if not planes:
                planes = claim_planes.get(claim_id, [])
            if not planes:
                continue
            if not has_report_plane_claims:
                for plane in planes:
                    plane_claims.setdefault(plane, []).append(claim_id)
            if item.get("allowed") is True:
                continue
            blockers = _safe_string_list(item.get("blockers"))
            if not has_report_plane_blockers:
                for plane in planes:
                    plane_blockers.setdefault(plane, []).extend(blockers)

    blocked_plane_ids = _safe_string_list(report_blocked_plane_ids)
    if not blocked_plane_ids:
        blocked_plane_ids = [
            plane for plane in plane_claims if plane in plane_blockers
        ]
    allowed_plane_ids = _safe_string_list(report_allowed_plane_ids)
    if not allowed_plane_ids:
        blocked_planes = set(blocked_plane_ids)
        allowed_plane_ids = [
            plane for plane in plane_claims if plane not in blocked_planes
        ]

    return {
        "plane_claims": {
            plane: list(dict.fromkeys(claim_ids))
            for plane, claim_ids in plane_claims.items()
        },
        "allowed_plane_ids": allowed_plane_ids,
        "blocked_plane_ids": blocked_plane_ids,
        "plane_blockers": {
            plane: sorted(set(blockers))
            for plane, blockers in plane_blockers.items()
            if blockers
        },
    }


def _claim_result_summary(
    claim_results: Any,
    *,
    fallback_claim_ids: Sequence[str],
    fallback_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    allowed_claim_ids: list[str] = []
    blocked_claim_ids: list[str] = []
    claim_blockers: dict[str, list[str]] = {}
    blockers: list[str] = list(fallback_blockers)

    if isinstance(claim_results, list):
        for item in claim_results:
            if not isinstance(item, Mapping):
                continue
            claim_id = str(item.get("claim_id") or "")
            if not claim_id:
                continue
            if item.get("allowed") is True:
                allowed_claim_ids.append(claim_id)
                continue
            blocked_claim_ids.append(claim_id)
            item_blockers = _safe_string_list(item.get("blockers"))
            if item_blockers:
                claim_blockers[claim_id] = sorted(set(item_blockers))
                blockers.extend(item_blockers)

    if not isinstance(claim_results, list) and fallback_blockers:
        blocked_claim_ids.extend(str(claim) for claim in fallback_claim_ids)
        for claim_id in fallback_claim_ids:
            claim_blockers[str(claim_id)] = sorted(set(fallback_blockers))

    return {
        "allowed_claim_ids": sorted(set(allowed_claim_ids)),
        "blocked_claim_ids": sorted(set(blocked_claim_ids)),
        "blockers": sorted(set(blockers)),
        "claim_blockers": claim_blockers,
    }


def _fail_closed_metadata(
    *,
    surface: str,
    requested_claims: Sequence[str],
    blockers: Sequence[str],
    claim_boundary: str,
) -> dict[str, Any]:
    summary = _claim_result_summary(
        None,
        fallback_claim_ids=requested_claims,
        fallback_blockers=blockers,
    )
    return {
        "schema": SCHEMA,
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "available": False,
        "surface": surface,
        "requested_claim_ids": list(requested_claims),
        **summary,
        **_claim_plane_summary(None),
        "proof_dependency_graph": {},
        "next_actions": [],
        "next_actions_by_plane": {},
        "claim_boundary": claim_boundary,
    }


def cross_plane_claim_gate_metadata(
    claims: Sequence[str],
    *,
    root: Path = DEFAULT_ROOT,
    surface: str = "api",
) -> dict[str, Any]:
    """Return compact fail-closed metadata for API surfaces with strong claims."""

    requested_claims = _unique_claims(claims)
    if build_cross_plane_proof_gate_report is None:
        return _fail_closed_metadata(
            surface=surface,
            blockers=["cross_plane_proof_gate_unavailable"],
            claim_boundary=(
                "Cross-plane claim gate unavailable; this API surface must not "
                "promote production, dataplane, DPI, traffic, trust-finality, or "
                "settlement claims from local readiness data alone."
            ),
            requested_claims=requested_claims,
        )

    try:
        report = build_cross_plane_proof_gate_report(root, claims=tuple(requested_claims))
    except Exception as exc:
        return _fail_closed_metadata(
            surface=surface,
            blockers=[f"cross_plane_proof_gate_error:{type(exc).__name__}"],
            claim_boundary=(
                "Cross-plane claim gate failed closed; this API surface must not "
                "promote production, dataplane, DPI, traffic, trust-finality, or "
                "settlement claims from local readiness data alone."
            ),
            requested_claims=requested_claims,
        )

    claim_results = report.get("claim_results")
    summary = _claim_result_summary(
        claim_results,
        fallback_claim_ids=requested_claims,
        fallback_blockers=_safe_string_list(report.get("blockers")),
    )
    plane_summary = _claim_plane_summary(
        claim_results,
        report_plane_claims=report.get("plane_claims"),
        report_plane_blockers=report.get("plane_blockers"),
        report_allowed_plane_ids=report.get("allowed_plane_ids"),
        report_blocked_plane_ids=report.get("blocked_plane_ids"),
    )

    return {
        "schema": report.get("schema", SCHEMA),
        "decision": report.get("decision", "CROSS_PLANE_CLAIMS_BLOCKED"),
        "allowed": report.get("allowed") is True,
        "available": True,
        "surface": surface,
        "requested_claim_ids": requested_claims,
        **summary,
        **plane_summary,
        "proof_dependency_graph": _safe_proof_dependency_graph(
            report.get("proof_dependency_graph")
        ),
        "next_actions": _safe_next_actions(report.get("next_actions")),
        "next_actions_by_plane": _safe_next_actions_by_plane(
            report.get("next_actions_by_plane")
        ),
        "summary": report.get("summary"),
        "context": report.get("context"),
        "claim_results": claim_results,
        "claim_boundary": report.get("claim_boundary"),
    }


def readiness_cross_plane_claim_gate_metadata(
    *,
    surface: str,
    root: Path = DEFAULT_ROOT,
    claims: Sequence[str] = DEFAULT_READINESS_CLAIMS,
) -> dict[str, Any]:
    """Return the standard fail-closed gate for API readiness surfaces."""

    return cross_plane_claim_gate_metadata(claims, root=root, surface=surface)
