#!/usr/bin/env python3
"""Decide whether local VPN healing should be blocked by NL/provider evidence.

This script reads local read-only snapshots only. It never connects to NL and
never mutates local or remote VPN state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


DEFAULT_ROOT = Path("/mnt/projects")
BLOCK_EXIT_CODE = 10
DEFAULT_MAX_AGE_SECONDS = 3600


def load_classifier(root: Path):
    path = root / "nl-diagnostics" / "classify_vpn_snapshot.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("classify_vpn_snapshot", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify_vpn_snapshot_for_guard"] = module
    spec.loader.exec_module(module)
    return module


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def parse_snapshot_timestamp(snapshot_dir: Path | None) -> datetime | None:
    if snapshot_dir is None:
        return None
    try:
        return datetime.strptime(snapshot_dir.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def snapshot_age_seconds(snapshot_dir: Path | None, now: datetime | None = None) -> int | None:
    timestamp = parse_snapshot_timestamp(snapshot_dir)
    if timestamp is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - timestamp).total_seconds()))


def evaluate_guard(
    state: dict[str, Any],
    snapshot_dir: Path | None = None,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    require_fresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    overall = str(state.get("overall_status", "unknown"))
    failure_domain = str(state.get("failure_domain", "unknown"))
    recommended_action = str(state.get("recommended_action", "operator_review"))
    age_seconds = snapshot_age_seconds(snapshot_dir, now)
    snapshot_stale = age_seconds is not None and age_seconds > max_age_seconds

    blocking_reason = ""
    if overall == "provider_outage":
        blocking_reason = "provider_outage"
    elif failure_domain == "provider_host":
        blocking_reason = "provider_host"
    elif recommended_action in {"provider_ticket", "failover"}:
        blocking_reason = f"recommended_action={recommended_action}"
    elif overall == "critical" and failure_domain == "nl_service":
        blocking_reason = "critical_nl_service"
    elif require_fresh and snapshot_stale:
        blocking_reason = f"stale_snapshot_age_seconds={age_seconds}"
    elif require_fresh and age_seconds is None:
        blocking_reason = "snapshot_age_unknown"

    guard_status = "block" if blocking_reason else "allow"
    warnings: list[str] = []
    if snapshot_stale:
        warnings.append(f"snapshot stale: age_seconds={age_seconds}, max_age_seconds={max_age_seconds}")
    elif age_seconds is None:
        warnings.append("snapshot age unknown")

    return {
        "schema_version": 1,
        "source": "scripts/vpn_provider_guard.py",
        "guard_status": guard_status,
        "blocking_reason": blocking_reason or None,
        "snapshot_dir": str(snapshot_dir) if snapshot_dir else None,
        "snapshot_age_seconds": age_seconds,
        "snapshot_max_age_seconds": max_age_seconds,
        "snapshot_stale": snapshot_stale,
        "overall_status": overall,
        "failure_domain": failure_domain,
        "recommended_action": recommended_action,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "warnings": warnings,
    }


def load_state(
    root: Path,
    snapshots_dir: Path,
    snapshot_dir: Path | None,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    require_fresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    selected = snapshot_dir or latest_snapshot(snapshots_dir)
    if selected is None:
        guard_status = "block" if require_fresh else "allow"
        return {
            "schema_version": 1,
            "source": "scripts/vpn_provider_guard.py",
            "guard_status": guard_status,
            "blocking_reason": "snapshot_missing" if require_fresh else None,
            "snapshot_dir": None,
            "snapshot_age_seconds": None,
            "snapshot_max_age_seconds": max_age_seconds,
            "snapshot_stale": None,
            "overall_status": "unknown",
            "failure_domain": "unknown",
            "recommended_action": "observe",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "reason": "no local snapshot available; guard cannot prove provider/NL block",
            "warnings": ["snapshot missing"],
        }

    classifier = load_classifier(root)
    if classifier is None:
        guard_status = "block" if require_fresh else "allow"
        age_seconds = snapshot_age_seconds(selected, now)
        return {
            "schema_version": 1,
            "source": "scripts/vpn_provider_guard.py",
            "guard_status": guard_status,
            "blocking_reason": "classifier_unavailable" if require_fresh else None,
            "snapshot_dir": str(selected),
            "snapshot_age_seconds": age_seconds,
            "snapshot_max_age_seconds": max_age_seconds,
            "snapshot_stale": age_seconds is not None and age_seconds > max_age_seconds,
            "overall_status": "unknown",
            "failure_domain": "unknown",
            "recommended_action": "observe",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "reason": "snapshot classifier unavailable; guard cannot prove provider/NL block",
            "warnings": ["snapshot classifier unavailable"],
        }

    state = classifier.classify(selected)
    return evaluate_guard(
        state,
        selected,
        max_age_seconds=max_age_seconds,
        require_fresh=require_fresh,
        now=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--snapshots-dir")
    parser.add_argument("--snapshot-dir")
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument("--require-fresh", action="store_true", help="Exit 10 when the latest snapshot is stale or missing")
    parser.add_argument("--json", action="store_true", help="Print JSON decision")
    parser.add_argument("--check", action="store_true", help="Exit 10 when guard blocks local healing")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    snapshots_dir = Path(args.snapshots_dir).resolve() if args.snapshots_dir else root / "nl-diagnostics" / "snapshots"
    snapshot_dir = Path(args.snapshot_dir).resolve() if args.snapshot_dir else None

    decision = load_state(
        root,
        snapshots_dir,
        snapshot_dir,
        max_age_seconds=args.max_age_seconds,
        require_fresh=args.require_fresh,
    )

    if args.json:
        print(json.dumps(decision, indent=2, sort_keys=True))
    elif args.check:
        status = decision["guard_status"]
        reason = decision.get("blocking_reason") or decision.get("reason") or "ok"
        suffix = ""
        if decision.get("snapshot_age_seconds") is not None:
            suffix = f" age_seconds={decision['snapshot_age_seconds']}"
        print(f"{status.upper()}: {reason}{suffix}")
    else:
        print(json.dumps(decision, indent=2, sort_keys=True))

    return BLOCK_EXIT_CODE if decision["guard_status"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
