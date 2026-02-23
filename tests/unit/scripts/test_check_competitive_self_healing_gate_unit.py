from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gate_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "check_competitive_self_healing_gate.py"
    spec = importlib.util.spec_from_file_location("competitive_gate", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load competitive gate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report_dict(
    current_failover: float = 50.0,
    target_failover: float = 30.0,
    rajant_failover: float = 13.0,
    ranking: list[str] | None = None,
):
    return {
        "profiles": [
            {
                "profile": "x0tta6bl4-current",
                "overall_p95_failover_ms": current_failover,
                "overall_p95_packet_loss_pct": 0.5,
            },
            {
                "profile": "x0tta6bl4-make-make-target",
                "overall_p95_failover_ms": target_failover,
                "overall_p95_packet_loss_pct": 0.3,
            },
            {
                "profile": "rajant-like",
                "overall_p95_failover_ms": rajant_failover,
                "overall_p95_packet_loss_pct": 0.1,
            },
        ],
        "ranking_by_p95_failover": ranking
        or ["rajant-like", "x0tta6bl4-make-make-target", "x0tta6bl4-current"],
    }


def _thresholds():
    return {
        "profiles": {
            "x0tta6bl4-current": {"max_p95_failover_ms": 60.0, "max_p95_packet_loss_pct": 0.8},
            "x0tta6bl4-make-make-target": {"max_p95_failover_ms": 35.0, "max_p95_packet_loss_pct": 0.6},
        },
        "relative": {
            "min_target_improvement_vs_current_pct": 25.0,
            "max_current_to_rajant_p95_failover_ratio": 4.0,
        },
        "ranking": {
            "expected_order_prefix": [
                "rajant-like",
                "x0tta6bl4-make-make-target",
                "x0tta6bl4-current",
            ]
        },
    }


def test_check_gates_passes_for_compliant_report():
    gate = _load_gate_module()
    failures = gate._check_gates(_report_dict(), _thresholds())  # noqa: SLF001
    assert failures == []


def test_check_gates_detects_absolute_threshold_violation():
    gate = _load_gate_module()
    failures = gate._check_gates(_report_dict(current_failover=70.0), _thresholds())  # noqa: SLF001
    assert any("x0tta6bl4-current: p95 failover" in item for item in failures)


def test_check_gates_detects_relative_improvement_violation():
    gate = _load_gate_module()
    failures = gate._check_gates(  # noqa: SLF001
        _report_dict(current_failover=50.0, target_failover=45.0),
        _thresholds(),
    )
    assert any("target improvement" in item for item in failures)


def test_check_gates_detects_ranking_violation():
    gate = _load_gate_module()
    failures = gate._check_gates(  # noqa: SLF001
        _report_dict(ranking=["x0tta6bl4-current", "rajant-like", "x0tta6bl4-make-make-target"]),
        _thresholds(),
    )
    assert any("ranking prefix mismatch" in item for item in failures)
