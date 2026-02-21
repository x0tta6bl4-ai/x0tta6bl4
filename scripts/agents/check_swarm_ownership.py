#!/usr/bin/env python3
"""Validate staged files against swarm ownership matrix."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(
    subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
)
OWNERSHIP_PATH = REPO_ROOT / "docs" / "team" / "swarm_ownership.json"


def load_ownership() -> dict:
    try:
        with OWNERSHIP_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[swarm] ownership file not found: {OWNERSHIP_PATH}", file=sys.stderr)
        sys.exit(2)


def list_staged_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], text=True
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def match_rule(path: str, rule: str) -> bool:
    if "*" in rule or "?" in rule or "[" in rule:
        return fnmatch.fnmatch(path, rule)
    if rule.endswith("/"):
        return path.startswith(rule)
    return path == rule


def is_allowed(path: str, rules: list[str]) -> bool:
    return any(match_rule(path, rule) for rule in rules)


def format_scope(rules: list[str]) -> str:
    return "\n".join(f"  - {rule}" for rule in rules)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check staged files ownership for swarm mode")
    parser.add_argument("--agent", help="Agent key from docs/team/swarm_ownership.json")
    parser.add_argument(
        "--print-scope", action="store_true", help="Print allowed file rules for selected agent"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ownership = load_ownership()
    agents = ownership.get("agents", {})
    agent = args.agent or ""

    if not agent:
        print("[swarm] no --agent provided. Use --agent or set SWARM_AGENT in hook.")
        return 0

    if agent not in agents:
        known = ", ".join(sorted(agents))
        print(f"[swarm] unknown agent '{agent}'. Known agents: {known}", file=sys.stderr)
        return 2

    allowed_rules = list(ownership.get("shared_allow", [])) + list(agents[agent].get("allow", []))

    if args.print_scope:
        print(f"[swarm] scope for {agent}:")
        print(format_scope(allowed_rules))
        return 0

    staged = list_staged_files()
    if not staged:
        return 0

    denied = [path for path in staged if not is_allowed(path, allowed_rules)]
    if not denied:
        print(f"[swarm] ownership check passed for '{agent}' ({len(staged)} staged file(s)).")
        return 0

    print(f"[swarm] ownership check failed for '{agent}'.", file=sys.stderr)
    print("[swarm] non-owned staged files:", file=sys.stderr)
    for path in denied:
        print(f"  - {path}", file=sys.stderr)
    print("[swarm] allowed scope:", file=sys.stderr)
    print(format_scope(allowed_rules), file=sys.stderr)
    print("[swarm] stage only owned files or switch SWARM_AGENT.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
