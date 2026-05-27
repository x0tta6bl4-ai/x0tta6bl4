"""Build the integration-spine semantic production blocker queue.

The queue is derived from retained local pipeline artifacts. It describes what
operator/live evidence still has to replace current component evidence; it does
not collect evidence, call live services, mutate runtime, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_COVERAGE = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
BLOCKING = "BLOCKING"

COLLECTOR_LAYERS = {
    "external-settlement": ["settlement_reward_loop", "production_closeout"],
    "self-healing-pqc-mesh": ["identity", "safe_actuator", "production_closeout"],
    "zero-trust-pqc": ["identity", "policy_engine", "production_closeout"],
    "paid-client-serviceability": ["settlement_reward_loop", "safe_actuator", "production_closeout"],
    "live-rollout": ["safe_actuator", "production_closeout"],
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


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _subject_from_name(name: str) -> str:
    return Path(name).stem


def _raw_subject_for_error(error: str, raw_files: List[Dict[str, Any]]) -> tuple[str, str]:
    subjects = [
        (_subject_from_name(str(item.get("name", ""))), str(item.get("path", "")))
        for item in raw_files
        if item.get("name") or item.get("path")
    ]
    for subject, path in subjects:
        if subject and (error == subject or error.startswith(f"{subject} ")):
            return subject, path
    fallback = error.split(" ", 1)[0].strip() or "unknown"
    for subject, path in subjects:
        if subject == fallback:
            return subject, path
    return fallback, ""


def _layers_for(collector_id: str, error: str) -> List[str]:
    layers = list(COLLECTOR_LAYERS.get(collector_id, ["production_closeout"]))
    if "operator-manifest" in error and "identity" not in layers:
        layers.insert(0, "identity")
    if any(marker in error for marker in ("payment", "settlement", "entitlement", "paid")) and "settlement_reward_loop" not in layers:
        layers.append("settlement_reward_loop")
    return sorted(set(layers), key=layers.index)


def _operator_action(subject: str, error: str, path: str) -> str:
    target = path or f"<retained raw path for {subject}>"
    return f"replace {target} with retained production evidence so this check passes: {error}"


def _external_blockers(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    blocking_inputs = [
        item
        for item in _dicts(pipeline.get("blocking_inputs"))
        if item.get("kind") == "external_settlement" or item.get("evidence_key") == "external_settlement"
    ]
    if not blocking_inputs and pipeline.get("summary", {}).get("external_settlement_ready") is False:
        blocking_inputs = [
            {
                "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                "errors": ["submitted external X0T settlement receipt with matching live RPC report is missing"],
                "required_action": "submit/locate real X0T transaction receipt, retain settlement-submit.json, and verify it against live Base RPC",
            }
        ]
    for idx, item in enumerate(blocking_inputs, start=1):
        errors = _strings(item.get("errors")) or ["submitted external X0T settlement receipt with matching live RPC report is missing"]
        items.append(
            {
                "id": f"external_settlement:{idx:03d}",
                "collector_id": "external-settlement",
                "raw_subject": "settlement-submit",
                "raw_evidence_path": item.get("destination_path", ".tmp/external-settlement-evidence/settlement-submit.json"),
                "preflight_error": errors[0],
                "operator_action": item.get("required_action")
                or "submit/locate real X0T transaction receipt, retain settlement-submit.json, and verify it against live Base RPC",
                "layers": COLLECTOR_LAYERS["external-settlement"],
                "status": OPERATOR_INPUT_REQUIRED,
            }
        )
    return items


def _collector_blockers(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for command in _dicts(pipeline.get("command_results")):
        collector_id = str(command.get("collector_id", ""))
        raw_files = _dicts((command.get("stdout_json") or {}).get("raw_files"))
        for idx, error in enumerate(_strings(command.get("preflight_errors")), start=1):
            subject, path = _raw_subject_for_error(error, raw_files)
            items.append(
                {
                    "id": f"{collector_id}:{idx:03d}",
                    "collector_id": collector_id,
                    "raw_subject": subject,
                    "raw_evidence_path": path,
                    "preflight_error": error,
                    "operator_action": _operator_action(subject, error, path),
                    "layers": _layers_for(collector_id, error),
                    "status": OPERATOR_INPUT_REQUIRED,
                }
            )
    return items


@dataclass(frozen=True)
class QueueInputs:
    root: Path
    pipeline_path: Path
    coverage_path: Path
    return_acceptance_path: Path
    pipeline_display: str = DEFAULT_PIPELINE
    coverage_display: str = DEFAULT_COVERAGE
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE


def build_queue(inputs: QueueInputs) -> Dict[str, Any]:
    pipeline = _read_json(inputs.pipeline_path)
    coverage = _read_json(inputs.coverage_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    source_errors: List[str] = []
    if pipeline is None:
        source_errors.append(f"missing or unreadable production input pipeline: {inputs.pipeline_display}")
        pipeline = {}
    if coverage is None:
        source_errors.append(f"missing or unreadable objective coverage audit: {inputs.coverage_display}")
        coverage = {}
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable production input return acceptance: {inputs.return_acceptance_display}")
        return_acceptance = {}
    elif return_acceptance.get("status") != "VERIFIED HERE" or return_acceptance.get("ok") is not True:
        source_errors.append("production input return acceptance status must be VERIFIED HERE and ok true")

    blocking_items = _external_blockers(pipeline) + _collector_blockers(pipeline)
    by_collector: Dict[str, int] = {}
    by_layer: Dict[str, int] = {}
    item_status_counts: Dict[str, int] = {}
    for item in blocking_items:
        collector_id = str(item.get("collector_id", ""))
        by_collector[collector_id] = by_collector.get(collector_id, 0) + 1
        item_status = str(item.get("status", ""))
        item_status_counts[item_status] = item_status_counts.get(item_status, 0) + 1
        for layer in _strings(item.get("layers")):
            by_layer[layer] = by_layer.get(layer, 0) + 1

    pipeline_summary = _summary(pipeline)
    coverage_summary = _summary(coverage)
    return_summary = _summary(return_acceptance)
    semantic_preflight_errors_total = sum(1 for item in blocking_items if item.get("collector_id") != "external-settlement")
    raw_ready = return_summary.get("raw_ready_to_stage") is True
    complete = not blocking_items and not source_errors and raw_ready

    return {
        "schema_version": "x0tta6bl4-integration-spine-semantic-production-blocker-queue-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Generated from current retained pipeline/objective audit artifacts. "
            "Does not create or upgrade production evidence."
        ),
        "source_artifacts": [inputs.pipeline_display, inputs.coverage_display, inputs.return_acceptance_display],
        "source_errors": source_errors,
        "blocking_items": blocking_items,
        "priority_order": [str(item.get("id", "")) for item in blocking_items if item.get("id")],
        "not_verified_yet": []
        if complete
        else [
            "operator/live production evidence must clear every semantic preflight blocker",
            "external settlement receipt must be retained and verified against live RPC",
        ],
        "summary": {
            "blocking_items_total": len(blocking_items),
            "blocking_items_operator_input_required": item_status_counts.get(OPERATOR_INPUT_REQUIRED, 0),
            "blocking_items_generic_blocking": item_status_counts.get(BLOCKING, 0),
            "semantic_preflight_errors_total": semantic_preflight_errors_total,
            "external_settlement_blockers": by_collector.get("external-settlement", 0),
            "collector_groups_blocking": sum(1 for key, count in by_collector.items() if key != "external-settlement" and count > 0),
            "current_collector_evidence_blockers": pipeline_summary.get(
                "collector_evidence_blockers",
                coverage_summary.get("current_collector_evidence_blockers", 0),
            ),
            "current_external_settlement_ready": pipeline_summary.get(
                "external_settlement_ready",
                coverage_summary.get("current_external_settlement_ready", False),
            ),
            "current_raw_files_expected": return_summary.get(
                "raw_files_expected",
                pipeline_summary.get("raw_files_expected", coverage_summary.get("current_raw_files_expected", 0)),
            ),
            "current_raw_files_installed": return_summary.get("raw_files_staged", 0),
            "raw_install_claim_source": "return_acceptance",
            "pipeline_raw_files_reported_installed": pipeline_summary.get(
                "raw_files_installed",
                coverage_summary.get("current_raw_files_installed", 0),
            ),
            "return_acceptance_raw_files_ready_to_stage": return_summary.get("raw_files_ready_to_stage", 0),
            "return_acceptance_raw_files_destination_existing": return_summary.get("raw_files_destination_existing", 0),
            "return_acceptance_raw_files_local_observation": return_summary.get("raw_files_local_observation", 0),
            "return_acceptance_raw_ready_to_stage": raw_ready,
            "by_collector": by_collector,
            "by_layer": by_layer,
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
    parser = argparse.ArgumentParser(description="Build the integration-spine semantic production blocker queue")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-clear", action="store_true", help="return 2 unless no semantic blockers remain")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_queue(
        QueueInputs(
            root=root,
            pipeline_path=_resolve(root, args.pipeline),
            coverage_path=_resolve(root, args.coverage),
            return_acceptance_path=_resolve(root, args.return_acceptance),
            pipeline_display=args.pipeline,
            coverage_display=args.coverage,
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
    if args.require_clear and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
