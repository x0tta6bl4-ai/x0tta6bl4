#!/usr/bin/env python3
"""Safe Pilot Triage Tool for x0tta6bl4.

Combines user subscription diagnostics with symptom intake requirements
to produce a redacted incident report for paid pilots.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
GHOST_DIAG_SCRIPT = ROOT / "services/nl-server/ghost-access/diagnose_user_subscription.py"
SYMPTOM_INTAKE_SCRIPT = ROOT / "nl-diagnostics/build_vpn_incident_symptom_intake.py"
TEMPLATE_FILE = ROOT / "docs/templates/PILOT_INCIDENT_REPORT_TEMPLATE.md"

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a safe pilot triage session.")
    parser.add_argument("--user-id", type=int, help="Ghost Access user ID")
    parser.add_argument("--username", help="Ghost Access username")
    parser.add_argument("--incident-id", default=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    return parser.parse_args(argv)

def run_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        # Try parsing stdout regardless of exit code
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"Exit code {result.returncode}"}
        return {}
    except Exception as exc:
        return {"error": str(exc)}

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # 1. Run User Subscription Diagnosis
    diag_cmd = [sys.executable, str(GHOST_DIAG_SCRIPT), "--json"]
    if args.user_id:
        diag_cmd.extend(["--user-id", str(args.user_id)])
    elif args.username:
        diag_cmd.extend(["--username", args.username])
    else:
        # If no user info, we can still run symptom intake logic later
        pass

    user_diag = {}
    if args.user_id or args.username:
        print(f"[*] Running subscription diagnosis for {args.username or args.user_id}...")
        user_diag = run_command(diag_cmd)

    # 2. Run Symptom Intake Template Generator (Read-only)
    print("[*] Collecting global VPN decision evidence...")
    symptom_intake = run_command([sys.executable, str(SYMPTOM_INTAKE_SCRIPT)])

    # 3. Combine results
    report = {
        "incident_id": args.incident_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_diagnosis": user_diag,
        "global_evidence": symptom_intake,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    # 4. Generate human-readable output (simplified Action Note)
    print("\n" + "="*60)
    print(f"PILOT TRIAGE REPORT: {args.incident_id}")
    print("="*60)

    if "error" in user_diag:
        print(f"User Diag ERROR: {user_diag['error']}")
    elif user_diag:
        summary = user_diag.get("summary", {})
        print(f"User Status: {user_diag.get('status', 'unknown').upper()}")
        print(f"Subscription: {'OK' if summary.get('subscription_token_present') else 'MISSING'}")
        print(f"Plan Expired: {summary.get('plan_expired')}")
        print(f"Active Devices: {summary.get('active_device_count')}")

        for rec in user_diag.get("recommendations", []):
            print(f"Recommendation: {rec}")

    print("\nGlobal VPN Evidence:")
    if "error" in symptom_intake:
        print(f"Global Evidence ERROR: {symptom_intake['error']}")
    else:
        glob_sum = symptom_intake.get("summary", {})
        print(f"Decision: {glob_sum.get('decision')}")
        print(f"Transport: {glob_sum.get('transport_status')}")
        print(f"Blocking History: {glob_sum.get('blocking_history_trend')}")

    print("\nNext Steps for Operator:")
    print("1. Copy the template from docs/templates/PILOT_INCIDENT_REPORT_TEMPLATE.md")
    print("2. Fill in the intake questions provided below.")
    print("3. Combine with the redacted evidence above.")

    print("\nIntake Questions to ask the user:")
    for q in symptom_intake.get("intake_questions", []):
        print(f"- {q}")

    return 0

if __name__ == "__main__":
    main()
