"""Build production evidence source-candidate audit for the integration spine.

The audit is deliberately strict. It can point at retained operator evidence
that might replace local/component evidence, but it does not install files,
collect live evidence, contact chains or clusters, or mark the goal complete.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.integration.external_settlement import validate_evidence_file


DEFAULT_INTAKE_MANIFEST = ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_OPERATOR_BUNDLE_ROOT = ".tmp/production-raw-evidence-operator-bundle"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_EVIDENCE = ".tmp/external-settlement-evidence/settlement-submit.json"
DEFAULT_EXTERNAL_SETTLEMENT_GATE = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"

REQUIRED_EVIDENCE_KEYS = {
    "billing-provisioning",
    "ebpf-observability",
    "external_settlement",
    "live_spire_mtls",
    "multi_host_mesh",
    "paid_client_path",
    "safe_rollout_rollback",
    "signed-release-provenance",
    "sla-telemetry",
    "stable-deploy",
}

COLLECTOR_BY_KEY = {
    "billing-provisioning": "billing-provisioning",
    "ebpf-observability": "ebpf-observability",
    "live_spire_mtls": "zero-trust-pqc",
    "multi_host_mesh": "self-healing-pqc-mesh",
    "paid_client_path": "paid-client-serviceability",
    "safe_rollout_rollback": "live-rollout",
    "signed-release-provenance": "signed-release-provenance",
    "sla-telemetry": "sla-telemetry",
    "stable-deploy": "stable-deploy",
}

PLACEHOLDER_RE = re.compile(
    r"(placeholder|template|todo|tbd|replace me|\bexample\b|\bsample\b|your name|changeme|<|>)",
    re.IGNORECASE,
)
LOCAL_CONTEXT_RE = re.compile(
    r"(local|production-like|contract-validation|component-verification|test|staging|dry-run|simulation|simulated)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, "artifact missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"artifact unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "artifact root must be a JSON object"
    return data, ""


def _json_pointer(data: Dict[str, Any], pointer: str) -> Any:
    current: Any = data
    for part in pointer.strip("/").split("/"):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _ready_pointer_values(data: Optional[Dict[str, Any]], pointers: Sequence[str]) -> Dict[str, Any]:
    if data is None:
        return {pointer: None for pointer in pointers}
    return {pointer: _json_pointer(data, pointer) for pointer in pointers}


def _ready_from_pointers(data: Optional[Dict[str, Any]], pointers: Sequence[str]) -> bool:
    return any(value is True or value == "READY" or value == "READY_TO_INSTALL" for value in _ready_pointer_values(data, pointers).values())


def _status(data: Dict[str, Any]) -> Any:
    return data.get("evidence_status", data.get("status"))


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER_RE.search(value))
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def _has_forbidden_marker(data: Dict[str, Any]) -> bool:
    if data.get("_template_only") is True or data.get("_not_evidence") is True:
        return True
    if data.get("template_only") is True or data.get("fake_or_simulated") is True:
        return True
    return _contains_placeholder(data.get("collected_by")) or _contains_placeholder(data.get("source_commands"))


def _context_text(data: Dict[str, Any]) -> str:
    fields = [
        data.get("claim_boundary", ""),
        data.get("environment", ""),
        data.get("cluster_context", ""),
        data.get("service_tier", ""),
        data.get("environment_id", ""),
    ]
    return " ".join(str(field) for field in fields if field is not None)


def _collector_entries(manifest: Optional[Dict[str, Any]], collector_id: str) -> List[Dict[str, Any]]:
    if not manifest:
        return []
    collectors = manifest.get("collectors", [])
    if not isinstance(collectors, list):
        return []
    for collector in collectors:
        if isinstance(collector, dict) and collector.get("collector_id") == collector_id:
            raw_files = collector.get("raw_files", [])
            return [item for item in raw_files if isinstance(item, dict)]
    return []


def _collector_script_name(collector_id: str) -> str:
    return collector_id.replace("-", "_")


def _collector_command(collector_id: str) -> str:
    return f"python3 scripts/ops/collect_{_collector_script_name(collector_id)}_evidence_bundle.py --require-ready"


def _verification_command(collector_id: str) -> str:
    return f"python3 scripts/ops/verify_{_collector_script_name(collector_id)}_evidence_gate.py --require-ready"


def _semantic_blockers_by_collector(semantic_queue: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not semantic_queue:
        return {}
    by_collector = semantic_queue.get("summary", {}).get("by_collector", {})
    if not isinstance(by_collector, dict):
        return {}
    result: Dict[str, int] = {}
    for key, value in by_collector.items():
        try:
            result[str(key)] = int(value)
        except (TypeError, ValueError):
            result[str(key)] = 0
    return result


@dataclass(frozen=True)
class BuildInputs:
    root: Path
    intake_manifest: Path
    semantic_queue: Path
    operator_bundle_root: Path
    external_settlement_evidence: Path
    external_settlement_gate: Path
    external_settlement_live_rpc: Path
    intake_manifest_display: str = DEFAULT_INTAKE_MANIFEST
    semantic_queue_display: str = DEFAULT_SEMANTIC_QUEUE
    operator_bundle_root_display: str = DEFAULT_OPERATOR_BUNDLE_ROOT
    external_settlement_evidence_display: str = DEFAULT_EXTERNAL_SETTLEMENT_EVIDENCE
    external_settlement_gate_display: str = DEFAULT_EXTERNAL_SETTLEMENT_GATE
    external_settlement_live_rpc_display: str = DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC


def _operator_bundle_candidate(
    root: Path,
    collector_id: str,
    entries: Sequence[Dict[str, Any]],
    bundle_root: Path,
    bundle_root_display: str,
) -> Dict[str, Any]:
    required_files: List[str] = []
    file_reports: List[Dict[str, Any]] = []
    errors: List[str] = []

    for entry in entries:
        raw_id = str(entry.get("raw_id", ""))
        file_name = str(entry.get("file_name", raw_id.split("/")[-1]))
        bundle_path = bundle_root / collector_id / file_name
        display_path = f"{bundle_root_display}/{collector_id}/{file_name}"
        required_files.append(display_path)
        data, read_error = _read_json(bundle_path if bundle_path.is_absolute() else root / bundle_path)
        file_errors: List[str] = []
        evidence_collector_id = data.get("collector_id") if data else None
        evidence_raw_id = data.get("raw_id") if data else None
        evidence_file_name = data.get("file_name") if data else None
        collector_id_matches = data is not None and evidence_collector_id == collector_id
        raw_id_matches = data is not None and evidence_raw_id == raw_id
        file_name_matches = data is not None and evidence_file_name == file_name
        if read_error:
            file_errors.append(read_error)
        if data is not None:
            if _status(data) != "VERIFIED HERE":
                file_errors.append("status/evidence_status must be VERIFIED HERE")
            if not collector_id_matches:
                file_errors.append("collector_id must match the intake manifest collector_id")
            if not raw_id_matches:
                file_errors.append("raw_id must match the intake manifest raw_id")
            if not file_name_matches:
                file_errors.append("file_name must match the intake manifest file_name")
            if not data.get("collected_at"):
                file_errors.append("collected_at is required")
            if _contains_placeholder(data.get("collected_by")) or not data.get("collected_by"):
                file_errors.append("collected_by must be specific and non-placeholder")
            source_commands = data.get("source_commands")
            if not isinstance(source_commands, list) or not source_commands:
                file_errors.append("source_commands must be a non-empty list")
            elif _contains_placeholder(source_commands):
                file_errors.append("source_commands must not contain placeholders")
            if _has_forbidden_marker(data):
                file_errors.append("template/mock/placeholder markers must be absent")
            if data.get("production_ready") is not True:
                file_errors.append("production_ready must be true for source-candidate promotion")
            blockers = data.get("production_promotion_blockers", [])
            if blockers:
                file_errors.append("production_promotion_blockers must be empty")
            context_text = _context_text(data)
            if LOCAL_CONTEXT_RE.search(context_text):
                file_errors.append("claim_boundary/environment still describes local, staging, test, or simulation context")
        file_reports.append(
            {
                "artifact_path": display_path,
                "available": data is not None,
                "errors": file_errors,
                "manifest_collector_id": collector_id,
                "manifest_raw_id": raw_id,
                "manifest_file_name": file_name,
                "manifest_raw_path": str(entry.get("path", "")),
                "evidence_collector_id": evidence_collector_id,
                "evidence_raw_id": evidence_raw_id,
                "evidence_file_name": evidence_file_name,
                "collector_id_matches_manifest": collector_id_matches,
                "raw_id_matches_manifest": raw_id_matches,
                "file_name_matches_manifest": file_name_matches,
                "raw_id": raw_id,
                "status": _status(data or {}) or ("NOT_FOUND" if data is None else ""),
            }
        )
        errors.extend(f"{display_path}: {error}" for error in file_errors)

    ready = bool(entries) and not errors
    identity_mismatches = [
        report
        for report in file_reports
        if report["available"]
        and (
            report["collector_id_matches_manifest"] is not True
            or report["raw_id_matches_manifest"] is not True
            or report["file_name_matches_manifest"] is not True
        )
    ]
    return {
        "source_id": f"operator_bundle:{collector_id}",
        "classification": "READY_SOURCE_CANDIDATE" if ready else "OPERATOR_REQUIRED",
        "available": bool(entries) and all(report["available"] for report in file_reports),
        "production_artifact": ready,
        "matches_raw_contract": ready,
        "status": "VERIFIED HERE" if ready else "NOT VERIFIED YET",
        "decision": "READY_TO_INSTALL" if ready else "BLOCKED",
        "artifact_paths": required_files,
        "file_reports": file_reports,
        "file_report_summary": {
            "files_total": len(file_reports),
            "files_available": sum(1 for report in file_reports if report["available"]),
            "collector_id_mismatches": sum(1 for report in file_reports if report["available"] and report["collector_id_matches_manifest"] is not True),
            "raw_id_mismatches": sum(1 for report in file_reports if report["available"] and report["raw_id_matches_manifest"] is not True),
            "file_name_mismatches": sum(1 for report in file_reports if report["available"] and report["file_name_matches_manifest"] is not True),
            "manifest_identity_mismatches_total": len(identity_mismatches),
        },
        "not_ready_reasons": errors,
        "reason": (
            "operator bundle satisfies strict production source-candidate contract"
            if ready
            else "operator bundle is missing real production-ready files or still contains local/template context"
        ),
    }


def _raw_route(inputs: BuildInputs, evidence_key: str, manifest: Optional[Dict[str, Any]], semantic_queue: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    collector_id = COLLECTOR_BY_KEY[evidence_key]
    entries = _collector_entries(manifest, collector_id)
    blockers = _semantic_blockers_by_collector(semantic_queue).get(collector_id, 0)
    raw_paths = [str(entry.get("path")) for entry in entries if entry.get("path")]
    operator_paths = [
        f"{inputs.operator_bundle_root_display}/{collector_id}/{entry.get('file_name', str(entry.get('raw_id', '')).split('/')[-1])}"
        for entry in entries
    ]
    candidate = _operator_bundle_candidate(
        inputs.root,
        collector_id,
        entries,
        inputs.operator_bundle_root,
        inputs.operator_bundle_root_display,
    )
    ready = candidate["production_artifact"] is True and blockers == 0
    if blockers:
        candidate["not_ready_reasons"] = list(candidate.get("not_ready_reasons", [])) + [
            f"semantic blockers still open for {collector_id}: {blockers}"
        ]
        candidate["matches_raw_contract"] = False
        candidate["production_artifact"] = False
        candidate["classification"] = "OPERATOR_REQUIRED"
        candidate["decision"] = "BLOCKED"

    return {
        "evidence_key": evidence_key,
        "kind": "raw_evidence",
        "collector_id": collector_id,
        "collector_command": _collector_command(collector_id),
        "verification_command": _verification_command(collector_id),
        "route_classification": "READY_TO_INSTALL" if ready else "PARTIAL_CONTEXT_ONLY",
        "semantic_blockers_total": blockers,
        "raw_paths": raw_paths,
        "raw_paths_total": len(raw_paths),
        "operator_bundle_paths": operator_paths,
        "field_replacements_total": len(operator_paths),
        "required_operator_action": (
            "Replace every listed retained/local raw file with operator-captured production JSON, "
            "including production_ready=true and no production_promotion_blockers, then rerun collectors and gates."
        ),
        "source_candidates": [
            candidate,
            {
                "source_id": f"current_retained_raw_files:{evidence_key}",
                "classification": "REJECTED_LOCAL_OBSERVATION",
                "available": bool(raw_paths),
                "production_artifact": False,
                "matches_raw_contract": False,
                "raw_paths": raw_paths,
                "reason": "Current retained raw files may satisfy syntax, but are not accepted as production source candidates.",
            },
        ],
    }


def _external_settlement_route(inputs: BuildInputs, semantic_queue: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    blockers = _semantic_blockers_by_collector(semantic_queue).get("external-settlement", 0)
    evidence_result = validate_evidence_file(inputs.external_settlement_evidence, inputs.external_settlement_evidence_display)
    live_rpc, rpc_error = _read_json(inputs.external_settlement_live_rpc)
    live_rpc_ready = (
        rpc_error == ""
        and live_rpc is not None
        and live_rpc.get("status") == "VERIFIED HERE"
        and live_rpc.get("summary", {}).get("x0t_external_settlement_live_rpc_ready") is True
    )
    retained_ready = evidence_result.valid
    ready = retained_ready and live_rpc_ready and blockers == 0

    reasons: List[str] = []
    if not evidence_result.valid:
        reasons.extend(evidence_result.errors or ["retained submitted settlement receipt is missing"])
    if not live_rpc_ready:
        reasons.append("live Base RPC settlement verification is not ready")
    if blockers:
        reasons.append(f"semantic blockers still open for external-settlement: {blockers}")

    gate, gate_error = _read_json(inputs.external_settlement_gate)
    ready_pointers = [
        "/ready",
        "/production_ready",
        "/summary/x0t_external_settlement_ready",
    ]

    return {
        "evidence_key": "external_settlement",
        "kind": "external_settlement",
        "collector_id": "external-settlement",
        "route_classification": "READY_TO_INSTALL" if ready else "PARTIAL_CONTEXT_ONLY",
        "semantic_blockers_total": blockers,
        "required_artifact_exists": inputs.external_settlement_evidence.exists(),
        "required_artifact_path": inputs.external_settlement_evidence_display,
        "required_operator_action": (
            "Submit or locate a real external X0T settlement transaction, retain settlement-submit.json, "
            "verify it against live Base RPC, and rerun the retained evidence gates."
        ),
        "verification_command": "python3 -m src.integration.external_settlement --require-ready --rpc-url <read-only Base RPC URL>",
        "source_candidates": [
            {
                "source_id": "required_artifact:external_settlement",
                "classification": "READY_SOURCE_CANDIDATE" if ready else "OPERATOR_REQUIRED",
                "available": evidence_result.found,
                "production_artifact": ready,
                "matches_raw_contract": ready,
                "status": "VERIFIED HERE" if ready else "NOT VERIFIED YET",
                "decision": "READY_TO_INSTALL" if ready else "BLOCKED",
                "artifact_path": inputs.external_settlement_evidence_display,
                "not_ready_reasons": reasons,
            },
            {
                "source_id": "gate:external-settlement",
                "classification": "READY_SOURCE_CANDIDATE" if _ready_from_pointers(gate, ready_pointers) and live_rpc_ready else "OPERATOR_REQUIRED",
                "available": gate is not None,
                "production_artifact": ready,
                "matches_raw_contract": ready,
                "status": (gate or {}).get("status", "NOT VERIFIED YET") if not gate_error else "NOT VERIFIED YET",
                "decision": (gate or {}).get("x0t_external_settlement_decision", (gate or {}).get("decision", "")),
                "artifact_path": inputs.external_settlement_gate_display,
                "ready_pointer_values": _ready_pointer_values(gate, ready_pointers),
                "not_ready_reasons": [] if ready else reasons,
                "required_artifacts": [
                    {
                        "artifact_path": inputs.external_settlement_live_rpc_display,
                        "available": live_rpc is not None,
                        "ready": live_rpc_ready,
                        "status": (live_rpc or {}).get("status", "NOT VERIFIED YET"),
                        "error": rpc_error,
                    }
                ],
            },
        ],
    }


def build_audit(inputs: BuildInputs) -> Dict[str, Any]:
    manifest, manifest_error = _read_json(inputs.intake_manifest)
    semantic_queue, semantic_error = _read_json(inputs.semantic_queue)
    routes = [_external_settlement_route(inputs, semantic_queue)]
    routes.extend(
        _raw_route(inputs, key, manifest, semantic_queue)
        for key in sorted(COLLECTOR_BY_KEY)
    )

    ready_routes = [route for route in routes if route.get("route_classification") == "READY_TO_INSTALL"]
    ready_candidates_total = sum(
        1
        for route in routes
        if any(
            isinstance(candidate, dict)
            and candidate.get("classification") == "READY_SOURCE_CANDIDATE"
            and candidate.get("production_artifact") is True
            and candidate.get("matches_raw_contract") is True
            for candidate in route.get("source_candidates", [])
        )
    )
    required_ready = len(ready_routes)
    missing_inputs = []
    if manifest_error:
        missing_inputs.append(f"{inputs.intake_manifest_display}: {manifest_error}")
    if semantic_error:
        missing_inputs.append(f"{inputs.semantic_queue_display}: {semantic_error}")
    all_ready = required_ready == len(REQUIRED_EVIDENCE_KEYS) and ready_candidates_total >= len(REQUIRED_EVIDENCE_KEYS)

    return {
        "schema_version": "x0tta6bl4-integration-spine-evidence-source-candidate-audit-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only audit of candidate sources for replacing integration-spine templates, mocks, "
            "external placeholders, and local/component raw files. It identifies candidates for operator "
            "review only; it does not create, install, or promote production evidence."
        ),
        "decision": "READY_SOURCE_CANDIDATES_AVAILABLE" if all_ready else "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED",
        "goal_can_be_marked_complete": False,
        "source_artifacts": {
            "intake_manifest": inputs.intake_manifest_display,
            "semantic_queue": inputs.semantic_queue_display,
            "operator_bundle_root": inputs.operator_bundle_root_display,
            "external_settlement_evidence": inputs.external_settlement_evidence_display,
            "external_settlement_live_rpc": inputs.external_settlement_live_rpc_display,
        },
        "required_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
        "evidence_source_routes": routes,
        "summary": {
            "required_inputs_ready": required_ready,
            "required_inputs_total": len(REQUIRED_EVIDENCE_KEYS),
            "ready_source_candidates_total": ready_candidates_total,
            "routes_total": len(routes),
            "routes_ready_to_install": required_ready,
            "routes_partial_or_blocked": len(routes) - required_ready,
            "operator_evidence_bundle_candidates_total": len(COLLECTOR_BY_KEY),
            "missing_or_unreadable_source_artifacts": missing_inputs,
        },
        "not_verified_yet": [] if all_ready else [
            "complete production source candidates for all integration-spine evidence keys",
            "operator bundle files with production_ready=true and no production_promotion_blockers",
            "external X0T settlement receipt verified against live Base RPC",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production evidence source-candidate audit")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--external-settlement-evidence", default=DEFAULT_EXTERNAL_SETTLEMENT_EVIDENCE)
    parser.add_argument("--external-settlement-gate", default=DEFAULT_EXTERNAL_SETTLEMENT_GATE)
    parser.add_argument("--external-settlement-live-rpc", default=DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless all source candidates are ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    inputs = BuildInputs(
        root=root,
        intake_manifest=_resolve(root, args.intake_manifest),
        semantic_queue=_resolve(root, args.semantic_queue),
        operator_bundle_root=_resolve(root, args.operator_bundle_root),
        external_settlement_evidence=_resolve(root, args.external_settlement_evidence),
        external_settlement_gate=_resolve(root, args.external_settlement_gate),
        external_settlement_live_rpc=_resolve(root, args.external_settlement_live_rpc),
        intake_manifest_display=str(Path(args.intake_manifest)),
        semantic_queue_display=str(Path(args.semantic_queue)),
        operator_bundle_root_display=str(Path(args.operator_bundle_root)),
        external_settlement_evidence_display=str(Path(args.external_settlement_evidence)),
        external_settlement_gate_display=str(Path(args.external_settlement_gate)),
        external_settlement_live_rpc_display=str(Path(args.external_settlement_live_rpc)),
    )
    report = build_audit(inputs)
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["decision"] != "READY_SOURCE_CANDIDATES_AVAILABLE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
