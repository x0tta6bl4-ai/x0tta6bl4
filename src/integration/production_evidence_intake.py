"""Production evidence intake gate for the integration spine.

The gate decides whether operator-supplied production evidence is ready to be
installed over retained component/local-observation raw evidence. It is
read-only and fail-closed: it never copies files, contacts live systems, or
marks the objective complete.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SOURCE_CANDIDATE_AUDIT = ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
DEFAULT_PRODUCTION_IMPORT = ".tmp/validation-shards/integration-spine-production-evidence-import-current.json"
DEFAULT_RAW_READINESS = ".tmp/validation-shards/production-raw-evidence-readiness-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json"

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

READY_CLASSIFICATIONS = {
    "READY_SOURCE_CANDIDATE",
    "READY_TO_INSTALL",
    "PRODUCTION_ARTIFACT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _ready_bool(value: Any) -> bool:
    return value is True or value == "READY" or value == "READY_TO_INSTALL" or value == "READY_TO_PROMOTE"


def _int_value(mapping: Dict[str, Any], key: str) -> int:
    try:
        return int(mapping.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


@dataclass
class EvidenceKeyIntake:
    evidence_key: str
    kind: str
    required_operator_action: str
    raw_paths: List[str] = field(default_factory=list)
    operator_bundle_paths: List[str] = field(default_factory=list)
    operator_bundle_file_report_summary: Dict[str, Any] = field(default_factory=dict)
    semantic_blockers_total: int = 0
    source_candidates_total: int = 0
    ready_source_candidates: List[Dict[str, Any]] = field(default_factory=list)
    rejected_or_context_sources: List[Dict[str, Any]] = field(default_factory=list)
    missing_or_blocking_reasons: List[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.ready_source_candidates) and not self.missing_or_blocking_reasons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_key": self.evidence_key,
            "kind": self.kind,
            "ready": self.ready,
            "required_operator_action": self.required_operator_action,
            "raw_paths": self.raw_paths,
            "operator_bundle_paths": self.operator_bundle_paths,
            "operator_bundle_file_report_summary": self.operator_bundle_file_report_summary,
            "semantic_blockers_total": self.semantic_blockers_total,
            "source_candidates_total": self.source_candidates_total,
            "ready_source_candidates": self.ready_source_candidates,
            "rejected_or_context_sources": self.rejected_or_context_sources,
            "missing_or_blocking_reasons": self.missing_or_blocking_reasons,
        }


@dataclass
class ProductionEvidenceIntakeGate:
    source_candidate_path: Path
    production_import_path: Path
    raw_readiness_path: Path
    source_candidate_display: str = DEFAULT_SOURCE_CANDIDATE_AUDIT
    production_import_display: str = DEFAULT_PRODUCTION_IMPORT
    raw_readiness_display: str = DEFAULT_RAW_READINESS
    source_candidate: Optional[Dict[str, Any]] = None
    production_import: Optional[Dict[str, Any]] = None
    raw_readiness: Optional[Dict[str, Any]] = None

    @classmethod
    def load(
        cls,
        source_candidate_path: Path,
        production_import_path: Path,
        raw_readiness_path: Path,
        source_candidate_display: str = DEFAULT_SOURCE_CANDIDATE_AUDIT,
        production_import_display: str = DEFAULT_PRODUCTION_IMPORT,
        raw_readiness_display: str = DEFAULT_RAW_READINESS,
    ) -> "ProductionEvidenceIntakeGate":
        return cls(
            source_candidate_path,
            production_import_path,
            raw_readiness_path,
            source_candidate_display,
            production_import_display,
            raw_readiness_display,
            _read_json(source_candidate_path),
            _read_json(production_import_path),
            _read_json(raw_readiness_path),
        )

    def _route_to_status(self, route: Dict[str, Any]) -> EvidenceKeyIntake:
        key = str(route.get("evidence_key", ""))
        candidates = route.get("source_candidates", [])
        ready_candidates: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        reasons: List[str] = []
        operator_bundle_file_report_summary: Dict[str, Any] = {}

        if not isinstance(candidates, list):
            candidates = []
            reasons.append("source_candidates must be a list")

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            classification = str(candidate.get("classification", ""))
            is_ready = (
                classification in READY_CLASSIFICATIONS
                and candidate.get("available") is True
                and candidate.get("matches_raw_contract") is True
                and candidate.get("production_artifact") is True
            )
            summary = {
                "source_id": candidate.get("source_id"),
                "classification": classification,
                "available": candidate.get("available"),
                "production_artifact": candidate.get("production_artifact"),
                "matches_raw_contract": candidate.get("matches_raw_contract"),
                "status": candidate.get("status"),
                "decision": candidate.get("decision"),
                "artifact_path": candidate.get("artifact_path"),
                "not_ready_reasons": candidate.get("not_ready_reasons", []),
                "reason": candidate.get("reason", ""),
            }
            file_report_summary = candidate.get("file_report_summary")
            if isinstance(file_report_summary, dict):
                summary["file_report_summary"] = file_report_summary
                if str(candidate.get("source_id", "")).startswith("operator_bundle:"):
                    operator_bundle_file_report_summary = file_report_summary
            if is_ready:
                ready_candidates.append(summary)
            else:
                rejected.append(summary)

        if not ready_candidates:
            reasons.append("no source candidate is a production artifact that matches the raw evidence contract")
        if route.get("kind") == "external_settlement" and route.get("required_artifact_exists") is not True:
            reasons.append(f"required artifact missing: {route.get('required_artifact_path')}")
        if route.get("route_classification") != "READY_TO_INSTALL":
            reasons.append(f"route classification is {route.get('route_classification')}")
        if int(route.get("semantic_blockers_total", 0) or 0) > 0:
            reasons.append(f"semantic blockers still open for evidence key: {route.get('semantic_blockers_total')}")

        return EvidenceKeyIntake(
            evidence_key=key,
            kind=str(route.get("kind", "")),
            required_operator_action=str(route.get("required_operator_action", "")),
            raw_paths=[path for path in route.get("raw_paths", []) if isinstance(path, str)],
            operator_bundle_paths=[path for path in route.get("operator_bundle_paths", []) if isinstance(path, str)],
            operator_bundle_file_report_summary=operator_bundle_file_report_summary,
            semantic_blockers_total=int(route.get("semantic_blockers_total", 0) or 0),
            source_candidates_total=len(candidates),
            ready_source_candidates=ready_candidates,
            rejected_or_context_sources=rejected,
            missing_or_blocking_reasons=reasons,
        )

    def evidence_key_statuses(self) -> List[EvidenceKeyIntake]:
        if not self.source_candidate:
            return []
        routes = self.source_candidate.get("evidence_source_routes", [])
        if not isinstance(routes, list):
            return []
        statuses = [self._route_to_status(route) for route in routes if isinstance(route, dict)]
        known = {status.evidence_key for status in statuses}
        for missing in sorted(REQUIRED_EVIDENCE_KEYS - known):
            statuses.append(
                EvidenceKeyIntake(
                    evidence_key=missing,
                    kind="missing_route",
                    required_operator_action="provide a source-candidate route for this required evidence key",
                    missing_or_blocking_reasons=["source-candidate route is missing"],
                )
            )
        return statuses

    def report(self) -> Dict[str, Any]:
        source_missing = self.source_candidate is None
        import_missing = self.production_import is None
        raw_missing = self.raw_readiness is None
        statuses = self.evidence_key_statuses()
        ready_statuses = [status for status in statuses if status.ready]
        pending_statuses = [status for status in statuses if not status.ready]

        source_summary = (self.source_candidate or {}).get("summary", {})
        import_summary = (self.production_import or {}).get("summary", {})
        raw_summary = (self.raw_readiness or {}).get("summary", {})

        source_gate_ready = (
            not source_missing
            and source_summary.get("required_inputs_ready") == source_summary.get("required_inputs_total")
            and source_summary.get("ready_source_candidates_total") == source_summary.get("required_inputs_total")
            and source_summary.get("required_inputs_total") == len(REQUIRED_EVIDENCE_KEYS)
        )
        import_gate_ready = (
            not import_missing
            and import_summary.get("production_evidence_complete") is True
            and import_summary.get("source_artifacts_ready") == import_summary.get("source_artifacts_total")
        )
        bundle_manifest_identity_mismatches_total = sum(
            int(status.operator_bundle_file_report_summary.get("manifest_identity_mismatches_total", 0) or 0)
            for status in statuses
        )
        bundle_collector_id_mismatches = sum(
            int(status.operator_bundle_file_report_summary.get("collector_id_mismatches", 0) or 0)
            for status in statuses
        )
        bundle_raw_id_mismatches = sum(
            int(status.operator_bundle_file_report_summary.get("raw_id_mismatches", 0) or 0)
            for status in statuses
        )
        bundle_file_name_mismatches = sum(
            int(status.operator_bundle_file_report_summary.get("file_name_mismatches", 0) or 0)
            for status in statuses
        )
        raw_collectors_total = _int_value(raw_summary, "collectors_total")
        raw_collectors_ready = _int_value(raw_summary, "collectors_ready")
        raw_files_total = _int_value(raw_summary, "raw_files_total")
        raw_files_ready = _int_value(raw_summary, "raw_files_ready")
        raw_files_local_observation = _int_value(raw_summary, "raw_files_local_observation")
        raw_structure_ready = (
            not raw_missing
            and raw_files_total > 0
            and _int_value(raw_summary, "raw_files_missing") == 0
            and _int_value(raw_summary, "raw_files_invalid_json") == 0
            and _int_value(raw_summary, "raw_files_conflicting_status_fields") == 0
            and _int_value(raw_summary, "raw_files_placeholder_collected_by") == 0
            and _int_value(raw_summary, "raw_files_placeholder_source_commands") == 0
            and _int_value(raw_summary, "raw_files_placeholder_values") == 0
            and bundle_manifest_identity_mismatches_total == 0
            and bundle_collector_id_mismatches == 0
            and bundle_raw_id_mismatches == 0
            and bundle_file_name_mismatches == 0
        )
        raw_production_content_ready = (
            raw_structure_ready
            and raw_files_ready == raw_files_total
            and raw_files_total > 0
            and raw_files_local_observation == 0
            and (raw_collectors_total == 0 or raw_collectors_ready == raw_collectors_total)
        )
        required_key_set_ready = {status.evidence_key for status in ready_statuses} == REQUIRED_EVIDENCE_KEYS
        ready = source_gate_ready and import_gate_ready and raw_production_content_ready and required_key_set_ready

        blocking_reasons: List[str] = []
        if source_missing:
            blocking_reasons.append("source-candidate audit artifact is missing or unreadable")
        if import_missing:
            blocking_reasons.append("production evidence import artifact is missing or unreadable")
        if raw_missing:
            blocking_reasons.append("raw evidence readiness artifact is missing or unreadable")
        if not source_gate_ready:
            blocking_reasons.append("source-candidate audit has no complete set of ready production candidates")
        if not import_gate_ready:
            blocking_reasons.append("production evidence import has not accepted all required source artifacts")
        if not raw_structure_ready:
            blocking_reasons.append("raw evidence operator bundle is not structurally ready")
        elif not raw_production_content_ready:
            blocking_reasons.append("raw evidence operator bundle is structurally ready but not production-grade")
        if not required_key_set_ready:
            blocking_reasons.append("not every required evidence key has a ready production source candidate")

        return {
            "schema_version": "x0tta6bl4-integration-spine-production-evidence-intake-v1",
            "generated_at": utc_now(),
            "status": "VERIFIED HERE",
            "ok": True,
            "claim_boundary": (
                "Read-only production evidence intake gate. It validates whether operator-supplied "
                "production evidence is ready to replace retained component evidence. It does not copy "
                "files, contact live systems, submit transactions, mutate NL/SPB/runtime state, or mark "
                "the integration objective complete."
            ),
            "decision": "READY_FOR_INSTALL" if ready else "BLOCKED_OPERATOR_EVIDENCE_REQUIRED",
            "goal_can_be_marked_complete": False,
            "source_artifacts": [
                self.source_candidate_display,
                self.production_import_display,
                self.raw_readiness_display,
            ],
            "summary": {
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "required_evidence_keys_ready": len(ready_statuses),
                "required_evidence_keys_pending": len(pending_statuses),
                "raw_operator_bundle_syntax_ready": raw_structure_ready,
                "raw_operator_bundle_structure_ready": raw_structure_ready,
                "raw_operator_bundle_identity_ready": bundle_manifest_identity_mismatches_total == 0,
                "raw_operator_bundle_production_content_ready": raw_production_content_ready,
                "source_candidate_gate_ready": source_gate_ready,
                "production_import_gate_ready": import_gate_ready,
                "ready_for_install": ready,
                "raw_readiness_files_ready": raw_files_ready,
                "raw_readiness_files_total": raw_files_total,
                "raw_readiness_files_local_observation": raw_files_local_observation,
                "raw_readiness_files_missing": raw_summary.get("raw_files_missing", 0),
                "raw_readiness_files_invalid_json": raw_summary.get("raw_files_invalid_json", 0),
                "raw_readiness_files_conflicting_status_fields": raw_summary.get("raw_files_conflicting_status_fields", 0),
                "raw_readiness_files_placeholder_values": raw_summary.get("raw_files_placeholder_values", 0),
                "raw_readiness_collectors_ready": raw_summary.get("collectors_ready", 0),
                "raw_readiness_collectors_blocked": raw_summary.get("collectors_blocked", 0),
                "raw_readiness_collectors_total": raw_summary.get("collectors_total", 0),
                "source_ready_candidates_total": source_summary.get("ready_source_candidates_total", 0),
                "source_required_inputs_ready": source_summary.get("required_inputs_ready", 0),
                "source_required_inputs_total": source_summary.get("required_inputs_total", 0),
                "production_import_source_artifacts_ready": import_summary.get("source_artifacts_ready", 0),
                "production_import_source_artifacts_total": import_summary.get("source_artifacts_total", 0),
                "bundle_manifest_identity_mismatches_total": bundle_manifest_identity_mismatches_total,
                "bundle_collector_id_mismatches": bundle_collector_id_mismatches,
                "bundle_raw_id_mismatches": bundle_raw_id_mismatches,
                "bundle_file_name_mismatches": bundle_file_name_mismatches,
            },
            "required_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
            "ready_evidence_keys": sorted(status.evidence_key for status in ready_statuses),
            "pending_evidence_keys": sorted(status.evidence_key for status in pending_statuses),
            "evidence_key_statuses": [status.to_dict() for status in statuses],
            "blocking_reasons": blocking_reasons,
            "required_next_evidence": [] if ready else [
                "real external X0T settlement receipt and live Base RPC verification",
                "production stable deploy evidence",
                "production eBPF observability evidence",
                "production signed release provenance evidence",
                "production billing/provisioning evidence",
                "production SLA telemetry evidence",
                "production SPIRE/mTLS customer-path capture",
                "live multi-host hostile mesh evidence",
                "paid-customer billing, activation, access, SLA, restore, rollback, and support evidence",
                "safe rollout/rollback evidence with digest-pinned images and retained provenance",
            ],
            "not_verified_yet": [] if ready else [
                "complete ready source candidates for all integration-spine evidence keys",
                "production evidence import accepting every required source artifact",
            ],
        }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate integration-spine production evidence intake readiness")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--source-candidate-audit", default=DEFAULT_SOURCE_CANDIDATE_AUDIT)
    parser.add_argument("--production-import", default=DEFAULT_PRODUCTION_IMPORT)
    parser.add_argument("--raw-readiness", default=DEFAULT_RAW_READINESS)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless all production evidence is ready for install")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    source_input = Path(args.source_candidate_audit)
    import_input = Path(args.production_import)
    raw_input = Path(args.raw_readiness)
    gate = ProductionEvidenceIntakeGate.load(
        source_input if source_input.is_absolute() else root / source_input,
        import_input if import_input.is_absolute() else root / import_input,
        raw_input if raw_input.is_absolute() else root / raw_input,
        str(source_input),
        str(import_input),
        str(raw_input),
    )
    report = gate.report()
    write_json(root / args.output_json, report)
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["summary"]["ready_for_install"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
