#!/usr/bin/env python3
"""
Swarm Coordinator (SCP)
=======================
Automates coordination between multiple AI agents.
Enforces file locking and task tracking to prevent conflicts.

Usage:
    python3 swarm.py start <task_name> --agent <agent_name> --files <file1> <file2>
    python3 swarm.py finish --agent <agent_name>
    python3 swarm.py status
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SWARM_DIR = Path(".swarm")
LOCKS_FILE = SWARM_DIR / "locks.json"
TASKS_FILE = SWARM_DIR / "active_tasks.json"

def load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def cmd_start(args):
    locks = load_json(LOCKS_FILE)
    tasks = load_json(TASKS_FILE)
    
    # 1. Check for conflicts
    conflicts = []
    for f in args.files:
        if f in locks:
            lock_info = locks[f]
            # Locks expire after 2 hours just in case
            lock_time = datetime.fromisoformat(lock_info['timestamp'])
            if (datetime.now() - lock_time).total_seconds() < 7200:
                conflicts.append(f"{f} (locked by {lock_info['agent']} since {lock_info['timestamp']})")
            else:
                print(f"Warning: Breaking stale lock on {f}")

    if conflicts:
        print("❌ CONFLICT DETECTED! The following files are busy:")
        for c in conflicts:
            print(f"  - {c}")
        print("ABORTING. Please pick a different task or wait.")
        sys.exit(1)

    # 2. Acquire locks
    timestamp = datetime.now().isoformat()
    for f in args.files:
        locks[f] = {
            "agent": args.agent,
            "task": args.task,
            "timestamp": timestamp
        }
    
    # 3. Register task
    tasks[args.agent] = {
        "task": args.task,
        "files": args.files,
        "start_time": timestamp,
        "status": "in_progress"
    }

    save_json(LOCKS_FILE, locks)
    save_json(TASKS_FILE, tasks)
    
    print(f"✅ Task '{args.task}' started for {args.agent}.")
    print(f"🔒 Locked {len(args.files)} files.")
    
    # Optional: Git branching automation could go here
    # os.system(f"git checkout -b feature/{args.agent}-{int(time.time())}")

def cmd_finish(args):
    locks = load_json(LOCKS_FILE)
    tasks = load_json(TASKS_FILE)
    
    if args.agent not in tasks:
        print(f"⚠️ No active task found for {args.agent}")
        return

    task_info = tasks[args.agent]
    files_to_unlock = task_info.get('files', [])
    
    # 1. Release locks
    unlocked_count = 0
    for f in files_to_unlock:
        if f in locks and locks[f]['agent'] == args.agent:
            del locks[f]
            unlocked_count += 1
            
    # 2. Archive task (or just remove)
    del tasks[args.agent]
    
    save_json(LOCKS_FILE, locks)
    save_json(TASKS_FILE, tasks)
    
    print(f"✅ Task finished for {args.agent}.")
    print(f"🔓 Released {unlocked_count} locks.")

def cmd_status(args):
    tasks = load_json(TASKS_FILE)
    locks = load_json(LOCKS_FILE)
    
    print("\n🐝 SWARM STATUS")
    print("===============")
    
    if not tasks:
        print("No active agents.")
    else:
        for agent, info in tasks.items():
            print(f"🤖 {agent}: {info['task']}")
            print(f"   Files: {', '.join(info['files'])}")
            print(f"   Started: {info['start_time']}")
            print("---")
            
    print(f"\n🔒 Active File Locks: {len(locks)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swarm Coordinator")
    subparsers = parser.add_subparsers()

    # Start
    p_start = subparsers.add_parser('start')
    p_start.add_argument('task', help="Task name")
    p_start.add_argument('--agent', required=True, help="Agent name (Gemini, Codex, etc)")
    p_start.add_argument('--files', nargs='+', required=True, help="List of files to lock")
    p_start.set_defaults(func=cmd_start)

    # Finish
    p_finish = subparsers.add_parser('finish')
    p_finish.add_argument('--agent', required=True, help="Agent name")
    p_finish.set_defaults(func=cmd_finish)

    # Status
    p_status = subparsers.add_parser('status')
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
