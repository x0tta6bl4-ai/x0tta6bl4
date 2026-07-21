"""Statistical utilities for x0tta6bl4 Validation Framework.

Provides confidence intervals, bootstrap resampling,
and regression detection.

Reference: docs/architecture/BENCHMARK_SPEC.md §1.1
"""

import math
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfidenceInterval:
    """Confidence interval for a metric."""
    mean: float
    ci_lower: float
    ci_upper: float
    confidence_level: float  # e.g., 0.95
    method: str  # "bootstrap" or "normal"


@dataclass
class RegressionResult:
    """Result of regression detection."""
    metric_name: str
    baseline_value: float
    current_value: float
    change_pct: float
    is_regression: bool
    severity: str  # "none", "warning", "critical"
    details: str


def bootstrap_ci(
    data: list[float],
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    statistic: str = "median",
    seed: int = 42,
) -> ConfidenceInterval:
    """Compute confidence interval via bootstrap resampling.

    Args:
        data: Sample measurements
        confidence_level: Confidence level (0.95 = 95% CI)
        n_bootstrap: Number of bootstrap resamples
        statistic: "median" or "mean"
        seed: Random seed for reproducibility

    Returns:
        ConfidenceInterval with bounds
    """
    if len(data) < 2:
        return ConfidenceInterval(
            mean=data[0] if data else 0,
            ci_lower=data[0] if data else 0,
            ci_upper=data[0] if data else 0,
            confidence_level=confidence_level,
            method="insufficient_data",
        )

    rng = random.Random(seed)
    bootstrap_stats = []

    for _ in range(n_bootstrap):
        sample = rng.choices(data, k=len(data))
        if statistic == "median":
            bootstrap_stats.append(sorted(sample)[len(sample) // 2])
        else:
            bootstrap_stats.append(sum(sample) / len(sample))

    bootstrap_stats.sort()
    alpha = 1 - confidence_level
    lower_idx = int(alpha / 2 * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap) - 1

    mean_val = sum(data) / len(data)
    sorted_data = sorted(data)
    median_val = sorted_data[len(sorted_data) // 2]

    return ConfidenceInterval(
        mean=median_val if statistic == "median" else mean_val,
        ci_lower=bootstrap_stats[lower_idx],
        ci_upper=bootstrap_stats[upper_idx],
        confidence_level=confidence_level,
        method=f"bootstrap_{statistic}_B={n_bootstrap}",
    )


def normal_ci(
    data: list[float],
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute confidence interval using normal approximation.

    Only valid for large N (N >= 30).
    """
    n = len(data)
    if n < 2:
        return ConfidenceInterval(
            mean=data[0] if data else 0,
            ci_lower=data[0] if data else 0,
            ci_upper=data[0] if data else 0,
            confidence_level=confidence_level,
            method="insufficient_data",
        )

    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    stdev = math.sqrt(variance)
    se = stdev / math.sqrt(n)

    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence_level, 1.96)

    return ConfidenceInterval(
        mean=mean,
        ci_lower=mean - z * se,
        ci_upper=mean + z * se,
        confidence_level=confidence_level,
        method=f"normal_z={z}",
    )


def detect_regression(
    baseline: list[float],
    current: list[float],
    metric_name: str,
    warning_threshold_pct: float = 10,
    critical_threshold_pct: float = 30,
    use_median: bool = True,
) -> RegressionResult:
    """Detect if current performance regressed compared to baseline.

    Args:
        baseline: Historical baseline measurements
        current: Current measurements
        metric_name: Name of the metric
        warning_threshold_pct: Percentage change that triggers WARNING
        critical_threshold_pct: Percentage change that triggers CRITICAL
        use_median: Use median (robust) instead of mean

    Returns:
        RegressionResult with severity
    """
    if not baseline or not current:
        return RegressionResult(
            metric_name=metric_name,
            baseline_value=0,
            current_value=0,
            change_pct=0,
            is_regression=False,
            severity="none",
            details="Insufficient data for regression detection",
        )

    sorted_baseline = sorted(baseline)
    sorted_current = sorted(current)

    if use_median:
        baseline_val = sorted_baseline[len(sorted_baseline) // 2]
        current_val = sorted_current[len(sorted_current) // 2]
    else:
        baseline_val = sum(baseline) / len(baseline)
        current_val = sum(current) / len(current)

    if baseline_val == 0:
        change_pct = 0 if current_val == 0 else 100
    else:
        change_pct = ((current_val - baseline_val) / baseline_val) * 100

    if change_pct > critical_threshold_pct:
        severity = "critical"
        is_regression = True
    elif change_pct > warning_threshold_pct:
        severity = "warning"
        is_regression = True
    else:
        severity = "none"
        is_regression = False

    return RegressionResult(
        metric_name=metric_name,
        baseline_value=baseline_val,
        current_value=current_val,
        change_pct=change_pct,
        is_regression=is_regression,
        severity=severity,
        details=f"Baseline: {baseline_val:.1f}, Current: {current_val:.1f}, Change: {change_pct:+.1f}%",
    )


def required_sample_size(
    expected_stdev: float,
    margin_of_error: float,
    confidence_level: float = 0.95,
) -> int:
    """Calculate required sample size for desired margin of error.

    Args:
        expected_stdev: Estimated standard deviation
        margin_of_error: Desired margin of error
        confidence_level: Confidence level

    Returns:
        Required N
    """
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence_level, 1.96)

    n = ((z * expected_stdev) / margin_of_error) ** 2
    return math.ceil(n)
