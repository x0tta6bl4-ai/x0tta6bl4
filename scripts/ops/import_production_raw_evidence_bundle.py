#!/usr/bin/env python3
"""Read-only acceptance gate for returned production raw-evidence bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.evidence_source_candidates import COLLECTOR_BY_KEY, DEFAULT_OPERATOR_BUNDLE_ROOT
from src.integration.operator_bundle_gate import build_report


DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-bundle-import-current.json"
RAW_EVIDENCE_KEYS = sorted(COLLECTOR_BY_KEY)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _gate_file_count(gate: Dict[str, Any], field: str) -> int:
    value = gate.get("summary", {}).get(field, 0)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def build_import_report(root: Path, bundle_root: str = DEFAULT_OPERATOR_BUNDLE_ROOT) -> Dict[str, Any]:
    gates = [
        build_report(root=root, evidence_key=key, operator_bundle_root=bundle_root)
        for key in RAW_EVIDENCE_KEYS
    ]
    ready_gates = [gate for gate in gates if gate.get("decision") == "READY_TO_INSTALL"]
    blocked_gates = [gate for gate in gates if gate.get("decision") != "READY_TO_INSTALL"]
    source_files_total = sum(_gate_file_count(gate, "bundle_files_total") for gate in gates)
    source_files_found = sum(_gate_file_count(gate, "bundle_files_available") for gate in gates)
    ready_files = sum(
        _gate_file_count(gate, "bundle_files_total")
        for gate in gates
        if gate.get("decision") == "READY_TO_INSTALL"
    )
    identity_mismatches = sum(
        _gate_file_count(gate, "bundle_manifest_identity_mismatches_total")
        for gate in gates
    )
    ready = len(ready_gates) == len(RAW_EVIDENCE_KEYS)

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-bundle-import-v1",
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only acceptance gate for operator-returned production raw-evidence bundle files. "
            "It validates bundle files through the integration operator-bundle gates. It does not "
            "copy files into retained raw-evidence destinations, contact live systems, mutate NL/SPB/"
            "VPN runtime, or mark the objective complete."
        ),
        "bundle_root": bundle_root,
        "materializes_evidence": False,
        "installs_raw_evidence": False,
        "mutates_files": False,
        "mutates_files_outside_outputs": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "goal_can_be_marked_complete": False,
        "raw_evidence_bundle_import_decision": "READY_TO_INSTALL" if ready else "BLOCKED",
        "summary": {
            "collectors_total": len(RAW_EVIDENCE_KEYS),
            "collectors_ready": len(ready_gates),
            "collectors_blocked": len(blocked_gates),
            "source_files_total": source_files_total,
            "source_files_found": source_files_found,
            "source_files_ready_to_install": ready_files,
            "bundle_manifest_identity_mismatches_total": identity_mismatches,
            "ready_to_install": ready,
        },
        "evidence_key_reports": [
            {
                "evidence_key": gate.get("evidence_key"),
                "collector_id": gate.get("collector_id"),
                "decision": gate.get("decision"),
                "summary": gate.get("summary", {}),
                "blocking_reasons": gate.get("blocking_reasons", []),
                "identity_update_plan": gate.get("identity_update_plan", []),
            }
            for gate in gates
        ],
        "not_verified_yet": [] if ready else [
            "all raw production operator-bundle gates must report READY_TO_INSTALL",
            "all returned bundle files must have production_ready=true and empty production_promotion_blockers",
            "manifest identity fields collector_id/raw_id/file_name must match the intake manifest",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate returned production raw-evidence bundle files")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_import_report(root, args.bundle_root)
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["raw_evidence_bundle_import_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["raw_evidence_bundle_import_decision"] != "READY_TO_INSTALL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
