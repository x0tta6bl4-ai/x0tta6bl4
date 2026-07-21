"""Validation History for x0tta6bl4 Validation Framework.

Tracks validation results over time, compares against baselines,
and detects regressions between runs.

Reference: MILESTONE_VALIDATION_V1.md, validation/VERSIONING.md
"""

import json
import glob
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .statistics import detect_regression, RegressionResult


@dataclass
class ValidationRun:
    """Single validation run record."""
    timestamp: str
    commit: str
    branch: str
    status: str  # PASS, WARNING, FAIL
    latency: dict
    recovery: dict
    invariants: dict
    sla_results: list[dict]
    regressions: list[dict] = field(default_factory=list)


@dataclass
class HistoryEntry:
    """Entry in the validation history."""
    run: ValidationRun
    comparison: Optional[dict] = None


class ValidationHistory:
    """Manages validation history and baseline comparisons."""

    def __init__(self, history_dir: Path = Path("results/history")):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "history.json"

    def load_history(self) -> list[dict]:
        """Load validation history from file."""
        if not self.history_file.exists():
            return []
        with open(self.history_file) as f:
            return json.load(f)

    def save_history(self, history: list[dict]) -> None:
        """Save validation history to file."""
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def add_run(self, run: ValidationRun) -> None:
        """Add a validation run to history."""
        history = self.load_history()
        history.append({
            "timestamp": run.timestamp,
            "commit": run.commit,
            "branch": run.branch,
            "status": run.status,
            "latency": run.latency,
            "recovery": run.recovery,
            "invariants": run.invariants,
            "sla_results": run.sla_results,
            "regressions": run.regressions,
        })
        self.save_history(history)

    def get_latest(self, n: int = 1) -> list[dict]:
        """Get the last N validation runs."""
        history = self.load_history()
        return history[-n:] if history else []

    def get_baseline(self) -> Optional[dict]:
        """Get the approved baseline."""
        baseline_file = self.history_dir / "baseline.json"
        if not baseline_file.exists():
            return None
        with open(baseline_file) as f:
            return json.load(f)

    def set_baseline(self, run: dict) -> None:
        """Set a run as the approved baseline."""
        baseline_file = self.history_dir / "baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(run, f, indent=2)

    def compare_with_baseline(self, current: dict) -> Optional[dict]:
        """Compare current run with the baseline."""
        baseline = self.get_baseline()
        if not baseline:
            return None

        comparisons = []

        # Compare latency
        for target in current.get("latency", {}):
            if target in baseline.get("latency", {}):
                curr_val = current["latency"][target].get("median_ms", 0)
                base_val = baseline["latency"][target].get("median_ms", 0)
                if base_val > 0:
                    change_pct = ((curr_val - base_val) / base_val) * 100
                    comparisons.append({
                        "metric": f"latency_{target}",
                        "baseline": base_val,
                        "current": curr_val,
                        "change_pct": round(change_pct, 2),
                        "severity": "critical" if change_pct > 30 else "warning" if change_pct > 10 else "none",
                    })

        # Compare recovery
        for metric in current.get("recovery", {}):
            if metric in baseline.get("recovery", {}):
                curr_val = current["recovery"][metric]
                base_val = baseline["recovery"][metric]
                if isinstance(curr_val, (int, float)) and isinstance(base_val, (int, float)) and base_val > 0:
                    change_pct = ((curr_val - base_val) / base_val) * 100
                    comparisons.append({
                        "metric": f"recovery_{metric}",
                        "baseline": base_val,
                        "current": curr_val,
                        "change_pct": round(change_pct, 2),
                        "severity": "critical" if change_pct > 30 else "warning" if change_pct > 10 else "none",
                    })

        return {
            "baseline_commit": baseline.get("commit"),
            "current_commit": current.get("commit"),
            "baseline_timestamp": baseline.get("timestamp"),
            "comparisons": comparisons,
            "regressions_detected": any(c["severity"] in ("warning", "critical") for c in comparisons),
        }

    def detect_regressions(self, window: int = 5) -> list[dict]:
        """Detect regressions across recent runs."""
        recent = self.get_latest(window)
        if len(recent) < 2:
            return []

        regressions = []
        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]

            for target in curr.get("latency", {}):
                if target in prev.get("latency", {}):
                    curr_val = curr["latency"][target].get("median_ms", 0)
                    prev_val = prev["latency"][target].get("median_ms", 0)
                    if prev_val > 0:
                        result = detect_regression(
                            [prev_val] * 30,
                            [curr_val] * 30,
                            f"latency_{target}",
                        )
                        if result.is_regression:
                            regressions.append({
                                "metric": f"latency_{target}",
                                "from_commit": prev.get("commit"),
                                "to_commit": curr.get("commit"),
                                "change_pct": round(result.change_pct, 2),
                                "severity": result.severity,
                            })

        return regressions

    def export_dashboard(self, output_path: Path) -> None:
        """Export history as dashboard JSON."""
        history = self.load_history()
        baseline = self.get_baseline()
        regressions = self.detect_regressions()

        dashboard = {
            "generated_at": datetime.now().isoformat(),
            "total_runs": len(history),
            "baseline": baseline,
            "recent_runs": history[-10:] if history else [],
            "regressions": regressions,
            "status_summary": {
                "PASS": sum(1 for r in history if r.get("status") == "PASS"),
                "WARNING": sum(1 for r in history if r.get("status") == "WARNING"),
                "FAIL": sum(1 for r in history if r.get("status") == "FAIL"),
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(dashboard, f, indent=2)


def load_run_from_results(results_dir: Path) -> Optional[ValidationRun]:
    """Load a ValidationRun from a results directory."""
    summary_file = results_dir / "summary.json"
    metadata_file = results_dir / "metadata.json"

    if not summary_file.exists() or not metadata_file.exists():
        return None

    with open(summary_file) as f:
        summary = json.load(f)
    with open(metadata_file) as f:
        metadata = json.load(f)

    return ValidationRun(
        timestamp=metadata.get("timestamp", ""),
        commit=metadata.get("git_commit", ""),
        branch=metadata.get("git_branch", "unknown"),
        status=summary.get("overall_verdict", "UNKNOWN"),
        latency=summary.get("latency", {}),
        recovery=summary.get("recovery", {}),
        invariants=summary.get("invariants", {}),
        sla_results=summary.get("sla_results", []),
        regressions=summary.get("regressions", []),
    )
