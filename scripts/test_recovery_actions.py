#!/usr/bin/env python3
"""
Production utility to test recovery actions.

Usage:
    python3 scripts/test_recovery_actions.py --action restart --service test-service
    python3 scripts/test_recovery_actions.py --action scale --deployment test --replicas 5
    python3 scripts/test_recovery_actions.py --list-actions
"""
import argparse
import asyncio
import sys
from typing import Any, Dict

try:
    from src.self_healing.recovery_actions import RecoveryActionExecutor

    RECOVERY_ACTIONS_AVAILABLE = True
except ImportError:
    RECOVERY_ACTIONS_AVAILABLE = False
    print("⚠️ Recovery actions not available", file=sys.stderr)
    sys.exit(1)


async def test_action(
    executor: RecoveryActionExecutor, action_type: str, **kwargs
) -> bool:
    """Test a recovery action"""
    print(f"Testing action: {action_type}")
    print(f"Parameters: {kwargs}")

    try:
        result = await executor.execute_action(action_type, **kwargs)
        if result:
            print(f"✅ Action '{action_type}' executed successfully")
        else:
            print(f"❌ Action '{action_type}' failed")
        return result
    except Exception as e:
        print(f"❌ Error executing action: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test recovery actions")
    parser.add_argument("--action", type=str, help="Action type to test")
    parser.add_argument(
        "--list-actions", action="store_true", help="List available actions"
    )
    parser.add_argument("--node-id", type=str, default="test-node", help="Node ID")

    # Action-specific arguments
    parser.add_argument(
        "--service", type=str, help="Service name (for restart/clear-cache)"
    )
    parser.add_argument(
        "--namespace", type=str, default="default", help="Kubernetes namespace"
    )
    parser.add_argument("--deployment", type=str, help="Deployment name (for scale)")
    parser.add_argument("--replicas", type=int, help="Number of replicas (for scale)")
    parser.add_argument("--old-route", type=str, help="Old route (for switch-route)")
    parser.add_argument("--new-route", type=str, help="New route (for switch-route)")
    parser.add_argument(
        "--primary-region", type=str, help="Primary region (for failover)"
    )
    parser.add_argument(
        "--fallback-region", type=str, help="Fallback region (for failover)"
    )
    parser.add_argument(
        "--cache-type", type=str, default="all", help="Cache type (for clear-cache)"
    )

    args = parser.parse_args()

    executor = RecoveryActionExecutor(node_id=args.node_id)

    if args.list_actions:
        print("Available Recovery Actions:")
        print("  1. Restart service")
        print("  2. Switch route")
        print("  3. Clear cache")
        print("  4. Scale up")
        print("  5. Failover")
        print("  6. Quarantine node")
        return

    if not args.action:
        print(
            "❌ Error: --action is required (use --list-actions to see available actions)"
        )
        sys.exit(1)

    # Build kwargs based on action type
    kwargs: Dict[str, Any] = {}

    if args.action == "Restart service":
        if not args.service:
            print("❌ Error: --service is required for restart action")
            sys.exit(1)
        kwargs = {"service_name": args.service, "namespace": args.namespace}
    elif args.action == "Scale up":
        if not args.deployment or not args.replicas:
            print("❌ Error: --deployment and --replicas are required for scale action")
            sys.exit(1)
        kwargs = {
            "deployment_name": args.deployment,
            "replicas": args.replicas,
            "namespace": args.namespace,
        }
    elif args.action == "Switch route":
        if not args.old_route or not args.new_route:
            print(
                "❌ Error: --old-route and --new-route are required for switch-route action"
            )
            sys.exit(1)
        kwargs = {"old_route": args.old_route, "new_route": args.new_route}
    elif args.action == "Clear cache":
        if not args.service:
            print("❌ Error: --service is required for clear-cache action")
            sys.exit(1)
        kwargs = {"service_name": args.service, "cache_type": args.cache_type}
    elif args.action == "Failover":
        if not args.primary_region or not args.fallback_region:
            print(
                "❌ Error: --primary-region and --fallback-region are required for failover action"
            )
            sys.exit(1)
        kwargs = {
            "service_name": args.service or "default-service",
            "primary_region": args.primary_region,
            "fallback_region": args.fallback_region,
        }
    elif args.action == "Quarantine node":
        if not args.node_id:
            print("❌ Error: --node-id is required for quarantine action")
            sys.exit(1)
        kwargs = {"node_id": args.node_id}
    else:
        print(f"❌ Error: Unknown action '{args.action}'")
        print("Use --list-actions to see available actions")
        sys.exit(1)

    # Execute action
    result = asyncio.run(test_action(executor, args.action, **kwargs))
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
