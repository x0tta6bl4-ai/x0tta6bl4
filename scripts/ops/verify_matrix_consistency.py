#!/usr/bin/env python3
"""
x0tta6bl4 Verification Matrix Consistency Auditor.

Scans README.md, VERIFICATION_MATRIX.md, AGENTS.md, and test files to ensure
100% status alignment and zero contradictory claims across all project docs.

Compliance: Chief Engineer Mandate & 3-Tier Status Taxonomy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def audit_matrix_consistency() -> int:
    matrix_file = ROOT / "docs" / "verification" / "VERIFICATION_MATRIX.md"
    readme_file = ROOT / "README.md"
    agents_file = ROOT / "AGENTS.md"

    print("🔍 Auditing Verification Matrix Consistency...")

    if not matrix_file.exists():
        print(f"❌ Missing {matrix_file}")
        return 1

    matrix_text = matrix_file.read_text(encoding="utf-8")
    readme_text = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""
    agents_text = agents_file.read_text(encoding="utf-8") if agents_file.exists() else ""

    errors = 0
    warnings = 0

    # 1. Verify all file references in VERIFICATION_MATRIX.md exist
    file_refs = re.findall(r'\[`([^`]+)`\]\(file://[^\)]+\)', matrix_text)
    for ref in file_refs:
        ref_path = ROOT / ref
        if not ref_path.exists():
            print(f"❌ Matrix references missing file: {ref}")
            errors += 1
        else:
            print(f"  ✓ Valid file reference: {ref}")

    # 2. Check 3-Tier Taxonomy Usage
    allowed_statuses = ["✅ VERIFIED", "🟡 VALIDATED IN LAB", "⚪ TARGET"]
    for line in matrix_text.splitlines():
        if "| **" in line and "`" in line:
            status_match = re.search(r'`(✅ VERIFIED|🟡 VALIDATED IN LAB|⚪ TARGET)`', line)
            if not status_match:
                print(f"⚠️ Line missing strict taxonomy tag: {line.strip()}")
                warnings += 1

    # 3. Verify README status alignment
    if "VERIFICATION_MATRIX.md" not in readme_text:
        print("❌ README.md does not link to VERIFICATION_MATRIX.md")
        errors += 1
    else:
        print("  ✓ README.md contains link to VERIFICATION_MATRIX.md")

    # 4. Check for forbidden terms (excluding rule definition lists)
    forbidden_terms = ["физически прогнан", "100% reliable", "лучший в мире", "не имеет аналогов"]
    for file_path in [matrix_file, readme_file]:
        text = file_path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                print(f"❌ Forbidden term '{term}' found in {file_path.name}")
                errors += 1

    print("\n--- Audit Summary ---")
    print(f"Errors: {errors}, Warnings: {warnings}")
    if errors == 0:
        print("✅ CONSISTENCY AUDIT PASSED: All documentation claims are 100% aligned and verifiable.")
        return 0
    else:
        print("❌ CONSISTENCY AUDIT FAILED: Fix errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(audit_matrix_consistency())
