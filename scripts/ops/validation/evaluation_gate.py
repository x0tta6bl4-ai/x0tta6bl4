"""Evaluation Gate for x0tta6bl4 Validation Framework.

Compares collected metrics against SLA thresholds.
Produces PASS / WARNING / FAIL verdicts.

Reference: docs/architecture/BENCHMARK_SPEC.md §5
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .metrics_collector import LatencyStats, RecoveryMetrics


class Verdict(Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass
class SLARule:
    """A single SLA evaluation rule."""
    name: str
    metric: str
    pass_threshold: float
    warning_threshold: float
    unit: str
    description: str
    rationale: str  # Why these thresholds were chosen
    requires_samples: int = 30  # Minimum samples for valid evaluation


@dataclass
class EvaluationResult:
    rule: SLARule
    verdict: Verdict
    measured_value: float
    details: str
    confidence_interval: Optional["ConfidenceInterval"] = None


DEFAULT_SLA_RULES: list[SLARule] = [
    SLARule(
        name="Node Failure Recovery",
        metric="recovery_time_ms",
        pass_threshold=2000,
        warning_threshold=5000,
        unit="ms",
        description="Time from failure detection to route restoration",
        rationale=(
            "2s PASS: User-perceptible delay threshold. Below 2s, most applications "
            "auto-retry transparently. 5s FAIL: Beyond this, TCP timeouts trigger "
            "application-level errors. Based on production observation: MAPE-K cycle "
            "is 5s, detection adds ~1s, route convergence adds ~0.5s."
        ),
        requires_samples=30,
    ),
    SLARule(
        name="Session Survival Rate",
        metric="session_survival_rate",
        pass_threshold=99.5,
        warning_threshold=95.0,
        unit="%",
        description="Percentage of sessions that survive failure event",
        rationale=(
            "99.5% PASS: At 500 concurrent users, 0.5% loss = 2.5 users affected. "
            "Acceptable for single-node failure. 95% FAIL: 5% loss = 25 users. "
            "Indicates systemic issue, not isolated failure."
        ),
        requires_samples=30,
    ),
    SLARule(
        name="PQC Handshake Overhead",
        metric="pqc_overhead_ms",
        pass_threshold=50,
        warning_threshold=150,
        unit="ms",
        description="Additional latency from ML-KEM-768 vs ECDHE",
        rationale=(
            "50ms PASS: ML-KEM-768 key generation ~25ms, encapsulation ~15ms, "
            "verification ~5ms on modern hardware. Total overhead ~45ms. "
            "150ms FAIL: Indicates CPU bottleneck or library issue."
        ),
        requires_samples=30,
    ),
    SLARule(
        name="Synthetic Loss Degradation",
        metric="loss_degradation_pct",
        pass_threshold=15,
        warning_threshold=30,
        unit="%",
        description="TTFB degradation under 20% packet loss",
        rationale=(
            "15% PASS: TCP retransmission overhead at 20% loss. "
            "Well-configured TCP (BBR) handles this with minimal TTFB impact. "
            "30% FAIL: Indicates protocol overhead or misconfigured congestion control."
        ),
        requires_samples=30,
    ),
    SLARule(
        name="Latency Median (Direct)",
        metric="latency_direct_median_ms",
        pass_threshold=100,
        warning_threshold=300,
        unit="ms",
        description="Median TTFB for direct connection (baseline)",
        rationale=(
            "100ms PASS: Typical RTT to major CDNs from Moscow datacenter. "
            "300ms FAIL: Indicates network issue, DNS resolution delay, "
            "or misconfigured outbound."
        ),
        requires_samples=30,
    ),
    SLARule(
        name="Latency Median (VPN)",
        metric="latency_vpn_median_ms",
        pass_threshold=500,
        warning_threshold=1500,
        unit="ms",
        description="Median TTFB through VPN tunnel",
        rationale=(
            "500ms PASS: Moscow→NL RTT ~40ms + TLS handshake ~30ms + "
            "WARP overhead ~20ms + HTTP overhead ~10ms ≈ 100ms. "
            "500ms allows 5x overhead for multi-hop routing. "
            "1500ms FAIL: Indicates routing issue, WARP degradation, "
            "or ISP throttling."
        ),
        requires_samples=30,
    ),
]


@dataclass
class EvaluationGate:
    """Evaluates metrics against SLA rules."""

    rules: list[SLARule] = field(default_factory=lambda: DEFAULT_SLA_RULES)
    results: list[EvaluationResult] = field(default_factory=list)

    def evaluate_recovery(
        self,
        metrics: list[RecoveryMetrics],
    ) -> list[EvaluationResult]:
        """Evaluate recovery metrics against SLA rules."""
        if not metrics:
            return []

        rule = next((r for r in self.rules if r.name == "Node Failure Recovery"), None)
        if not rule:
            return []

        recovery_times = [m.recovery_time_ms for m in metrics]
        avg_recovery = sum(recovery_times) / len(recovery_times)

        if avg_recovery < rule.pass_threshold:
            verdict = Verdict.PASS
        elif avg_recovery < rule.warning_threshold:
            verdict = Verdict.WARNING
        else:
            verdict = Verdict.FAIL

        result = EvaluationResult(
            rule=rule,
            verdict=verdict,
            measured_value=avg_recovery,
            details=f"Average recovery time: {avg_recovery:.0f}ms (N={len(metrics)})",
        )
        self.results.append(result)
        return [result]

    def evaluate_session_survival(
        self,
        metrics: list[RecoveryMetrics],
    ) -> list[EvaluationResult]:
        """Evaluate session survival rate."""
        if not metrics:
            return []

        rule = next((r for r in self.rules if r.name == "Session Survival Rate"), None)
        if not rule:
            return []

        survived = sum(1 for m in metrics if m.session_survived)
        rate = (survived / len(metrics)) * 100

        if rate >= rule.pass_threshold:
            verdict = Verdict.PASS
        elif rate >= rule.warning_threshold:
            verdict = Verdict.WARNING
        else:
            verdict = Verdict.FAIL

        result = EvaluationResult(
            rule=rule,
            verdict=verdict,
            measured_value=rate,
            details=f"Survival rate: {rate:.1f}% ({survived}/{len(metrics)})",
        )
        self.results.append(result)
        return [result]

    def evaluate_latency(
        self,
        stats: dict[str, LatencyStats],
        baseline_target: str,
        vpn_target: str,
    ) -> list[EvaluationResult]:
        """Evaluate latency stats against SLA rules."""
        results = []

        baseline = stats.get(baseline_target)
        vpn = stats.get(vpn_target)

        if baseline:
            rule = next((r for r in self.rules if r.name == "Latency Median (Direct)"), None)
            if rule:
                if baseline.median_ms <= rule.pass_threshold:
                    verdict = Verdict.PASS
                elif baseline.median_ms <= rule.warning_threshold:
                    verdict = Verdict.WARNING
                else:
                    verdict = Verdict.FAIL

                r = EvaluationResult(
                    rule=rule,
                    verdict=verdict,
                    measured_value=baseline.median_ms,
                    details=f"Direct median: {baseline.median_ms:.0f}ms (N={baseline.n})",
                )
                self.results.append(r)
                results.append(r)

        if vpn:
            rule = next((r for r in self.rules if r.name == "Latency Median (VPN)"), None)
            if rule:
                if vpn.median_ms <= rule.pass_threshold:
                    verdict = Verdict.PASS
                elif vpn.median_ms <= rule.warning_threshold:
                    verdict = Verdict.WARNING
                else:
                    verdict = Verdict.FAIL

                r = EvaluationResult(
                    rule=rule,
                    verdict=verdict,
                    measured_value=vpn.median_ms,
                    details=f"VPN median: {vpn.median_ms:.0f}ms (N={vpn.n})",
                )
                self.results.append(r)
                results.append(r)

        return results

    def get_overall_verdict(self) -> Verdict:
        """Get overall verdict from all evaluation results."""
        if not self.results:
            return Verdict.WARNING

        verdicts = [r.verdict for r in self.results]

        if Verdict.FAIL in verdicts:
            return Verdict.FAIL
        elif Verdict.WARNING in verdicts:
            return Verdict.WARNING
        else:
            return Verdict.PASS

    def export_json(self, output_path: Path) -> None:
        """Export evaluation results to JSON."""
        data = {
            "overall_verdict": self.get_overall_verdict().value,
            "results": [
                {
                    "rule": r.rule.name,
                    "verdict": r.verdict.value,
                    "measured": r.measured_value,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
