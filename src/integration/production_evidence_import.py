"""Build production evidence import and next-input reports from source candidates.

The reports are read-only coordination artifacts. They keep the production
gap index aligned with the current 10-key evidence contract without collecting
evidence, staging files, contacting live systems, or promoting readiness.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS


DEFAULT_SOURCE_CANDIDATE_AUDIT = ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
DEFAULT_IMPORT_OUTPUT = ".tmp/validation-shards/integration-spine-production-evidence-import-current.json"
DEFAULT_NEXT_INPUTS_OUTPUT = ".tmp/validation-shards/integration-spine-production-next-inputs-current.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> List[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str)]


def _first_string(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _route_by_key(source_candidate: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    routes = (source_candidate or {}).get("evidence_source_routes", [])
    if not isinstance(routes, list):
        return {}
    return {str(route.get("evidence_key", "")): route for route in routes if isinstance(route, dict)}


def _candidate_ready(candidate: Dict[str, Any]) -> bool:
    return (
        candidate.get("classification") == "READY_SOURCE_CANDIDATE"
        and candidate.get("available") is True
        and candidate.get("production_artifact") is True
        and candidate.get("matches_raw_contract") is True
    )


def _primary_candidate(route: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [item for item in _as_list(route.get("source_candidates")) if isinstance(item, dict)]
    for candidate in candidates:
        if _candidate_ready(candidate):
            return candidate
    for candidate in candidates:
        source_id = str(candidate.get("source_id", ""))
        if source_id.startswith("operator_bundle:") or source_id == "required_artifact:external_settlement":
            return candidate
    return candidates[0] if candidates else {}


def _candidate_errors(route: Dict[str, Any], candidate: Dict[str, Any]) -> List[str]:
    errors = [
        str(error)
        for error in _as_list(candidate.get("not_ready_reasons"))
        if isinstance(error, str)
    ]
    if not errors and isinstance(candidate.get("reason"), str) and candidate.get("reason"):
        errors.append(str(candidate["reason"]))
    blockers = route.get("semantic_blockers_total", 0) or 0
    try:
        blockers_int = int(blockers)
    except (TypeError, ValueError):
        blockers_int = 0
    if blockers_int > 0 and not any("semantic blockers" in error for error in errors):
        collector = route.get("collector_id") or route.get("evidence_key")
        errors.append(f"semantic blockers still open for {collector}: {blockers_int}")
    return errors[:40]


def _artifact_paths(route: Dict[str, Any], candidate: Dict[str, Any]) -> List[str]:
    paths = _string_list(candidate.get("artifact_paths"))
    if paths:
        return paths
    artifact_path = candidate.get("artifact_path")
    if isinstance(artifact_path, str) and artifact_path:
        return [artifact_path]
    operator_paths = _string_list(route.get("operator_bundle_paths"))
    if operator_paths:
        return operator_paths
    required = route.get("required_artifact_path")
    return [required] if isinstance(required, str) and required else []


def _artifact_exists(route: Dict[str, Any], candidate: Dict[str, Any], paths: List[str]) -> bool:
    if route.get("kind") == "external_settlement":
        return route.get("required_artifact_exists") is True
    if candidate:
        return candidate.get("available") is True
    return bool(paths)


def _source_item(root: Path, key: str, route: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not route:
        source_path = ""
        errors = ["source-candidate route is missing"]
        next_item = {
            "evidence_key": key,
            "kind": "missing_route",
            "ready": False,
            "source_artifact_exists": False,
            "source_artifact_path": source_path,
            "source_artifact_paths": [],
            "operator_action": "provide a source-candidate route for this required evidence key",
            "verification_command": "",
            "collector_command": "",
            "errors": errors,
            "collector_preflight_errors": errors,
            "collector_semantic_blocker_raw_paths": [],
            "collector_semantic_blockers_total": 0,
        }
        import_item = {
            "evidence_key": key,
            "kind": "missing_route",
            "ready": False,
            "artifact_exists": False,
            "artifact_path": source_path,
            "artifact_paths": [],
            "supporting_artifact_exists": False,
            "supporting_artifact_path": "",
            "errors": errors,
        }
        return next_item, import_item

    candidate = _primary_candidate(route)
    paths = _artifact_paths(route, candidate)
    path = _first_string(paths)
    exists = _artifact_exists(route, candidate, paths)
    ready = route.get("route_classification") == "READY_TO_INSTALL" and _candidate_ready(candidate)
    errors = [] if ready else _candidate_errors(route, candidate)
    source_id = str(candidate.get("source_id", ""))

    next_item = {
        "evidence_key": key,
        "kind": route.get("kind", ""),
        "collector_id": route.get("collector_id", ""),
        "ready": ready,
        "source_artifact_exists": exists,
        "source_artifact_path": path,
        "source_artifact_paths": paths,
        "operator_action": route.get("required_operator_action", ""),
        "verification_command": route.get("verification_command", ""),
        "collector_command": route.get("collector_command", ""),
        "errors": errors,
        "collector_preflight_errors": errors,
        "collector_semantic_blocker_raw_paths": _string_list(route.get("raw_paths")),
        "collector_semantic_blockers_total": route.get("semantic_blockers_total", 0),
        "operator_bundle_paths": _string_list(route.get("operator_bundle_paths")),
        "raw_paths": _string_list(route.get("raw_paths")),
        "source_candidate_id": source_id,
        "route_classification": route.get("route_classification", ""),
    }
    import_item = {
        "evidence_key": key,
        "kind": route.get("kind", ""),
        "collector_id": route.get("collector_id", ""),
        "ready": ready,
        "artifact_exists": exists,
        "artifact_path": path,
        "artifact_paths": paths,
        "supporting_artifact_exists": False,
        "supporting_artifact_path": "",
        "source_candidate_id": source_id,
        "source_candidate_classification": candidate.get("classification", ""),
        "source_candidate_status": candidate.get("status", ""),
        "source_candidate_decision": candidate.get("decision", ""),
        "production_artifact": candidate.get("production_artifact") is True,
        "matches_raw_contract": candidate.get("matches_raw_contract") is True,
        "errors": errors,
    }
    if route.get("kind") == "external_settlement":
        for required in _as_list(candidate.get("required_artifacts")):
            if isinstance(required, dict):
                import_item["supporting_artifact_path"] = str(required.get("artifact_path", ""))
                import_item["supporting_artifact_exists"] = required.get("available") is True
                break
    return next_item, import_item


def build_reports(
    root: Path,
    source_candidate_path: Path,
    source_candidate_display: str = DEFAULT_SOURCE_CANDIDATE_AUDIT,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    source_candidate, source_error = _read_json(source_candidate_path)
    routes = _route_by_key(source_candidate)
    next_items: List[Dict[str, Any]] = []
    import_items: List[Dict[str, Any]] = []
    for key in sorted(REQUIRED_EVIDENCE_KEYS):
        next_item, import_item = _source_item(root, key, routes.get(key))
        next_items.append(next_item)
        import_items.append(import_item)

    ready_items = [item for item in import_items if item.get("ready") is True]
    pending_items = [item for item in import_items if item.get("ready") is not True]
    found_items = [item for item in import_items if item.get("artifact_exists") is True]
    missing_items = [item for item in import_items if item.get("artifact_exists") is not True]
    artifact_files_total = sum(len(item.get("artifact_paths", []) or []) for item in import_items)
    artifact_files_found = sum(
        len(item.get("artifact_paths", []) or [])
        for item in import_items
        if item.get("artifact_exists") is True
    )
    complete = not source_error and len(ready_items) == len(REQUIRED_EVIDENCE_KEYS)

    common_boundary = (
        "Repo-generated read-only production evidence import/next-input view. It derives "
        "required inputs from the current source-candidate audit and does not collect evidence, "
        "copy files, run collectors, contact live systems, submit transactions, mutate runtime, "
        "or mark the objective complete."
    )
    import_report = {
        "schema_version": "x0tta6bl4-integration-spine-production-evidence-import-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": common_boundary,
        "production_evidence_import_decision": "READY_TO_IMPORT" if complete else "BLOCKED_PRODUCTION_EVIDENCE",
        "goal_can_be_marked_complete": False,
        "materializes_evidence": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "runs_live_cluster": False,
        "runs_live_customer_path": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "source_artifacts": [source_candidate_display],
        "source_load_errors": [source_error] if source_error else [],
        "source_results": import_items,
        "summary": {
            "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
            "production_evidence_complete": complete,
            "source_artifacts_total": len(import_items),
            "source_artifacts_ready": len(ready_items),
            "source_artifacts_pending": len(pending_items),
            "source_artifact_files_total": artifact_files_total,
            "source_artifact_files_found": artifact_files_found,
            "source_artifact_files_missing": max(artifact_files_total - artifact_files_found, 0),
            "source_artifact_keys_found": len(found_items),
            "source_artifact_keys_missing": len(missing_items),
            "external_settlement_live_rpc_ready": False,
        },
        "not_verified_yet": [] if complete else [
            "all 10 required evidence keys have ready production source artifacts",
            "all 63 raw evidence files are production-ready",
            "external X0T settlement receipt is retained and live-RPC verified",
        ],
    }
    next_report = {
        "schema_version": "x0tta6bl4-integration-spine-production-next-inputs-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": common_boundary,
        "decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if complete else "BLOCKED_PRODUCTION_INPUTS",
        "ready_for_production_closeout_review": complete,
        "goal_can_be_marked_complete": False,
        "source_of_truth": source_candidate_display,
        "source_load_errors": [source_error] if source_error else [],
        "required_inputs": next_items,
        "operator_commands": [
            item.get("collector_command")
            for item in next_items
            if item.get("collector_command")
        ]
        + [
            item.get("verification_command")
            for item in next_items
            if item.get("verification_command")
        ],
        "summary": {
            "required_inputs_total": len(next_items),
            "required_inputs_ready": len([item for item in next_items if item.get("ready") is True]),
            "required_inputs_pending": len([item for item in next_items if item.get("ready") is not True]),
            "ready_evidence_keys": [item["evidence_key"] for item in next_items if item.get("ready") is True],
            "pending_evidence_keys": [item["evidence_key"] for item in next_items if item.get("ready") is not True],
            "source_artifacts_total": len(import_items),
            "source_artifacts_ready": len(ready_items),
            "source_artifacts_pending": len(pending_items),
            "source_artifact_files_total": artifact_files_total,
            "source_artifact_files_found": artifact_files_found,
            "source_artifact_files_missing": max(artifact_files_total - artifact_files_found, 0),
            "production_evidence_import_decision": import_report["production_evidence_import_decision"],
            "production_ready": complete,
        },
        "not_verified_yet": [] if complete else [
            "all production next inputs are backed by ready source candidates",
            "production evidence import is complete",
        ],
    }
    return next_report, import_report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production evidence import reports")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--source-candidate-audit", default=DEFAULT_SOURCE_CANDIDATE_AUDIT)
    parser.add_argument("--output-import-json", default=DEFAULT_IMPORT_OUTPUT)
    parser.add_argument("--output-next-inputs-json", default=DEFAULT_NEXT_INPUTS_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    source_input = Path(args.source_candidate_audit)
    next_report, import_report = build_reports(
        root=root,
        source_candidate_path=_resolve(root, args.source_candidate_audit),
        source_candidate_display=str(source_input),
    )
    _write_json(_resolve(root, args.output_next_inputs_json), next_report)
    _write_json(_resolve(root, args.output_import_json), import_report)
    print(json.dumps({
        "decision": import_report["production_evidence_import_decision"],
        "goal_can_be_marked_complete": False,
        "summary": import_report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and import_report["summary"]["production_evidence_complete"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
