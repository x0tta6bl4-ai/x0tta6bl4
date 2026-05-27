#!/usr/bin/env python3
"""Verify x0tta6bl4_pulse external evidence files against the proof contract.

This command is read-only. It uses the same external evidence requirements as
the proof gate and is intended for intake checks before replacing fail-closed
gap records with real lab, kernel, security-review, or production-readiness
evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def load_proof_gate(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_proof_gate_for_external_intake", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def requirement_by_claim(proof) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}


def build_report(root: Path = ROOT, claims: list[str] | None = None) -> dict[str, Any]:
    proof = load_proof_gate(root)
    requirements = requirement_by_claim(proof)
    selected_claims = claims or list(requirements)
    unknown = sorted(set(selected_claims) - set(requirements))
    rows = []
    for claim_id in selected_claims:
        if claim_id in requirements:
            rows.append(proof.validate_external_evidence(root, requirements[claim_id]))

    failures = [f"unknown claim: {claim_id}" for claim_id in unknown]
    for row in rows:
        if row["status"] != "VERIFIED":
            failures.extend(f"{row['claim_id']}: {error}" for error in row["errors"])

    return {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_intake.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "rows": rows,
        "failures": failures,
        "claim_boundary": {
            "note": "Read-only intake validation only; it does not upgrade proof-gate claims by itself.",
        },
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"status={report['status']}",
        "rows:",
    ]
    for row in report["rows"]:
        lines.append(f"- {row['claim_id']}: {row['status']} ({row['evidence']})")
        for error in row["errors"]:
            lines.append(f"  - {error}")
    if report["failures"]:
        lines.append("failures:")
        lines.extend(f"- {failure}" for failure in report["failures"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--claim", action="append", help="Claim id to validate. Repeatable.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = build_report(root=root, claims=args.claim)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    if args.require_pass and report["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
