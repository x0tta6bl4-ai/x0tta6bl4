from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "x0t-cli.sh"


def _run_cli(tmp_path: Path, *args: str, env_overrides: dict[str, str] | None = None):
    env = os.environ.copy()
    env.update(
        {
            "X0T_PROJECT_DIR": str(Path(__file__).resolve().parents[3]),
            "X0T_RUNTIME_DIR": str(tmp_path),
        }
    )
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        ["bash", str(_script_path()), *args],
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )


def test_earnings_reads_structured_stats_before_logs(tmp_path):
    stats_path = tmp_path / "node_stats.json"
    log_path = tmp_path / "x0t_vpn.log"
    stats_path.write_text(
        json.dumps(
            {
                "node_id": "node-17",
                "earnings_today": "1.25",
                "balance": "1002.5",
                "packets": 42,
                "bytes": 8192,
            }
        ),
        encoding="utf-8",
    )
    log_path.write_text("Reward queued: should not be used\n", encoding="utf-8")

    result = _run_cli(
        tmp_path,
        "earnings",
        env_overrides={
            "X0T_VPN_STATS_FILE": str(stats_path),
            "X0T_VPN_LOG_FILE": str(log_path),
        },
    )

    assert result.returncode == 0
    assert "Node: node-17" in result.stdout
    assert "Earnings Today: 1.25 X0T" in result.stdout
    assert "Balance: 1002.5 X0T" in result.stdout
    assert "Reward queued: should not be used" not in result.stdout


def test_earnings_falls_back_to_recent_reward_events(tmp_path):
    log_path = tmp_path / "x0t_vpn.log"
    log_path.write_text(
        "\n".join(
            [
                "ignored line",
                "Reward queued: 0.0100 X0T for 100 packets",
                "Reward queued: 0.0200 X0T for 200 packets",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        tmp_path,
        "earnings",
        env_overrides={
            "X0T_VPN_STATS_FILE": str(tmp_path / "missing_stats.json"),
            "X0T_VPN_LOG_FILE": str(log_path),
        },
    )

    assert result.returncode == 0
    assert "Structured stats not found" in result.stdout
    assert "Reward queued: 0.0100 X0T" in result.stdout
    assert "Reward queued: 0.0200 X0T" in result.stdout
