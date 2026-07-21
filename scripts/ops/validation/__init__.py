"""x0tta6bl4 Validation Framework.

Reproducible validation suite for measuring system properties:
- Node failure recovery time
- Packet loss resilience
- Transport fallback
- PQC handshake overhead
- High concurrency scaling
- Architecture invariants (I1-I7)
- Regression detection
- Confidence intervals

Reference: docs/architecture/BENCHMARK_SPEC.md

Usage:
    python -m scripts.ops.validation.runner --samples 30
    python -m scripts.ops.validation.runner --suite V1 --failure F1 --dry-run
    python -m scripts.ops.validation.runner --check-invariants
"""

from .failure_taxonomy import FailureType, get_failure, list_failures, FAILURE_TAXONOMY
from .failure_injector import FailureInjector, InjectionResult
from .metrics_collector import MetricsCollector, LatencyStats, RecoveryMetrics
from .evaluation_gate import EvaluationGate, Verdict, SLARule
from .invariants import Invariant, InvariantCheck, InvariantStatus, get_invariant, list_invariants, check_invariant
from .statistics import bootstrap_ci, normal_ci, detect_regression, ConfidenceInterval, RegressionResult
from .history import ValidationHistory, ValidationRun, load_run_from_results
from .report import generate_html_report

__all__ = [
    "FailureType",
    "get_failure",
    "list_failures",
    "FAILURE_TAXONOMY",
    "FailureInjector",
    "InjectionResult",
    "MetricsCollector",
    "LatencyStats",
    "RecoveryMetrics",
    "EvaluationGate",
    "Verdict",
    "SLARule",
    "Invariant",
    "InvariantCheck",
    "InvariantStatus",
    "get_invariant",
    "list_invariants",
    "check_invariant",
    "bootstrap_ci",
    "normal_ci",
    "detect_regression",
    "ConfidenceInterval",
    "RegressionResult",
    "ValidationHistory",
    "ValidationRun",
    "load_run_from_results",
    "generate_html_report",
]
