#!/usr/bin/env python3
"""
Production Deployment Preparation

Validates all prerequisites before production deployment.
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

project_root = Path(__file__).parent.parent


def check_file_exists(filepath: Path) -> Tuple[bool, str]:
    """Check if file exists."""
    if filepath.exists():
        return True, f"✅ {filepath.name}"
    return False, f"❌ {filepath.name} missing"


def check_baseline() -> Tuple[bool, str]:
    """Check if baseline exists."""
    baseline_file = project_root / "baseline_metrics.json"
    if baseline_file.exists():
        return True, "✅ Baseline metrics exist"
    return False, "❌ Baseline metrics missing"


def check_documentation() -> List[Tuple[bool, str]]:
    """Check if all documentation exists."""
    docs = [
        project_root / "docs/team/ON_CALL_RUNBOOK.md",
        project_root / "docs/team/INCIDENT_RESPONSE_PLAN.md",
        project_root / "docs/team/READINESS_CHECKLIST.md",
        project_root / "LAUNCH_READINESS_REPORT.md",
        project_root / "PRE_DEPLOYMENT_PLAN.md",
    ]

    results = []
    for doc in docs:
        results.append(check_file_exists(doc))

    return results


def check_scripts() -> List[Tuple[bool, str]]:
    """Check if all scripts exist."""
    scripts = [
        project_root / "scripts/security_audit_checklist.py",
        project_root / "scripts/performance_baseline.py",
        project_root / "scripts/staging_deployment.py",
        project_root / "scripts/run_load_test.py",
        project_root / "scripts/run_staging_validation.sh",
    ]

    results = []
    for script in scripts:
        results.append(check_file_exists(script))

    return results


def run_security_audit() -> Tuple[bool, str]:
    """Run security audit."""
    try:
        result = subprocess.run(
            ["python3", "scripts/security_audit_checklist.py"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, "✅ Security audit passed"
        return False, f"❌ Security audit failed: {result.stderr[:100]}"
    except Exception as e:
        return False, f"❌ Security audit error: {str(e)[:100]}"


def main():
    """Main validation function."""
    print("\n" + "=" * 60)
    print("🚀 PRODUCTION DEPLOYMENT PREPARATION")
    print("=" * 60 + "\n")

    all_passed = True

    # Check baseline
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("BASELINE CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    baseline_ok, baseline_msg = check_baseline()
    print(baseline_msg)
    if not baseline_ok:
        all_passed = False
    print()

    # Check documentation
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("DOCUMENTATION CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    doc_results = check_documentation()
    for passed, msg in doc_results:
        print(msg)
        if not passed:
            all_passed = False
    print()

    # Check scripts
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SCRIPTS CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    script_results = check_scripts()
    for passed, msg in script_results:
        print(msg)
        if not passed:
            all_passed = False
    print()

    # Run security audit
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SECURITY AUDIT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    audit_ok, audit_msg = run_security_audit()
    print(audit_msg)
    if not audit_ok:
        all_passed = False
    print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("✅ PRODUCTION DEPLOYMENT: READY")
        print("\nAll prerequisites met. Ready for production deployment!")
        print("\nNext steps:")
        print("  1. Final executive approval (Jan 6-7)")
        print("  2. Canary deployment 5% (Jan 8)")
        print("  3. Monitor and scale gradually")
        sys.exit(0)
    else:
        print("❌ PRODUCTION DEPLOYMENT: NOT READY")
        print("\nPlease fix missing prerequisites before deployment.")
        sys.exit(1)


if __name__ == "__main__":
    main()
