"""Build the integration-spine raw evidence inventory.

The inventory classifies retained raw evidence files against the current
semantic production blocker queue. It is read-only and cannot promote component
evidence to production proof by itself.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json"


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


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _collector_counts(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for record in records:
        collector = str(record.get("collector", ""))
        classification = str(record.get("classification", ""))
        result.setdefault(collector, {})
        result[collector][classification] = result[collector].get(classification, 0) + 1
    return result


def _status(data: Dict[str, Any]) -> Any:
    return data.get("evidence_status", data.get("status"))


def _explicit_bool(data: Dict[str, Any], key: str) -> bool:
    return data.get(key) is True or data.get(f"_{key}") is True


def _blockers_by_path(semantic_queue: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for item in _dicts(semantic_queue.get("blocking_items")):
        path = str(item.get("raw_evidence_path", ""))
        if path:
            result.setdefault(path, []).append(item)
    return result


def _record(root: Path, install: Dict[str, Any], blockers_by_path: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    display_path = str(install.get("destination_path", ""))
    path = Path(display_path)
    data = _read_json(path if path.is_absolute() else root / path) or {}
    blockers = blockers_by_path.get(display_path, [])
    production_promotion_blockers = _strings(data.get("production_promotion_blockers"))
    template_only = _explicit_bool(data, "template_only") or data.get("_not_evidence") is True
    fake_or_simulated = _explicit_bool(data, "fake_or_simulated")
    semantic_errors = [str(item.get("preflight_error", "")) for item in blockers if item.get("preflight_error")]
    explicit_production_ready = data.get("production_ready") is True or data.get("production_claim") is True
    verified_here_component = data.get("evidence_status") == "VERIFIED HERE" and data.get("status") == "VERIFIED HERE"

    if template_only:
        classification = "TEMPLATE_ONLY"
    elif fake_or_simulated:
        classification = "FAKE_OR_SIMULATED"
    elif blockers or production_promotion_blockers or not explicit_production_ready:
        classification = "RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE"
    else:
        classification = "PRODUCTION_GRADE"
    usable = classification == "PRODUCTION_GRADE"

    return {
        "path": display_path,
        "collector": install.get("collector_id", ""),
        "subject": Path(display_path).stem,
        "status": data.get("status", "NOT_FOUND" if not data else ""),
        "evidence_status": _status(data) or ("NOT_FOUND" if not data else ""),
        "environment": data.get("environment"),
        "template_only": template_only,
        "fake_or_simulated": fake_or_simulated,
        "verified_here_component_evidence": verified_here_component,
        "production_promotion_blockers_total": len(production_promotion_blockers),
        "semantic_blockers_total": len(blockers),
        "semantic_blocker_ids": [str(item.get("id", "")) for item in blockers if item.get("id")],
        "semantic_preflight_errors": semantic_errors,
        "classification": classification,
        "usable_for_goal_completion": usable,
        "claim_boundary_blocks_production_promotion": not usable,
    }


@dataclass(frozen=True)
class InventoryInputs:
    root: Path
    pipeline_path: Path
    semantic_queue_path: Path
    return_acceptance_path: Path
    pipeline_display: str = DEFAULT_PIPELINE
    semantic_queue_display: str = DEFAULT_SEMANTIC_QUEUE
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE


def build_inventory(inputs: InventoryInputs) -> Dict[str, Any]:
    pipeline = _read_json(inputs.pipeline_path)
    semantic_queue = _read_json(inputs.semantic_queue_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    source_errors: List[str] = []
    if pipeline is None:
        source_errors.append(f"missing or unreadable production input pipeline: {inputs.pipeline_display}")
        pipeline = {}
    if semantic_queue is None:
        source_errors.append(f"missing or unreadable semantic blocker queue: {inputs.semantic_queue_display}")
        semantic_queue = {}
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable production input return acceptance: {inputs.return_acceptance_display}")
        return_acceptance = {}
    elif return_acceptance.get("status") != "VERIFIED HERE" or return_acceptance.get("ok") is not True:
        source_errors.append("production input return acceptance status must be VERIFIED HERE and ok true")

    blockers = _blockers_by_path(semantic_queue)
    records = [
        _record(inputs.root, item, blockers)
        for item in _dicts(pipeline.get("raw_install_results"))
        if item.get("destination_path")
    ]
    usable = [item for item in records if item.get("usable_for_goal_completion") is True]
    semantic_blocking_files = [item for item in records if item.get("semantic_blockers_total", 0) > 0]
    pipeline_summary = _summary(pipeline)
    return_summary = _summary(return_acceptance)
    files_total = len(records)
    return_raw_expected = _int_value(return_summary, "raw_files_expected")
    return_raw_staged = _int_value(return_summary, "raw_files_staged")
    return_raw_ready_to_stage = _int_value(return_summary, "raw_files_ready_to_stage")
    return_raw_local_observation = _int_value(return_summary, "raw_files_local_observation")
    return_raw_destination_existing = _int_value(return_summary, "raw_files_destination_existing")
    return_raw_ready = return_summary.get("raw_ready_to_stage") is True
    return_acceptance_covers_records = return_raw_expected == files_total and return_raw_staged == files_total
    complete = (
        bool(records)
        and len(usable) == files_total
        and not source_errors
        and return_acceptance_covers_records
        and return_raw_ready
        and return_raw_local_observation == 0
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-raw-evidence-inventory-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Inventory of current retained raw evidence files for the four semantic production collectors. "
            "It classifies evidence; it does not create production proof or upgrade readiness."
        ),
        "source_artifacts": [
            inputs.semantic_queue_display,
            inputs.pipeline_display,
            inputs.return_acceptance_display,
        ],
        "source_errors": source_errors,
        "records": records,
        "summary": {
            "files_total": files_total,
            "pipeline_raw_files_expected": pipeline_summary.get("raw_files_expected", files_total),
            "pipeline_raw_files_installed": pipeline_summary.get("raw_files_installed", files_total),
            "pipeline_raw_files_reported_installed": pipeline_summary.get("raw_files_installed", files_total),
            "raw_install_claim_source": "return_acceptance",
            "return_acceptance_raw_files_expected": return_raw_expected,
            "return_acceptance_raw_files_staged": return_raw_staged,
            "return_acceptance_raw_files_ready_to_stage": return_raw_ready_to_stage,
            "return_acceptance_raw_files_destination_existing": return_raw_destination_existing,
            "return_acceptance_raw_files_local_observation": return_raw_local_observation,
            "return_acceptance_raw_ready_to_stage": return_raw_ready,
            "return_acceptance_covers_records": return_acceptance_covers_records,
            "classification_counts": _count_by(records, "classification"),
            "collector_classification_counts": _collector_counts(records),
            "template_only_files": sum(1 for item in records if item.get("template_only") is True),
            "fake_or_simulated_files": sum(1 for item in records if item.get("fake_or_simulated") is True),
            "usable_for_goal_completion_files": len(usable),
            "semantic_blockers_total": sum(int(item.get("semantic_blockers_total", 0)) for item in records),
            "semantic_blocking_files": len(semantic_blocking_files),
            "verified_here_component_files": sum(1 for item in records if item.get("verified_here_component_evidence") is True),
            "source_errors_total": len(source_errors),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the integration-spine raw evidence inventory")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless every retained raw file is production-grade")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_inventory(
        InventoryInputs(
            root=root,
            pipeline_path=_resolve(root, args.pipeline),
            semantic_queue_path=_resolve(root, args.semantic_queue),
            return_acceptance_path=_resolve(root, args.return_acceptance),
            pipeline_display=args.pipeline,
            semantic_queue_display=args.semantic_queue,
            return_acceptance_display=args.return_acceptance,
        )
    )
    write_json(_resolve(root, args.output_json), report)
    print(
        json.dumps(
            {
                "completion_decision": report["completion_decision"],
                "goal_can_be_marked_complete": report["goal_can_be_marked_complete"],
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
