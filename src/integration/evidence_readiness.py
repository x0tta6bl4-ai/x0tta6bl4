"""Raw evidence and semantic blocker readiness gate for integration spine."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_RAW_INVENTORY = ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-evidence-readiness-current.json"


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


def _status_verified(value: Any) -> bool:
    return value == "VERIFIED HERE"


@dataclass
class EvidenceReadinessGate:
    raw_inventory_path: Path
    semantic_queue_path: Path
    raw_display_path: str = DEFAULT_RAW_INVENTORY
    semantic_display_path: str = DEFAULT_SEMANTIC_QUEUE
    raw_inventory: Optional[Dict[str, Any]] = None
    semantic_queue: Optional[Dict[str, Any]] = None
    raw_errors: List[str] = field(default_factory=list)
    semantic_errors: List[str] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        raw_inventory_path: Path,
        semantic_queue_path: Path,
        raw_display_path: str = DEFAULT_RAW_INVENTORY,
        semantic_display_path: str = DEFAULT_SEMANTIC_QUEUE,
    ) -> "EvidenceReadinessGate":
        return cls(
            raw_inventory_path,
            semantic_queue_path,
            raw_display_path,
            semantic_display_path,
            _read_json(raw_inventory_path),
            _read_json(semantic_queue_path),
        )

    def validate_raw_inventory(self) -> List[str]:
        errors: List[str] = []
        raw = self.raw_inventory
        if raw is None:
            return ["raw evidence inventory is missing or unreadable"]
        if raw.get("ok") is not True:
            errors.append("raw evidence inventory ok must be true")
        if not _status_verified(raw.get("status")):
            errors.append("raw evidence inventory status must be VERIFIED HERE")

        summary = raw.get("summary", {})
        files_total = summary.get("files_total", 0)
        usable = summary.get("usable_for_goal_completion_files", 0)
        semantic_blockers = summary.get("semantic_blockers_total", 0)
        if files_total <= 0:
            errors.append("raw evidence inventory must contain at least one file")
        if summary.get("pipeline_raw_files_expected") != files_total:
            errors.append("pipeline_raw_files_expected must equal files_total")
        if summary.get("raw_install_claim_source") != "return_acceptance":
            errors.append("raw_install_claim_source must be return_acceptance")
        if summary.get("return_acceptance_raw_files_expected") != files_total:
            errors.append("return_acceptance_raw_files_expected must equal files_total")
        if summary.get("return_acceptance_raw_files_staged") != files_total:
            errors.append("return_acceptance_raw_files_staged must equal files_total")
        if summary.get("return_acceptance_raw_ready_to_stage") is not True:
            errors.append("return_acceptance_raw_ready_to_stage must be true")
        if summary.get("return_acceptance_raw_files_local_observation", 0) != 0:
            errors.append("return_acceptance_raw_files_local_observation must be 0")
        if summary.get("template_only_files", 0) != 0:
            errors.append("template_only_files must be 0")
        if summary.get("fake_or_simulated_files", 0) != 0:
            errors.append("fake_or_simulated_files must be 0")
        if usable != files_total:
            errors.append("usable_for_goal_completion_files must equal files_total")
        if semantic_blockers != 0:
            errors.append("semantic_blockers_total must be 0")

        classification_counts = summary.get("classification_counts", {})
        if classification_counts != {"PRODUCTION_GRADE": files_total}:
            errors.append("classification_counts must contain only PRODUCTION_GRADE for every raw file")

        for idx, record in enumerate(raw.get("records", [])):
            prefix = f"records[{idx}]"
            if not record.get("usable_for_goal_completion"):
                errors.append(f"{prefix} usable_for_goal_completion must be true")
            if record.get("classification") != "PRODUCTION_GRADE":
                errors.append(f"{prefix} classification must be PRODUCTION_GRADE")
            if record.get("template_only"):
                errors.append(f"{prefix} template_only must be false")
            if record.get("fake_or_simulated"):
                errors.append(f"{prefix} fake_or_simulated must be false")
            if record.get("semantic_blockers_total", 0) != 0:
                errors.append(f"{prefix} semantic_blockers_total must be 0")
            if record.get("semantic_preflight_errors"):
                errors.append(f"{prefix} semantic_preflight_errors must be empty")
            if not _status_verified(record.get("evidence_status")):
                errors.append(f"{prefix} evidence_status must be VERIFIED HERE")

        self.raw_errors = errors
        return errors

    def validate_semantic_queue(self) -> List[str]:
        errors: List[str] = []
        semantic = self.semantic_queue
        if semantic is None:
            return ["semantic production blocker queue is missing or unreadable"]
        if semantic.get("ok") is not True:
            errors.append("semantic production blocker queue ok must be true")
        if not _status_verified(semantic.get("status")):
            errors.append("semantic production blocker queue status must be VERIFIED HERE")
        if semantic.get("completion_decision") != "COMPLETE":
            errors.append("semantic production blocker queue completion_decision must be COMPLETE")
        if semantic.get("goal_can_be_marked_complete") is not True:
            errors.append("semantic production blocker queue goal_can_be_marked_complete must be true")

        summary = semantic.get("summary", {})
        if summary.get("blocking_items_total", 0) != 0:
            errors.append("blocking_items_total must be 0")
        if summary.get("semantic_preflight_errors_total", 0) != 0:
            errors.append("semantic_preflight_errors_total must be 0")
        if summary.get("collector_groups_blocking", 0) != 0:
            errors.append("collector_groups_blocking must be 0")
        if summary.get("current_external_settlement_ready") is not True:
            errors.append("current_external_settlement_ready must be true")
        if semantic.get("blocking_items"):
            errors.append("blocking_items must be empty")
        if semantic.get("priority_order"):
            errors.append("priority_order must be empty")

        self.semantic_errors = errors
        return errors

    def report(self) -> Dict[str, Any]:
        raw_errors = self.validate_raw_inventory()
        semantic_errors = self.validate_semantic_queue()
        raw_summary = (self.raw_inventory or {}).get("summary", {})
        semantic_summary = (self.semantic_queue or {}).get("summary", {})
        raw_ready = not raw_errors
        semantic_ready = not semantic_errors
        ready = raw_ready and semantic_ready

        return {
            "schema_version": "x0tta6bl4-integration-spine-evidence-readiness-v1",
            "generated_at": utc_now(),
            "status": "VERIFIED HERE",
            "ok": True,
            "claim_boundary": (
                "Read-only readiness gate for retained raw evidence inventory and semantic production "
                "blocker queue. It does not create production evidence, mutate runtime state, or mark "
                "the integration objective complete."
            ),
            "decision": "READY_TO_PROMOTE" if ready else "BLOCKED_ON_PRODUCTION_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "source_artifacts": [
                self.raw_display_path,
                self.semantic_display_path,
            ],
            "summary": {
                "raw_inventory_ready": raw_ready,
                "semantic_queue_ready": semantic_ready,
                "production_evidence_ready": ready,
                "raw_files_total": raw_summary.get("files_total", 0),
                "raw_files_usable_for_goal_completion": raw_summary.get("usable_for_goal_completion_files", 0),
                "raw_semantic_blockers_total": raw_summary.get("semantic_blockers_total", 0),
                "semantic_blocking_items_total": semantic_summary.get("blocking_items_total", 0),
                "semantic_preflight_errors_total": semantic_summary.get("semantic_preflight_errors_total", 0),
                "semantic_current_external_settlement_ready": semantic_summary.get("current_external_settlement_ready", False),
            },
            "raw_inventory_errors": raw_errors,
            "semantic_queue_errors": semantic_errors,
            "required_next_evidence": [] if ready else [
                "replace retained raw files with production-grade evidence accepted by the source collectors",
                "close every semantic production blocker",
                "rerun external settlement, rollout provenance, raw evidence, semantic queue, and completion audit gates",
            ],
            "not_verified_yet": [] if ready else [
                "all retained raw evidence files are production-grade and usable for goal completion",
                "semantic production blocker queue has zero blocking items",
            ],
        }


def build_report(raw_inventory_path: Path, semantic_queue_path: Path, raw_display: str, semantic_display: str) -> Dict[str, Any]:
    return EvidenceReadinessGate.load(
        raw_inventory_path,
        semantic_queue_path,
        raw_display,
        semantic_display,
    ).report()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate raw evidence and semantic blocker readiness")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--raw-inventory", default=DEFAULT_RAW_INVENTORY)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless raw evidence and semantic queue are ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    raw_input = Path(args.raw_inventory)
    semantic_input = Path(args.semantic_queue)
    raw_path = raw_input if raw_input.is_absolute() else root / raw_input
    semantic_path = semantic_input if semantic_input.is_absolute() else root / semantic_input

    report = build_report(raw_path, semantic_path, str(raw_input), str(semantic_input))
    write_json(root / args.output_json, report)
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["summary"]["production_evidence_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
