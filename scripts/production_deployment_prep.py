#!/usr/bin/env python3
"""
Production Deployment Preparation

Validates local deployment-preparation prerequisites.
This is not production deployment readiness proof.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

project_root = Path(__file__).parent.parent
PRODUCTION_DEPLOYMENT_PREP_CLAIM_BOUNDARY = (
    "This script checks local preparation prerequisites such as baseline files, "
    "documentation, helper scripts, and a local security audit command. It does "
    "not prove release approval, live deployment safety, canary success, customer "
    "traffic, external DPI bypass, settlement finality, production SLOs, or "
    "production deployment readiness."
)


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


def deployment_preparation_report() -> Dict[str, Any]:
    """Return bounded local deployment-preparation evidence."""
    baseline_ok, baseline_msg = check_baseline()
    doc_results = check_documentation()
    script_results = check_scripts()
    audit_ok, audit_msg = run_security_audit()
    local_prerequisites_passed = all(
        [baseline_ok, audit_ok]
        + [passed for passed, _msg in doc_results]
        + [passed for passed, _msg in script_results]
    )
    return {
        "baseline": {"passed": baseline_ok, "message": baseline_msg},
        "documentation": [
            {"passed": passed, "message": message}
            for passed, message in doc_results
        ],
        "scripts": [
            {"passed": passed, "message": message}
            for passed, message in script_results
        ],
        "security_audit": {"passed": audit_ok, "message": audit_msg},
        "local_prerequisites_passed": local_prerequisites_passed,
        "production_deployment_ready": False,
        "production_deployment_claim_allowed": False,
        "claim_boundary": PRODUCTION_DEPLOYMENT_PREP_CLAIM_BOUNDARY,
    }


def main():
    """Main validation function."""
    print("\n" + "=" * 60)
    print("🚀 PRODUCTION DEPLOYMENT PREPARATION")
    print("=" * 60 + "\n")

    report = deployment_preparation_report()

    # Check baseline
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("BASELINE CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(report["baseline"]["message"])
    print()

    # Check documentation
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("DOCUMENTATION CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for item in report["documentation"]:
        print(item["message"])
    print()

    # Check scripts
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SCRIPTS CHECK")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for item in report["scripts"]:
        print(item["message"])
    print()

    # Run security audit
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SECURITY AUDIT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(report["security_audit"]["message"])
    print()

    # Summary
    print("=" * 60)
    if report["local_prerequisites_passed"]:
        print("✅ DEPLOYMENT PREPARATION: LOCAL CHECKS PASSED")
        print(f"\nClaim boundary: {report['claim_boundary']}")
        print("\nNext steps:")
        print("  1. Run scripts/ops/check_real_readiness.py")
        print("  2. Attach release approval, rollout, traffic, settlement, and SLO evidence")
        print("  3. Keep canary/go-live decisions behind current evidence gates")
        sys.exit(0)
    else:
        print("❌ DEPLOYMENT PREPARATION: LOCAL CHECKS INCOMPLETE")
        print("\nPlease fix missing local prerequisites before release review.")
        sys.exit(1)


if __name__ == "__main__":
    main()
