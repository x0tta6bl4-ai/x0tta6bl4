#!/usr/bin/env python3
"""
Production utility to check Zero Trust enforcement status.

Usage:
    python3 scripts/check_zero_trust_status.py
    python3 scripts/check_zero_trust_status.py --detailed
    python3 scripts/check_zero_trust_status.py --peer spiffe://x0tta6bl4.mesh/workload/api
"""
import argparse
import json
import sys
from typing import Any, Dict

try:
    from src.security.zero_trust.enforcement import get_zero_trust_enforcer

    ZERO_TRUST_AVAILABLE = True
except ImportError:
    ZERO_TRUST_AVAILABLE = False
    print("⚠️ Zero Trust enforcement not available", file=sys.stderr)
    sys.exit(1)


def format_trust_score(score) -> str:
    """Format trust score for display"""
    score_map = {
        0: "🔴 UNTRUSTED",
        1: "🟠 LOW",
        2: "🟡 MEDIUM",
        3: "🟢 HIGH",
        4: "✅ TRUSTED",
    }
    return score_map.get(
        score.value if hasattr(score, "value") else score, "❓ UNKNOWN"
    )


def main():
    parser = argparse.ArgumentParser(description="Check Zero Trust enforcement status")
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed information"
    )
    parser.add_argument("--peer", type=str, help="Check specific peer")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    enforcer = get_zero_trust_enforcer()

    if args.peer:
        # Check specific peer
        result = enforcer.enforce(args.peer, "/api/v1/health")

        if args.json:
            output = {
                "peer": args.peer,
                "allowed": result.allowed,
                "trust_score": (
                    result.trust_score.value
                    if hasattr(result.trust_score, "value")
                    else str(result.trust_score)
                ),
                "reason": result.reason,
                "isolation_level": (
                    result.isolation_level.value
                    if result.isolation_level
                    and hasattr(result.isolation_level, "value")
                    else None
                ),
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Peer: {args.peer}")
            print(f"Allowed: {'✅ YES' if result.allowed else '❌ NO'}")
            print(f"Trust Score: {format_trust_score(result.trust_score)}")
            print(f"Reason: {result.reason}")
            if result.isolation_level:
                print(f"Isolation Level: {result.isolation_level}")
    else:
        # Show statistics
        stats = enforcer.get_enforcement_stats()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("=" * 60)
            print("Zero Trust Enforcement Status")
            print("=" * 60)
            print(f"Total Requests: {stats['total_requests']}")
            print(f"Allowed: {stats['allowed']} ({stats['allow_rate']*100:.1f}%)")
            print(f"Denied: {stats['denied']} ({stats['deny_rate']*100:.1f}%)")
            print(f"Isolated: {stats['isolated']} ({stats['isolation_rate']*100:.1f}%)")
            print(f"Tracked Peers: {stats['tracked_peers']}")

            if args.detailed:
                print("\n" + "=" * 60)
                print("Detailed Information")
                print("=" * 60)
                print(f"Success Rate: {stats.get('success_rate', 0)*100:.1f}%")
                print(
                    f"Avg Sync Duration: {stats.get('avg_sync_duration_ms', 0):.2f}ms"
                )
                print(f"Bytes Sent: {stats.get('bytes_sent', 0)}")
                print(f"Bytes Received: {stats.get('bytes_received', 0)}")
                print(f"Conflicts Resolved: {stats.get('conflicts_resolved', 0)}")


if __name__ == "__main__":
    main()
