"""Read-only readiness gate for retained production raw-evidence files.

This gate deliberately separates "JSON exists and parses" from "operator
production evidence is ready". Retained component or local-observation files
must stay blocked until an operator replaces them with production-ready JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_INTAKE_MANIFEST = ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-readiness-current.json"
DEFAULT_REQUIRED_PROVENANCE_FIELDS = ["collected_at", "collected_by", "source_commands"]

PLACEHOLDER_RE = re.compile(
    r"(placeholder|template|todo|tbd|replace me|\bexample\b|\bsample\b|your name|changeme|<[^>\n]+>)",
    re.IGNORECASE,
)
LOCAL_CONTEXT_RE = re.compile(
    r"(local|production-like|contract-validation|component-verification|test|staging|dry-run|simulation|simulated|retained)",
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


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER_RE.search(value))
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def _evidence_status(data: Dict[str, Any]) -> Any:
    return data.get("evidence_status", data.get("status"))


def _conflicting_status_fields(data: Dict[str, Any]) -> bool:
    if "status" not in data or "evidence_status" not in data:
        return False
    status = data.get("status")
    if isinstance(status, (dict, list)):
        return False
    return status != data.get("evidence_status")


def _valid_collected_at(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _context_text(data: Dict[str, Any]) -> str:
    fields = [
        data.get("claim_boundary", ""),
        data.get("environment", ""),
        data.get("cluster_context", ""),
        data.get("service_tier", ""),
        data.get("environment_id", ""),
    ]
    return " ".join(str(field) for field in fields if field is not None)


def _has_template_marker(data: Dict[str, Any], manifest_item: Dict[str, Any]) -> bool:
    return (
        manifest_item.get("template_rejected") is False
        or data.get("_template_only") is True
        or data.get("_not_evidence") is True
        or data.get("template_only") is True
        or data.get("fake_or_simulated") is True
    )


def _required_provenance_fields(manifest_item: Dict[str, Any]) -> List[str]:
    value = manifest_item.get("required_operator_provenance_fields")
    fields = [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []
    return fields or list(DEFAULT_REQUIRED_PROVENANCE_FIELDS)


def _classify_file(root: Path, manifest_item: Dict[str, Any]) -> Dict[str, Any]:
    path_display = str(manifest_item.get("path", ""))
    raw_id = str(manifest_item.get("raw_id", ""))
    path = Path(path_display)
    full_path = path if path.is_absolute() else root / path
    data, read_error = _read_json(full_path)
    errors: List[str] = []
    counters = {
        "raw_files_conflicting_status_fields": 0,
        "raw_files_invalid_collected_at": 0,
        "raw_files_invalid_json": 0,
        "raw_files_local_observation": 0,
        "raw_files_missing": 0,
        "raw_files_missing_provenance": 0,
        "raw_files_placeholder_collected_by": 0,
        "raw_files_placeholder_source_commands": 0,
        "raw_files_placeholder_values": 0,
        "raw_files_template_only": 0,
        "raw_files_wrong_status": 0,
    }

    if data is None:
        counters["raw_files_missing" if read_error == "artifact missing" else "raw_files_invalid_json"] = 1
        return {
            "path": path_display,
            "raw_id": raw_id,
            "status": "MISSING" if read_error == "artifact missing" else "INVALID_JSON",
            "ready": False,
            "errors": [read_error],
            "counters": counters,
        }

    required_status = str(manifest_item.get("required_evidence_status") or "VERIFIED HERE")
    observed_status = _evidence_status(data)
    if observed_status != required_status:
        counters["raw_files_wrong_status"] = 1
        errors.append(f"status/evidence_status must be {required_status}")
    if _conflicting_status_fields(data):
        counters["raw_files_conflicting_status_fields"] = 1
        errors.append("status and evidence_status conflict")

    if not _valid_collected_at(data.get("collected_at")):
        counters["raw_files_invalid_collected_at"] = 1
        errors.append("collected_at must be a valid timestamp")

    required_fields = _required_provenance_fields(manifest_item)
    for field in required_fields:
        if field not in data or data.get(field) in ("", None, []):
            counters["raw_files_missing_provenance"] = 1
            errors.append(f"{field} is required")

    if _contains_placeholder(data.get("collected_by")):
        counters["raw_files_placeholder_collected_by"] = 1
        counters["raw_files_placeholder_values"] = 1
        errors.append("collected_by must not contain placeholders")

    source_commands = data.get("source_commands")
    if not isinstance(source_commands, list) or not source_commands:
        counters["raw_files_missing_provenance"] = 1
        errors.append("source_commands must be a non-empty list")
    elif _contains_placeholder(source_commands):
        counters["raw_files_placeholder_source_commands"] = 1
        counters["raw_files_placeholder_values"] = 1
        errors.append("source_commands must not contain placeholders")

    if _has_template_marker(data, manifest_item):
        counters["raw_files_template_only"] = 1
        errors.append("template/mock/placeholder markers must be absent")

    blockers = data.get("production_promotion_blockers", [])
    local_context = bool(LOCAL_CONTEXT_RE.search(_context_text(data)))
    production_ready = data.get("production_ready") is True and not blockers and not local_context
    if not production_ready:
        counters["raw_files_local_observation"] = 1
        errors.append(
            "raw evidence is retained/local/component context until production_ready=true, "
            "production_promotion_blockers=[], and production context is observed"
        )

    ready = not errors
    return {
        "path": path_display,
        "raw_id": raw_id,
        "status": "READY_FOR_COLLECTOR" if ready else "LOCAL_OBSERVATION",
        "ready": ready,
        "errors": sorted(set(errors)),
        "counters": counters,
    }


def _empty_summary(collectors_total: int = 0) -> Dict[str, int]:
    return {
        "collectors_blocked": 0,
        "collectors_ready": 0,
        "collectors_total": collectors_total,
        "raw_files_conflicting_status_fields": 0,
        "raw_files_invalid_collected_at": 0,
        "raw_files_invalid_json": 0,
        "raw_files_local_observation": 0,
        "raw_files_missing": 0,
        "raw_files_missing_provenance": 0,
        "raw_files_placeholder_collected_by": 0,
        "raw_files_placeholder_source_commands": 0,
        "raw_files_placeholder_values": 0,
        "raw_files_ready": 0,
        "raw_files_template_only": 0,
        "raw_files_total": 0,
        "raw_files_wrong_status": 0,
    }


def build_report(root: Path, intake_manifest_path: Path = Path(DEFAULT_INTAKE_MANIFEST)) -> Dict[str, Any]:
    manifest, manifest_error = _read_json(intake_manifest_path)
    manifest_collectors = _dicts((manifest or {}).get("collectors"))
    summary = _empty_summary(len(manifest_collectors))
    collectors: List[Dict[str, Any]] = []
    source_errors = [f"{DEFAULT_INTAKE_MANIFEST}: {manifest_error}"] if manifest_error else []

    for collector in manifest_collectors:
        raw_files = _dicts(collector.get("raw_files"))
        file_reports = [_classify_file(root, item) for item in raw_files]
        collector_summary = _empty_summary(1)
        collector_summary["raw_files_total"] = len(file_reports)

        for report in file_reports:
            counters = report.pop("counters")
            for key, value in counters.items():
                collector_summary[key] += int(value)
            if report["ready"]:
                collector_summary["raw_files_ready"] += 1

        collector_ready = bool(file_reports) and collector_summary["raw_files_ready"] == collector_summary["raw_files_total"]
        collector_summary["collectors_ready"] = 1 if collector_ready else 0
        collector_summary["collectors_blocked"] = 0 if collector_ready else 1
        collectors.append(
            {
                "collector_id": collector.get("collector_id", ""),
                "collector_script": collector.get("collector_script", ""),
                "collector_ready": collector_ready,
                "files": file_reports,
                **collector_summary,
            }
        )
        for key, value in collector_summary.items():
            if key != "collectors_total":
                summary[key] += int(value)

    if source_errors:
        summary["collectors_blocked"] = summary["collectors_total"]
        summary["collectors_ready"] = 0

    ready = (
        not source_errors
        and summary["collectors_total"] > 0
        and summary["collectors_ready"] == summary["collectors_total"]
        and summary["raw_files_ready"] == summary["raw_files_total"]
        and summary["raw_files_total"] > 0
        and summary["raw_files_local_observation"] == 0
    )

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-readiness-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only raw evidence readiness checker. It reads retained raw roots, classifies files, "
            "and never collects evidence, runs collectors, contacts live systems, mutates runtime state, "
            "or promotes /goal completion."
        ),
        "raw_evidence_readiness_decision": "READY_FOR_COLLECTORS" if ready else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
        "ready_for_collectors": ready,
        "goal_can_be_marked_complete": False,
        "materializes_evidence": False,
        "mutates_files": False,
        "mutates_files_outside_outputs": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "runs_live_cluster": False,
        "runs_live_customer_path": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "source_artifacts": [str(intake_manifest_path)],
        "source_errors": source_errors,
        "collectors": collectors,
        "summary": summary,
        "not_verified_yet": [] if ready else [
            "operator-supplied production raw evidence with production_ready=true",
            "empty production_promotion_blockers for every raw file",
            "production context without local/test/staging/simulation claim boundaries",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate retained production raw-evidence readiness")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.intake_manifest)
    output_path = Path(args.output_json)
    report = build_report(root, manifest_path if manifest_path.is_absolute() else root / manifest_path)
    write_json(output_path if output_path.is_absolute() else root / output_path, report)
    print(json.dumps({
        "decision": report["raw_evidence_readiness_decision"],
        "ready_for_collectors": report["ready_for_collectors"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready_for_collectors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
