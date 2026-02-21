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

SWARM_STATE_DIR = GIT_COMMON_DIR / "swarm"
SWARM_STATE_FILE = SWARM_STATE_DIR / "coordination_state.json"
SWARM_LOCK_FILE = SWARM_STATE_DIR / "coordination.lock"
OWNERSHIP_FILE = REPO_ROOT / "docs" / "team" / "swarm_ownership.json"
MAX_EVENTS = 500


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
        }
    with SWARM_STATE_FILE.open("r", encoding="utf-8") as fh:
        state = json.load(fh)
    state.setdefault("version", 1)
    state.setdefault("updated_at", isoformat_z(utcnow()))
    state.setdefault("agents", {})
    state.setdefault("leases", {})
    state.setdefault("events", [])
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = isoformat_z(utcnow())
    tmp_file = SWARM_STATE_FILE.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=True, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_file, SWARM_STATE_FILE)


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
        payload = {
            "updated_at": state.get("updated_at"),
            "purged_expired": purged,
            "active_leases": len(leases),
            "agents": agents,
            "leases": leases,
            "events_tail": state.get("events", [])[-20:],
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
    return 0


def cmd_cleanup(_: argparse.Namespace) -> int:
    with locked_state() as state:
        removed = purge_expired_leases(state, utcnow())
        add_event(state, action="cleanup", agent="system", paths=[], note=f"removed={removed}")
    print(f"[swarm] cleanup removed {removed} expired lease(s).")
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
