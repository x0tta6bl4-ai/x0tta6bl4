#!/usr/bin/env python3
"""Generate Utrecht pilot governance artifacts from observation logs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OBS_LOG = REPO_ROOT / "docs/governance/proposals/UTRECHT_PILOT_OBSERVATION_LOG.md"
DEFAULT_SUMMARY = REPO_ROOT / "docs/governance/proposals/UTRECHT_PILOT_KPI_SUMMARY.md"
DEFAULT_FUNDING = REPO_ROOT / "docs/governance/proposals/UTRECHT_PILOT_SCALE_FUNDING_2026_Q2.md"


@dataclass(frozen=True)
class Observation:
    timestamp_utc: str
    drill_result: str
    drill_rc: int
    api_health: str
    report_file: str
    notes: str

    @property
    def is_success(self) -> bool:
        return self.drill_result.upper() == "SUCCESS" and self.drill_rc == 0


@dataclass(frozen=True)
class Summary:
    total_observations: int
    success_count: int
    failure_count: int
    success_rate_pct: float
    reachable_count: int
    reachable_rate_pct: float
    latest_timestamp: str
    first_timestamp: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Utrecht pilot KPI and governance artifacts")
    parser.add_argument("--observation-log", type=Path, default=DEFAULT_OBS_LOG)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--funding-output", type=Path, default=DEFAULT_FUNDING)
    parser.add_argument("--mesh-id", default="mesh-000d249803b2656f")
    parser.add_argument(
        "--dashboard-url",
        default="http://maas.x0tta6bl4.io/dashboard/mesh-000d249803b2656f",
    )
    parser.add_argument(
        "--iso-evidence-sha256",
        default="fd1073472046788e430758ba1b9d644eab9bbcbce0155a987fd27fc3bf380d93",
    )
    parser.add_argument("--window-target-days", type=int, default=14)
    parser.add_argument("--minimum-days", type=int, default=7)
    parser.add_argument("--minimum-success-rate", type=float, default=95.0)
    parser.add_argument("--write-summary", action="store_true")
    parser.add_argument("--write-funding-draft", action="store_true")
    return parser.parse_args()


def _strip_cell(value: str) -> str:
    return value.strip().strip("`")


def parse_observations(lines: Iterable[str]) -> List[Observation]:
    observations: List[Observation] = []
    for raw in lines:
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        if cells[0].lower().startswith("timestamp"):
            continue
        try:
            obs = Observation(
                timestamp_utc=_strip_cell(cells[0]),
                drill_result=_strip_cell(cells[1]),
                drill_rc=int(_strip_cell(cells[2])),
                api_health=_strip_cell(cells[3]),
                report_file=_strip_cell(cells[4]),
                notes=_strip_cell(cells[5]),
            )
        except ValueError:
            continue
        observations.append(obs)
    return observations


def build_summary(observations: List[Observation]) -> Summary:
    if not observations:
        return Summary(
            total_observations=0,
            success_count=0,
            failure_count=0,
            success_rate_pct=0.0,
            reachable_count=0,
            reachable_rate_pct=0.0,
            latest_timestamp="n/a",
            first_timestamp="n/a",
        )

    total = len(observations)
    success = sum(1 for obs in observations if obs.is_success)
    failures = total - success
    reachable = sum(1 for obs in observations if obs.api_health.lower() == "reachable")
    success_rate = (success / total) * 100.0
    reachable_rate = (reachable / total) * 100.0

    sorted_obs = sorted(observations, key=lambda x: x.timestamp_utc)
    return Summary(
        total_observations=total,
        success_count=success,
        failure_count=failures,
        success_rate_pct=success_rate,
        reachable_count=reachable,
        reachable_rate_pct=reachable_rate,
        first_timestamp=sorted_obs[0].timestamp_utc,
        latest_timestamp=sorted_obs[-1].timestamp_utc,
    )


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def write_summary_file(
    *,
    output: Path,
    summary: Summary,
    observation_log: Path,
    mesh_id: str,
    dashboard_url: str,
    iso_evidence_sha256: str,
    window_target_days: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            [
                "# Utrecht Pilot KPI Summary",
                "",
                f"Mesh ID: `{mesh_id}`",
                f"Dashboard: `{dashboard_url}`",
                f"Observation Log: `{_display_path(observation_log)}`",
                f"ISO Evidence SHA256: `{iso_evidence_sha256}`",
                "",
                "## Current Snapshot",
                "",
                f"- Total observations: **{summary.total_observations}** / target **{window_target_days}**",
                f"- Success drills: **{summary.success_count}**",
                f"- Failed drills: **{summary.failure_count}**",
                f"- Success rate: **{_fmt_pct(summary.success_rate_pct)}**",
                f"- API reachable rate: **{_fmt_pct(summary.reachable_rate_pct)}**",
                f"- Window start: `{summary.first_timestamp}`",
                f"- Latest observation: `{summary.latest_timestamp}`",
                "",
                "## Operational Gate Signals",
                "",
                f"- Reliability gate candidate: {'PASS' if summary.failure_count == 0 else 'FAIL'}",
                (
                    "- Observation depth gate candidate: PASS"
                    if summary.total_observations >= window_target_days
                    else "- Observation depth gate candidate: IN_PROGRESS"
                ),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_funding_draft(
    *,
    output: Path,
    summary: Summary,
    summary_path: Path,
    observation_log: Path,
    mesh_id: str,
    dashboard_url: str,
    iso_evidence_sha256: str,
    minimum_days: int,
    minimum_success_rate: float,
) -> None:
    ready = (
        summary.total_observations >= minimum_days
        and summary.success_rate_pct >= minimum_success_rate
        and summary.failure_count == 0
    )
    more_days_needed = max(0, minimum_days - summary.total_observations)
    gate_text = "READY_FOR_VOTE" if ready else "NOT_READY"

    lines = [
        "# DAO Proposal: x0tta6bl4-UTRECHT-PILOT-SCALE-FUNDING-2026-Q2",
        "",
        "**Status:** Draft",
        "**Type:** Conditional Funding",
        "**Date:** 2026-03-04",
        "",
        "## 1. Executive Summary",
        "This proposal requests budget approval to scale Utrecht pilot operations from 50 nodes to 100+ nodes once reliability gates are met.",
        "",
        "## 2. Current Evidence Snapshot",
        f"- Mesh ID: `{mesh_id}`",
        f"- Dashboard: `{dashboard_url}`",
        f"- Observation log: `{_display_path(observation_log)}`",
        f"- KPI summary: `{_display_path(summary_path)}`",
        f"- ISO evidence SHA256: `{iso_evidence_sha256}`",
        "",
        "## 3. Gate Evaluation",
        f"- Gate status: **{gate_text}**",
        f"- Observations collected: **{summary.total_observations}**",
        f"- Success rate: **{_fmt_pct(summary.success_rate_pct)}** (required: >= {_fmt_pct(minimum_success_rate)})",
        f"- Failure count: **{summary.failure_count}** (required: 0)",
        f"- API reachable rate: **{_fmt_pct(summary.reachable_rate_pct)}**",
        f"- Latest observation: `{summary.latest_timestamp}`",
    ]

    if ready:
        lines.extend(
            [
                "",
                "Recommendation: proceed to treasury vote for scale-up execution.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"Recommendation: continue observation window; additional days needed to minimum gate: **{more_days_needed}**.",
            ]
        )

    lines.extend(
        [
            "",
            "## 4. Requested Budget (to be filled by treasury owner)",
            "- Infra expansion: `TBD`",
            "- Ops and on-call: `TBD`",
            "- Security/compliance overhead: `TBD`",
            "- Total requested: `TBD`",
            "",
            "## 5. Voting Options",
            "- **YES:** Approve funding for 100+ node scale-up when gate status is READY_FOR_VOTE.",
            "- **NO:** Defer funding and continue at current pilot scale.",
            "- **ABSTAIN:** No preference.",
            "",
            "---",
            "*Auto-generated from Utrecht pilot observation artifacts.*",
            "",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.write_summary and not args.write_funding_draft:
        print("Nothing to do: use --write-summary and/or --write-funding-draft")
        return 2

    if not args.observation_log.exists():
        print(f"Observation log not found: {args.observation_log}")
        return 1

    observations = parse_observations(args.observation_log.read_text(encoding="utf-8").splitlines())
    summary = build_summary(observations)

    if args.write_summary:
        write_summary_file(
            output=args.summary_output,
            summary=summary,
            observation_log=args.observation_log,
            mesh_id=args.mesh_id,
            dashboard_url=args.dashboard_url,
            iso_evidence_sha256=args.iso_evidence_sha256,
            window_target_days=args.window_target_days,
        )
        print(f"Summary written: {args.summary_output}")

    if args.write_funding_draft:
        write_funding_draft(
            output=args.funding_output,
            summary=summary,
            summary_path=args.summary_output,
            observation_log=args.observation_log,
            mesh_id=args.mesh_id,
            dashboard_url=args.dashboard_url,
            iso_evidence_sha256=args.iso_evidence_sha256,
            minimum_days=args.minimum_days,
            minimum_success_rate=args.minimum_success_rate,
        )
        print(f"Funding draft written: {args.funding_output}")

    print(
        "KPI snapshot:"
        f" observations={summary.total_observations}"
        f" success_rate={summary.success_rate_pct:.2f}%"
        f" failures={summary.failure_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
