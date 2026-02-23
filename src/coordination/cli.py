#!/usr/bin/env python3
"""
Agent Coordination CLI

Command-line interface for managing agent coordination.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .state import AgentCoordinator, AgentRole, AgentStatus
from .events import EventBus, EventType, get_event_bus
from .tasks import TaskQueue, TaskStatus, TaskPriority, TaskType, get_task_queue
from .conflicts import ConflictDetector, ConflictSeverity


def cmd_register(args):
    """Register a new agent."""
    coordinator = AgentCoordinator(args.project_root)
    
    role = AgentRole(args.role)
    state = coordinator.register_agent(
        agent_id=args.agent_id,
        role=role,
        metadata={"description": args.description} if args.description else None
    )
    
    print(f"✅ Registered agent: {args.agent_id}")
    print(f"   Role: {role.value}")
    print(f"   Status: {state.status.value}")
    
    return 0


def cmd_unregister(args):
    """Unregister an agent."""
    coordinator = AgentCoordinator(args.project_root)
    
    coordinator.unregister_agent(args.agent_id)
    print(f"✅ Unregistered agent: {args.agent_id}")
    
    return 0


def cmd_status(args):
    """Show coordination status."""
    coordinator = AgentCoordinator(args.project_root)
    
    print("\n📊 Agent Coordination Status")
    print("=" * 50)
    
    # Show agents
    agents = coordinator.get_all_agents()
    if agents:
        print(f"\n🤖 Registered Agents ({len(agents)}):")
        for agent in agents:
            status_emoji = {
                "idle": "⚪",
                "working": "🟢",
                "waiting": "🟡",
                "blocked": "🔴",
                "offline": "⚫",
            }.get(agent.status.value, "❓")
            
            print(f"  {status_emoji} {agent.agent_id} ({agent.role.value})")
            if agent.current_task:
                print(f"      Task: {agent.current_task}")
            if agent.locked_files:
                print(f"      Locks: {', '.join(agent.locked_files)}")
    else:
        print("\n🤖 No registered agents")
    
    # Show locks
    if coordinator.locks:
        print(f"\n🔒 Active Locks ({len(coordinator.locks)}):")
        for path, lock in coordinator.locks.items():
            print(f"  📄 {path}")
            print(f"      Agent: {lock.agent_id}")
            print(f"      Since: {lock.acquired_at.strftime('%H:%M:%S')}")
    else:
        print("\n🔒 No active locks")
    
    # Show conflicts
    conflicts = coordinator.find_conflicts()
    if conflicts:
        print(f"\n⚠️  Potential Conflicts ({len(conflicts)}):")
        for conflict in conflicts:
            print(f"  - {conflict['type']}: {conflict.get('path', 'N/A')}")
            print(f"    Agents: {', '.join(conflict['agents'])}")
    
    return 0


def cmd_lock(args):
    """Acquire or release a lock."""
    coordinator = AgentCoordinator(args.project_root)
    
    if args.release:
        if coordinator.release_lock(args.agent_id, args.path):
            print(f"✅ Released lock on {args.path}")
            return 0
        else:
            print(f"❌ Failed to release lock on {args.path}")
            return 1
    else:
        if coordinator.acquire_lock(args.agent_id, args.path):
            print(f"✅ Acquired lock on {args.path}")
            return 0
        else:
            print(f"❌ Failed to acquire lock on {args.path}")
            lock_info = coordinator.get_lock_info(args.path)
            if lock_info:
                print(f"   Already locked by: {lock_info.agent_id}")
            return 1


def cmd_heartbeat(args):
    """Send a heartbeat for an agent."""
    coordinator = AgentCoordinator(args.project_root)
    
    if coordinator.heartbeat(args.agent_id):
        print(f"✅ Heartbeat received from {args.agent_id}")
        return 0
    else:
        print(f"❌ Unknown agent: {args.agent_id}")
        return 1


def cmd_tasks(args):
    """Manage tasks."""
    queue = TaskQueue(args.project_root)
    
    if args.list:
        print("\n📋 Task Queue")
        print("=" * 50)
        
        stats = queue.get_stats()
        print(f"\nTotal: {stats['total']}")
        for status, count in stats['by_status'].items():
            if count > 0:
                print(f"  {status}: {count}")
        
        if stats['overdue'] > 0:
            print(f"\n⚠️  Overdue: {stats['overdue']}")
        
        if stats['blocked'] > 0:
            print(f"\n🚫 Blocked: {stats['blocked']}")
        
        # Show ready tasks
        ready = queue.get_ready_tasks()
        if ready:
            print(f"\n✅ Ready Tasks ({len(ready)}):")
            for task in ready[:10]:  # Show first 10
                print(f"  [{task.task_id}] {task.title}")
                print(f"      Priority: {task.priority.name}")
                if task.assigned_role:
                    print(f"      Role: {task.assigned_role}")
        
        return 0
    
    elif args.create:
        task = queue.add_task(
            task_type=TaskType(args.type),
            title=args.title,
            description=args.description or "",
            priority=TaskPriority[args.priority.upper()],
            assigned_role=args.role,
        )
        print(f"✅ Created task: {task.task_id}")
        print(f"   Title: {task.title}")
        print(f"   Priority: {task.priority.name}")
        return 0
    
    elif args.assign:
        if queue.assign_task(args.task_id, args.agent_id):
            print(f"✅ Assigned task {args.task_id} to {args.agent_id}")
            return 0
        else:
            print(f"❌ Failed to assign task {args.task_id}")
            return 1
    
    elif args.complete:
        if queue.complete_task(args.task_id, args.result or "Completed"):
            print(f"✅ Completed task: {args.task_id}")
            return 0
        else:
            print(f"❌ Failed to complete task {args.task_id}")
            return 1
    
    elif args.pipeline:
        tasks = queue.create_pipeline(
            title=args.title,
            description=args.description or "",
            files=set(args.files.split(",")) if args.files else set(),
            priority=TaskPriority[args.priority.upper()],
        )
        print(f"✅ Created pipeline with {len(tasks)} tasks:")
        for task in tasks:
            print(f"   [{task.task_id}] {task.title} → {task.assigned_role or 'any'}")
        return 0
    
    else:
        print("Use --list, --create, --assign, --complete, or --pipeline")
        return 1


def cmd_events(args):
    """View events."""
    bus = EventBus(args.project_root)
    
    events = bus.get_event_history(limit=args.limit)
    
    print(f"\n📜 Event History ({len(events)} events)")
    print("=" * 50)
    
    for event in events:
        timestamp = event.timestamp.strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {event.event_type.value}")
        print(f"  Source: {event.source_agent}")
        if event.target_agents:
            print(f"  Targets: {', '.join(event.target_agents)}")
        if event.data:
            print(f"  Data: {json.dumps(event.data, indent=4)[:200]}")
    
    return 0


def cmd_conflicts(args):
    """Manage conflicts."""
    coordinator = AgentCoordinator(args.project_root)
    detector = ConflictDetector(coordinator, args.project_root)
    
    if args.detect:
        conflicts = detector.detect_conflicts()
        print(f"\n🔍 Detected {len(conflicts)} conflicts")
        
        for conflict in conflicts:
            severity_emoji = {
                "low": "🟡",
                "medium": "🟠",
                "high": "🔴",
                "critical": "💀",
            }.get(conflict.severity.value, "❓")
            
            print(f"\n{severity_emoji} [{conflict.conflict_id}]")
            print(f"   Type: {conflict.conflict_type.value}")
            print(f"   Agents: {', '.join(conflict.agents)}")
            if conflict.path:
                print(f"   Path: {conflict.path}")
            print(f"   Description: {conflict.description}")
        
        return 0
    
    elif args.resolve:
        conflicts = detector.get_active_conflicts()
        if not conflicts:
            print("✅ No active conflicts to resolve")
            return 0
        
        resolutions = detector.auto_resolve()
        print(f"\n🔧 Resolved {len(resolutions)} conflicts")
        
        for resolution in resolutions:
            print(f"\n  [{resolution.conflict_id}]")
            print(f"   Strategy: {resolution.strategy.value}")
            if resolution.winner:
                print(f"   Winner: {resolution.winner}")
            print(f"   Message: {resolution.message}")
        
        return 0
    
    else:
        conflicts = detector.get_active_conflicts()
        print(f"\n⚠️  Active Conflicts ({len(conflicts)})")
        print("=" * 50)
        
        for conflict in conflicts:
            print(f"\n  [{conflict.conflict_id}] {conflict.conflict_type.value}")
            print(f"   Severity: {conflict.severity.value}")
            print(f"   Agents: {', '.join(conflict.agents)}")
        
        return 0


def cmd_next(args):
    """Get next task for an agent."""
    coordinator = AgentCoordinator(args.project_root)
    queue = TaskQueue(args.project_root)
    
    state = coordinator.get_agent_state(args.agent_id)
    if not state:
        print(f"❌ Agent not registered: {args.agent_id}")
        return 1
    
    tasks = queue.get_tasks_for_agent(args.agent_id, state.role.value)
    
    if tasks:
        task = tasks[0]
        print(f"\n📋 Next Task for {args.agent_id}")
        print("=" * 50)
        print(f"  ID: {task.task_id}")
        print(f"  Title: {task.title}")
        print(f"  Type: {task.task_type.value}")
        print(f"  Priority: {task.priority.name}")
        if task.target_files:
            print(f"  Files: {', '.join(task.target_files)}")
        print(f"\n  Description:")
        print(f"  {task.description[:200]}")
    else:
        print(f"\n✅ No tasks available for {args.agent_id}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Agent Coordination CLI for MaaS x0tta6bl4"
    )
    parser.add_argument(
        "--project-root", "-p",
        default=".",
        help="Project root directory"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new agent")
    register_parser.add_argument("agent_id", help="Unique agent ID")
    register_parser.add_argument("role", choices=["gemini", "codex", "claude", "glm5", "human"], help="Agent role")
    register_parser.add_argument("--description", "-d", help="Agent description")
    register_parser.set_defaults(func=cmd_register)
    
    # Unregister command
    unregister_parser = subparsers.add_parser("unregister", help="Unregister an agent")
    unregister_parser.add_argument("agent_id", help="Agent ID to unregister")
    unregister_parser.set_defaults(func=cmd_unregister)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show coordination status")
    status_parser.set_defaults(func=cmd_status)
    
    # Lock command
    lock_parser = subparsers.add_parser("lock", help="Acquire or release a lock")
    lock_parser.add_argument("agent_id", help="Agent ID")
    lock_parser.add_argument("path", help="File path to lock")
    lock_parser.add_argument("--release", "-r", action="store_true", help="Release the lock")
    lock_parser.set_defaults(func=cmd_lock)
    
    # Heartbeat command
    heartbeat_parser = subparsers.add_parser("heartbeat", help="Send agent heartbeat")
    heartbeat_parser.add_argument("agent_id", help="Agent ID")
    heartbeat_parser.set_defaults(func=cmd_heartbeat)
    
    # Tasks command
    tasks_parser = subparsers.add_parser("tasks", help="Manage tasks")
    tasks_parser.add_argument("--list", "-l", action="store_true", help="List tasks")
    tasks_parser.add_argument("--create", "-c", action="store_true", help="Create a task")
    tasks_parser.add_argument("--assign", "-a", action="store_true", help="Assign a task")
    tasks_parser.add_argument("--complete", action="store_true", help="Complete a task")
    tasks_parser.add_argument("--pipeline", action="store_true", help="Create a pipeline")
    tasks_parser.add_argument("--task-id", "-t", help="Task ID")
    tasks_parser.add_argument("--title", help="Task title")
    tasks_parser.add_argument("--description", "-d", help="Task description")
    tasks_parser.add_argument("--type", choices=[t.value for t in TaskType], help="Task type")
    tasks_parser.add_argument("--priority", "-p", choices=["critical", "high", "medium", "low", "background"], default="medium")
    tasks_parser.add_argument("--role", help="Assigned role")
    tasks_parser.add_argument("--agent-id", help="Agent ID for assignment")
    tasks_parser.add_argument("--result", help="Task result")
    tasks_parser.add_argument("--files", help="Comma-separated target files")
    tasks_parser.set_defaults(func=cmd_tasks)
    
    # Events command
    events_parser = subparsers.add_parser("events", help="View events")
    events_parser.add_argument("--limit", "-l", type=int, default=20, help="Number of events")
    events_parser.set_defaults(func=cmd_events)
    
    # Conflicts command
    conflicts_parser = subparsers.add_parser("conflicts", help="Manage conflicts")
    conflicts_parser.add_argument("--detect", "-d", action="store_true", help="Detect conflicts")
    conflicts_parser.add_argument("--resolve", "-r", action="store_true", help="Auto-resolve conflicts")
    conflicts_parser.set_defaults(func=cmd_conflicts)
    
    # Next command
    next_parser = subparsers.add_parser("next", help="Get next task for agent")
    next_parser.add_argument("agent_id", help="Agent ID")
    next_parser.set_defaults(func=cmd_next)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
