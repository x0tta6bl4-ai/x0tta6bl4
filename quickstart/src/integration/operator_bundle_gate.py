"""Read-only gate for integration-spine operator evidence bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.evidence_source_candidates import (
    COLLECTOR_BY_KEY,
    DEFAULT_EXTERNAL_SETTLEMENT_EVIDENCE,
    DEFAULT_EXTERNAL_SETTLEMENT_GATE,
    DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC,
    DEFAULT_INTAKE_MANIFEST,
    DEFAULT_OPERATOR_BUNDLE_ROOT,
    DEFAULT_SEMANTIC_QUEUE,
    BuildInputs,
    build_audit,
    utc_now,
)


PREFIX_BY_KEY = {
    "billing-provisioning": "billing_provisioning",
    "ebpf-observability": "ebpf_observability",
    "live_spire_mtls": "zero_trust_pqc",
    "multi_host_mesh": "self_healing_pqc_mesh",
    "paid_client_path": "paid_client_serviceability",
    "safe_rollout_rollback": "live_rollout",
    "signed-release-provenance": "signed_release_provenance",
    "sla-telemetry": "sla_telemetry",
    "stable-deploy": "stable_deploy",
}

DEFAULT_OUTPUT_BY_KEY = {
    "billing-provisioning": ".tmp/validation-shards/billing-provisioning-evidence-gate-current.json",
    "ebpf-observability": ".tmp/validation-shards/ebpf-observability-evidence-gate-current.json",
    "live_spire_mtls": ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
    "multi_host_mesh": ".tmp/validation-shards/self-healing-pqc-mesh-evidence-gate-current.json",
    "paid_client_path": ".tmp/validation-shards/paid-client-serviceability-evidence-gate-current.json",
    "safe_rollout_rollback": ".tmp/validation-shards/live-rollout-evidence-gate-current.json",
    "signed-release-provenance": ".tmp/validation-shards/signed-release-provenance-evidence-gate-current.json",
    "sla-telemetry": ".tmp/validation-shards/sla-telemetry-evidence-gate-current.json",
    "stable-deploy": ".tmp/validation-shards/stable-deploy-evidence-gate-current.json",
}


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _route_by_key(audit: Dict[str, Any], evidence_key: str) -> Dict[str, Any]:
    for route in audit.get("evidence_source_routes", []):
        if isinstance(route, dict) and route.get("evidence_key") == evidence_key:
            return route
    return {}


def _candidate_errors(route: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for candidate in route.get("source_candidates", []):
        if not isinstance(candidate, dict):
            continue
        for reason in candidate.get("not_ready_reasons", []):
            if isinstance(reason, str):
                errors.append(reason)
    return errors


def _operator_bundle_candidate(route: Dict[str, Any]) -> Dict[str, Any]:
    for candidate in route.get("source_candidates", []):
        if isinstance(candidate, dict) and str(candidate.get("source_id", "")).startswith("operator_bundle:"):
            return candidate
    return {}


def _identity_update_plan(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for report in candidate.get("file_reports", []):
        if not isinstance(report, dict):
            continue
        mismatch_fields = [
            field
            for field, key in (
                ("collector_id", "collector_id_matches_manifest"),
                ("raw_id", "raw_id_matches_manifest"),
                ("file_name", "file_name_matches_manifest"),
            )
            if report.get("available") and report.get(key) is not True
        ]
        clean = (
            report.get("available") is True
            and report.get("collector_id_matches_manifest") is True
            and report.get("raw_id_matches_manifest") is True
            and report.get("file_name_matches_manifest") is True
        )
        if clean:
            continue
        plan.append(
            {
                "path": report.get("artifact_path", ""),
                "available": report.get("available"),
                "suggested_fields": {
                    "collector_id": report.get("manifest_collector_id"),
                    "raw_id": report.get("manifest_raw_id"),
                    "file_name": report.get("manifest_file_name"),
                },
                "current_fields": {
                    "collector_id": report.get("evidence_collector_id"),
                    "raw_id": report.get("evidence_raw_id"),
                    "file_name": report.get("evidence_file_name"),
                },
                "identity_mismatch_fields": mismatch_fields,
                "json_merge_patch": {
                    "collector_id": report.get("manifest_collector_id"),
                    "raw_id": report.get("manifest_raw_id"),
                    "file_name": report.get("manifest_file_name"),
                } if mismatch_fields else {},
                "json_patch_operations": [
                    {
                        "op": "add" if report.get(f"evidence_{field}") is None else "replace",
                        "path": f"/{field}",
                        "value": report.get(f"manifest_{field}"),
                    }
                    for field in mismatch_fields
                ],
                "read_error": report.get("read_error", ""),
            }
        )
    return plan


def build_report(
    *,
    root: Path,
    evidence_key: str,
    intake_manifest: str = DEFAULT_INTAKE_MANIFEST,
    semantic_queue: str = DEFAULT_SEMANTIC_QUEUE,
    operator_bundle_root: str = DEFAULT_OPERATOR_BUNDLE_ROOT,
    external_settlement_evidence: str = DEFAULT_EXTERNAL_SETTLEMENT_EVIDENCE,
    external_settlement_gate: str = DEFAULT_EXTERNAL_SETTLEMENT_GATE,
    external_settlement_live_rpc: str = DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC,
) -> Dict[str, Any]:
    if evidence_key not in COLLECTOR_BY_KEY:
        raise ValueError(f"unsupported evidence_key: {evidence_key}")

    inputs = BuildInputs(
        root=root,
        intake_manifest=_resolve(root, intake_manifest),
        semantic_queue=_resolve(root, semantic_queue),
        operator_bundle_root=_resolve(root, operator_bundle_root),
        external_settlement_evidence=_resolve(root, external_settlement_evidence),
        external_settlement_gate=_resolve(root, external_settlement_gate),
        external_settlement_live_rpc=_resolve(root, external_settlement_live_rpc),
        intake_manifest_display=str(Path(intake_manifest)),
        semantic_queue_display=str(Path(semantic_queue)),
        operator_bundle_root_display=str(Path(operator_bundle_root)),
        external_settlement_evidence_display=str(Path(external_settlement_evidence)),
        external_settlement_gate_display=str(Path(external_settlement_gate)),
        external_settlement_live_rpc_display=str(Path(external_settlement_live_rpc)),
    )
    audit = build_audit(inputs)
    route = _route_by_key(audit, evidence_key)
    collector_id = COLLECTOR_BY_KEY[evidence_key]
    prefix = PREFIX_BY_KEY[evidence_key]
    ready = route.get("route_classification") == "READY_TO_INSTALL"
    errors = _candidate_errors(route)
    semantic_blockers = int(route.get("semantic_blockers_total") or 0)
    bundle_candidate = _operator_bundle_candidate(route)
    file_report_summary = bundle_candidate.get("file_report_summary", {})
    identity_plan = _identity_update_plan(bundle_candidate)
    identity_plan_command = (
        f"python3 -m src.integration.operator_bundle_identity "
        f"--root . --evidence-key {evidence_key} --require-clean"
    )

    report: Dict[str, Any] = {
        "schema_version": "x0tta6bl4-integration-spine-operator-bundle-gate-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only gate for already supplied operator production evidence bundle files. "
            "It does not collect live evidence, mutate runtime state, install bundles, "
            "contact external systems, or mark the objective complete."
        ),
        "evidence_key": evidence_key,
        "collector_id": collector_id,
        "decision": "READY_TO_INSTALL" if ready else "BLOCKED",
        f"{prefix}_decision": "READY" if ready else "BLOCKED",
        "goal_can_be_marked_complete": False,
        "route": route,
        "summary": {
            f"{prefix}_ready": ready,
            "production_ready": ready,
            "route_classification": route.get("route_classification", ""),
            "semantic_blockers_total": semantic_blockers,
            "required_artifact_exists": route.get("required_artifact_exists"),
            "source_candidates_total": len(route.get("source_candidates", [])),
            "not_ready_reasons_total": len(errors),
            "bundle_files_total": file_report_summary.get("files_total", 0),
            "bundle_files_available": file_report_summary.get("files_available", 0),
            "bundle_manifest_identity_mismatches_total": file_report_summary.get("manifest_identity_mismatches_total", 0),
            "bundle_raw_id_mismatches": file_report_summary.get("raw_id_mismatches", 0),
            "bundle_collector_id_mismatches": file_report_summary.get("collector_id_mismatches", 0),
            "bundle_file_name_mismatches": file_report_summary.get("file_name_mismatches", 0),
            "bundle_files_needing_identity_update": len(identity_plan),
        },
        "identity_plan_command": identity_plan_command,
        "identity_update_plan": identity_plan,
        "blocking_reasons": errors + (
            [f"semantic blockers still open for {collector_id}: {semantic_blockers}"]
            if semantic_blockers
            else []
        ),
        "not_verified_yet": [] if ready else [
            f"{evidence_key} operator bundle is not production ready",
            "all required bundle files must be real production evidence with production_ready=true",
        ],
    }
    return report


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None, *, default_evidence_key: str = "", default_output: str = "") -> int:
    parser = argparse.ArgumentParser(description="Validate an integration-spine operator evidence bundle")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence-key", default=default_evidence_key)
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--raw-root", default="", help=argparse.SUPPRESS)
    parser.add_argument("--output-json", default=default_output)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = args.output_json or DEFAULT_OUTPUT_BY_KEY.get(args.evidence_key, "")
    if not output:
        raise SystemExit("--output-json is required for unsupported evidence keys")

    report = build_report(
        root=root,
        evidence_key=args.evidence_key,
        intake_manifest=args.intake_manifest,
        semantic_queue=args.semantic_queue,
        operator_bundle_root=args.operator_bundle_root,
    )
    write_json(_resolve(root, output), report)
    print(json.dumps({
        "decision": report["decision"],
        "evidence_key": report["evidence_key"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["decision"] != "READY_TO_INSTALL":
        return 2
    return 0


def main_for_profile(evidence_key: str, default_output: str, argv: Optional[List[str]] = None) -> int:
    return main(argv, default_evidence_key=evidence_key, default_output=default_output)


if __name__ == "__main__":
    raise SystemExit(main())
