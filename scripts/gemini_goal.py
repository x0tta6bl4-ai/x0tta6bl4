#!/usr/bin/env python3
"""
Gemini Goal Manager for x0tta6bl4
Simulates the /goal command behavior of Codex/Claude Code.
Updates coordination state and logs goals.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(".agent-coord/state.json")
LOG_FILE = Path(".agent-coord/log.jsonl")
AUDIT_FILE = Path(".tmp/validation-shards/gemini-ghost-core-vv-audit-current.json")

CLAIM_OVERRIDE_RULES = (
    ("xdp_live_attach", "ebpf_current_xdp_attach"),
    ("GHOST-CORE", "ghost_core_mvp_stabilization_completed"),
    ("Share-to-Earn", "share_to_earn_blockchain_payout_engine"),
    ("SPIRE", "spire_live_svid_current_runtime"),
)

BLOCKING_DECISIONS = {
    "FAILED_SECURITY_CONCERN",
    "NOT_VERIFIED",
    "NOT_VERIFIED_CURRENT_RUNTIME",
    "NOT_VERIFIED_PRODUCTION",
    "PARTIAL_LOCAL_RUNTIME_ONLY",
}


def get_timestamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _audit_claims_by_id(audit):
    claims = audit.get("claims", [])
    if not isinstance(claims, list):
        return {}
    return {
        str(claim.get("id")): claim
        for claim in claims
        if isinstance(claim, dict) and claim.get("id")
    }


def audit_override_for_verified_item(item, audit):
    claims = _audit_claims_by_id(audit)
    item_lower = item.lower()
    for marker, claim_id in CLAIM_OVERRIDE_RULES:
        if marker.lower() not in item_lower:
            continue
        claim = claims.get(claim_id, {})
        decision = str(claim.get("decision", ""))
        if decision in BLOCKING_DECISIONS:
            return {
                "claim_id": claim_id,
                "decision": decision,
                "claim": str(claim.get("claim", "")),
                "limits": [
                    str(limit)
                    for limit in claim.get("limits", [])
                    if isinstance(limit, str)
                ],
            }
    return {}


def audit_overrides_for_verified_items(items, audit):
    overrides = []
    for item in items:
        override = audit_override_for_verified_item(str(item), audit)
        if override:
            overrides.append({"item": str(item), **override})
    return overrides


def show_goal():
    if not STATE_FILE.exists():
        print("Coordination state not found.")
        return

    state = _load_json(STATE_FILE)
    audit = _load_json(AUDIT_FILE)
    gemini = state.get("agents", {}).get("gemini", {})
    status = gemini.get("status", "unknown")

    print(f"\n🎯 [GEMINI GOAL STATUS]")
    print(f"Status: {status.upper()}")
    print("-" * 30)

    if audit:
        summary = audit.get("summary", {})
        print("\n🧾 Current V&V Audit Boundary:")
        print(f"  Decision: {audit.get('decision', 'unknown')}")
        print(f"  Generated: {audit.get('generated_at', 'unknown')}")
        print(
            "  Production promotion allowed: "
            f"{summary.get('production_promotion_allowed', False)}"
        )

    # Show items from global_not_verified_yet that might be relevant
    pending = state.get("global_not_verified_yet", [])
    if pending:
        print("\n📥 Pending Tasks (Global Queue):")
        for i, task in enumerate(pending, 1):
            print(f"  {i}. {task}")

    if audit.get("not_verified_yet"):
        print("\n🚧 Gemini V&V Still Not Verified:")
        for item in audit.get("not_verified_yet", [])[:7]:
            print(f"  - {item}")

    # Show audit-aware raw coordination claims.
    verified = gemini.get("last_verified_here", [])
    if verified:
        print("\n🧭 Recent Gemini Coordination Claims (audit-aware):")
        for item in verified[-5:]:
            override = audit_override_for_verified_item(str(item), audit)
            if override:
                print(f"  - {item}")
                print(f"    ↳ superseded by audit: {override['decision']}")
            else:
                print(f"  - {item}")

    overrides = audit_overrides_for_verified_items(verified, audit)
    if overrides:
        print("\n⚠️ Superseded Gemini Claims:")
        for override in overrides:
            print(f"  - {override['item']} -> {override['decision']}")
    print("-" * 30 + "\n")

def set_goal(goal_text):
    print(f"🚀 Setting new goal: {goal_text}")

    # 1. Update Log
    log_entry = {
        "ts": get_timestamp(),
        "agent": "gemini",
        "event": "goal_set",
        "goal": goal_text,
        "status": "in_progress"
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # 2. Update State
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        if "agents" not in state: state["agents"] = {}
        if "gemini" not in state["agents"]: state["agents"]["gemini"] = {}

        state["agents"]["gemini"]["status"] = "in_progress"
        state["agents"]["gemini"]["current_goal"] = goal_text
        state["_updated"] = get_timestamp()

        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    print("✅ Goal recorded in coordination state.")

def main():
    if len(sys.argv) < 2:
        show_goal()
        return

    command = sys.argv[1]
    if command == "set":
        if len(sys.argv) < 3:
            print("Usage: /goal set <goal_text>")
            return
        set_goal(" ".join(sys.argv[2:]))
    elif command == "status":
        show_goal()
    else:
        # Default behavior: treat as setting a goal if no sub-command
        set_goal(" ".join(sys.argv[1:]))

if __name__ == "__main__":
    main()
