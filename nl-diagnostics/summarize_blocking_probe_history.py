#!/usr/bin/env python3
"""Summarize local blocking probe history from read-only snapshots."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def load_probe(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def snapshot_id_from_probe_path(path: Path) -> str:
    try:
        return path.parents[1].name
    except IndexError:
        return "unknown"


def iter_probe_files(snapshots_dir: Path) -> list[Path]:
    return sorted(snapshots_dir.glob("*/local/blocking_probe.json"))


def summarize_probe(snapshot_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    targets = payload.get("targets") or []
    if not isinstance(targets, list):
        targets = []

    degraded_targets: list[dict[str, Any]] = []
    ok_count = 0
    for target in targets:
        if not isinstance(target, dict):
            continue
        assessment = str(target.get("assessment") or "unknown")
        if assessment == "ok":
            ok_count += 1
            continue
        degraded_targets.append(
            {
                "label": target.get("label"),
                "kind": target.get("kind"),
                "group": target.get("group"),
                "assessment": assessment,
                "direct_ok": target.get("direct_ok"),
                "socks_ok": target.get("socks_ok"),
                "direct_http_code": target.get("direct_http_code"),
                "socks_http_code": target.get("socks_http_code"),
            }
        )

    return {
        "snapshot": snapshot_id,
        "generated_at": payload.get("generated_at"),
        "assessment": summary.get("assessment", "unknown"),
        "target_count": len(targets),
        "ok_count": ok_count,
        "degraded_count": len(degraded_targets),
        "group_assessments": summary.get("group_assessments", {}),
        "degraded_targets": degraded_targets,
        "socks_proxy_detected": payload.get("socks_proxy_detected"),
        "socks_port": payload.get("socks_port"),
        "http_proxy_configured": payload.get("http_proxy_configured"),
        "targets_source": payload.get("targets_source"),
    }


def summarize_history(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assessment_counts: dict[str, int] = {}
    degraded_by_target: dict[str, int] = {}
    degraded_by_group: dict[str, int] = {}

    for row in rows:
        assessment = str(row.get("assessment") or "unknown")
        assessment_counts[assessment] = assessment_counts.get(assessment, 0) + 1
        for target in row.get("degraded_targets") or []:
            if not isinstance(target, dict):
                continue
            label = str(target.get("label") or "unknown")
            group = str(target.get("group") or "default")
            degraded_by_target[label] = degraded_by_target.get(label, 0) + 1
            degraded_by_group[group] = degraded_by_group.get(group, 0) + 1

    if not rows:
        trend = "no_data"
    elif all(row.get("assessment") == "no_probe_evidence" for row in rows):
        trend = "stable_no_probe_evidence"
    elif any(row.get("degraded_count", 0) for row in rows):
        trend = "has_degradation"
    else:
        trend = "mixed"

    return {
        "snapshot_count": len(rows),
        "trend": trend,
        "assessment_counts": dict(sorted(assessment_counts.items())),
        "degraded_by_target": dict(sorted(degraded_by_target.items())),
        "degraded_by_group": dict(sorted(degraded_by_group.items())),
        "latest": rows[-1] if rows else None,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    history = payload["history"]
    summary = payload["summary"]
    lines = [
        "# Blocking Probe History",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"snapshots_dir: `{payload['snapshots_dir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Timeline",
        "",
        "| Snapshot | Assessment | OK/Total | Degraded targets |",
        "|---|---|---:|---|",
    ]
    for row in history:
        degraded = ", ".join(
            f"{target.get('label')}={target.get('assessment')}"
            for target in row.get("degraded_targets", [])
        ) or "-"
        lines.append(
            f"| `{row['snapshot']}` | `{row['assessment']}` | "
            f"{row['ok_count']}/{row['target_count']} | {degraded} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    if summary["trend"] == "stable_no_probe_evidence":
        lines.append("All available blocking probes report no direct-vs-SOCKS blocking evidence.")
    elif summary["trend"] == "has_degradation":
        lines.append("At least one snapshot has degraded probe targets. Check repeated targets/groups before changing profiles.")
    else:
        lines.append("Probe history is incomplete or mixed; collect more snapshots before making profile decisions.")

    lines.extend(
        [
            "",
            "No NL or SPB writes were performed by this history summary.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_payload(snapshots_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in iter_probe_files(snapshots_dir):
        payload = load_probe(path)
        if payload is None:
            continue
        rows.append(summarize_probe(snapshot_id_from_probe_path(path), payload))
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/summarize_blocking_probe_history.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshots_dir": str(snapshots_dir),
        "summary": summarize_history(rows),
        "history": rows,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize blocking probe history")
    parser.add_argument("--snapshots-dir", default="nl-diagnostics/snapshots")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    payload = build_payload(Path(args.snapshots_dir))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
