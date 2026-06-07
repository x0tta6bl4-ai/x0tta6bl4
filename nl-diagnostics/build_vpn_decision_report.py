#!/usr/bin/env python3
"""Build a local VPN decision report from read-only evidence.

The script reads local snapshot files only. It does not connect to NL and does
not change local or remote VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.md"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def classify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    classifier = load_module(
        "classify_vpn_snapshot_for_decision",
        DIAGNOSTICS_DIR / "classify_vpn_snapshot.py",
    )
    return classifier.classify(snapshot_dir)


def build_blocking_history(snapshots_dir: Path) -> dict[str, Any]:
    history = load_module(
        "summarize_blocking_probe_history_for_decision",
        DIAGNOSTICS_DIR / "summarize_blocking_probe_history.py",
    )
    return history.build_payload(snapshots_dir)


def decide_action(classification: dict[str, Any], blocking_history: dict[str, Any]) -> dict[str, Any]:
    overall = str(classification.get("overall_status") or "unknown")
    failure_domain = str(classification.get("failure_domain") or "unknown")
    recommended_action = str(classification.get("recommended_action") or "unknown")
    transport = str(classification.get("transport_status") or "unknown")
    provider = str(classification.get("provider_status") or "unknown")
    blocking = classification.get("blocking_assessment") or {}
    blocking_category = str(blocking.get("category") or "none") if isinstance(blocking, dict) else "none"
    profile_policy = classification.get("profile_switch_policy") or {}
    profile_decision = str(profile_policy.get("decision") or "unknown") if isinstance(profile_policy, dict) else "unknown"
    history_summary = blocking_history.get("summary") or {}
    history_trend = str(history_summary.get("trend") or "unknown")

    blocked_actions = [
        "do not restart x-ui from app/blocking evidence alone",
        "do not change NL without explicit write approval",
        "do not auto-switch VPN profile",
        "do not use SPB as fallback while SPB is disabled",
    ]

    if overall == "provider_outage" or failure_domain == "provider_host" or recommended_action == "provider_ticket":
        decision = "provider_ticket"
        confidence = "high"
        reason = "classification points to provider or host failure"
        next_actions = [
            "build or refresh provider incident packet",
            "keep NL mutation blocked until provider symptoms are understood",
        ]
    elif overall == "critical" and failure_domain == "local_client":
        decision = "local_fix"
        confidence = "high"
        reason = "local client path is critical"
        next_actions = [
            "fix local route/SOCKS/client state first",
            "collect a new read-only snapshot after the local fix",
        ]
    elif overall == "critical" and failure_domain == "nl_service":
        decision = "nl_readonly_review"
        confidence = "high"
        reason = "NL service or listener evidence is critical"
        next_actions = [
            "inspect NL services/listeners read-only",
            "prepare backup and rollback plan before any future NL write",
        ]
    elif failure_domain == "monitoring" or blocking_category == "monitoring_gap":
        decision = "restore_transport_canary_monitor"
        confidence = "high"
        reason = "core VPN has live TCP/x-ui evidence, but transport canary evidence is not configured"
        next_actions = [
            "run the local dry-run/precheck for restoring ghost-access-vpn-monitor.timer",
            "apply the monitor restore only after explicit approval",
            "collect a fresh read-only snapshot after the monitor evidence is refreshed",
        ]
    elif profile_decision == "manual_profile_review" or blocking_category == "anti_block_candidate":
        decision = "manual_profile_review"
        confidence = "medium"
        reason = "runtime/profile policy asks for manual profile review"
        next_actions = [
            "compare direct, SOCKS, and app-specific probes",
            "review profile switch manually; automatic switching remains disabled",
        ]
    elif history_trend == "has_degradation" or blocking_category in {
        "exit_ip_or_vpn_rejected",
        "possible_local_isp_block",
        "vpn_path_degraded",
    }:
        decision = "app_path_investigation"
        confidence = "medium"
        reason = "blocking probe history or current blocking category has degraded path evidence"
        next_actions = [
            "repeat the degraded app/path probes from another network when possible",
            "separate exit-IP rejection from tunnel health before changing profiles",
        ]
    elif overall in {"ok", "advisory"} and transport in {"healthy", "advisory"}:
        decision = "observe"
        confidence = "high" if history_trend == "stable_no_probe_evidence" else "medium"
        reason = "core VPN is healthy/advisory and blocking probes show no direct-vs-SOCKS failure"
        next_actions = [
            "keep observing current VPN path",
            "when a user-visible outage happens, collect a fresh read-only snapshot with blocking probes",
            "test Telegram/media separately from core VPN transport",
        ]
    else:
        decision = "operator_review"
        confidence = "medium"
        reason = "evidence is mixed or not covered by a stronger automatic decision"
        next_actions = [
            "review classifier evidence and warnings",
            "collect another read-only snapshot if the current one is stale",
        ]

    if provider == "recent_boot_gap" and decision == "observe":
        next_actions.append("keep provider boot gap on watch; build provider packet if transport degrades")

    return {
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
        "next_actions": next_actions,
        "blocked_actions": blocked_actions,
        "inputs": {
            "overall_status": overall,
            "failure_domain": failure_domain,
            "recommended_action": recommended_action,
            "transport_status": transport,
            "provider_status": provider,
            "blocking_category": blocking_category,
            "profile_policy_decision": profile_decision,
            "blocking_history_trend": history_trend,
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def build_payload(snapshot_dir: Path, snapshots_dir: Path) -> dict[str, Any]:
    classification = classify_snapshot(snapshot_dir)
    blocking_history = build_blocking_history(snapshots_dir)
    decision = decide_action(classification, blocking_history)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_vpn_decision_report.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot_dir),
        "decision": decision,
        "classification": classification,
        "blocking_probe_history_summary": blocking_history.get("summary"),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    classification = payload["classification"]
    history = payload.get("blocking_probe_history_summary") or {}

    lines = [
        "# Current VPN Decision",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"snapshot: `{payload['snapshot']}`",
        "",
        "## Status",
        "",
        f"decision: `{decision['decision']}`",
        f"confidence: `{decision['confidence']}`",
        f"reason: {decision['reason']}",
        "",
        "## Current State",
        "",
        "```text",
        f"overall_status={classification.get('overall_status')}",
        f"transport_status={classification.get('transport_status')}",
        f"telegram_media_status={classification.get('telegram_media_status')}",
        f"provider_status={classification.get('provider_status')}",
        f"failure_domain={classification.get('failure_domain')}",
        f"recommended_action={classification.get('recommended_action')}",
        f"blocking_category={(classification.get('blocking_assessment') or {}).get('category')}",
        f"blocking_history_trend={history.get('trend')}",
        f"blocking_history_snapshots={history.get('snapshot_count')}",
        "nl_mutation_allowed=false",
        "auto_profile_switch_allowed=false",
        "spb_fallback_allowed=false",
        "```",
        "",
        "## Next Actions",
        "",
    ]
    for action in decision["next_actions"]:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## Blocked Actions",
            "",
        ]
    )
    for action in decision["blocked_actions"]:
        lines.append(f"- {action}")

    warnings = classification.get("warnings") or []
    problems = classification.get("problems") or []
    evidence = classification.get("evidence") or []
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Problems",
            "",
        ]
    )
    if problems:
        lines.extend(f"- {problem}" for problem in problems)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    if evidence:
        lines.extend(f"- {item}" for item in evidence)
    else:
        lines.append("- none")

    latest = history.get("latest") if isinstance(history, dict) else None
    if isinstance(latest, dict):
        lines.extend(
            [
                "",
                "## Blocking Probe History",
                "",
                "```text",
                f"snapshot_count={history.get('snapshot_count')}",
                f"trend={history.get('trend')}",
                f"latest_snapshot={latest.get('snapshot')}",
                f"latest_targets_ok={latest.get('ok_count')}/{latest.get('target_count')}",
                f"latest_degraded_targets={latest.get('degraded_count')}",
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "No NL or SPB writes were performed by this report.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build current VPN decision report")
    parser.add_argument("--snapshot", help="Snapshot directory. Defaults to latest snapshot.")
    parser.add_argument("--snapshots-dir", default=str(SNAPSHOTS_DIR))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    snapshots_dir = Path(args.snapshots_dir)
    snapshot_dir = Path(args.snapshot) if args.snapshot else latest_snapshot(snapshots_dir)
    if snapshot_dir is None:
        raise SystemExit(f"no snapshots found under {snapshots_dir}")
    payload = build_payload(snapshot_dir, snapshots_dir)

    if args.json_out:
        json_out = Path(args.json_out)
        json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        markdown_out = Path(args.markdown_out)
        markdown_out.write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
