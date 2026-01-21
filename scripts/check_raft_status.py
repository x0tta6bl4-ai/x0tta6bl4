#!/usr/bin/env python3
"""
Production utility to check Raft consensus status.

Usage:
    python3 scripts/check_raft_status.py
    python3 scripts/check_raft_status.py --node-id node-1
    python3 scripts/check_raft_status.py --json
"""
import argparse
import sys
import json
from pathlib import Path

try:
    from src.consensus.raft_production import get_production_raft_node
    RAFT_PRODUCTION_AVAILABLE = True
except ImportError:
    RAFT_PRODUCTION_AVAILABLE = False
    print("⚠️ Production Raft not available", file=sys.stderr)
    sys.exit(1)


def format_state(state) -> str:
    """Format Raft state for display"""
    state_map = {
        "follower": "👤 FOLLOWER",
        "candidate": "🗳️ CANDIDATE",
        "leader": "👑 LEADER"
    }
    return state_map.get(state, f"❓ {state.upper()}")


def main():
    parser = argparse.ArgumentParser(description="Check Raft consensus status")
    parser.add_argument("--node-id", type=str, default="node-1", help="Node ID")
    parser.add_argument("--peers", type=str, nargs="+", default=["node-2", "node-3"], help="Peer node IDs")
    parser.add_argument("--storage-path", type=str, help="Storage path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    storage_path = args.storage_path or f"/var/lib/x0tta6bl4/raft/{args.node_id}"
    
    try:
        node = get_production_raft_node(
            node_id=args.node_id,
            peers=args.peers,
            storage_path=storage_path
        )
        
        status = node.get_status()
        
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            print("=" * 60)
            print("Raft Consensus Status")
            print("=" * 60)
            print(f"Node ID: {status['node_id']}")
            print(f"State: {format_state(status['state'])}")
            print(f"Term: {status['term']}")
            print(f"Commit Index: {status['commit_index']}")
            print(f"Last Applied: {status['last_applied']}")
            print(f"Log Length: {status['log_length']}")
            print(f"Peers: {', '.join(status['peers'])}")
            
            # Check storage
            storage = node.storage
            state_file = storage.state_file
            log_file = storage.log_file
            
            print("\n" + "=" * 60)
            print("Persistent Storage")
            print("=" * 60)
            print(f"State File: {state_file} ({'✅ EXISTS' if state_file.exists() else '❌ MISSING'})")
            print(f"Log File: {log_file} ({'✅ EXISTS' if log_file.exists() else '❌ MISSING'})")
            
            if state_file.exists():
                state = storage.load_state()
                if state:
                    print(f"Saved Term: {state.get('current_term', 'N/A')}")
                    print(f"Voted For: {state.get('voted_for', 'N/A')}")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

