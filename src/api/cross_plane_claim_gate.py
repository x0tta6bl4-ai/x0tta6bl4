"""Small API helper for fail-closed cross-plane claim-gate metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

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
    "settlement_finality",
    "dpi_bypass",
)


def _unique_claims(claims: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(claim) for claim in claims if str(claim).strip()))


def cross_plane_claim_gate_metadata(
    claims: Sequence[str],
    *,
    root: Path = DEFAULT_ROOT,
    surface: str = "api",
) -> dict[str, Any]:
    """Return compact fail-closed metadata for API surfaces with strong claims."""

    requested_claims = _unique_claims(claims)
    if build_cross_plane_proof_gate_report is None:
        return {
            "schema": SCHEMA,
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "available": False,
            "surface": surface,
            "requested_claim_ids": requested_claims,
            "blockers": ["cross_plane_proof_gate_unavailable"],
            "claim_boundary": (
                "Cross-plane claim gate unavailable; this API surface must not "
                "promote production, dataplane, DPI, traffic, trust-finality, or "
                "settlement claims from local readiness data alone."
            ),
        }

    try:
        report = build_cross_plane_proof_gate_report(root, claims=tuple(requested_claims))
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "available": False,
            "surface": surface,
            "requested_claim_ids": requested_claims,
            "blockers": [f"cross_plane_proof_gate_error:{type(exc).__name__}"],
            "claim_boundary": (
                "Cross-plane claim gate failed closed; this API surface must not "
                "promote production, dataplane, DPI, traffic, trust-finality, or "
                "settlement claims from local readiness data alone."
            ),
        }

    return {
        "schema": report.get("schema", SCHEMA),
        "decision": report.get("decision", "CROSS_PLANE_CLAIMS_BLOCKED"),
        "allowed": report.get("allowed") is True,
        "available": True,
        "surface": surface,
        "requested_claim_ids": requested_claims,
        "summary": report.get("summary"),
        "context": report.get("context"),
        "claim_results": report.get("claim_results"),
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
