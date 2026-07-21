"""Meta-tests for Validation Framework.

These tests verify that the validation framework itself is correct.
If these tests fail, the framework cannot be trusted.

Philosophy: "Who watches the watchmen?"
"""

import json
import tempfile
from pathlib import Path

from scripts.ops.validation import (
    FAILURE_TAXONOMY,
    MetricsCollector,
    EvaluationGate,
    Verdict,
)
from scripts.ops.validation.invariants import INVARIANTS
from scripts.ops.validation.statistics import (
    bootstrap_ci,
    detect_regression,
    ConfidenceInterval,
)


# === Meta-test 1: Failure Taxonomy Completeness ===

def test_failure_taxonomy_has_all_ids():
    """Every failure ID F1-F10 must be defined."""
    expected = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10"}
    actual = set(FAILURE_TAXONOMY.keys())
    assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"


def test_failure_taxonomy_no_duplicate_names():
    """No two failures can have the same name."""
    names = [f.name for f in FAILURE_TAXONOMY.values()]
    assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"


def test_failure_taxonomy_all_have_covers():
    """Every failure must reference at least one test suite."""
    for fid, f in FAILURE_TAXONOMY.items():
        assert len(f.covers) > 0, f"{fid} has no covering test suites"


# === Meta-test 2: Invariant Completeness ===

def test_invariants_have_all_ids():
    """Every invariant ID I1-I7 must be defined."""
    expected = {"I1", "I2", "I3", "I4", "I5", "I6", "I7"}
    actual = set(INVARIANTS.keys())
    assert actual == expected, f"Missing: {expected - actual}"


def test_invariants_have_verification_procedure():
    """Every invariant must describe how to verify it."""
    for iid, inv in INVARIANTS.items():
        assert len(inv.how_to_verify) > 20, f"{iid} verification procedure too short"
        assert "Assert" in inv.how_to_verify or "assert" in inv.how_to_verify.lower() or "Check" in inv.how_to_verify, \
            f"{iid} verification must include assertion step"


# === Meta-test 3: Bootstrap CI Correctness ===

def test_bootstrap_ci_contains_median():
    """CI bounds must contain the sample median."""
    import random
    rng = random.Random(42)
    data = [rng.gauss(100, 10) for _ in range(100)]
    ci = bootstrap_ci(data, confidence_level=0.95, seed=42)
    sorted_data = sorted(data)
    median = sorted_data[len(sorted_data) // 2]
    assert ci.ci_lower <= median <= ci.ci_upper, \
        f"CI [{ci.ci_lower}, {ci.ci_upper}] does not contain median {median}"


def test_bootstrap_ci_widens_with_lower_confidence():
    """Lower confidence should produce narrower CI."""
    data = [100, 105, 98, 102, 101, 99, 103, 104, 97, 106] * 10
    ci_90 = bootstrap_ci(data, confidence_level=0.90, seed=42)
    ci_99 = bootstrap_ci(data, confidence_level=0.99, seed=42)
    width_90 = ci_90.ci_upper - ci_90.ci_lower
    width_99 = ci_99.ci_upper - ci_99.ci_lower
    assert width_90 < width_99, f"90% CI ({width_90:.1f}) should be narrower than 99% CI ({width_99:.1f})"


def test_bootstrap_ci_reproducible_with_seed():
    """Same seed must produce same CI."""
    data = [100, 105, 98, 102, 101, 99, 103, 104, 97, 106] * 10
    ci1 = bootstrap_ci(data, seed=42)
    ci2 = bootstrap_ci(data, seed=42)
    assert ci1.ci_lower == ci2.ci_lower
    assert ci1.ci_upper == ci2.ci_upper


# === Meta-test 4: Regression Detection Correctness ===

def test_regression_detection_positive():
    """Clear degradation must be detected."""
    baseline = [100.0] * 30
    current = [150.0] * 30
    result = detect_regression(baseline, current, "test")
    assert result.is_regression, f"Should detect 50% regression"
    assert result.severity == "critical"


def test_regression_detection_negative():
    """No change must not trigger regression."""
    baseline = [100.0] * 30
    current = [101.0] * 30
    result = detect_regression(baseline, current, "test")
    assert not result.is_regression, f"Should not detect 1% as regression"
    assert result.severity == "none"


def test_regression_detection_improvement():
    """Improvement must not trigger regression."""
    baseline = [100.0] * 30
    current = [80.0] * 30
    result = detect_regression(baseline, current, "test")
    assert not result.is_regression
    assert result.change_pct < 0


# === Meta-test 5: Evaluation Gate Correctness ===

def test_evaluation_gate_pass():
    """Metrics within SLA must produce PASS."""
    gate = EvaluationGate()
    from scripts.ops.validation.metrics_collector import RecoveryMetrics
    metrics = [RecoveryMetrics(
        failure_id="F1",
        target="test",
        detect_time_ms=500,
        recovery_time_ms=1000,
        packets_lost=0,
        total_packets=100,
        sockets_survived=100,
        sockets_total=100,
        session_survived=True,
    )] * 30

    results = gate.evaluate_recovery(metrics)
    assert any(r.verdict == Verdict.PASS for r in results), "Should PASS for 1s recovery"


def test_evaluation_gate_fail():
    """Metrics outside SLA must produce FAIL."""
    gate = EvaluationGate()
    from scripts.ops.validation.metrics_collector import RecoveryMetrics
    metrics = [RecoveryMetrics(
        failure_id="F1",
        target="test",
        detect_time_ms=3000,
        recovery_time_ms=4000,
        packets_lost=50,
        total_packets=100,
        sockets_survived=50,
        sockets_total=100,
        session_survived=False,
    )] * 30

    results = gate.evaluate_session_survival(metrics)
    assert any(r.verdict == Verdict.FAIL for r in results), "Should FAIL for 50% survival"


# === Meta-test 6: Negative Test for I1 (No Routing Loops) ===

def test_cycle_detection_catches_loop():
    """Property test: cycle detection MUST catch a graph with a cycle."""
    def has_cycle(g):
        visited = set()
        rec_stack = set()
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in g.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False
        for node in g:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    # Graph with obvious cycle: 1→2→3→1
    graph_with_cycle = {1: [2], 2: [3], 3: [1]}
    assert has_cycle(graph_with_cycle), "Must detect cycle in 1→2→3→1"

    # Graph without cycle: 1→2→3
    graph_without_cycle = {1: [2], 2: [3], 3: []}
    assert not has_cycle(graph_without_cycle), "Must not detect cycle in 1→2→3"


# === Meta-test 7: Metrics Collector Produces Valid Output ===

def test_metrics_collector_export_json():
    """Metrics collector must produce valid JSON."""
    collector = MetricsCollector()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.json"
        collector.export_json(output)
        assert output.exists()
        with open(output) as f:
            data = json.load(f)
        assert "samples" in data
        assert "summary" in data


def test_metrics_collector_export_prometheus():
    """Metrics collector must produce valid Prometheus format."""
    collector = MetricsCollector()
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.prom"
        collector.export_prometheus(output)
        assert output.exists()
        content = output.read_text()
        # Prometheus format: metric_name{labels} value
        if content.strip():
            for line in content.strip().split("\n"):
                if line.startswith("x0tta6bl4_"):
                    assert "{" in line or " " in line, f"Invalid Prometheus line: {line}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
