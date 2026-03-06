#!/usr/bin/env python3
"""Swarm coordination runtime with file leases shared across all worktrees."""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


REPO_ROOT = Path(git_output("rev-parse", "--show-toplevel"))
GIT_COMMON_DIR_RAW = Path(git_output("rev-parse", "--git-common-dir"))
if GIT_COMMON_DIR_RAW.is_absolute():
    GIT_COMMON_DIR = GIT_COMMON_DIR_RAW
else:
    GIT_COMMON_DIR = (REPO_ROOT / GIT_COMMON_DIR_RAW).resolve()

SWARM_STATE_DIR = Path(
    os.environ.get("X0TTA6BL4_SWARM_STATE_DIR", str(GIT_COMMON_DIR / "swarm"))
).resolve()
SWARM_STATE_FILE = SWARM_STATE_DIR / "coordination_state.json"
SWARM_LOCK_FILE = SWARM_STATE_DIR / "coordination.lock"
OWNERSHIP_FILE = REPO_ROOT / "docs" / "team" / "swarm_ownership.json"
DEFAULT_ROADMAP_QUEUE_FILE = REPO_ROOT / "plans" / "ROADMAP_AGENT_QUEUE.json"
MAX_EVENTS = 500
MAX_REQUEST_NOTES = 200
ROADMAP_TASK_MODES = {"verification", "validation"}
REQUEST_NOTE_KINDS = {
    "start",
    "intent",
    "progress",
    "decision",
    "blocker",
    "handoff",
    "done",
    "alert",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def ensure_state_dir() -> None:
    SWARM_STATE_DIR.mkdir(parents=True, exist_ok=True)
    SWARM_LOCK_FILE.touch(exist_ok=True)


@contextmanager
def locked_state() -> dict[str, Any]:
    ensure_state_dir()
    with SWARM_LOCK_FILE.open("r+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        state = load_state()
        try:
            yield state
        finally:
            save_state(state)
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def load_ownership() -> dict[str, Any]:
    if not OWNERSHIP_FILE.exists():
        raise FileNotFoundError(f"ownership file is missing: {OWNERSHIP_FILE}")
    with OWNERSHIP_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_state() -> dict[str, Any]:
    if not SWARM_STATE_FILE.exists():
        return {
            "version": 1,
            "updated_at": isoformat_z(utcnow()),
            "agents": {},
            "leases": {},
            "events": [],
            "request_channel": {
                "active_request_id": None,
                "next_request_seq": 1,
                "items": {},
            },
            "roadmap_dispatch": {
                "version": 1,
                "queue_file": "",
                "synced_at": None,
                "synced_by": None,
                "derived_from": [],
                "agents": {},
                "tasks": [],
            },
        }
    with SWARM_STATE_FILE.open("r", encoding="utf-8") as fh:
        state = json.load(fh)
    state.setdefault("version", 1)
    state.setdefault("updated_at", isoformat_z(utcnow()))
    state.setdefault("agents", {})
    state.setdefault("leases", {})
    state.setdefault("events", [])
    request_channel = state.setdefault("request_channel", {})
    request_channel.setdefault("active_request_id", None)
    request_channel.setdefault("next_request_seq", 1)
    request_channel.setdefault("items", {})
    roadmap_dispatch = state.setdefault("roadmap_dispatch", {})
    roadmap_dispatch.setdefault("version", 1)
    roadmap_dispatch.setdefault("queue_file", "")
    roadmap_dispatch.setdefault("synced_at", None)
    roadmap_dispatch.setdefault("synced_by", None)
    roadmap_dispatch.setdefault("derived_from", [])
    roadmap_dispatch.setdefault("agents", {})
    roadmap_dispatch.setdefault("tasks", [])
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = isoformat_z(utcnow())
    tmp_file = SWARM_STATE_FILE.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=True, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_file, SWARM_STATE_FILE)


def ensure_request_agent(agent: str) -> None:
    if not agent:
        raise ValueError("request agent cannot be empty")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if any(ch not in allowed for ch in agent):
        raise ValueError(
            "request agent may only contain letters, digits, '-', '_' or '.'"
        )


def request_channel(state: dict[str, Any]) -> dict[str, Any]:
    channel = state.setdefault("request_channel", {})
    channel.setdefault("active_request_id", None)
    channel.setdefault("next_request_seq", 1)
    channel.setdefault("items", {})
    return channel


def roadmap_dispatch(state: dict[str, Any]) -> dict[str, Any]:
    dispatch = state.setdefault("roadmap_dispatch", {})
    dispatch.setdefault("version", 1)
    dispatch.setdefault("queue_file", "")
    dispatch.setdefault("synced_at", None)
    dispatch.setdefault("synced_by", None)
    dispatch.setdefault("derived_from", [])
    dispatch.setdefault("agents", {})
    dispatch.setdefault("tasks", [])
    return dispatch


def touch_agent_state(state: dict[str, Any], agent: str, now: datetime) -> None:
    agents_state = state.setdefault("agents", {})
    current = agents_state.get(agent, {})
    active_leases = len(
        [path for path, lease in state.setdefault("leases", {}).items() if lease.get("agent") == agent]
    )
    ttl_seconds = current.get("ttl_seconds", 0)
    agents_state[agent] = {
        "last_seen": isoformat_z(now),
        "ttl_seconds": ttl_seconds,
        "active_leases": active_leases,
    }


def allocate_request_id(channel: dict[str, Any]) -> str:
    items = channel.setdefault("items", {})
    seq = int(channel.get("next_request_seq", 1))
    while True:
        request_id = f"R{seq:04d}"
        if request_id not in items:
            channel["next_request_seq"] = seq + 1
            return request_id
        seq += 1


def active_request(channel: dict[str, Any]) -> dict[str, Any] | None:
    active_id = channel.get("active_request_id")
    if not active_id:
        return None
    request = channel.setdefault("items", {}).get(active_id)
    if request and request.get("status") == "open":
        return request
    return None


def resolve_request(
    state: dict[str, Any],
    request_id: str | None,
    *,
    require_open: bool,
) -> dict[str, Any]:
    channel = request_channel(state)
    resolved_id = request_id or channel.get("active_request_id")
    if not resolved_id:
        raise ValueError("no active request is open")
    request = channel.setdefault("items", {}).get(resolved_id)
    if not request:
        raise ValueError(f"request '{resolved_id}' not found")
    if require_open and request.get("status") != "open":
        raise ValueError(f"request '{resolved_id}' is not open")
    return request


def append_request_note(
    request: dict[str, Any],
    *,
    ts: str,
    agent: str,
    kind: str,
    message: str,
    files: list[str] | None = None,
    next_action: str = "",
) -> dict[str, Any]:
    note = {
        "ts": ts,
        "agent": agent,
        "kind": kind,
        "message": message,
    }
    if files:
        note["files"] = files
    if next_action:
        note["next"] = next_action

    notes = request.setdefault("notes", [])
    notes.append(note)
    if len(notes) > MAX_REQUEST_NOTES:
        del notes[: len(notes) - MAX_REQUEST_NOTES]
    return note


def request_summary(request: dict[str, Any], *, note_limit: int = 5) -> dict[str, Any]:
    payload = {
        "id": request.get("id"),
        "summary": request.get("summary"),
        "status": request.get("status"),
        "opened_at": request.get("opened_at"),
        "opened_by": request.get("opened_by"),
        "closed_at": request.get("closed_at"),
        "closed_by": request.get("closed_by"),
        "result": request.get("result"),
    }
    notes = request.get("notes", [])
    if note_limit > 0:
        payload["notes_tail"] = notes[-note_limit:]
    else:
        payload["notes_tail"] = []
    return payload


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def load_roadmap_queue(path: Path) -> dict[str, Any]:
    queue_path = path.resolve()
    if not queue_path.exists():
        raise FileNotFoundError(f"roadmap queue file is missing: {queue_path}")
    with queue_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    agents = payload.get("agents", {})
    if agents and not isinstance(agents, dict):
        raise ValueError(f"roadmap queue agents must be an object: {queue_path}")
    for agent_name, agent_meta in agents.items():
        ensure_request_agent(str(agent_name))
        if agent_meta is None:
            continue
        if not isinstance(agent_meta, dict):
            raise ValueError(f"roadmap queue agent '{agent_name}' must be an object")
        preferred_mode = str(agent_meta.get("preferred_mode", "")).strip()
        if preferred_mode and preferred_mode not in ROADMAP_TASK_MODES:
            raise ValueError(
                f"roadmap agent '{agent_name}' has invalid preferred_mode '{preferred_mode}'"
            )
        allowed_modes = agent_meta.get("allowed_modes", [])
        if allowed_modes:
            if not isinstance(allowed_modes, list):
                raise ValueError(
                    f"roadmap agent '{agent_name}' allowed_modes must be a list"
                )
            for mode in allowed_modes:
                mode_value = str(mode).strip()
                if mode_value not in ROADMAP_TASK_MODES:
                    raise ValueError(
                        f"roadmap agent '{agent_name}' has invalid allowed_mode '{mode_value}'"
                    )
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"roadmap queue file has no tasks: {queue_path}")
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("roadmap queue task entries must be objects")
        for field in (
            "id",
            "agent",
            "initiative",
            "status",
            "summary",
            "exact_next_command",
            "mode",
        ):
            if not str(task.get(field, "")).strip():
                raise ValueError(f"roadmap task is missing required field '{field}'")
        ensure_request_agent(str(task["agent"]))
        task_mode = str(task.get("mode", "")).strip()
        if task_mode not in ROADMAP_TASK_MODES:
            raise ValueError(f"roadmap task '{task['id']}' has invalid mode '{task_mode}'")
    return payload


def roadmap_tasks_for_agent(
    tasks: list[dict[str, Any]], agent: str, mode: str | None = None
) -> list[dict[str, Any]]:
    scoped = [task for task in tasks if task.get("agent") == agent]
    if mode:
        scoped = [task for task in scoped if str(task.get("mode", "")).strip() == mode]
    if not scoped:
        return []
    ready = [task for task in scoped if task.get("status") == "ready"]
    blocked = [task for task in scoped if task.get("status") == "blocked"]
    other = [task for task in scoped if task.get("status") not in {"ready", "blocked"}]
    return ready + blocked + other


def roadmap_summary_payload(dispatch: dict[str, Any]) -> dict[str, Any]:
    by_agent: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    for task in dispatch.get("tasks", []):
        agent = str(task.get("agent", "")).strip()
        if not agent:
            continue
        by_agent[agent] = by_agent.get(agent, 0) + 1
        mode = str(task.get("mode", "")).strip()
        if mode:
            by_mode[mode] = by_mode.get(mode, 0) + 1
    return {
        "queue_file": dispatch.get("queue_file", ""),
        "synced_at": dispatch.get("synced_at"),
        "synced_by": dispatch.get("synced_by"),
        "derived_from": dispatch.get("derived_from", []),
        "tasks_total": len(dispatch.get("tasks", [])),
        "tasks_by_agent": by_agent,
        "tasks_by_mode": by_mode,
        "agents": dispatch.get("agents", {}),
    }


def list_staged_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], text=True
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def match_rule(path: str, rule: str) -> bool:
    if any(ch in rule for ch in "*?["):
        return fnmatch.fnmatch(path, rule)
    if rule.endswith("/"):
        return path.startswith(rule)
    return path == rule


def is_allowed(path: str, rules: list[str]) -> bool:
    return any(match_rule(path, rule) for rule in rules)


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        norm = path.strip()
        if norm.startswith("./"):
            norm = norm[2:]
        if not norm or norm in seen:
            continue
        seen.add(norm)
        ordered.append(norm)
    return ordered


def purge_expired_leases(state: dict[str, Any], now: datetime) -> int:
    removed = 0
    leases = state.get("leases", {})
    expired_paths: list[str] = []
    for path, lease in leases.items():
        expires_at = parse_time(lease["expires_at"])
        if expires_at <= now:
            expired_paths.append(path)
    for path in expired_paths:
        del leases[path]
        removed += 1
    return removed


def add_event(
    state: dict[str, Any],
    *,
    action: str,
    agent: str,
    paths: list[str],
    note: str = "",
) -> None:
    events = state.setdefault("events", [])
    events.append(
        {
            "ts": isoformat_z(utcnow()),
            "action": action,
            "agent": agent,
            "paths": paths,
            "note": note,
        }
    )
    if len(events) > MAX_EVENTS:
        del events[: len(events) - MAX_EVENTS]


def ensure_agent(agent: str, ownership: dict[str, Any]) -> None:
    agents = ownership.get("agents", {})
    if agent not in agents:
        known = ", ".join(sorted(agents))
        raise ValueError(f"unknown agent '{agent}'. Known agents: {known}")


def allowed_rules(agent: str, ownership: dict[str, Any]) -> list[str]:
    return list(ownership.get("shared_allow", [])) + list(
        ownership.get("agents", {}).get(agent, {}).get("allow", [])
    )


def validate_scope(agent: str, paths: list[str], ownership: dict[str, Any]) -> list[str]:
    rules = allowed_rules(agent, ownership)
    return [path for path in paths if not is_allowed(path, rules)]


def owned_literal_paths(agent: str, ownership: dict[str, Any], include_shared: bool) -> list[str]:
    paths: list[str] = []
    if include_shared:
        paths.extend(ownership.get("shared_allow", []))
    paths.extend(ownership.get("agents", {}).get(agent, {}).get("allow", []))
    literal = [p for p in paths if not any(ch in p for ch in "*?[") and not p.endswith("/")]
    return unique_paths(literal)


def claim_paths(
    *,
    state: dict[str, Any],
    ownership: dict[str, Any],
    agent: str,
    paths: list[str],
    ttl_seconds: int,
    now: datetime,
    note: str,
) -> tuple[list[str], list[tuple[str, str, str]]]:
    denied = validate_scope(agent, paths, ownership)
    if denied:
        return denied, []

    leases = state.setdefault("leases", {})
    conflicts: list[tuple[str, str, str]] = []
    for path in paths:
        lease = leases.get(path)
        if not lease:
            continue
        if lease["agent"] == agent:
            continue
        if parse_time(lease["expires_at"]) > now:
            conflicts.append((path, lease["agent"], lease["expires_at"]))

    if conflicts:
        return [], conflicts

    expires_at = isoformat_z(now + timedelta(seconds=ttl_seconds))
    for path in paths:
        leases[path] = {
            "agent": agent,
            "claimed_at": isoformat_z(now),
            "expires_at": expires_at,
            "note": note,
        }

    agents_state = state.setdefault("agents", {})
    agents_state[agent] = {
        "last_seen": isoformat_z(now),
        "ttl_seconds": ttl_seconds,
        "active_leases": len([p for p, l in leases.items() if l.get("agent") == agent]),
    }
    add_event(state, action="claim", agent=agent, paths=paths, note=note)
    return [], []


def cmd_claim(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)

    paths = unique_paths(args.paths or [])
    if args.from_staged:
        paths.extend(unique_paths(list_staged_files()))
        paths = unique_paths(paths)
    if not paths:
        print("[swarm] no paths provided.")
        return 2

    now = utcnow()
    with locked_state() as state:
        purge_expired_leases(state, now)
        denied, conflicts = claim_paths(
            state=state,
            ownership=ownership,
            agent=args.agent,
            paths=paths,
            ttl_seconds=args.ttl,
            now=now,
            note=args.note or "manual-claim",
        )
        if denied:
            print(f"[swarm] scope violation for '{args.agent}':", file=sys.stderr)
            for path in denied:
                print(f"  - {path}", file=sys.stderr)
            return 1
        if conflicts:
            print("[swarm] claim conflicts:", file=sys.stderr)
            for path, owner, expires_at in conflicts:
                print(f"  - {path}: locked by {owner} until {expires_at}", file=sys.stderr)
            return 1

    print(f"[swarm] claimed {len(paths)} path(s) for '{args.agent}' (ttl={args.ttl}s).")
    return 0


def cmd_ensure_staged(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)
    staged = unique_paths(list_staged_files())
    if not staged:
        return 0

    now = utcnow()
    with locked_state() as state:
        purge_expired_leases(state, now)
        denied, conflicts = claim_paths(
            state=state,
            ownership=ownership,
            agent=args.agent,
            paths=staged,
            ttl_seconds=args.ttl,
            now=now,
            note="pre-commit-auto",
        )
        if denied:
            print(f"[swarm] scope violation for '{args.agent}' on staged files:", file=sys.stderr)
            for path in denied:
                print(f"  - {path}", file=sys.stderr)
            return 1
        if conflicts:
            print("[swarm] staged file lock conflicts:", file=sys.stderr)
            for path, owner, expires_at in conflicts:
                print(f"  - {path}: locked by {owner} until {expires_at}", file=sys.stderr)
            print("[swarm] wait for lease expiration or ask owner to release.", file=sys.stderr)
            return 1

    print(f"[swarm] staged files lease check passed for '{args.agent}' ({len(staged)} file(s)).")
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)
    now = utcnow()
    expires_at = isoformat_z(now + timedelta(seconds=args.ttl))

    with locked_state() as state:
        purge_expired_leases(state, now)
        leases = state.setdefault("leases", {})
        touched = 0
        for lease in leases.values():
            if lease.get("agent") == args.agent:
                lease["expires_at"] = expires_at
                touched += 1
        agents_state = state.setdefault("agents", {})
        agents_state[args.agent] = {
            "last_seen": isoformat_z(now),
            "ttl_seconds": args.ttl,
            "active_leases": touched,
        }
        add_event(state, action="heartbeat", agent=args.agent, paths=[], note=f"touched={touched}")

    print(f"[swarm] heartbeat for '{args.agent}': {touched} lease(s) extended.")
    return 0


def cmd_claim_owned(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)
    paths = owned_literal_paths(args.agent, ownership, include_shared=args.include_shared)
    if not paths:
        print(f"[swarm] no literal owned paths for '{args.agent}'.")
        return 2

    now = utcnow()
    with locked_state() as state:
        purge_expired_leases(state, now)
        denied, conflicts = claim_paths(
            state=state,
            ownership=ownership,
            agent=args.agent,
            paths=paths,
            ttl_seconds=args.ttl,
            now=now,
            note=args.note or "claim-owned",
        )
        if denied:
            print(f"[swarm] scope violation for '{args.agent}':", file=sys.stderr)
            for path in denied:
                print(f"  - {path}", file=sys.stderr)
            return 1
        if conflicts:
            print("[swarm] claim-owned conflicts:", file=sys.stderr)
            for path, owner, expires_at in conflicts:
                print(f"  - {path}: locked by {owner} until {expires_at}", file=sys.stderr)
            return 1

    print(f"[swarm] claim-owned acquired {len(paths)} path(s) for '{args.agent}'.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)

    if args.claim_owned:
        claim_args = argparse.Namespace(
            agent=args.agent,
            include_shared=args.include_shared,
            ttl=args.ttl,
            note="watch-start",
        )
        claim_rc = cmd_claim_owned(claim_args)
        if claim_rc != 0:
            return claim_rc

    print(
        f"[swarm] watch started for '{args.agent}' (ttl={args.ttl}s, interval={args.interval}s)."
    )
    try:
        while True:
            hb_args = argparse.Namespace(agent=args.agent, ttl=args.ttl)
            rc = cmd_heartbeat(hb_args)
            if rc != 0:
                return rc
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("[swarm] watch stopped by user.")
        return 0


def cmd_release(args: argparse.Namespace) -> int:
    ownership = load_ownership()
    ensure_agent(args.agent, ownership)
    paths = unique_paths(args.paths or [])

    with locked_state() as state:
        now = utcnow()
        purge_expired_leases(state, now)
        leases = state.setdefault("leases", {})
        removed: list[str] = []

        if paths:
            for path in paths:
                lease = leases.get(path)
                if lease and lease.get("agent") == args.agent:
                    del leases[path]
                    removed.append(path)
        else:
            for path in list(leases):
                if leases[path].get("agent") == args.agent:
                    del leases[path]
                    removed.append(path)

        agents_state = state.setdefault("agents", {})
        agents_state[args.agent] = {
            "last_seen": isoformat_z(now),
            "ttl_seconds": args.ttl,
            "active_leases": len([p for p, l in leases.items() if l.get("agent") == args.agent]),
        }
        add_event(state, action="release", agent=args.agent, paths=removed, note="manual-release")

    print(f"[swarm] released {len(removed)} path(s) for '{args.agent}'.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    with locked_state() as state:
        now = utcnow()
        purged = purge_expired_leases(state, now)
        leases = state.get("leases", {})
        agents = state.get("agents", {})
        channel = request_channel(state)
        current_request = active_request(channel)
        dispatch = roadmap_dispatch(state)
        payload = {
            "updated_at": state.get("updated_at"),
            "purged_expired": purged,
            "active_leases": len(leases),
            "agents": agents,
            "leases": leases,
            "events_tail": state.get("events", [])[-20:],
            "request_channel": {
                "active_request_id": channel.get("active_request_id"),
                "open_requests": len(
                    [
                        item
                        for item in channel.get("items", {}).values()
                        if item.get("status") == "open"
                    ]
                ),
                "active_request": request_summary(current_request, note_limit=3)
                if current_request
                else None,
            },
            "roadmap_dispatch": roadmap_summary_payload(dispatch),
        }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(f"[swarm] active leases: {payload['active_leases']} (purged {purged} expired)")
    for path, lease in sorted(leases.items()):
        print(
            f"  - {path} :: {lease['agent']} until {lease['expires_at']}"
            + (f" [{lease.get('note')}]" if lease.get("note") else "")
        )
    if not leases:
        print("  (none)")
    request_info = payload["request_channel"]
    if request_info["active_request"]:
        current = request_info["active_request"]
        print(
            f"[swarm] active request: {current['id']} "
            f"({current['summary']}) [{current['status']}]"
        )
    else:
        print("[swarm] active request: (none)")
    roadmap_info = payload["roadmap_dispatch"]
    if roadmap_info["synced_at"]:
        print(
            f"[swarm] roadmap sync: {roadmap_info['synced_at']} by "
            f"{roadmap_info['synced_by']} ({roadmap_info['tasks_total']} task(s))"
        )
    else:
        print("[swarm] roadmap sync: (none)")
    return 0


def cmd_cleanup(_: argparse.Namespace) -> int:
    with locked_state() as state:
        removed = purge_expired_leases(state, utcnow())
        add_event(state, action="cleanup", agent="system", paths=[], note=f"removed={removed}")
    print(f"[swarm] cleanup removed {removed} expired lease(s).")
    return 0


def cmd_open_request(args: argparse.Namespace) -> int:
    ensure_request_agent(args.agent)
    summary = args.summary.strip()
    if not summary:
        print("[swarm] request summary cannot be empty", file=sys.stderr)
        return 2

    now = utcnow()
    with locked_state() as state:
        purge_expired_leases(state, now)
        channel = request_channel(state)
        existing = active_request(channel)
        if existing:
            if args.reuse_if_open:
                touch_agent_state(state, args.agent, now)
                payload = request_summary(existing, note_limit=args.note_tail)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
                else:
                    print(
                        f"[swarm] active request already open: {existing['id']} "
                        f"({existing['summary']})"
                    )
                return 0
            print(
                f"[swarm] request '{existing['id']}' is already open; "
                "close it or use --reuse-if-open",
                file=sys.stderr,
            )
            return 1

        request_id = args.request_id or allocate_request_id(channel)
        if request_id in channel["items"]:
            print(f"[swarm] request '{request_id}' already exists", file=sys.stderr)
            return 1

        request = {
            "id": request_id,
            "summary": summary,
            "status": "open",
            "opened_at": isoformat_z(now),
            "opened_by": args.agent,
            "notes": [],
        }
        append_request_note(
            request,
            ts=isoformat_z(now),
            agent=args.agent,
            kind="start",
            message=summary,
            next_action=args.next,
        )
        channel["items"][request_id] = request
        channel["active_request_id"] = request_id
        touch_agent_state(state, args.agent, now)
        add_event(state, action="open-request", agent=args.agent, paths=[], note=request_id)
        payload = request_summary(request, note_limit=args.note_tail)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"[swarm] opened request '{payload['id']}': {payload['summary']}")
    return 0


def cmd_show_request(args: argparse.Namespace) -> int:
    with locked_state() as state:
        request = resolve_request(state, args.request_id, require_open=args.open_only)
        payload = request_summary(request, note_limit=args.note_tail)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(f"[swarm] request {payload['id']} [{payload['status']}]")
    print(f"  summary: {payload['summary']}")
    print(f"  opened_by: {payload['opened_by']} at {payload['opened_at']}")
    if payload.get("closed_at"):
        print(f"  closed_by: {payload.get('closed_by')} at {payload['closed_at']}")
    if payload.get("result"):
        print(f"  result: {payload['result']}")
    return 0


def cmd_post_note(args: argparse.Namespace) -> int:
    ensure_request_agent(args.agent)
    kind = args.kind.strip().lower()
    if kind not in REQUEST_NOTE_KINDS:
        print(
            "[swarm] invalid note kind. Allowed: " + ", ".join(sorted(REQUEST_NOTE_KINDS)),
            file=sys.stderr,
        )
        return 2

    message = args.message.strip()
    if not message:
        print("[swarm] note message cannot be empty", file=sys.stderr)
        return 2

    files = unique_paths(args.files or [])
    now = utcnow()
    with locked_state() as state:
        request = resolve_request(state, args.request_id, require_open=True)
        note = append_request_note(
            request,
            ts=isoformat_z(now),
            agent=args.agent,
            kind=kind,
            message=message,
            files=files,
            next_action=args.next,
        )
        touch_agent_state(state, args.agent, now)
        add_event(
            state,
            action=f"request-note:{kind}",
            agent=args.agent,
            paths=files,
            note=request["id"],
        )

    if args.json:
        print(json.dumps(note, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"[swarm] note posted to {request['id']} [{kind}]")
    return 0


def cmd_tail_notes(args: argparse.Namespace) -> int:
    with locked_state() as state:
        request = resolve_request(state, args.request_id, require_open=False)
        notes = request.get("notes", [])[-args.limit :]
        payload = {
            "request": request_summary(request, note_limit=0),
            "notes": notes,
        }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(f"[swarm] notes for {payload['request']['id']} [{payload['request']['status']}]")
    if not notes:
        print("  (no notes)")
        return 0
    for note in notes:
        files = f" files={','.join(note['files'])}" if note.get("files") else ""
        next_action = f" next={note['next']}" if note.get("next") else ""
        print(
            f"  - {note['ts']} {note['agent']} [{note['kind']}] "
            f"{note['message']}{files}{next_action}"
        )
    return 0


def cmd_close_request(args: argparse.Namespace) -> int:
    ensure_request_agent(args.agent)
    result = args.result.strip()
    if not result:
        print("[swarm] close result cannot be empty", file=sys.stderr)
        return 2

    now = utcnow()
    with locked_state() as state:
        request = resolve_request(state, args.request_id, require_open=True)
        append_request_note(
            request,
            ts=isoformat_z(now),
            agent=args.agent,
            kind="done",
            message=result,
            next_action=args.next,
        )
        request["status"] = "closed"
        request["closed_at"] = isoformat_z(now)
        request["closed_by"] = args.agent
        request["result"] = result
        channel = request_channel(state)
        if channel.get("active_request_id") == request.get("id"):
            channel["active_request_id"] = None
        touch_agent_state(state, args.agent, now)
        add_event(state, action="close-request", agent=args.agent, paths=[], note=request["id"])
        payload = request_summary(request, note_limit=args.note_tail)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"[swarm] closed request '{payload['id']}' with result: {payload['result']}")
    return 0


def cmd_roadmap_sync(args: argparse.Namespace) -> int:
    ensure_request_agent(args.agent)
    queue_path = Path(args.queue_file or DEFAULT_ROADMAP_QUEUE_FILE)
    payload = load_roadmap_queue(queue_path)
    now = utcnow()

    with locked_state() as state:
        purge_expired_leases(state, now)
        dispatch = roadmap_dispatch(state)
        dispatch["queue_file"] = repo_relative(queue_path)
        dispatch["synced_at"] = isoformat_z(now)
        dispatch["synced_by"] = args.agent
        dispatch["derived_from"] = list(payload.get("derived_from", []))
        dispatch["agents"] = dict(payload.get("agents", {}))
        dispatch["tasks"] = list(payload.get("tasks", []))
        touch_agent_state(state, args.agent, now)
        add_event(
            state,
            action="roadmap-sync",
            agent=args.agent,
            paths=[repo_relative(queue_path)],
            note=f"tasks={len(dispatch['tasks'])}",
        )
        if args.post_note:
            request = active_request(request_channel(state))
            if request:
                summary_parts = []
                for agent in sorted(dispatch.get("agents", {})):
                    next_tasks = roadmap_tasks_for_agent(dispatch.get("tasks", []), agent)
                    if next_tasks:
                        summary_parts.append(
                            f"{agent}={next_tasks[0]['id']}@{next_tasks[0].get('mode', '?')}"
                        )
                append_request_note(
                    request,
                    ts=isoformat_z(now),
                    agent=args.agent,
                    kind="decision",
                    message="roadmap sync: " + ", ".join(summary_parts or ["no tasks"]),
                    files=[repo_relative(queue_path)],
                )

        summary = roadmap_summary_payload(dispatch)

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(
        f"[swarm] roadmap synced from {summary['queue_file']} by {summary['synced_by']} "
        f"({summary['tasks_total']} task(s))"
    )
    return 0


def cmd_roadmap_next(args: argparse.Namespace) -> int:
    ensure_request_agent(args.agent)

    with locked_state() as state:
        dispatch = roadmap_dispatch(state)
        queue_file = dispatch.get("queue_file", "") or repo_relative(DEFAULT_ROADMAP_QUEUE_FILE)
        synced_at = dispatch.get("synced_at")
        synced_by = dispatch.get("synced_by")
    queue_path = REPO_ROOT / queue_file if not Path(queue_file).is_absolute() else Path(queue_file)
    try:
        payload = load_roadmap_queue(queue_path)
        tasks = list(payload.get("tasks", []))
        agents_meta = dict(payload.get("agents", {}))
        queue_file = repo_relative(queue_path)
    except Exception:
        tasks = list(dispatch.get("tasks", []))
        agents_meta = dict(dispatch.get("agents", {}))
        if not tasks:
            payload = load_roadmap_queue(DEFAULT_ROADMAP_QUEUE_FILE)
            tasks = list(payload.get("tasks", []))
            agents_meta = dict(payload.get("agents", {}))
            queue_file = repo_relative(DEFAULT_ROADMAP_QUEUE_FILE)
            synced_at = None
            synced_by = None

    requested_mode = (args.mode or "").strip()
    preferred_mode = str(agents_meta.get(args.agent, {}).get("preferred_mode", "")).strip()
    effective_mode = requested_mode or preferred_mode or None
    if effective_mode and effective_mode not in ROADMAP_TASK_MODES:
        print(f"[swarm] invalid roadmap mode '{effective_mode}'", file=sys.stderr)
        return 2

    next_tasks = roadmap_tasks_for_agent(tasks, args.agent, effective_mode)[: args.limit]
    result = {
        "agent": args.agent,
        "mode": effective_mode,
        "queue_file": queue_file,
        "synced_at": synced_at,
        "synced_by": synced_by,
        "preferred_mode": preferred_mode or None,
        "tasks": next_tasks,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    suffix = f" mode={effective_mode}" if effective_mode else ""
    if not next_tasks:
        print(f"[swarm] roadmap next for {args.agent}{suffix}: (none)")
        return 0

    print(f"[swarm] roadmap next for {args.agent}{suffix}:")
    for task in next_tasks:
        blocker = f" blocker={task['blocker']}" if task.get("blocker") else ""
        print(
            f"  - {task['id']} [{task['status']}|{task.get('mode', '?')}] {task['summary']}"
            f" next={task['exact_next_command']}{blocker}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swarm coordination utility")
    sub = parser.add_subparsers(dest="command", required=True)

    claim = sub.add_parser("claim", help="Claim path leases for an agent")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--paths", nargs="*", default=[])
    claim.add_argument("--from-staged", action="store_true")
    claim.add_argument("--ttl", type=int, default=1800)
    claim.add_argument("--note", default="")
    claim.set_defaults(func=cmd_claim)

    ensure = sub.add_parser("ensure-staged", help="Ensure staged paths are leased by agent")
    ensure.add_argument("--agent", required=True)
    ensure.add_argument("--ttl", type=int, default=1800)
    ensure.set_defaults(func=cmd_ensure_staged)

    heartbeat = sub.add_parser("heartbeat", help="Extend existing leases for an agent")
    heartbeat.add_argument("--agent", required=True)
    heartbeat.add_argument("--ttl", type=int, default=1800)
    heartbeat.set_defaults(func=cmd_heartbeat)

    claim_owned = sub.add_parser("claim-owned", help="Claim all literal owned paths")
    claim_owned.add_argument("--agent", required=True)
    claim_owned.add_argument("--ttl", type=int, default=1800)
    claim_owned.add_argument("--note", default="")
    claim_owned.add_argument("--include-shared", action="store_true")
    claim_owned.set_defaults(func=cmd_claim_owned)

    release = sub.add_parser("release", help="Release path leases")
    release.add_argument("--agent", required=True)
    release.add_argument("--paths", nargs="*", default=[])
    release.add_argument("--ttl", type=int, default=1800)
    release.set_defaults(func=cmd_release)

    status = sub.add_parser("status", help="Print lease status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    open_request = sub.add_parser(
        "open-request",
        help="Open a request-scoped coordination thread in shared swarm state",
    )
    open_request.add_argument("--agent", required=True)
    open_request.add_argument("--summary", required=True)
    open_request.add_argument("--request-id", default="")
    open_request.add_argument("--next", default="")
    open_request.add_argument("--note-tail", type=int, default=3)
    open_request.add_argument("--reuse-if-open", action=argparse.BooleanOptionalAction, default=True)
    open_request.add_argument("--json", action="store_true")
    open_request.set_defaults(func=cmd_open_request)

    show_request = sub.add_parser("show-request", help="Show the active or selected request")
    show_request.add_argument("--request-id", default="")
    show_request.add_argument("--note-tail", type=int, default=5)
    show_request.add_argument("--open-only", action="store_true")
    show_request.add_argument("--json", action="store_true")
    show_request.set_defaults(func=cmd_show_request)

    post_note = sub.add_parser("post-note", help="Append a request note")
    post_note.add_argument("--agent", required=True)
    post_note.add_argument("--request-id", default="")
    post_note.add_argument("--kind", required=True)
    post_note.add_argument("--message", required=True)
    post_note.add_argument("--files", nargs="*", default=[])
    post_note.add_argument("--next", default="")
    post_note.add_argument("--json", action="store_true")
    post_note.set_defaults(func=cmd_post_note)

    tail_notes = sub.add_parser("tail-notes", help="Show recent notes for a request")
    tail_notes.add_argument("--request-id", default="")
    tail_notes.add_argument("--limit", type=int, default=10)
    tail_notes.add_argument("--json", action="store_true")
    tail_notes.set_defaults(func=cmd_tail_notes)

    close_request = sub.add_parser("close-request", help="Close the active or selected request")
    close_request.add_argument("--agent", required=True)
    close_request.add_argument("--request-id", default="")
    close_request.add_argument("--result", required=True)
    close_request.add_argument("--next", default="")
    close_request.add_argument("--note-tail", type=int, default=5)
    close_request.add_argument("--json", action="store_true")
    close_request.set_defaults(func=cmd_close_request)

    roadmap_sync = sub.add_parser(
        "roadmap-sync",
        help="Sync the machine-readable roadmap queue into shared swarm state",
    )
    roadmap_sync.add_argument("--agent", required=True)
    roadmap_sync.add_argument("--queue-file", default=str(DEFAULT_ROADMAP_QUEUE_FILE))
    roadmap_sync.add_argument("--post-note", action="store_true")
    roadmap_sync.add_argument("--json", action="store_true")
    roadmap_sync.set_defaults(func=cmd_roadmap_sync)

    roadmap_next = sub.add_parser(
        "roadmap-next",
        help="Show the next roadmap-derived task(s) for an agent",
    )
    roadmap_next.add_argument("--agent", required=True)
    roadmap_next.add_argument("--limit", type=int, default=3)
    roadmap_next.add_argument("--mode", choices=sorted(ROADMAP_TASK_MODES))
    roadmap_next.add_argument("--json", action="store_true")
    roadmap_next.set_defaults(func=cmd_roadmap_next)

    cleanup = sub.add_parser("cleanup", help="Remove expired leases")
    cleanup.set_defaults(func=cmd_cleanup)

    watch = sub.add_parser("watch", help="Heartbeat loop for long-running sessions")
    watch.add_argument("--agent", required=True)
    watch.add_argument("--ttl", type=int, default=1800)
    watch.add_argument("--interval", type=int, default=300)
    watch.add_argument("--claim-owned", action="store_true")
    watch.add_argument("--include-shared", action="store_true")
    watch.set_defaults(func=cmd_watch)

    return parser


def main() -> int:
    try:
        parser = build_parser()
        args = parser.parse_args()
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"[swarm] {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[swarm] {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"[swarm] git command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
