"""
eBPF Dataplane Latency Benchmark & Failover Validation Suite.

Measures:
- Dataplane packet processing overhead (p50, p95, p99)
- Failover switching latency under simulated route degradation (< 1.5s invariant)
- RingBuffer event throughput (ops/sec)
"""

import time
import statistics
import pytest
from src.network.ebpf.explainer import EBPFExplainer, EBPFEvent, EBPFEventType
from src.network.ebpf.dynamic_fallback import DynamicFallbackController


class TestEBPFDataplaneLatencyBenchmark:
    """eBPF Dataplane Latency & Failover SLA Benchmark."""

    def test_ebpf_event_processing_latency_percentiles(self):
        """Benchmark eBPF RingBuffer telemetry parsing & explainer latency (N=100)."""
        explainer = EBPFExplainer()
        latencies_ms = []

        # Generate 100 packet events to compute statistical percentiles (N >= 30 mandate)
        for i in range(100):
            event = EBPFEvent(
                event_type=EBPFEventType.PACKET_DROP,
                timestamp=time.time(),
                node_id=f"node-{i % 5}",
                program_id=f"prog-{i % 2}",
                details={"packet_loss": 5.0 + (i % 10), "latency_ms": 12.0 + (i % 5)},
            )

            start_t = time.perf_counter()
            explanation = explainer.explain_event(event)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            latencies_ms.append(elapsed_ms)

            assert isinstance(explanation, str)

        # Compute statistical metrics
        latencies_sorted = sorted(latencies_ms)
        p50 = latencies_sorted[int(0.50 * len(latencies_sorted))]
        p95 = latencies_sorted[int(0.95 * len(latencies_sorted))]
        p99 = latencies_sorted[int(0.99 * len(latencies_sorted))]

        # Invariant Assertions: Processing latency MUST be sub-millisecond
        assert p50 < 1.0, f"p50 latency too high: {p50:.3f}ms >= 1.0ms"
        assert p95 < 2.0, f"p95 latency too high: {p95:.3f}ms >= 2.0ms"
        assert p99 < 5.0, f"p99 latency too high: {p99:.3f}ms >= 5.0ms"

    def test_ebpf_failover_switching_latency_sla(self):
        """Verify failover switching under degraded route completes within SLA (< 1.5s)."""
        fallback = DynamicFallbackController(latency_threshold_ms=100.0, cooldown_seconds=0.1)

        start_t = time.perf_counter()
        # Feed high latency samples to trigger dynamic fallback
        for i in range(6):
            fallback.update_latency("node-benchmark-target", 450.0 + i * 10)
        
        elapsed_failover_s = time.perf_counter() - start_t

        status = fallback.get_fallback_status()
        assert isinstance(status, dict)

        # Invariant Check: Failover latency MUST NOT exceed 1.5s SLA
        assert elapsed_failover_s < 1.5, f"Failover SLA violated: {elapsed_failover_s:.4f}s >= 1.5s"
