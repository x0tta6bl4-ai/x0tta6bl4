#!/usr/bin/env python3
"""
Production utility to check CRDT sync status.

Usage:
    python3 scripts/check_crdt_sync_status.py
    python3 scripts/check_crdt_sync_status.py --node-id node-1
    python3 scripts/check_crdt_sync_status.py --json
"""
import argparse
import sys
import json

try:
    from src.data_sync.crdt_optimizations import get_crdt_optimizer
    CRDT_OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    CRDT_OPTIMIZATIONS_AVAILABLE = False
    print("⚠️ CRDT optimizations not available", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Check CRDT sync status")
    parser.add_argument("--node-id", type=str, default="node-1", help="Node ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    optimizer = get_crdt_optimizer(args.node_id)
    
    metrics = optimizer.get_metrics()
    
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("=" * 60)
        print("CRDT Sync Status")
        print("=" * 60)
        print(f"Node ID: {args.node_id}")
        print(f"Total Syncs: {metrics['total_syncs']}")
        print(f"Successful Syncs: {metrics['successful_syncs']}")
        print(f"Failed Syncs: {metrics['failed_syncs']}")
        print(f"Success Rate: {metrics['success_rate']*100:.1f}%")
        print(f"Avg Sync Duration: {metrics['avg_sync_duration_ms']:.2f}ms")
        print(f"Bytes Sent: {metrics['bytes_sent']:,}")
        print(f"Bytes Received: {metrics['bytes_received']:,}")
        print(f"Conflicts Resolved: {metrics['conflicts_resolved']}")
        
        # Show CRDT state
        state = optimizer.sync_manager.get_crdt_state()
        if state:
            print("\n" + "=" * 60)
            print("CRDT State")
            print("=" * 60)
            for key, value in state.items():
                print(f"{key}: {value}")


if __name__ == "__main__":
    main()

