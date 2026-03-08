#!/usr/bin/env python3
"""Validate presence of ISO 27001 P2 readiness documentation artifacts."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RequiredDoc:
    path: str
    purpose: str
    must_contain: tuple[str, ...] = ()


REQUIRED_DOCS: tuple[RequiredDoc, ...] = (
    RequiredDoc(
        path="docs/compliance/ISO_IEC_27001_2025_READINESS.md",
        purpose="Readiness baseline and decision boundaries",
        must_contain=("Status:", "Required Artifacts Before External Audit"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_EVIDENCE_INDEX.md",
        purpose="Evidence catalog and collection rules",
        must_contain=("Evidence Collection Rules", "Core Evidence Set"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md",
        purpose="Risk register and treatment tracking",
        must_contain=("Active Risks", "Review Cadence"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_POLICY_INDEX.md",
        purpose="Unified policy index and ownership",
        must_contain=("Policy Register", "Review and Approval Workflow"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_RISK_ACCEPTANCE_CRITERIA.md",
        purpose="Risk acceptance thresholds and sign-off policy",
        must_contain=("Risk Acceptance Matrix", "Approval Authority"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_INTERNAL_AUDIT_PROGRAM.md",
        purpose="Internal audit plan and corrective action loop",
        must_contain=("Audit Scope", "Corrective Actions"),
    ),
    RequiredDoc(
        path="docs/compliance/ISO_27001_2025_DOCUMENT_CONTROL_POLICY.md",
        purpose="Document control, retention, and traceability",
        must_contain=("Versioning Rules", "Retention Rules"),
    ),
)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    missing_files: list[str] = []
    missing_markers: list[str] = []

    print("# ISO 27001 P2 Readiness Check")

    for doc in REQUIRED_DOCS:
        full_path = REPO_ROOT / doc.path
        if not full_path.exists():
            missing_files.append(doc.path)
            print(f"[MISSING] {doc.path} :: {doc.purpose}")
            continue

        content = full_path.read_text(encoding="utf-8")
        missing_tokens = [token for token in doc.must_contain if token not in content]
        if missing_tokens:
            marker_text = ", ".join(missing_tokens)
            missing_markers.append(f"{doc.path} -> {marker_text}")
            print(f"[WARN] {doc.path} :: missing markers: {marker_text}")
        else:
            print(f"[OK] {doc.path}")

    print()
    if missing_files:
        print("Missing required files:")
        for path in missing_files:
            print(f"- {path}")

    if missing_markers:
        print("Missing required content markers:")
        for item in missing_markers:
            print(f"- {item}")

    if missing_files or missing_markers:
        print()
        print("RESULT: FAIL")
        return 1

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
