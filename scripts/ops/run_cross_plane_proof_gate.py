#!/usr/bin/env python3
"""Fail-closed proof gate for strong cross-plane claims.

This gate does not collect live evidence. It converts the current cross-plane
evidence map into explicit allow/block decisions for claim surfaces that are
easy to over-promote: production readiness, dataplane delivery, trust finality,
DPI bypass, settlement finality, and traffic delivery. The CLI can optionally
write the local gate report as a validation shard.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
DEFAULT_MAP = Path("docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json")
DEFAULT_AUDIT = Path("docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md")
DEFAULT_OUTPUT_JSON = Path(".tmp/validation-shards/cross-plane-proof-gate-current.json")
GHOST_PULSE_PROOF_GATE = Path("scripts/ops/run_ghost_pulse_proof_gate.py")
GHOST_PULSE_EXTERNAL_IMPORT = Path("scripts/ops/import_ghost_pulse_external_evidence.py")
GHOST_PULSE_REPLACEMENT_CANDIDATES = Path("scripts/ops/verify_ghost_pulse_replacement_candidates.py")
GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE = Path("scripts/ops/verify_ghost_pulse_external_evidence_intake.py")
EXTERNAL_DPI_VALIDATOR = Path("scripts/ops/verify_external_dpi_proxy_reachability_evidence.py")
EXTERNAL_DPI_CONTRACT = Path("docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json")
GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST = Path(
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
)
GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST = Path(
    "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
)
GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST = Path(
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
)
EXTERNAL_SETTLEMENT_MODULE = Path("src/integration/external_settlement.py")
EXTERNAL_SETTLEMENT_HANDOFF_MODULE = Path("src/integration/external_settlement_operator_handoff.py")
SERVICE_EVENT_TRACE_MODULE = Path("src/services/service_event_trace.py")
EVENTBUS_LOG = Path(".agent_coordination/events.log")
EVENTBUS_TAIL_SCAN_LIMIT = 1000
ECONOMY_BOUNDARY_CANDIDATE_SCAN_LIMIT = 500
ECONOMY_BOUNDARY_SOURCE_AGENTS = (
    "maas-marketplace",
    "maas-settlement",
    "share-to-earn",
    "token-rewards",
    "token-bridge",
)
DATAPLANE_PROOF_SOURCE_AGENTS = (
    "mesh-action-enforcer",
    "mesh-recovery-orchestrator",
    "real-network-adapter",
)
LOCAL_OBSERVED_STATE_ONLY_SOURCE_AGENTS = (
    "mesh-telemetry-collector",
    "mesh-yggdrasil-optimizer",
    "yggdrasil-client",
)
DPI_IMPORT_BUNDLE_GLOB = "ghost-pulse-external-evidence-import-*"
DPI_IMPORT_REPORT_NAME = "import-report.json"
DPI_IMPORT_REPORT_SCAN_LIMIT = 50
DPI_INTAKE_FAILURES_LIMIT = 10
DATAPLANE_DELIVERY_CLAIM_ID = "dataplane_delivery"
DPI_LAB_CLAIM_ID = "dpi_lab"
PRODUCTION_READINESS_CLAIM_ID = "production_readiness"
EXTERNAL_SETTLEMENT_CLAIM_ID = "external_settlement"
ECONOMY_BOUNDARY_CLAIM_ID = "economy_boundary"
TRUST_FINALITY_CLAIM_ID = "trust_finality"
TRUST_FINALITY_SOURCE_AGENTS = (
    "service-identity-status",
    "spiffe-agent-manager",
    "spiffe-mapek-loop",
    "spiffe-workload-api",
)
CUSTOMER_TRAFFIC_CLAIM_ID = "customer_traffic"
CUSTOMER_TRAFFIC_SOURCE_AGENTS = (
    "customer-traffic-probe",
    "maas-customer-traffic",
    "production-customer-traffic",
)
REQUIRED_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}


@dataclass(frozen=True)
class ClaimRequirement:
    claim_id: str
    description: str
    high_risk: bool
    required_planes: tuple[str, ...] = ()
    required_all_flags: tuple[str, ...] = ()
    required_any_flag_groups: tuple[tuple[str, ...], ...] = ()
    blocking_false_flags: tuple[str, ...] = ()


CLAIM_REQUIREMENTS: dict[str, ClaimRequirement] = {
    "local_observed_state": ClaimRequirement(
        claim_id="local_observed_state",
        description="Local command/event evidence exists and remains local-only.",
        high_risk=False,
        required_planes=("data_plane", "evidence_plane"),
        required_all_flags=("local_observed_state", "eventbus_evidence"),
    ),
    "local_billing_lifecycle": ClaimRequirement(
        claim_id="local_billing_lifecycle",
        description="Local billing lifecycle claim through the billing claim gate.",
        high_risk=False,
        required_planes=("economy_plane", "evidence_plane"),
        required_all_flags=("billing_claim_gate_present", "local_billing_lifecycle_claim_allowed"),
    ),
    "local_reward_accounting": ClaimRequirement(
        claim_id="local_reward_accounting",
        description="Local reward/accounting claim through the reward claim gate.",
        high_risk=False,
        required_planes=("economy_plane", "evidence_plane"),
        required_all_flags=("local_reward_accounting_event", "local_reward_accounting_claim_allowed"),
    ),
    "dataplane_delivery": ClaimRequirement(
        claim_id="dataplane_delivery",
        description="Customer or mesh dataplane delivery claim.",
        high_risk=True,
        required_planes=("data_plane", "evidence_plane"),
        required_all_flags=("dataplane_confirmed",),
        required_any_flag_groups=(("customer_dataplane_delivery_claim_allowed", "traffic_delivery_claim_allowed"),),
        blocking_false_flags=(
            "dataplane_confirmed",
            "customer_dataplane_delivery_claim_allowed",
            "traffic_delivery_claim_allowed",
        ),
    ),
    "traffic_delivery": ClaimRequirement(
        claim_id="traffic_delivery",
        description="Traffic delivery claim.",
        high_risk=True,
        required_planes=("data_plane", "evidence_plane"),
        required_any_flag_groups=(("traffic_delivery_confirmed", "traffic_delivery_claim_allowed"),),
        blocking_false_flags=("traffic_delivery_confirmed", "traffic_delivery_claim_allowed"),
    ),
    "trust_finality": ClaimRequirement(
        claim_id="trust_finality",
        description="Live trust or identity finality claim.",
        high_risk=True,
        required_planes=("trust_plane", "evidence_plane"),
        required_any_flag_groups=(
            (
                "live_spire_svid_confirmed",
                "did_ownership_confirmed",
                "wallet_control_confirmed",
                "chain_identity_finality_confirmed",
            ),
        ),
        blocking_false_flags=(
            "live_spire_svid_confirmed",
            "did_ownership_confirmed",
            "wallet_control_confirmed",
            "chain_identity_finality_confirmed",
        ),
    ),
    "dpi_bypass": ClaimRequirement(
        claim_id="dpi_bypass",
        description="External DPI/proxy bypass claim.",
        high_risk=True,
        required_planes=("data_plane", "evidence_plane"),
        required_all_flags=("external_dpi_tested", "dpi_bypass_confirmed", "bypass_confirmed"),
        blocking_false_flags=("external_dpi_tested", "dpi_bypass_confirmed", "bypass_confirmed"),
    ),
    "settlement_finality": ClaimRequirement(
        claim_id="settlement_finality",
        description="Provider, bank, chain, or token settlement finality claim.",
        high_risk=True,
        required_planes=("economy_plane", "evidence_plane"),
        required_any_flag_groups=(
            (
                "payment_settlement_confirmed",
                "external_settlement_finality_confirmed",
                "settlement_finality_confirmed",
                "live_token_settlement_confirmed",
                "reward_token_settlement_finality_claim_allowed",
            ),
        ),
        blocking_false_flags=(
            "payment_settlement_confirmed",
            "payment_provider_settlement_claim_allowed",
            "bank_settlement_claim_allowed",
            "external_settlement_finality_confirmed",
            "settlement_finality_confirmed",
            "live_token_settlement_confirmed",
            "reward_token_settlement_finality_claim_allowed",
        ),
    ),
    "customer_traffic": ClaimRequirement(
        claim_id="customer_traffic",
        description="Production customer traffic claim.",
        high_risk=True,
        required_planes=("data_plane", "evidence_plane"),
        required_all_flags=("production_customer_traffic_confirmed",),
        blocking_false_flags=("production_customer_traffic_confirmed",),
    ),
    "production_readiness": ClaimRequirement(
        claim_id="production_readiness",
        description="Repository/runtime production-readiness claim.",
        high_risk=True,
        required_planes=(
            "data_plane",
            "control_plane",
            "trust_plane",
            "evidence_plane",
            "economy_plane",
        ),
        required_all_flags=(
            "dataplane_confirmed",
            "production_customer_traffic_confirmed",
            "production_readiness_claim_allowed",
        ),
        required_any_flag_groups=(
            (
                "settlement_finality_confirmed",
                "payment_settlement_confirmed",
                "external_settlement_finality_confirmed",
            ),
            (
                "live_spire_svid_confirmed",
                "did_ownership_confirmed",
                "wallet_control_confirmed",
                "chain_identity_finality_confirmed",
            ),
        ),
        blocking_false_flags=(
            "dataplane_confirmed",
            "production_customer_traffic_confirmed",
            "production_readiness_claim_allowed",
            "reward_production_readiness_claim_allowed",
            "settlement_finality_confirmed",
            "payment_settlement_confirmed",
            "external_settlement_finality_confirmed",
        ),
    ),
}

DEFAULT_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "trust_finality",
    "dpi_bypass",
    "settlement_finality",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(root: Path, path: Path) -> str:
    return str(path.relative_to(root) if path.is_relative_to(root) else path)


def source_artifact_identity(root: Path, path: Path, role: str) -> dict[str, Any]:
    digest = sha256_file(path)
    return {
        "role": role,
        "path": display_path(root, path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_symlink": path.is_symlink(),
        "sha256": digest,
        "sha256_present": bool(digest),
        "claim_boundary": (
            "Source artifact identity proves which local file the proof gate read; "
            "it does not prove that the underlying external-world claim is true."
        ),
    }


def load_script_module(root: Path, rel_path: Path, module_name: str):
    path = root / rel_path
    if not path.exists():
        path = ROOT / rel_path
    module_roots = [path.parents[2] if len(path.parents) > 2 else root, root, ROOT]
    for module_root in reversed(module_roots):
        module_root_text = str(module_root)
        if module_root_text not in sys.path:
            sys.path.insert(0, module_root_text)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bounded_event_log_entries(path: Path, *, limit: int = 1000) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _source_filtered_event_log_entries(
    path: Path,
    *,
    source_agents: Sequence[str],
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_agent_set = {str(agent) for agent in source_agents if str(agent)}
    bounded_limit = max(1, candidate_limit)
    metadata: dict[str, Any] = {
        "strategy": "source_agent_prefiltered_reverse_scan",
        "candidate_events_scanned_limit": bounded_limit,
        "candidate_source_agents": sorted(source_agent_set),
        "event_log_lines_total": 0,
        "event_log_lines_seen": 0,
        "source_filtered_candidates_seen": 0,
        "candidate_events_returned": 0,
        "malformed_lines_skipped": 0,
    }
    if not path.is_file():
        return [], metadata
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        metadata["read_error"] = type(exc).__name__
        return [], metadata

    metadata["event_log_lines_total"] = len(lines)
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        metadata["event_log_lines_seen"] += 1
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            metadata["malformed_lines_skipped"] += 1
            continue
        if not isinstance(entry, dict):
            continue
        if source_agent_set and str(entry.get("source_agent") or "") not in source_agent_set:
            continue
        metadata["source_filtered_candidates_seen"] += 1
        entries.append(entry)
        if len(entries) >= bounded_limit:
            break

    metadata["candidate_events_returned"] = len(entries)
    return entries, metadata


def _count_list_or_field(value: Mapping[str, Any], count_field: str, list_field: str) -> int:
    count = value.get(count_field)
    if isinstance(count, int):
        return count
    items = value.get(list_field)
    return len(items) if isinstance(items, list) else 0


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dataplane_revalidation_candidates(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = []
    for value in (
        data.get("post_action_dataplane_revalidation"),
        _mapping(data.get("result")).get("post_action_dataplane_revalidation"),
        data,
    ):
        candidate = _mapping(value)
        if candidate and (
            "post_action_dataplane_revalidated" in candidate
            or "restored_dataplane_claim_allowed" in candidate
        ):
            candidates.append(candidate)
    return candidates


def _dataplane_candidate_blockers(
    event: Mapping[str, Any],
    revalidation: Mapping[str, Any],
) -> list[str]:
    data = _mapping(event.get("data"))
    gate = _mapping(revalidation.get("claim_gate"))
    observed = _mapping(gate.get("observed_evidence"))
    evidence = _mapping(revalidation.get("evidence")) or _mapping(data.get("downstream_evidence"))
    blockers: list[str] = []
    dataplane_confirmed = (
        revalidation.get("dataplane_confirmed") is True
        or data.get("dataplane_confirmed") is True
    )
    post_action_revalidated = (
        revalidation.get("post_action_dataplane_revalidated") is True
        or data.get("post_action_dataplane_revalidated") is True
    )
    restored_allowed = (
        revalidation.get("restored_dataplane_claim_allowed") is True
        or data.get("restored_dataplane_claim_allowed") is True
    )
    probe_attempted = (
        revalidation.get("probe_attempted") is True
        or gate.get("post_action_probe_attempted") is True
        or observed.get("probe_attempted") is True
    )
    if not dataplane_confirmed:
        blockers.append("dataplane_probe_not_confirmed")
    if not post_action_revalidated:
        blockers.append("post_action_dataplane_not_revalidated")
    if not restored_allowed:
        blockers.append("restored_dataplane_claim_not_allowed")
    if not probe_attempted:
        blockers.append("bounded_dataplane_probe_not_attempted")
    if not gate:
        blockers.append("restored_dataplane_claim_gate_missing")
    else:
        if gate.get("restored_dataplane_claim_allowed") is not True:
            blockers.append("restored_dataplane_claim_gate_not_allowed")
        if gate.get("redacted") is not True:
            blockers.append("restored_dataplane_claim_gate_not_redacted")
        if observed.get("probe_attempted") is not True:
            blockers.append("restored_dataplane_claim_gate_probe_not_observed")
        if observed.get("dataplane_confirmed") is not True:
            blockers.append("restored_dataplane_claim_gate_dataplane_not_observed")
        if gate.get("blockers"):
            blockers.append("restored_dataplane_claim_gate_has_blockers")

    event_ids_count = _count_list_or_field(evidence, "event_ids_count", "event_ids")
    events_total = _count_list_or_field(evidence, "events_total", "event_ids")
    source_agents_count = _count_list_or_field(evidence, "source_agents_count", "source_agents")
    source_agents = _safe_string_list(evidence.get("source_agents"))
    if evidence.get("redacted") is not True:
        blockers.append("dataplane_evidence_not_redacted")
    if event_ids_count <= 0 or events_total <= 0:
        blockers.append("dataplane_evidence_event_ids_missing")
    if source_agents_count <= 0:
        blockers.append("dataplane_evidence_source_agents_missing")
    elif not any(agent in DATAPLANE_PROOF_SOURCE_AGENTS for agent in source_agents):
        blockers.append("dataplane_evidence_source_agent_not_dataplane_probe")
        if all(agent in LOCAL_OBSERVED_STATE_ONLY_SOURCE_AGENTS for agent in source_agents):
            blockers.append("dataplane_evidence_is_local_observed_state_only")
    if not (revalidation.get("claim_boundary") or gate.get("claim_boundary")):
        blockers.append("dataplane_claim_boundary_missing")

    if data.get("production_readiness_claim_allowed") is True:
        blockers.append("dataplane_event_overpromotes_production_readiness")
    if data.get("customer_traffic_claim_allowed") is True or data.get("live_customer_traffic_confirmed") is True:
        blockers.append("dataplane_event_overpromotes_customer_traffic")
    return blockers


def _trust_candidate_blockers(event: Mapping[str, Any]) -> list[str]:
    data = _mapping(event.get("data"))
    gate = _mapping(data.get("claim_gate")) or _mapping(data.get("service_identity_claim_gate"))
    blockers: list[str] = []
    trust_confirmed = any(
        value is True
        for value in (
            data.get("live_spire_svid_confirmed"),
            data.get("live_spiffe_svid_confirmed"),
            data.get("did_ownership_confirmed"),
            data.get("wallet_control_confirmed"),
            data.get("chain_identity_finality_confirmed"),
            gate.get("live_spiffe_svid_claim_allowed"),
            gate.get("did_ownership_claim_allowed"),
            gate.get("wallet_control_claim_allowed"),
            gate.get("chain_identity_finality_claim_allowed"),
            gate.get("production_trust_finality_claim_allowed"),
        )
    )
    redacted = any(
        value is True
        for value in (
            data.get("raw_identity_values_redacted"),
            data.get("raw_identifiers_redacted"),
            data.get("payloads_redacted"),
            gate.get("raw_identity_values_redacted"),
            gate.get("payloads_redacted"),
        )
    )

    if not gate:
        blockers.append("trust_finality_claim_gate_missing")
    if not trust_confirmed:
        blockers.append("trust_finality_not_confirmed")
    if not redacted:
        blockers.append("trust_finality_evidence_not_redacted")
    if not (data.get("claim_boundary") or gate.get("claim_boundary")):
        blockers.append("trust_finality_claim_boundary_missing")
    if gate.get("dataplane_delivery_claim_allowed") is True or data.get("dataplane_confirmed") is True:
        blockers.append("trust_event_overpromotes_dataplane")
    if gate.get("production_readiness_claim_allowed") is True or data.get("production_readiness_claim_allowed") is True:
        blockers.append("trust_event_overpromotes_production_readiness")
    return blockers


def trust_finality_artifact_evidence(root: Path) -> dict[str, Any]:
    path = resolve_path(root, EVENTBUS_LOG)
    result: dict[str, Any] = {
        "claim_id": TRUST_FINALITY_CLAIM_ID,
        "required_for_claims": ["trust_finality", "production_readiness"],
        "valid": False,
        "event_log_path": EVENTBUS_LOG.as_posix(),
        "event_log_exists": path.is_file(),
        "events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "tail_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_source_agents": sorted(TRUST_FINALITY_SOURCE_AGENTS),
        "candidate_scan": None,
        "matching_events": 0,
        "selected_event": None,
        "candidate_blockers": [],
        "blockers": [],
        "claim_boundary": (
            "A retained EventBus trust-finality event can support bounded SPIFFE, "
            "DID, wallet, or chain-identity finality claims only when its own "
            "redacted claim gate allows that trust claim. It does not prove "
            "dataplane delivery, customer traffic, settlement finality, or "
            "production readiness by itself."
        ),
    }
    if not path.is_file():
        result["blockers"].append("trust_finality_event_log_missing")
        return result

    scanned_event_ids: set[str] = set()

    def select_if_valid(event: Mapping[str, Any], scan_source: str) -> bool:
        event_id = str(event.get("event_id") or "")
        if event_id and event_id in scanned_event_ids:
            return False
        if event_id:
            scanned_event_ids.add(event_id)
        if str(event.get("source_agent") or "") not in TRUST_FINALITY_SOURCE_AGENTS:
            return False
        candidate_blockers = _trust_candidate_blockers(event)
        if candidate_blockers:
            for blocker in candidate_blockers:
                if blocker not in result["candidate_blockers"] and len(result["candidate_blockers"]) < 20:
                    result["candidate_blockers"].append(blocker)
            return False
        result["matching_events"] += 1
        result["selected_event"] = {
            "event_id": str(event.get("event_id") or ""),
            "event_type": str(event.get("event_type") or ""),
            "source_agent": str(event.get("source_agent") or ""),
            "timestamp": str(event.get("timestamp") or ""),
            "scan_source": scan_source,
            "trust_finality_confirmed": True,
            "redacted": True,
        }
        result["valid"] = True
        return True

    for event in reversed(_bounded_event_log_entries(path, limit=EVENTBUS_TAIL_SCAN_LIMIT)):
        if select_if_valid(event, "tail_scan"):
            return result

    source_filtered_events, candidate_scan = _source_filtered_event_log_entries(
        path,
        source_agents=TRUST_FINALITY_SOURCE_AGENTS,
        candidate_limit=EVENTBUS_TAIL_SCAN_LIMIT,
    )
    result["candidate_scan"] = candidate_scan
    for event in source_filtered_events:
        if select_if_valid(event, "source_agent_prefiltered_reverse_scan"):
            return result

    result["blockers"].append("verified_trust_finality_event_not_found")
    return result


def _customer_traffic_candidate_blockers(event: Mapping[str, Any]) -> list[str]:
    data = _mapping(event.get("data"))
    gate = _mapping(data.get("claim_gate")) or _mapping(
        data.get("customer_traffic_claim_gate")
    )
    evidence = _mapping(data.get("evidence")) or _mapping(data.get("downstream_evidence"))
    blockers: list[str] = []
    customer_confirmed = any(
        value is True
        for value in (
            data.get("production_customer_traffic_confirmed"),
            data.get("live_customer_traffic_confirmed"),
            data.get("customer_traffic_confirmed"),
            gate.get("production_customer_traffic_confirmed"),
            gate.get("live_customer_traffic_confirmed"),
            gate.get("customer_traffic_claim_allowed"),
            gate.get("customer_traffic_delivery_claim_allowed"),
        )
    )
    redacted = any(
        value is True
        for value in (
            data.get("raw_identifiers_redacted"),
            data.get("raw_values_redacted"),
            data.get("payloads_redacted"),
            gate.get("raw_identifiers_redacted"),
            gate.get("payloads_redacted"),
            evidence.get("redacted"),
        )
    )

    if not gate:
        blockers.append("customer_traffic_claim_gate_missing")
    if not customer_confirmed:
        blockers.append("customer_traffic_not_confirmed")
    if not redacted:
        blockers.append("customer_traffic_evidence_not_redacted")
    if not (data.get("claim_boundary") or gate.get("claim_boundary")):
        blockers.append("customer_traffic_claim_boundary_missing")
    if data.get("production_readiness_claim_allowed") is True or gate.get("production_readiness_claim_allowed") is True:
        blockers.append("customer_traffic_event_overpromotes_production_readiness")
    if data.get("settlement_finality_confirmed") is True or gate.get("external_settlement_finality_claim_allowed") is True:
        blockers.append("customer_traffic_event_overpromotes_settlement_finality")
    return blockers


def customer_traffic_artifact_evidence(root: Path) -> dict[str, Any]:
    path = resolve_path(root, EVENTBUS_LOG)
    result: dict[str, Any] = {
        "claim_id": CUSTOMER_TRAFFIC_CLAIM_ID,
        "required_for_claim": "customer_traffic",
        "required_for_claims": ["customer_traffic", "production_readiness"],
        "valid": False,
        "event_log_path": EVENTBUS_LOG.as_posix(),
        "event_log_exists": path.is_file(),
        "events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "tail_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_source_agents": sorted(CUSTOMER_TRAFFIC_SOURCE_AGENTS),
        "candidate_scan": None,
        "matching_events": 0,
        "selected_event": None,
        "candidate_blockers": [],
        "blockers": [],
        "claim_boundary": (
            "A retained EventBus customer-traffic event can support a bounded "
            "production customer traffic claim only when a redacted end-to-end "
            "customer-path claim gate allows it. Dataplane probes, mesh peer "
            "observations, billing lifecycle, trust finality, or settlement "
            "events do not prove customer traffic by themselves."
        ),
    }
    if not path.is_file():
        result["blockers"].append("customer_traffic_event_log_missing")
        return result

    scanned_event_ids: set[str] = set()

    def select_if_valid(event: Mapping[str, Any], scan_source: str) -> bool:
        event_id = str(event.get("event_id") or "")
        if event_id and event_id in scanned_event_ids:
            return False
        if event_id:
            scanned_event_ids.add(event_id)
        if str(event.get("source_agent") or "") not in CUSTOMER_TRAFFIC_SOURCE_AGENTS:
            return False
        candidate_blockers = _customer_traffic_candidate_blockers(event)
        if candidate_blockers:
            for blocker in candidate_blockers:
                if blocker not in result["candidate_blockers"] and len(result["candidate_blockers"]) < 20:
                    result["candidate_blockers"].append(blocker)
            return False
        result["matching_events"] += 1
        result["selected_event"] = {
            "event_id": str(event.get("event_id") or ""),
            "event_type": str(event.get("event_type") or ""),
            "source_agent": str(event.get("source_agent") or ""),
            "timestamp": str(event.get("timestamp") or ""),
            "scan_source": scan_source,
            "production_customer_traffic_confirmed": True,
            "redacted": True,
        }
        result["valid"] = True
        return True

    for event in reversed(_bounded_event_log_entries(path, limit=EVENTBUS_TAIL_SCAN_LIMIT)):
        if select_if_valid(event, "tail_scan"):
            return result

    source_filtered_events, candidate_scan = _source_filtered_event_log_entries(
        path,
        source_agents=CUSTOMER_TRAFFIC_SOURCE_AGENTS,
        candidate_limit=EVENTBUS_TAIL_SCAN_LIMIT,
    )
    result["candidate_scan"] = candidate_scan
    for event in source_filtered_events:
        if select_if_valid(event, "source_agent_prefiltered_reverse_scan"):
            return result

    result["blockers"].append("verified_customer_traffic_event_not_found")
    return result


def dataplane_delivery_artifact_evidence(root: Path) -> dict[str, Any]:
    path = resolve_path(root, EVENTBUS_LOG)
    result: dict[str, Any] = {
        "claim_id": DATAPLANE_DELIVERY_CLAIM_ID,
        "required_for_claim": "dataplane_delivery",
        "required_for_claims": [
            "dataplane_delivery",
            "traffic_delivery",
            "production_readiness",
        ],
        "valid": False,
        "event_log_path": EVENTBUS_LOG.as_posix(),
        "event_log_exists": path.is_file(),
        "events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "tail_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_source_agents": sorted(DATAPLANE_PROOF_SOURCE_AGENTS),
        "candidate_scan": None,
        "matching_events": 0,
        "selected_event": None,
        "candidate_blockers": [],
        "blockers": [],
        "claim_boundary": (
            "A retained EventBus post-action dataplane probe can support bounded "
            "mesh dataplane delivery only. It does not prove customer traffic, "
            "production SLOs, external reachability, DPI bypass, settlement "
            "finality, or production readiness."
        ),
    }
    if not path.is_file():
        result["blockers"].append("dataplane_event_log_missing")
        return result

    scanned_event_ids: set[str] = set()

    def select_if_valid(event: Mapping[str, Any], scan_source: str) -> bool:
        event_id = str(event.get("event_id") or "")
        if event_id and event_id in scanned_event_ids:
            return False
        if event_id:
            scanned_event_ids.add(event_id)
        data = _mapping(event.get("data"))
        if not data:
            return False
        for revalidation in _dataplane_revalidation_candidates(data):
            candidate_blockers = _dataplane_candidate_blockers(event, revalidation)
            if candidate_blockers:
                for blocker in candidate_blockers:
                    if blocker not in result["candidate_blockers"] and len(result["candidate_blockers"]) < 20:
                        result["candidate_blockers"].append(blocker)
                continue
            result["matching_events"] += 1
            result["selected_event"] = {
                "event_id": str(event.get("event_id") or ""),
                "event_type": str(event.get("event_type") or ""),
                "source_agent": str(event.get("source_agent") or ""),
                "timestamp": str(event.get("timestamp") or ""),
                "scan_source": scan_source,
                "dataplane_confirmed": True,
                "post_action_dataplane_revalidated": True,
                "restored_dataplane_claim_allowed": True,
                "redacted": True,
            }
            result["valid"] = True
            return True
        return False

    for event in reversed(_bounded_event_log_entries(path, limit=EVENTBUS_TAIL_SCAN_LIMIT)):
        if select_if_valid(event, "tail_scan"):
            return result

    source_filtered_events, candidate_scan = _source_filtered_event_log_entries(
        path,
        source_agents=DATAPLANE_PROOF_SOURCE_AGENTS,
        candidate_limit=EVENTBUS_TAIL_SCAN_LIMIT,
    )
    result["candidate_scan"] = candidate_scan
    for event in source_filtered_events:
        if select_if_valid(event, "source_agent_prefiltered_reverse_scan"):
            return result

    result["blockers"].append("verified_dataplane_delivery_event_not_found")
    return result


def _event_trace_summary(root: Path, event: Mapping[str, Any]) -> Mapping[str, Any]:
    precomputed = _mapping(event.get("evidence_summary"))
    if precomputed:
        return precomputed
    trace = load_script_module(root, SERVICE_EVENT_TRACE_MODULE, "cross_plane_service_event_trace")
    return _mapping(trace.event_trace_evidence_summary(_mapping(event.get("data"))))


def _redact_external_settlement_live_rpc_report(report: Mapping[str, Any]) -> dict[str, Any]:
    redacted = dict(report)
    endpoint = redacted.get("rpc_endpoint")
    redacted["rpc_endpoint_present"] = False
    redacted["rpc_endpoint_scheme"] = ""
    redacted["rpc_endpoint_hash"] = None
    if endpoint:
        endpoint_text = str(endpoint)
        redacted["rpc_endpoint_present"] = True
        redacted["rpc_endpoint_scheme"] = (
            endpoint_text.split(":", 1)[0].lower() if "://" in endpoint_text else ""
        )
        redacted["rpc_endpoint_hash"] = hashlib.sha256(endpoint_text.encode("utf-8")).hexdigest()[:16]
    redacted["rpc_endpoint"] = None
    redacted["rpc_endpoint_redacted"] = True
    return redacted


def external_settlement_operator_handoff_context(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "ready_for_completion_rerun": False,
        "decision": None,
        "handoff_decision": None,
        "report_path": None,
        "summary": {},
        "missing_inputs": [],
        "source_reports": [],
        "blockers": [],
        "claim_boundary": (
            "External settlement operator handoff context is diagnostic evidence for "
            "the next local operator steps. It does not prove settlement finality, "
            "production readiness, customer traffic, provider settlement, bank "
            "settlement, or token economic finality."
        ),
    }
    try:
        handoff = load_script_module(
            root,
            EXTERNAL_SETTLEMENT_HANDOFF_MODULE,
            "cross_plane_external_settlement_operator_handoff",
        )
        report = handoff.build_report(root)
        summary = _mapping(report.get("summary"))
        result.update(
            {
                "available": True,
                "ready_for_completion_rerun": report.get("ready_for_completion_rerun") is True,
                "decision": report.get("decision"),
                "handoff_decision": report.get("handoff_decision"),
                "report_path": str(getattr(handoff, "DEFAULT_OUTPUT", "")),
                "summary": {
                    "capture_preflight_available": summary.get("capture_preflight_available") is True,
                    "capture_preflight_decision": summary.get("capture_preflight_decision", ""),
                    "capture_inputs_ready": summary.get("capture_inputs_ready") is True,
                    "evidence_exists": summary.get("evidence_exists") is True,
                    "evidence_file_ready": summary.get("evidence_file_ready") is True,
                    "live_rpc_ready": summary.get("live_rpc_ready") is True,
                    "production_import_external_settlement_ready": (
                        summary.get("production_import_external_settlement_ready") is True
                    ),
                    "completion_gate_external_settlement_ready": (
                        summary.get("completion_gate_external_settlement_ready") is True
                    ),
                    "current_blocker_ready": summary.get("current_blocker_ready") is True,
                    "source_errors_total": summary.get("source_errors_total", 0),
                    "missing_inputs_total": summary.get("missing_inputs_total", 0),
                    "operator_command_entrypoints_missing": (
                        summary.get("operator_command_entrypoints_missing", 0)
                    ),
                    "operator_commands_with_shell_redirection_placeholders": (
                        summary.get("operator_commands_with_shell_redirection_placeholders", 0)
                    ),
                    "operator_sequence_ready": summary.get("operator_sequence_ready") is True,
                    "source_alignment_ready": summary.get("source_alignment_ready") is True,
                    "safety_flags_ready": summary.get("safety_flags_ready") is True,
                },
                "missing_inputs": [
                    {
                        "id": str(item.get("id", "")),
                        "status": str(item.get("status", "")),
                        "reason": str(item.get("reason", "")),
                        "required_artifact": str(item.get("required_artifact", "")),
                    }
                    for item in (
                        report.get("missing_inputs")
                        if isinstance(report.get("missing_inputs"), list)
                        else []
                    )[:10]
                    if isinstance(item, Mapping)
                ],
                "source_reports": [
                    {
                        "label": str(item.get("label", "")),
                        "path": str(item.get("path", "")),
                        "status": str(item.get("status", "")),
                        "decision": str(item.get("decision", "")),
                        "ok": item.get("ok") is True,
                    }
                    for item in (
                        report.get("source_reports")
                        if isinstance(report.get("source_reports"), list)
                        else []
                    )[:10]
                    if isinstance(item, Mapping)
                ],
            }
        )
    except Exception as exc:
        result["blockers"].append(f"external_settlement_operator_handoff_context_error:{type(exc).__name__}")
    return result


def _economy_boundary_candidate_blockers(summary: Mapping[str, Any]) -> list[str]:
    economy = _mapping(summary.get("economy_finality_summary"))
    high_risk_gate = _mapping(economy.get("high_risk_claim_gate"))
    settlement = _mapping(summary.get("settlement_evidence"))
    settlement_gate = _mapping(settlement.get("claim_gate"))
    reward_gate = _mapping(summary.get("reward_claim_gate"))
    request = _mapping(summary.get("request_evidence"))
    output = _mapping(settlement.get("output_summary"))
    blockers: list[str] = []

    if economy.get("present") is not True:
        blockers.append("economy_boundary_summary_missing")
    if high_risk_gate.get("present") is not True:
        blockers.append("economy_high_risk_claim_gate_missing")
    required_claims = _mapping(high_risk_gate.get("required_for_high_risk_claims"))
    if "settlement_finality" not in required_claims:
        blockers.append("economy_settlement_finality_requirement_missing")
    if not economy.get("claim_boundary") or not high_risk_gate.get("claim_boundary"):
        blockers.append("economy_claim_boundary_missing")
    if high_risk_gate.get("redacted") is not True:
        blockers.append("economy_high_risk_gate_not_redacted")

    redacted = any(
        value is True
        for value in (
            settlement_gate.get("raw_identifiers_redacted"),
            settlement_gate.get("payloads_redacted"),
            reward_gate.get("raw_identifiers_redacted"),
            reward_gate.get("payloads_redacted"),
            request.get("raw_identifiers_redacted"),
            output.get("raw_identifiers_redacted"),
            output.get("payloads_redacted"),
        )
    )
    if not redacted:
        blockers.append("economy_event_redaction_metadata_missing")

    local_or_pending_boundary = bool(
        economy.get("local_or_pending_only") is True
        and high_risk_gate.get("external_settlement_finality_claim_allowed") is False
        and "external_settlement_finality_missing" in (high_risk_gate.get("blockers") or [])
    )
    finality_boundary = bool(high_risk_gate.get("external_settlement_finality_claim_allowed") is True)
    if not (local_or_pending_boundary or finality_boundary):
        blockers.append("economy_settlement_boundary_not_demonstrated")
    if high_risk_gate.get("production_readiness_claim_allowed") is True:
        blockers.append("economy_boundary_overpromotes_production_readiness")
    return blockers


def economy_boundary_artifact_evidence(root: Path) -> dict[str, Any]:
    path = resolve_path(root, EVENTBUS_LOG)
    result: dict[str, Any] = {
        "claim_id": ECONOMY_BOUNDARY_CLAIM_ID,
        "required_for_claims": ["settlement_finality", "production_readiness"],
        "valid": False,
        "event_log_path": EVENTBUS_LOG.as_posix(),
        "event_log_exists": path.is_file(),
        "events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "tail_events_scanned_limit": EVENTBUS_TAIL_SCAN_LIMIT,
        "candidate_events_scanned_limit": ECONOMY_BOUNDARY_CANDIDATE_SCAN_LIMIT,
        "candidate_source_agents": sorted(ECONOMY_BOUNDARY_SOURCE_AGENTS),
        "candidate_scan": None,
        "matching_events": 0,
        "selected_event": None,
        "blockers": [],
        "claim_boundary": (
            "A retained EventBus economy-boundary event can support proof-gate "
            "separation between local/pending economy lifecycle evidence and "
            "settlement or production claims. It does not prove provider "
            "settlement, bank settlement, token finality, dataplane delivery, "
            "customer traffic, or production readiness by itself."
        ),
    }
    if not path.is_file():
        result["blockers"].append("economy_event_log_missing")
        return result

    trace_errors: list[str] = []
    scanned_event_ids: set[str] = set()

    def select_if_valid(event: Mapping[str, Any], scan_source: str) -> bool:
        event_id = str(event.get("event_id") or "")
        if event_id and event_id in scanned_event_ids:
            return False
        if event_id:
            scanned_event_ids.add(event_id)
        try:
            summary = _event_trace_summary(root, event)
        except Exception as exc:
            trace_errors.append(type(exc).__name__)
            return False
        blockers = _economy_boundary_candidate_blockers(summary)
        if blockers:
            return False
        economy = _mapping(summary.get("economy_finality_summary"))
        high_risk_gate = _mapping(economy.get("high_risk_claim_gate"))
        result["matching_events"] += 1
        result["selected_event"] = {
            "event_id": str(event.get("event_id") or ""),
            "event_type": str(event.get("event_type") or ""),
            "source_agent": str(event.get("source_agent") or ""),
            "timestamp": str(event.get("timestamp") or ""),
            "scan_source": scan_source,
            "economy_evidence_present": True,
            "local_or_pending_only": economy.get("local_or_pending_only") is True,
            "external_settlement_finality_claim_allowed": (
                high_risk_gate.get("external_settlement_finality_claim_allowed") is True
            ),
            "production_readiness_claim_allowed": False,
            "redacted": True,
        }
        result["valid"] = True
        return True

    for event in reversed(_bounded_event_log_entries(path, limit=EVENTBUS_TAIL_SCAN_LIMIT)):
        if select_if_valid(event, "tail_scan"):
            return result

    source_filtered_events, candidate_scan = _source_filtered_event_log_entries(
        path,
        source_agents=ECONOMY_BOUNDARY_SOURCE_AGENTS,
        candidate_limit=ECONOMY_BOUNDARY_CANDIDATE_SCAN_LIMIT,
    )
    result["candidate_scan"] = candidate_scan
    for event in source_filtered_events:
        if select_if_valid(event, "source_agent_prefiltered_reverse_scan"):
            return result

    result["blockers"].append("verified_economy_boundary_event_not_found")
    if trace_errors:
        result["trace_summary_errors"] = sorted(set(trace_errors))
    return result


def _display_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()


def _import_reports(root: Path) -> list[Path]:
    verification_root = root / "docs" / "verification"
    if not verification_root.is_dir():
        return []
    reports = [
        path / DPI_IMPORT_REPORT_NAME
        for path in verification_root.glob(DPI_IMPORT_BUNDLE_GLOB)
        if path.is_dir() and (path / DPI_IMPORT_REPORT_NAME).is_file()
    ]
    reports.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[:DPI_IMPORT_REPORT_SCAN_LIMIT]


def _dpi_lab_import_report_blockers(
    root: Path,
    report_path: Path,
    report: Mapping[str, Any],
    artifact_rel: str,
    artifact_sha256: str,
) -> list[str]:
    blockers: list[str] = []
    artifacts = _mapping(report.get("artifacts"))
    write_freshness = _mapping(report.get("write_freshness"))
    claim_gate = _mapping(report.get("external_dpi_intake_claim_gate"))
    destination_after = _mapping(report.get("destination_validation_after"))
    external_dpi = _mapping(report.get("external_dpi_proxy_validation"))
    expected_import_report = _display_path(root, report_path)

    if report.get("schema") != "x0tta6bl4.ghost_pulse.external_evidence_import.v1":
        blockers.append("import_report_schema_unexpected")
    if report.get("claim_id") != DPI_LAB_CLAIM_ID:
        blockers.append("import_report_claim_mismatch")
    if report.get("decision") != "READY_TO_IMPORT":
        blockers.append("import_report_not_ready_to_import")
    if report.get("write_requested") is not True:
        blockers.append("import_report_write_not_requested")
    if report.get("written") is not True:
        blockers.append("import_report_not_written")
    if report.get("destination") != artifact_rel:
        blockers.append("import_report_destination_mismatch")
    if report.get("destination_sha256_after") != artifact_sha256:
        blockers.append("import_report_destination_sha256_mismatch")
    if destination_after.get("status") != "VERIFIED":
        blockers.append("import_report_destination_validation_not_verified")
    if external_dpi.get("decision") != "READY_TO_IMPORT":
        blockers.append("import_report_external_dpi_proxy_not_ready")
    if artifacts.get("import_report") != expected_import_report:
        blockers.append("import_report_artifact_path_mismatch")
    if artifacts.get("destination_json") != artifact_rel:
        blockers.append("import_report_destination_artifact_mismatch")
    if write_freshness.get("fresh") is not True:
        blockers.append("import_report_write_freshness_not_fresh")
    if write_freshness.get("replacement_report_current") is not True:
        blockers.append("import_report_replacement_report_not_current")
    if write_freshness.get("intake_report_current") is not True:
        blockers.append("import_report_intake_report_not_current")
    if write_freshness.get("claim_ready_in_replacement_report") is not True:
        blockers.append("import_report_claim_not_ready_in_replacement_report")
    if write_freshness.get("claim_ready_in_intake_report") is not True:
        blockers.append("import_report_claim_not_ready_in_intake_report")
    if write_freshness.get("write_command_currently_ready") is not True:
        blockers.append("import_report_write_command_not_ready")
    if claim_gate.get("write_freshness_claim_allowed") is not True:
        blockers.append("import_report_claim_gate_write_freshness_not_allowed")
    if claim_gate.get("local_latest_evidence_copy_claim_allowed") is not True:
        blockers.append("import_report_claim_gate_latest_copy_not_allowed")
    if claim_gate.get("proof_gate_dpi_bypass_claim_allowed") is not False:
        blockers.append("import_report_claim_gate_overpromotes_dpi_bypass")
    if claim_gate.get("production_readiness_claim_allowed") is not False:
        blockers.append("import_report_claim_gate_overpromotes_production")
    return blockers


def dpi_lab_import_freshness_evidence(root: Path, artifact_path: Path | None) -> dict[str, Any]:
    artifact_rel = _display_path(root, artifact_path) if artifact_path else None
    result: dict[str, Any] = {
        "schema": "x0tta6bl4.cross_plane.dpi_lab_import_freshness.v1",
        "claim_id": DPI_LAB_CLAIM_ID,
        "required_for_claim": "dpi_bypass",
        "valid": False,
        "artifact_path": artifact_rel,
        "artifact_sha256": None,
        "import_bundle_glob": f"docs/verification/{DPI_IMPORT_BUNDLE_GLOB}/{DPI_IMPORT_REPORT_NAME}",
        "reports_scanned_limit": DPI_IMPORT_REPORT_SCAN_LIMIT,
        "reports_scanned": 0,
        "selected_report": None,
        "candidate_report_blockers": [],
        "blockers": [],
        "claim_boundary": (
            "The latest dpi_lab artifact must match a retained external-evidence "
            "import bundle whose write_freshness gate was true. This proves local "
            "import provenance only; it is not independent live DPI or production proof."
        ),
    }
    if artifact_path is None:
        result["blockers"].append("dpi_lab_artifact_path_missing")
        return result
    if not artifact_path.is_file() or artifact_path.is_symlink():
        result["blockers"].append("dpi_lab_artifact_file_not_readable")
        return result
    artifact_sha = sha256_file(artifact_path)
    result["artifact_sha256"] = artifact_sha
    if not artifact_sha or not artifact_rel:
        result["blockers"].append("dpi_lab_artifact_sha256_missing")
        return result

    for report_path in _import_reports(root):
        result["reports_scanned"] += 1
        try:
            report = load_json(report_path)
        except Exception as exc:
            blocker = f"import_report_load_error:{type(exc).__name__}"
            if blocker not in result["candidate_report_blockers"]:
                result["candidate_report_blockers"].append(blocker)
            continue
        blockers = _dpi_lab_import_report_blockers(root, report_path, report, artifact_rel, artifact_sha)
        if blockers:
            for blocker in blockers:
                if blocker not in result["candidate_report_blockers"] and len(result["candidate_report_blockers"]) < 30:
                    result["candidate_report_blockers"].append(blocker)
            continue
        result["selected_report"] = {
            "path": _display_path(root, report_path),
            "bundle": str(report.get("bundle") or ""),
            "timestamp_utc": str(report.get("timestamp_utc") or ""),
            "candidate": str(report.get("candidate") or ""),
            "destination_sha256_after": artifact_sha,
            "write_freshness_claim_allowed": True,
            "local_latest_evidence_copy_claim_allowed": True,
        }
        result["valid"] = True
        return result

    result["blockers"].append("verified_dpi_lab_fresh_import_report_not_found")
    return result


def _bounded_string_list(value: Any, *, limit: int) -> tuple[list[str], int]:
    if not isinstance(value, list):
        return [], 0
    items = [str(item) for item in value]
    return items[:limit], len(items)


def _failure_metadata(value: Any, *, limit: int = DPI_INTAKE_FAILURES_LIMIT) -> dict[str, Any]:
    failures, total = _bounded_string_list(value, limit=limit)
    return {
        "failures": failures,
        "failures_total": total,
        "failures_limit": limit,
        "failures_capped": total > limit,
    }


def _claim_record(report: Mapping[str, Any], field: str, claim_id: str) -> Mapping[str, Any]:
    for item in _dicts(report.get(field)):
        if item.get("claim_id") == claim_id:
            return item
    return {}


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _command_shape_context(row: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    read_only = task.get("read_only_import_command") or row.get("read_only_import_command")
    write = task.get("write_import_command") or row.get("write_import_command")
    collector = task.get("collector_command_shape")
    return {
        "read_only_import_entrypoint_present": isinstance(read_only, list) and bool(read_only),
        "read_only_import_requires_ready": isinstance(read_only, list) and "--require-ready" in read_only,
        "write_import_entrypoint_present": isinstance(write, list) and bool(write),
        "write_import_requires_write_flag": isinstance(write, list) and "--write" in write,
        "collector_entrypoint_present": isinstance(collector, list) and bool(collector),
        "collector_external_probe_flag_present": (
            isinstance(collector, list) and "--allow-external-probes" in collector
        ),
        "collector_local_input_placeholders_present": (
            isinstance(collector, list)
            and any("local input only" in str(item) for item in collector)
        ),
        "acceptance_entrypoints_count": _list_count(task.get("acceptance_commands") or row.get("acceptance_commands")),
        "required_entrypoints_count": _list_count(task.get("required_commands") or row.get("required_commands")),
    }


def _external_dpi_validation_context(value: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(value.get("summary"))
    return {
        "decision": value.get("decision"),
        "status": value.get("status"),
        "summary": {
            "ready_to_import": summary.get("ready_to_import") is True,
            "external_dpi_tested": summary.get("external_dpi_tested") is True,
            "dpi_bypass_confirmed": summary.get("dpi_bypass_confirmed") is True,
            "bypass_confirmed": summary.get("bypass_confirmed") is True,
            "dataplane_confirmed": summary.get("dataplane_confirmed") is True,
            "production_ready": summary.get("production_ready") is True,
            "redaction_performed": summary.get("redaction_performed") is True,
            "forbidden_raw_fields_absent": summary.get("forbidden_raw_fields_absent") is True,
        },
        **_failure_metadata(value.get("failures")),
    }


def _report_context(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "decision": report.get("decision"),
        "ready_count": _list_count(report.get("ready")),
        "not_ready_count": _list_count(report.get("not_ready")),
        **_failure_metadata(report.get("failures")),
    }


def dpi_lab_intake_context(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "claim_id": DPI_LAB_CLAIM_ID,
        "ready_to_import": False,
        "ready_for_write_import": False,
        "replacement_report_path": GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.as_posix(),
        "replacement_report_exists": resolve_path(root, GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST).is_file(),
        "intake_report_path": GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.as_posix(),
        "intake_report_exists": resolve_path(root, GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST).is_file(),
        "replacement_report": None,
        "intake_report": None,
        "candidate": None,
        "candidate_exists": None,
        "candidate_is_file": None,
        "candidate_is_symlink": None,
        "candidate_sha256_present": False,
        "validation": None,
        "external_dpi_proxy_validation": None,
        "command_shapes": {},
        "blockers": [],
        "claim_boundary": (
            "DPI intake context is diagnostic operator handoff metadata. It shows "
            "whether a replacement candidate is ready to import, but it does not "
            "prove DPI bypass, production readiness, customer traffic, anonymity, "
            "or durable censorship resistance."
        ),
    }

    replacement_report: Mapping[str, Any] = {}
    intake_report: Mapping[str, Any] = {}
    try:
        replacement = load_script_module(
            root,
            GHOST_PULSE_REPLACEMENT_CANDIDATES,
            "cross_plane_ghost_pulse_replacement_candidates",
        )
        replacement_report = _mapping(
            replacement.build_report(
                root,
                resolve_path(root, GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST),
            )
        )
        result["available"] = True
        result["replacement_report"] = _report_context(replacement_report)
    except Exception as exc:
        result["blockers"].append(f"dpi_replacement_context_error:{type(exc).__name__}")

    try:
        intake = load_script_module(
            root,
            GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE,
            "cross_plane_ghost_pulse_external_evidence_intake",
        )
        intake_report = _mapping(
            intake.build_report(
                root,
                resolve_path(root, GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST),
            )
        )
        result["available"] = True
        result["intake_report"] = _report_context(intake_report)
    except Exception as exc:
        result["blockers"].append(f"dpi_intake_context_error:{type(exc).__name__}")

    row = _claim_record(replacement_report, "rows", DPI_LAB_CLAIM_ID)
    task = _claim_record(intake_report, "collection_tasks", DPI_LAB_CLAIM_ID)
    if not row and replacement_report:
        result["blockers"].append("dpi_replacement_row_missing")
    if not task and intake_report:
        result["blockers"].append("dpi_intake_collection_task_missing")

    source = task or row
    result["candidate"] = source.get("candidate")
    result["candidate_exists"] = source.get("candidate_exists")
    result["candidate_is_file"] = source.get("candidate_is_file")
    result["candidate_is_symlink"] = source.get("candidate_is_symlink")
    result["candidate_sha256_present"] = bool(source.get("candidate_sha256"))
    result["ready_to_import"] = task.get("ready_to_import") is True or row.get("ready_to_import") is True
    result["command_shapes"] = _command_shape_context(row, task)
    result["ready_for_write_import"] = (
        result["ready_to_import"] is True
        and result["command_shapes"].get("write_import_entrypoint_present") is True
    )

    validation_failures = task.get("failures") or row.get("failures") or row.get("validation_errors")
    result["validation"] = {
        "status": task.get("validation_status") or row.get("validation_status"),
        "row_status": task.get("status") or row.get("status"),
        "import_decision": task.get("import_decision") or row.get("import_decision"),
        **_failure_metadata(validation_failures),
    }

    external_validation = _mapping(task.get("external_dpi_proxy_validation")) or _mapping(
        row.get("external_dpi_proxy_validation")
    )
    result["external_dpi_proxy_validation"] = _external_dpi_validation_context(external_validation)
    return result


def dpi_lab_artifact_evidence(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "claim_id": DPI_LAB_CLAIM_ID,
        "required_for_claim": "dpi_bypass",
        "valid": False,
        "artifact_path": None,
        "artifact_exists": False,
        "proof_gate_validation": None,
        "external_dpi_proxy_validation": None,
        "import_freshness": None,
        "intake_context": None,
        "blockers": [],
        "claim_boundary": (
            "Imported dpi_lab evidence can support bounded DPI/proxy bypass only. "
            "It does not prove production readiness, durable censorship bypass, "
            "anonymity, provider health, customer traffic, or settlement finality."
        ),
    }
    result["intake_context"] = dpi_lab_intake_context(root)
    try:
        proof = load_script_module(root, GHOST_PULSE_PROOF_GATE, "cross_plane_ghost_pulse_proof_gate")
        requirements = proof.requirement_by_claim()
        requirement = requirements.get(DPI_LAB_CLAIM_ID)
        if not requirement:
            result["blockers"].append("dpi_lab_requirement_missing")
            return result
        artifact_path = resolve_path(root, Path(requirement["path"]))
        result["artifact_path"] = (
            artifact_path.relative_to(root).as_posix()
            if artifact_path.is_relative_to(root)
            else artifact_path.as_posix()
        )
        result["artifact_exists"] = artifact_path.is_file()
        proof_validation = proof.validate_external_evidence(root, requirement)
        result["proof_gate_validation"] = proof_validation
        if proof_validation.get("status") != "VERIFIED":
            result["blockers"].append("dpi_lab_proof_gate_validation_not_verified")
    except Exception as exc:
        result["blockers"].append(f"dpi_lab_proof_gate_validation_error:{exc}")
        return result

    try:
        validator = load_script_module(root, EXTERNAL_DPI_VALIDATOR, "cross_plane_external_dpi_validator")
        contract = load_json(resolve_path(root, EXTERNAL_DPI_CONTRACT))
        payload = load_json(resolve_path(root, Path(str(result["artifact_path"]))))
        failures = []
        failures.extend(validator.validate_payload(contract, payload))
        failures.extend(validator.source_artifact_errors(root, payload))
        external_validation = {
            "decision": validator.DECISION_READY if not failures else validator.DECISION_REJECTED,
            "failures": failures,
            "summary": {
                "external_dpi_tested": bool(validator.dotted_get(payload, "result_summary.external_dpi_tested")),
                "dpi_bypass_confirmed": bool(validator.dotted_get(payload, "result_summary.dpi_bypass_confirmed")),
                "bypass_confirmed": bool(validator.dotted_get(payload, "result_summary.bypass_confirmed")),
                "dataplane_confirmed": bool(validator.dotted_get(payload, "result_summary.dataplane_confirmed")),
                "production_ready": bool(validator.dotted_get(payload, "result_summary.production_ready")),
            },
        }
        result["external_dpi_proxy_validation"] = external_validation
        if external_validation["decision"] != validator.DECISION_READY:
            result["blockers"].append("external_dpi_proxy_validation_not_ready")
    except Exception as exc:
        result["blockers"].append(f"external_dpi_proxy_validation_error:{exc}")

    import_freshness = dpi_lab_import_freshness_evidence(
        root,
        resolve_path(root, Path(str(result["artifact_path"]))) if result.get("artifact_path") else None,
    )
    result["import_freshness"] = import_freshness
    if import_freshness.get("valid") is not True:
        result["blockers"].append("dpi_lab_import_freshness_not_verified")

    result["valid"] = not result["blockers"]
    return result


def production_readiness_artifact_evidence(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "claim_id": PRODUCTION_READINESS_CLAIM_ID,
        "required_for_claim": "production_readiness",
        "valid": False,
        "artifact_path": None,
        "artifact_exists": False,
        "proof_gate_validation": None,
        "blockers": [],
        "claim_boundary": (
            "Imported production_readiness evidence can support a local proof-gate "
            "decision only after Ghost Pulse validates operator approval, rollback "
            "plan, monitoring plan, and prior claim references. It is not independent "
            "live customer traffic, settlement finality, or production SLO proof."
        ),
    }
    try:
        proof = load_script_module(root, GHOST_PULSE_PROOF_GATE, "cross_plane_production_readiness_proof_gate")
        requirements = proof.requirement_by_claim()
        requirement = requirements.get(PRODUCTION_READINESS_CLAIM_ID)
        if not requirement:
            result["blockers"].append("production_readiness_requirement_missing")
            return result
        artifact_path = resolve_path(root, Path(requirement["path"]))
        result["artifact_path"] = (
            artifact_path.relative_to(root).as_posix()
            if artifact_path.is_relative_to(root)
            else artifact_path.as_posix()
        )
        result["artifact_exists"] = artifact_path.is_file()
        proof_validation = proof.validate_external_evidence(root, requirement)
        result["proof_gate_validation"] = proof_validation
        if proof_validation.get("status") != "VERIFIED":
            result["blockers"].append("production_readiness_proof_gate_validation_not_verified")
    except Exception as exc:
        result["blockers"].append(f"production_readiness_proof_gate_validation_error:{exc}")

    result["valid"] = not result["blockers"]
    return result


def external_settlement_artifact_evidence(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "claim_id": EXTERNAL_SETTLEMENT_CLAIM_ID,
        "required_for_claim": "settlement_finality",
        "required_for_claims": ["settlement_finality", "production_readiness"],
        "valid": False,
        "evidence_path": None,
        "evidence_exists": False,
        "retained_evidence_validation": None,
        "live_rpc_report_path": None,
        "live_rpc_report": None,
        "blocker_report_path": None,
        "blocker_report": None,
        "operator_handoff": None,
        "blockers": [],
        "claim_boundary": (
            "External settlement evidence can support settlement_finality and the "
            "settlement leg of production_readiness only when the retained receipt "
            "is valid and a saved read-only live RPC/blocker report says "
            "READY_TO_PROMOTE. It does not prove production readiness by itself, "
            "customer traffic, provider settlement, bank settlement, or token "
            "economic finality."
        ),
    }
    try:
        settlement = load_script_module(root, EXTERNAL_SETTLEMENT_MODULE, "cross_plane_external_settlement")
        evidence_rel = Path(settlement.DEFAULT_EVIDENCE_PATH)
        rpc_rel = Path(settlement.DEFAULT_RPC_REPORT)
        blocker_rel = Path(settlement.DEFAULT_BLOCKER_REPORT)
        evidence_path = resolve_path(root, evidence_rel)
        rpc_path = resolve_path(root, rpc_rel)
        blocker_path = resolve_path(root, blocker_rel)
        result["evidence_path"] = evidence_rel.as_posix()
        result["live_rpc_report_path"] = rpc_rel.as_posix()
        result["blocker_report_path"] = blocker_rel.as_posix()
        result["operator_handoff"] = external_settlement_operator_handoff_context(root)
        result["evidence_exists"] = evidence_path.is_file()

        retained = settlement.validate_evidence_file(evidence_path, evidence_rel.as_posix())
        retained_report = retained.report()
        result["retained_evidence_validation"] = retained_report
        if retained.valid is not True:
            result["blockers"].append("external_settlement_retained_evidence_not_verified")

        if not rpc_path.is_file():
            result["blockers"].append("external_settlement_live_rpc_report_missing")
        else:
            rpc_report = _redact_external_settlement_live_rpc_report(load_json(rpc_path))
            result["live_rpc_report"] = rpc_report
            rpc_summary = rpc_report.get("summary") if isinstance(rpc_report, Mapping) else {}
            rpc_result = rpc_report.get("live_rpc_result") if isinstance(rpc_report, Mapping) else {}
            if not isinstance(rpc_summary, Mapping) or rpc_summary.get("x0t_external_settlement_live_rpc_ready") is not True:
                result["blockers"].append("external_settlement_live_rpc_not_ready")
            if not isinstance(rpc_summary, Mapping) or rpc_summary.get("live_rpc_checked") is not True:
                result["blockers"].append("external_settlement_live_rpc_not_checked")
            if not isinstance(rpc_result, Mapping) or rpc_result.get("errors"):
                result["blockers"].append("external_settlement_live_rpc_errors_present")
            if retained.valid and isinstance(rpc_result, Mapping):
                if str(rpc_result.get("transaction_hash", "")).lower() != retained.transaction_hash.lower():
                    result["blockers"].append("external_settlement_live_rpc_transaction_hash_mismatch")

        if not blocker_path.is_file():
            result["blockers"].append("external_settlement_blocker_report_missing")
        else:
            blocker_report = load_json(blocker_path)
            result["blocker_report"] = blocker_report
            blocker_summary = blocker_report.get("summary") if isinstance(blocker_report, Mapping) else {}
            if blocker_report.get("decision") != "READY_TO_PROMOTE":
                result["blockers"].append("external_settlement_blocker_not_ready_to_promote")
            if not isinstance(blocker_summary, Mapping) or blocker_summary.get("x0t_external_settlement_ready") is not True:
                result["blockers"].append("external_settlement_blocker_summary_not_ready")
            source_artifacts = blocker_report.get("source_artifacts") if isinstance(blocker_report, Mapping) else []
            expected_sources = {
                settlement.DEFAULT_EVIDENCE_REPORT,
                settlement.DEFAULT_RPC_REPORT,
            }
            if not isinstance(source_artifacts, list) or not expected_sources.issubset(
                {str(item) for item in source_artifacts}
            ):
                result["blockers"].append("external_settlement_blocker_source_artifacts_missing")
    except Exception as exc:
        result["blockers"].append(f"external_settlement_artifact_validation_error:{exc}")

    result["valid"] = not result["blockers"]
    return result


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def collect_flag_index(evidence_map: Mapping[str, Any]) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = {}
    for link in _dicts(evidence_map.get("cross_plane_links")):
        link_id = str(link.get("id") or "unknown-link")
        flags = link.get("proof_flags")
        if not isinstance(flags, dict):
            continue
        for flag, value in flags.items():
            bucket = "true_links" if value is True else "false_links" if value is False else "non_bool_links"
            flag_state = index.setdefault(str(flag), {"true_links": [], "false_links": [], "non_bool_links": []})
            flag_state[bucket].append(link_id)
    return index


def map_context(root: Path, map_path: Path, audit_path: Path, evidence_map: Mapping[str, Any] | None) -> dict[str, Any]:
    planes = evidence_map.get("planes") if isinstance(evidence_map, Mapping) else None
    plane_ids = set(planes) if isinstance(planes, Mapping) else set()
    current_gaps = evidence_map.get("current_gaps") if isinstance(evidence_map, Mapping) else []
    next_actions = evidence_map.get("next_actions") if isinstance(evidence_map, Mapping) else []
    gaps = _dicts(current_gaps)
    blocking_gaps = [item for item in gaps if item.get("blocks_real_readiness") is not False]
    non_blocking_gaps = [item for item in gaps if item.get("blocks_real_readiness") is False]
    actions = _dicts(next_actions)
    map_identity = source_artifact_identity(root, map_path, "current_cross_plane_evidence_map")
    audit_identity = source_artifact_identity(root, audit_path, "current_active_goal_gap_audit")
    return {
        "map_path": map_identity["path"],
        "audit_path": audit_identity["path"],
        "map_exists": map_path.exists(),
        "audit_exists": audit_path.exists(),
        "map_sha256": map_identity["sha256"],
        "audit_sha256": audit_identity["sha256"],
        "source_artifact_hashes_present": (
            map_identity["sha256_present"] is True and audit_identity["sha256_present"] is True
        ),
        "source_artifacts": [map_identity, audit_identity],
        "status": evidence_map.get("status") if isinstance(evidence_map, Mapping) else None,
        "required_planes_present": REQUIRED_PLANES.issubset(plane_ids),
        "plane_ids": sorted(plane_ids),
        "open_gap_ids": [str(item.get("id")) for item in blocking_gaps if item.get("id")],
        "non_blocking_gap_ids": [
            str(item.get("id")) for item in non_blocking_gaps if item.get("id")
        ],
        "next_action_ids": [str(item.get("id")) for item in actions if item.get("id")],
        "current_gap_count": len(blocking_gaps),
        "tracked_gap_count": len(gaps),
        "non_blocking_gap_count": len(non_blocking_gaps),
        "next_action_count": len(actions),
    }


def context_blockers(context: Mapping[str, Any], *, high_risk: bool) -> list[str]:
    blockers: list[str] = []
    if context.get("map_exists") is not True:
        blockers.append("current_evidence_map_missing")
    if context.get("audit_exists") is not True:
        blockers.append("current_active_goal_audit_missing")
    if context.get("status") != "working_map_not_production_completion_proof":
        blockers.append("current_evidence_map_unexpected_status")
    if context.get("required_planes_present") is not True:
        blockers.append("current_evidence_required_planes_missing")
    if high_risk and context.get("current_gap_count"):
        blockers.append("current_evidence_open_gaps")
    if high_risk and context.get("next_action_count"):
        blockers.append("current_evidence_next_actions_open")
    return blockers


def evaluate_claim(
    claim_id: str,
    context: Mapping[str, Any],
    flag_index: Mapping[str, Mapping[str, list[str]]],
    artifact_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    requirement = CLAIM_REQUIREMENTS.get(claim_id)
    if requirement is None:
        return {
            "claim_id": claim_id,
            "allowed": False,
            "known_claim": False,
            "high_risk": True,
            "blockers": ["unknown_claim"],
            "missing_true_flags": [],
            "blocking_false_flags": [],
            "satisfied_true_flags": [],
            "claim_boundary": "Unknown claims are blocked by default.",
        }

    blockers = context_blockers(context, high_risk=requirement.high_risk)
    missing_true_flags: list[str] = []
    blocking_false_flags: list[dict[str, Any]] = []
    satisfied_true_flags: list[str] = []
    missing_any_groups: list[list[str]] = []
    supporting_artifact_evidence: dict[str, Mapping[str, Any]] = {}

    for flag in requirement.required_all_flags:
        true_links = flag_index.get(flag, {}).get("true_links", [])
        if true_links:
            satisfied_true_flags.append(flag)
        else:
            missing_true_flags.append(flag)
            blockers.append(f"missing_true_flag:{flag}")

    for group in requirement.required_any_flag_groups:
        if any(flag_index.get(flag, {}).get("true_links") for flag in group):
            satisfied_true_flags.extend(
                flag for flag in group if flag_index.get(flag, {}).get("true_links")
            )
        else:
            missing_any_groups.append(list(group))
            blockers.append("missing_any_true_flags:" + ",".join(group))

    for flag in requirement.blocking_false_flags:
        false_links = flag_index.get(flag, {}).get("false_links", [])
        if false_links:
            blocking_false_flags.append({"flag": flag, "links": sorted(false_links)})
            blockers.append(f"explicit_false_flag:{flag}")

    claim_artifact_evidence: Mapping[str, Any] | None = None
    if claim_id == "dataplane_delivery":
        claim_artifact_evidence = (artifact_evidence or {}).get(DATAPLANE_DELIVERY_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("dataplane_delivery_eventbus_artifact_not_verified")
    elif claim_id == "traffic_delivery":
        claim_artifact_evidence = (artifact_evidence or {}).get(DATAPLANE_DELIVERY_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("traffic_delivery_dataplane_artifact_not_verified")
    elif claim_id == "trust_finality":
        claim_artifact_evidence = (artifact_evidence or {}).get(TRUST_FINALITY_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("trust_finality_eventbus_artifact_not_verified")
    elif claim_id == "customer_traffic":
        claim_artifact_evidence = (artifact_evidence or {}).get(CUSTOMER_TRAFFIC_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("customer_traffic_eventbus_artifact_not_verified")
    elif claim_id == "dpi_bypass":
        claim_artifact_evidence = (artifact_evidence or {}).get(DPI_LAB_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("dpi_lab_imported_artifact_not_verified")
    elif claim_id == "production_readiness":
        claim_artifact_evidence = (artifact_evidence or {}).get(PRODUCTION_READINESS_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("production_readiness_imported_artifact_not_verified")
        dataplane_boundary = (artifact_evidence or {}).get(DATAPLANE_DELIVERY_CLAIM_ID)
        if dataplane_boundary is not None:
            supporting_artifact_evidence[DATAPLANE_DELIVERY_CLAIM_ID] = dataplane_boundary
        if not dataplane_boundary or dataplane_boundary.get("valid") is not True:
            blockers.append("production_readiness_dataplane_artifact_not_verified")
        customer_traffic = (artifact_evidence or {}).get(CUSTOMER_TRAFFIC_CLAIM_ID)
        if customer_traffic is not None:
            supporting_artifact_evidence[CUSTOMER_TRAFFIC_CLAIM_ID] = customer_traffic
        if not customer_traffic or customer_traffic.get("valid") is not True:
            blockers.append("production_readiness_customer_traffic_artifact_not_verified")
        economy_boundary = (artifact_evidence or {}).get(ECONOMY_BOUNDARY_CLAIM_ID)
        if economy_boundary is not None:
            supporting_artifact_evidence[ECONOMY_BOUNDARY_CLAIM_ID] = economy_boundary
        if not economy_boundary or economy_boundary.get("valid") is not True:
            blockers.append("economy_boundary_artifact_not_verified")
        external_settlement = (artifact_evidence or {}).get(EXTERNAL_SETTLEMENT_CLAIM_ID)
        if external_settlement is not None:
            supporting_artifact_evidence[EXTERNAL_SETTLEMENT_CLAIM_ID] = external_settlement
        if not external_settlement or external_settlement.get("valid") is not True:
            blockers.append("production_readiness_external_settlement_artifact_not_verified")
        trust_boundary = (artifact_evidence or {}).get(TRUST_FINALITY_CLAIM_ID)
        if trust_boundary is not None:
            supporting_artifact_evidence[TRUST_FINALITY_CLAIM_ID] = trust_boundary
        if not trust_boundary or trust_boundary.get("valid") is not True:
            blockers.append("trust_finality_artifact_not_verified")
    elif claim_id == "settlement_finality":
        claim_artifact_evidence = (artifact_evidence or {}).get(EXTERNAL_SETTLEMENT_CLAIM_ID)
        if not claim_artifact_evidence or claim_artifact_evidence.get("valid") is not True:
            blockers.append("external_settlement_artifact_not_verified")
        economy_boundary = (artifact_evidence or {}).get(ECONOMY_BOUNDARY_CLAIM_ID)
        if economy_boundary is not None:
            supporting_artifact_evidence[ECONOMY_BOUNDARY_CLAIM_ID] = economy_boundary
        if not economy_boundary or economy_boundary.get("valid") is not True:
            blockers.append("economy_boundary_artifact_not_verified")

    allowed = not blockers
    result = {
        "claim_id": claim_id,
        "known_claim": True,
        "allowed": allowed,
        "high_risk": requirement.high_risk,
        "description": requirement.description,
        "claim_planes": list(requirement.required_planes),
        "blockers": sorted(set(blockers)),
        "missing_true_flags": sorted(set(missing_true_flags)),
        "missing_any_flag_groups": missing_any_groups,
        "blocking_false_flags": blocking_false_flags,
        "satisfied_true_flags": sorted(set(satisfied_true_flags)),
        "claim_boundary": (
            "Allowed means the current map has the required proof flags and no "
            "open current-evidence blockers for this claim. It is still a local "
            "gate decision, not independent live-system proof."
            if allowed
            else "Blocked claims must not be promoted as production, dataplane, trust-finality, DPI, traffic, or settlement proof."
        ),
    }
    if claim_artifact_evidence is not None:
        result["required_artifact_evidence"] = claim_artifact_evidence
    if supporting_artifact_evidence:
        result["supporting_artifact_evidence"] = supporting_artifact_evidence
    return result


def build_report(
    root: Path,
    *,
    map_path: Path = DEFAULT_MAP,
    audit_path: Path = DEFAULT_AUDIT,
    claims: Sequence[str] = DEFAULT_CLAIMS,
) -> dict[str, Any]:
    root = root.resolve()
    resolved_map = resolve_path(root, map_path)
    resolved_audit = resolve_path(root, audit_path)
    load_errors: list[str] = []
    evidence_map: dict[str, Any] | None = None
    if resolved_map.exists():
        try:
            evidence_map = load_json(resolved_map)
        except Exception as exc:
            load_errors.append(f"current_evidence_map_invalid:{exc}")
    context = map_context(root, resolved_map, resolved_audit, evidence_map)
    flag_index = collect_flag_index(evidence_map or {})
    artifact_evidence: dict[str, Mapping[str, Any]] = {}
    if any(claim in claims for claim in ("dataplane_delivery", "traffic_delivery", "production_readiness")):
        artifact_evidence[DATAPLANE_DELIVERY_CLAIM_ID] = dataplane_delivery_artifact_evidence(root)
    if any(claim in claims for claim in ("trust_finality", "production_readiness")):
        artifact_evidence[TRUST_FINALITY_CLAIM_ID] = trust_finality_artifact_evidence(root)
    if any(claim in claims for claim in ("customer_traffic", "production_readiness")):
        artifact_evidence[CUSTOMER_TRAFFIC_CLAIM_ID] = customer_traffic_artifact_evidence(root)
    if any(claim in claims for claim in ("settlement_finality", "production_readiness")):
        artifact_evidence[ECONOMY_BOUNDARY_CLAIM_ID] = economy_boundary_artifact_evidence(root)
    if "dpi_bypass" in claims:
        artifact_evidence[DPI_LAB_CLAIM_ID] = dpi_lab_artifact_evidence(root)
    if "production_readiness" in claims:
        artifact_evidence[PRODUCTION_READINESS_CLAIM_ID] = production_readiness_artifact_evidence(root)
    if any(claim in claims for claim in ("settlement_finality", "production_readiness")):
        artifact_evidence[EXTERNAL_SETTLEMENT_CLAIM_ID] = external_settlement_artifact_evidence(root)
    claim_results = [evaluate_claim(claim, context, flag_index, artifact_evidence) for claim in claims]
    if load_errors:
        for result in claim_results:
            result["allowed"] = False
            result["blockers"] = sorted(set([*result.get("blockers", []), *load_errors]))
    allowed = all(item.get("allowed") is True for item in claim_results)
    allowed_claim_ids: list[str] = []
    blocked_claim_ids: list[str] = []
    blockers: list[str] = []
    claim_blockers: dict[str, list[str]] = {}
    plane_claims: dict[str, list[str]] = {}
    for result in claim_results:
        claim_id = str(result.get("claim_id") or "")
        if not claim_id:
            continue
        for plane in result.get("claim_planes", []):
            plane_claims.setdefault(str(plane), []).append(claim_id)
        if result.get("allowed") is True:
            allowed_claim_ids.append(claim_id)
            continue
        blocked_claim_ids.append(claim_id)
        result_blockers = [
            str(blocker)
            for blocker in result.get("blockers", [])
            if str(blocker)
        ]
        if result_blockers:
            claim_blockers[claim_id] = sorted(set(result_blockers))
            blockers.extend(result_blockers)
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "decision": "CROSS_PLANE_CLAIMS_ALLOWED" if allowed else "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": allowed,
        "context": context,
        "claim_results": claim_results,
        "allowed_claim_ids": allowed_claim_ids,
        "blocked_claim_ids": blocked_claim_ids,
        "blockers": sorted(set(blockers)),
        "claim_blockers": claim_blockers,
        "plane_claims": plane_claims,
        "summary": {
            "claims_total": len(claim_results),
            "claims_allowed": sum(1 for item in claim_results if item.get("allowed") is True),
            "claims_blocked": sum(1 for item in claim_results if item.get("allowed") is not True),
            "known_flags_total": len(flag_index),
            "high_risk_claims_requested": sum(1 for item in claim_results if item.get("high_risk") is True),
            "external_artifacts_checked": len(artifact_evidence),
        },
        "claim_boundary": (
            "This proof gate is a reusable local enforcement layer for strong claims. "
            "It does not collect live evidence and cannot make an absent external proof true."
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--map", dest="map_path", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--audit", dest="audit_path", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--claim", action="append", choices=sorted(CLAIM_REQUIREMENTS))
    parser.add_argument("--require-allowed", action="store_true")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help=f"Write the full local proof-gate report to a JSON file, for example {DEFAULT_OUTPUT_JSON}",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        map_path=args.map_path,
        audit_path=args.audit_path,
        claims=tuple(args.claim or DEFAULT_CLAIMS),
    )
    if args.output_json is not None:
        atomic_write_json(resolve_path(args.root, args.output_json), report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report["decision"])
        for result in report["claim_results"]:
            status = "ALLOWED" if result.get("allowed") else "BLOCKED"
            blockers = ", ".join(result.get("blockers") or [])
            print(f"- {result.get('claim_id')}: {status}" + (f" ({blockers})" if blockers else ""))
    return 0 if (report["allowed"] is True or not args.require_allowed) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
