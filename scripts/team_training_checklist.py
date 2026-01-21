#!/usr/bin/env python3
"""
Team Training Checklist

Validates that team is ready for production deployment.
"""

import sys
from pathlib import Path
from typing import List, Dict

project_root = Path(__file__).parent.parent

def check_runbook_exists() -> bool:
    """Check if runbook exists."""
    runbook = project_root / "docs/team/ON_CALL_RUNBOOK.md"
    return runbook.exists()

def check_incident_plan_exists() -> bool:
    """Check if incident response plan exists."""
    plan = project_root / "docs/team/INCIDENT_RESPONSE_PLAN.md"
    return plan.exists()

def check_readiness_checklist_exists() -> bool:
    """Check if readiness checklist exists."""
    checklist = project_root / "docs/team/READINESS_CHECKLIST.md"
    return checklist.exists()

def check_documentation_complete() -> Dict[str, bool]:
    """Check if all documentation is complete."""
    docs = {
        "Runbook": check_runbook_exists(),
        "Incident Response Plan": check_incident_plan_exists(),
        "Readiness Checklist": check_readiness_checklist_exists(),
    }
    return docs

def main():
    """Main function."""
    print("\n" + "="*60)
    print("📚 TEAM TRAINING CHECKLIST")
    print("="*60 + "\n")
    
    docs = check_documentation_complete()
    
    all_complete = True
    for doc_name, exists in docs.items():
        status = "✅" if exists else "❌"
        print(f"{status} {doc_name}")
        if not exists:
            all_complete = False
    
    print()
    print("="*60)
    
    if all_complete:
        print("✅ ALL DOCUMENTATION READY")
        print("\nTeam training materials:")
        print("  • On-Call Runbook: docs/team/ON_CALL_RUNBOOK.md")
        print("  • Incident Response Plan: docs/team/INCIDENT_RESPONSE_PLAN.md")
        print("  • Readiness Checklist: docs/team/READINESS_CHECKLIST.md")
        print("\nNext steps:")
        print("  1. Review all documentation")
        print("  2. Conduct team training session")
        print("  3. Setup on-call rotation")
        print("  4. Test incident response procedures")
        sys.exit(0)
    else:
        print("❌ SOME DOCUMENTATION MISSING")
        print("\nPlease create missing documentation before team training.")
        sys.exit(1)

if __name__ == "__main__":
    main()

