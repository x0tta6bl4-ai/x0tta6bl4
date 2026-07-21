"""Metrics Collector for x0tta6bl4 Validation Framework.

Collects telemetry during validation runs:
- Latency (TCP connect, TLS handshake, TTFB, total)
- Packet loss
- Recovery time
- Socket survival rate

Reference: docs/architecture/BENCHMARK_SPEC.md §6
"""

import json
import time
import subprocess
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LatencySample:
    """Single latency measurement."""
    target: str
    timestamp: float
    tcp_conn_ms: float = 0
    tls_handshake_ms: float = 0
    ttfb_ms: float = 0
    total_ms: float = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class LatencyStats:
    """Aggregated latency statistics."""
    target: str
    n: int
    mean_ms: float
    median_ms: float
    stdev_ms: float
    min_ms: float
    max_ms: float
    iqr_ms: float  # Interquartile range
    p95_ms: Optional[float] = None  # Only valid when N >= 100
    p99_ms: Optional[float] = None  # Only valid when N >= 100
    success_rate: float = 1.0


@dataclass
class RecoveryMetrics:
    """Metrics for failure recovery measurement."""
    failure_id: str
    target: str
    detect_time_ms: float
    recovery_time_ms: float
    packets_lost: int
    total_packets: int
    sockets_survived: int
    sockets_total: int
    session_survived: bool


@dataclass
class MetricsCollector:
    """Collects and aggregates validation metrics."""

    samples: list[LatencySample] = field(default_factory=list)
    recovery_metrics: list[RecoveryMetrics] = field(default_factory=list)

    def measure_latency(
        self,
        target: str,
        url: str,
        proxy: Optional[str] = None,
        timeout_sec: float = 10.0,
    ) -> LatencySample:
        """Measure latency to a target URL.

        Measures TCP connect, TLS handshake, TTFB, and total time.
        """
        cmd_parts = [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            '"%{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{http_code}"',
            "--connect-timeout",
            str(int(timeout_sec)),
            "--max-time",
            str(int(timeout_sec)),
        ]

        if proxy:
            cmd_parts.extend(["--proxy", proxy])

        cmd_parts.append(url)
        cmd = " ".join(cmd_parts)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec + 5,
            )

            values = proc.stdout.strip().strip('"').split()
            if len(values) >= 4:
                tcp_conn = float(values[0]) * 1000
                tls_handshake = float(values[1]) * 1000
                ttfb = float(values[2]) * 1000
                total = float(values[3]) * 1000
                http_code = int(values[4]) if len(values) > 4 else 0
                success = 200 <= http_code < 400

                sample = LatencySample(
                    target=target,
                    timestamp=time.time(),
                    tcp_conn_ms=tcp_conn,
                    tls_handshake_ms=tls_handshake - tcp_conn,
                    ttfb_ms=ttfb,
                    total_ms=total,
                    success=success,
                )
            else:
                sample = LatencySample(
                    target=target,
                    timestamp=time.time(),
                    success=False,
                    error=f"Unexpected output: {proc.stdout}",
                )

        except (subprocess.TimeoutExpired, Exception) as e:
            sample = LatencySample(
                target=target,
                timestamp=time.time(),
                success=False,
                error=str(e),
            )

        self.samples.append(sample)
        return sample

    def measure_recovery_time(
        self,
        failure_id: str,
        target: str,
        check_interval_ms: float = 100,
        max_wait_sec: float = 30,
    ) -> RecoveryMetrics:
        """Measure time to recover from a failure.

        Returns RecoveryMetrics with detect_time and recovery_time.
        """
        start = time.monotonic()
        detected = False
        detect_time = 0
        recovered = False
        recovery_time = 0
        checks = 0

        while (time.monotonic() - start) < max_wait_sec:
            checks += 1
            try:
                proc = subprocess.run(
                    f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout 2 --max-time 3 {target}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                http_code = proc.stdout.strip().strip("'")

                if not detected and http_code in ("000", ""):
                    detected = True
                    detect_time = (time.monotonic() - start) * 1000

                if detected and http_code not in ("000", ""):
                    recovered = True
                    recovery_time = (time.monotonic() - start) * 1000
                    break

            except Exception:
                if not detected:
                    detected = True
                    detect_time = (time.monotonic() - start) * 1000

            time.sleep(check_interval_ms / 1000)

        metrics = RecoveryMetrics(
            failure_id=failure_id,
            target=target,
            detect_time_ms=detect_time if detected else max_wait_sec * 1000,
            recovery_time_ms=recovery_time if recovered else max_wait_sec * 1000,
            packets_lost=0,
            total_packets=checks,
            sockets_survived=1 if recovered else 0,
            sockets_total=1,
            session_survived=recovered,
        )

        self.recovery_metrics.append(metrics)
        return metrics

    def compute_latency_stats(self, target: str) -> Optional[LatencyStats]:
        """Compute aggregated latency statistics for a target."""
        target_samples = [s for s in self.samples if s.target == target and s.success]
        if not target_samples:
            return None

        total_samples = [s for s in self.samples if s.target == target]
        n = len(target_samples)
        totals = [s.total_ms for s in target_samples]

        sorted_totals = sorted(totals)
        q1_idx = len(sorted_totals) // 4
        q3_idx = (3 * len(sorted_totals)) // 4

        stats = LatencyStats(
            target=target,
            n=n,
            mean_ms=statistics.mean(totals),
            median_ms=statistics.median(totals),
            stdev_ms=statistics.stdev(totals) if n > 1 else 0,
            min_ms=min(totals),
            max_ms=max(totals),
            iqr_ms=sorted_totals[q3_idx] - sorted_totals[q1_idx],
            success_rate=n / len(total_samples) if total_samples else 0,
        )

        if n >= 100:
            p95_idx = int(0.95 * n)
            p99_idx = int(0.99 * n)
            stats.p95_ms = sorted_totals[min(p95_idx, n - 1)]
            stats.p99_ms = sorted_totals[min(p99_idx, n - 1)]

        return stats

    def export_json(self, output_path: Path) -> None:
        """Export all metrics to JSON."""
        data = {
            "samples": [
                {
                    "target": s.target,
                    "timestamp": s.timestamp,
                    "tcp_conn_ms": s.tcp_conn_ms,
                    "tls_handshake_ms": s.tls_handshake_ms,
                    "ttfb_ms": s.ttfb_ms,
                    "total_ms": s.total_ms,
                    "success": s.success,
                    "error": s.error,
                }
                for s in self.samples
            ],
            "recovery": [
                {
                    "failure_id": r.failure_id,
                    "target": r.target,
                    "detect_time_ms": r.detect_time_ms,
                    "recovery_time_ms": r.recovery_time_ms,
                    "session_survived": r.session_survived,
                }
                for r in self.recovery_metrics
            ],
            "summary": {},
        }

        for target in set(s.target for s in self.samples):
            stats = self.compute_latency_stats(target)
            if stats:
                data["summary"][target] = {
                    "n": stats.n,
                    "mean_ms": round(stats.mean_ms, 2),
                    "median_ms": round(stats.median_ms, 2),
                    "stdev_ms": round(stats.stdev_ms, 2),
                    "iqr_ms": round(stats.iqr_ms, 2),
                    "success_rate": round(stats.success_rate, 4),
                    "p95_ms": round(stats.p95_ms, 2) if stats.p95_ms else None,
                    "p99_ms": round(stats.p99_ms, 2) if stats.p99_ms else None,
                }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def export_prometheus(self, output_path: Path) -> None:
        """Export metrics in Prometheus format."""
        lines = []
        for target in set(s.target for s in self.samples):
            stats = self.compute_latency_stats(target)
            if stats:
                safe_target = target.replace(".", "_").replace("/", "_")
                lines.append(f'x0tta6bl4_latency_mean_ms{{target="{target}"}} {stats.mean_ms:.2f}')
                lines.append(f'x0tta6bl4_latency_median_ms{{target="{target}"}} {stats.median_ms:.2f}')
                lines.append(f'x0tta6bl4_latency_stdev_ms{{target="{target}"}} {stats.stdev_ms:.2f}')
                lines.append(f'x0tta6bl4_success_rate{{target="{target}"}} {stats.success_rate:.4f}')

        for r in self.recovery_metrics:
            lines.append(f'x0tta6bl4_recovery_detect_ms{{failure="{r.failure_id}",target="{r.target}"}} {r.detect_time_ms:.2f}')
            lines.append(f'x0tta6bl4_recovery_total_ms{{failure="{r.failure_id}",target="{r.target}"}} {r.recovery_time_ms:.2f}')
            lines.append(f'x0tta6bl4_session_survived{{failure="{r.failure_id}",target="{r.target}"}} {1 if r.session_survived else 0}')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("\n".join(lines) + "\n")
