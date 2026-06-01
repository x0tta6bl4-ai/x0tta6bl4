#!/usr/bin/env python3
"""Inventory SafeActuator evidence-metadata adoption across control paths.

This is a static source inventory. It proves that source files contain the
expected typed metadata plumbing; it does not prove runtime execution or
production readiness.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "x0tta6bl4.safe_actuator_metadata_adoption.v1"
CLAIM_BOUNDARY = (
    "SafeActuator metadata adoption inventory is a static source scan only. "
    "It can show where typed redacted evidence metadata is wired in source, "
    "but it does not prove runtime execution, EventBus delivery, dataplane "
    "delivery, settlement finality, production SLOs, or production readiness."
)
DEFAULT_SCAN_ROOTS = ("src", "scripts")
EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "archive",
    "backup-20260410-090811",
    "docker-data-old",
    "docker-ext4",
    "node_modules",
    "recovered_photos",
}
DEFAULT_HIGH_RISK_FILES = (
    "src/mesh/action_enforcer.py",
    "src/network/mptcp_manager.py",
    "src/swarm/pbft.py",
    "src/swarm/intelligence/mapek.py",
    "src/dao/governance.py",
    "src/dao/governance_contract.py",
    "src/dao/proposal_executor_webhook.py",
    "src/dao/bridge/core.py",
    "src/self_healing/mape_k/manager.py",
    "src/self_healing/ebpf_anomaly_detector.py",
    "src/services/pqc_rotator_service.py",
    "src/server/ghost_server.py",
    "src/security/spiffe/server/client.py",
    "src/security/spiffe/agent/manager.py",
    "src/deployment/canary_deployment.py",
    "src/deployment/multi_cloud_deployment.py",
    "scripts/canary_deployment.py",
    "scripts/production_monitor.py",
    "scripts/auto_rollback.py",
    "scripts/deploy/production_deploy.py",
)


@dataclass(frozen=True)
class ResultCall:
    path: str
    line: int
    function: str
    has_evidence_metadata: bool
    source: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iter_python_files(root: Path, scan_roots: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for rel in scan_roots:
        base = root / rel
        if base.is_file() and base.suffix == ".py":
            files.append(base)
            continue
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            parts = set(path.relative_to(root).parts)
            if parts & EXCLUDED_DIRS:
                continue
            files.append(path)
    return sorted(set(files))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


class SafeActuatorCallVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, rel_path: str, source: str) -> None:
        self.path = path
        self.rel_path = rel_path
        self.source = source
        self.function_stack: list[str] = []
        self.result_calls: list[ResultCall] = []
        self.safe_actuator_calls = 0
        self.async_safe_actuator_calls = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node.func)
        if name == "SafeActuator":
            self.safe_actuator_calls += 1
        elif name == "AsyncSafeActuator":
            self.async_safe_actuator_calls += 1
        elif name == "SafeActuatorResult":
            has_metadata = any(keyword.arg == "evidence_metadata" for keyword in node.keywords)
            snippet = ast.get_source_segment(self.source, node) or "SafeActuatorResult(...)"
            self.result_calls.append(
                ResultCall(
                    path=self.rel_path,
                    line=getattr(node, "lineno", 0),
                    function=self.function_stack[-1] if self.function_stack else "<module>",
                    has_evidence_metadata=has_metadata,
                    source=" ".join(snippet.strip().split())[:240],
                )
            )
        self.generic_visit(node)


def _scan_file(root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8", errors="replace")
    visitor = SafeActuatorCallVisitor(path, rel, source)
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return {
            "path": rel,
            "parse_error": f"{exc.__class__.__name__}: {exc}",
            "safe_actuator_calls": 0,
            "async_safe_actuator_calls": 0,
            "safe_actuator_result_calls": 0,
            "result_calls_with_evidence_metadata": 0,
            "result_calls_without_evidence_metadata": 0,
            "metadata_publish_marker_present": "safe_actuator_evidence_metadata" in source,
            "typed_metadata_class_marker_present": "SafeActuatorEvidenceMetadata" in source,
            "result_calls": [],
        }
    visitor.visit(tree)
    result_calls = visitor.result_calls
    with_metadata = [item for item in result_calls if item.has_evidence_metadata]
    without_metadata = [item for item in result_calls if not item.has_evidence_metadata]
    return {
        "path": rel,
        "parse_error": "",
        "safe_actuator_calls": visitor.safe_actuator_calls,
        "async_safe_actuator_calls": visitor.async_safe_actuator_calls,
        "safe_actuator_result_calls": len(result_calls),
        "result_calls_with_evidence_metadata": len(with_metadata),
        "result_calls_without_evidence_metadata": len(without_metadata),
        "metadata_publish_marker_present": "safe_actuator_evidence_metadata" in source,
        "typed_metadata_class_marker_present": "SafeActuatorEvidenceMetadata" in source,
        "result_calls": [item.__dict__ for item in result_calls],
    }


def _file_record_is_metadata_aware(record: dict[str, Any]) -> bool:
    if record.get("parse_error"):
        return False
    if record.get("result_calls_with_evidence_metadata", 0) > 0:
        return True
    if record.get("metadata_publish_marker_present") is True:
        return True
    if record.get("typed_metadata_class_marker_present") is True:
        return True
    return False


def build_report(
    root: Path,
    *,
    scan_roots: Iterable[str] = DEFAULT_SCAN_ROOTS,
    high_risk_files: Iterable[str] = DEFAULT_HIGH_RISK_FILES,
    sample_limit: int = 25,
) -> dict[str, Any]:
    root = root.resolve()
    files = _iter_python_files(root, scan_roots)
    records = [_scan_file(root, path) for path in files]
    active_records = [
        record
        for record in records
        if record["safe_actuator_calls"]
        or record["async_safe_actuator_calls"]
        or record["safe_actuator_result_calls"]
        or record["metadata_publish_marker_present"]
        or record["typed_metadata_class_marker_present"]
    ]
    result_records = [record for record in records if record["safe_actuator_result_calls"]]
    parse_errors = [record for record in records if record.get("parse_error")]

    result_calls_total = sum(record["safe_actuator_result_calls"] for record in records)
    result_calls_with_metadata = sum(
        record["result_calls_with_evidence_metadata"] for record in records
    )
    result_calls_without_metadata = sum(
        record["result_calls_without_evidence_metadata"] for record in records
    )
    missing_samples: list[dict[str, Any]] = []
    for record in result_records:
        for call in record["result_calls"]:
            if call.get("has_evidence_metadata") is False:
                missing_samples.append(call)
    missing_samples = missing_samples[:sample_limit]

    records_by_path = {record["path"]: record for record in records}
    high_risk: list[dict[str, Any]] = []
    blockers: list[str] = []
    for rel in high_risk_files:
        record = records_by_path.get(rel)
        present = record is not None
        metadata_aware = bool(record and _file_record_is_metadata_aware(record))
        if not present:
            blockers.append(f"high_risk_file_missing:{rel}")
        elif not metadata_aware:
            blockers.append(f"high_risk_file_lacks_metadata_marker:{rel}")
        high_risk.append(
            {
                "path": rel,
                "present": present,
                "metadata_aware": metadata_aware,
                "safe_actuator_calls": record.get("safe_actuator_calls", 0) if record else 0,
                "async_safe_actuator_calls": (
                    record.get("async_safe_actuator_calls", 0) if record else 0
                ),
                "safe_actuator_result_calls": (
                    record.get("safe_actuator_result_calls", 0) if record else 0
                ),
                "result_calls_with_evidence_metadata": (
                    record.get("result_calls_with_evidence_metadata", 0) if record else 0
                ),
                "metadata_publish_marker_present": (
                    record.get("metadata_publish_marker_present") is True if record else False
                ),
                "typed_metadata_class_marker_present": (
                    record.get("typed_metadata_class_marker_present") is True if record else False
                ),
            }
        )

    high_risk_ready = not blockers
    parse_error_free = len(parse_errors) == 0
    full_metadata_coverage_ready = (
        result_calls_without_metadata == 0 and parse_error_free
    )
    adoption_ratio = (
        round(result_calls_with_metadata / result_calls_total, 4)
        if result_calls_total
        else 1.0
    )
    return {
        "schema": SCHEMA,
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": (
            "SAFE_ACTUATOR_METADATA_FULL_COVERAGE"
            if high_risk_ready and full_metadata_coverage_ready
            else "SAFE_ACTUATOR_METADATA_HIGH_RISK_COVERED"
            if high_risk_ready
            else "SAFE_ACTUATOR_METADATA_HIGH_RISK_GAPS"
        ),
        "generated_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "files_scanned": len(files),
            "files_with_safe_actuator_surface": len(active_records),
            "files_with_safe_actuator_result_calls": len(result_records),
            "parse_errors": len(parse_errors),
            "safe_actuator_calls": sum(record["safe_actuator_calls"] for record in records),
            "async_safe_actuator_calls": sum(
                record["async_safe_actuator_calls"] for record in records
            ),
            "safe_actuator_result_calls": result_calls_total,
            "result_calls_with_evidence_metadata": result_calls_with_metadata,
            "result_calls_without_evidence_metadata": result_calls_without_metadata,
            "result_call_metadata_adoption_ratio": adoption_ratio,
            "high_risk_files_checked": len(high_risk),
            "high_risk_files_metadata_aware": sum(
                1 for item in high_risk if item["metadata_aware"]
            ),
            "high_risk_coverage_ready": high_risk_ready,
            "full_metadata_coverage_ready": full_metadata_coverage_ready,
            "parse_error_free": parse_error_free,
            "missing_metadata_samples_capped": len(missing_samples),
        },
        "blockers": blockers,
        "parse_errors": [
            {"path": record["path"], "error": record["parse_error"]}
            for record in parse_errors[:sample_limit]
        ],
        "high_risk_files": high_risk,
        "missing_metadata_samples": missing_samples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory SafeActuator evidence metadata adoption."
    )
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON")
    parser.add_argument(
        "--require-high-risk-covered",
        action="store_true",
        help="Exit 2 when known high-risk control paths lack metadata markers.",
    )
    parser.add_argument(
        "--require-full-coverage",
        action="store_true",
        help="Exit 2 when any SafeActuatorResult call lacks evidence_metadata.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(Path(args.root))
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if args.json or not args.output_json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    summary = report.get("summary", {})
    if args.require_high_risk_covered and report["blockers"]:
        return 2
    if args.require_full_coverage and (
        report["blockers"] or not summary.get("full_metadata_coverage_ready")
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
