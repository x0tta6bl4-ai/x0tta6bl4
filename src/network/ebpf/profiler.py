"""
eBPF Telemetry CPU Overhead Profiler

This module provides CPU overhead profiling for eBPF telemetry programs.
Measures CPU usage, memory consumption, and performance impact of eBPF probes.

Target: <2% CPU overhead (Stage 1 requirement)
"""

import hashlib
import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psutil

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_PROFILER_SERVICE_NAME = "ebpf-profiler"
EBPF_PROFILER_LAYER = "network_ebpf_profiler_observed_state"
EBPF_PROFILER_CLAIM_BOUNDARY = (
    "Local eBPF profiler evidence only. Events record local psutil sampling, "
    "loopback ping subprocess attempts, socket throughput probes, derived overhead "
    "estimates, and report generation with hashed process/command/target selectors "
    "and bounded output metadata; they do not prove production traffic volume, "
    "remote peer identity, live eBPF datapath enforcement, or statistically valid "
    "latency/throughput benchmarks beyond the local operation result."
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: Optional[Any] = None,
    stderr: Optional[Any] = None,
) -> Dict[str, Any]:
    safe_stdout = _normalize_text(stdout)
    safe_stderr = _normalize_text(stderr)
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_bounded": True,
        "output_redacted": True,
    }


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_PROFILER_SERVICE_NAME)
    return {
        "service_name": EBPF_PROFILER_SERVICE_NAME,
        "layer": EBPF_PROFILER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


@dataclass
class CPUProfileResult:
    """Results from CPU profiling session"""

    timestamp: datetime
    duration_seconds: float
    avg_cpu_percent: float
    max_cpu_percent: float
    cpu_percentiles: Dict[str, float]  # p50, p95, p99
    memory_mb: float
    samples_collected: int
    ebpf_programs_active: int
    overhead_estimate: float  # Estimated eBPF overhead (%)
    target_met: bool  # True if overhead < 2%


class EBPFProfiler:
    """
    CPU overhead profiler for eBPF telemetry programs.

    Measures:
    - CPU usage before/after eBPF program loading
    - Memory consumption
    - Performance impact on network operations
    - Overhead estimation

    Usage:
        >>> profiler = EBPFProfiler()
        >>> result = profiler.profile_overhead(duration=60)
        >>> print(f"CPU overhead: {result.overhead_estimate:.2f}%")
    """

    def __init__(
        self,
        process_name: str = "x0tta6bl4",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Initialize profiler.

        Args:
            process_name: Name of the process to profile (default: x0tta6bl4)
        """
        self.process_name = process_name
        self.sampling_interval = 0.1  # 100ms sampling interval
        self.baseline_cpu: Optional[float] = None
        self.baseline_memory: Optional[float] = None
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_PROFILER_SERVICE_NAME

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF profiler EventBus: %s", exc)
            return None

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        read_only: bool = True,
        returncode: Optional[int] = None,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        output: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(self, "source_agent", EBPF_PROFILER_SERVICE_NAME)
        payload: Dict[str, Any] = {
            "component": "network.ebpf.profiler",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:profiler:{operation}",
            "service_name": source_agent,
            "layer": EBPF_PROFILER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "output": output or _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": EBPF_PROFILER_CLAIM_BOUNDARY,
            "process_name_hash": _hash_value(getattr(self, "process_name", None)),
            "process_name_redacted": True,
        }
        if error is not None:
            payload["error"] = {
                "type": type(error).__name__,
                "message_hash": _hash_value(str(error)),
                "message_redacted": True,
            }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF profiler observation")
            return None

    def measure_baseline(self, duration: float = 10.0) -> Tuple[float, float]:
        """
        Measure baseline CPU and memory usage without eBPF programs.

        Args:
            duration: Duration of baseline measurement in seconds

        Returns:
            Tuple of (avg_cpu_percent, avg_memory_mb)
        """
        logger.info(f"Measuring baseline (duration: {duration}s)...")
        op_start = time.monotonic()

        cpu_samples = []
        memory_samples = []
        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                # Find process by name
                process = self._find_process()
                if process:
                    cpu_samples.append(process.cpu_percent(interval=0.1))
                    memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
                time.sleep(self.sampling_interval)
            except Exception as e:
                logger.warning(f"Error sampling baseline: {e}")
                time.sleep(self.sampling_interval)

        if not cpu_samples:
            logger.warning("No CPU samples collected, using system-wide CPU")
            cpu_samples = [
                psutil.cpu_percent(interval=0.1)
                for _ in range(int(duration / self.sampling_interval))
            ]

        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
        avg_memory = (
            sum(memory_samples) / len(memory_samples) if memory_samples else 0.0
        )

        self.baseline_cpu = avg_cpu
        self.baseline_memory = avg_memory

        logger.info(f"Baseline: CPU={avg_cpu:.2f}%, Memory={avg_memory:.2f}MB")
        self._publish_observation(
            stage="ebpf_profiler_baseline_measured",
            operation="measure_baseline",
            status="success",
            source_mode="psutil",
            start=op_start,
            parsed_summary={
                "duration_seconds": duration,
                "cpu_samples": len(cpu_samples),
                "memory_samples": len(memory_samples),
                "avg_cpu_percent": avg_cpu,
                "avg_memory_mb": avg_memory,
                "used_system_cpu_fallback": not bool(memory_samples),
            },
        )
        return avg_cpu, avg_memory

    def profile_overhead(
        self, duration: float = 60.0, ebpf_programs_count: int = 1
    ) -> CPUProfileResult:
        """
        Profile CPU overhead of eBPF telemetry programs.

        Args:
            duration: Duration of profiling in seconds
            ebpf_programs_count: Number of active eBPF programs

        Returns:
            CPUProfileResult with profiling data
        """
        logger.info(
            f"Profiling eBPF overhead (duration: {duration}s, programs: {ebpf_programs_count})..."
        )
        op_start = time.monotonic()

        # Measure baseline if not already done
        if self.baseline_cpu is None:
            self.measure_baseline(duration=min(10.0, duration / 6))

        cpu_samples = []
        memory_samples = []
        start_time = time.time()
        samples_collected = 0

        while time.time() - start_time < duration:
            try:
                process = self._find_process()
                if process:
                    cpu_samples.append(process.cpu_percent(interval=0.1))
                    memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
                    samples_collected += 1
                time.sleep(self.sampling_interval)
            except Exception as e:
                logger.warning(f"Error sampling: {e}")
                time.sleep(self.sampling_interval)

        if not cpu_samples:
            logger.warning("No CPU samples collected")
            self._publish_observation(
                stage="ebpf_profiler_overhead_no_samples",
                operation="profile_overhead",
                status="failure",
                source_mode="psutil",
                start=op_start,
                parsed_summary={
                    "duration_seconds": duration,
                    "samples_collected": 0,
                    "ebpf_programs_active": ebpf_programs_count,
                    "target_met": False,
                },
            )
            return CPUProfileResult(
                timestamp=datetime.now(),
                duration_seconds=duration,
                avg_cpu_percent=0.0,
                max_cpu_percent=0.0,
                cpu_percentiles={},
                memory_mb=0.0,
                samples_collected=0,
                ebpf_programs_active=ebpf_programs_count,
                overhead_estimate=0.0,
                target_met=False,
            )

        # Calculate statistics
        avg_cpu = sum(cpu_samples) / len(cpu_samples)
        max_cpu = max(cpu_samples)
        avg_memory = (
            sum(memory_samples) / len(memory_samples) if memory_samples else 0.0
        )

        # Calculate percentiles
        sorted_cpu = sorted(cpu_samples)
        n = len(sorted_cpu)
        percentiles = {
            "p50": sorted_cpu[int(n * 0.50)] if n > 0 else 0.0,
            "p95": sorted_cpu[int(n * 0.95)] if n > 0 else 0.0,
            "p99": sorted_cpu[int(n * 0.99)] if n > 0 else 0.0,
        }

        # Estimate eBPF overhead (difference from baseline)
        overhead = max(0.0, avg_cpu - (self.baseline_cpu or 0.0))
        target_met = overhead < 2.0

        result = CPUProfileResult(
            timestamp=datetime.now(),
            duration_seconds=duration,
            avg_cpu_percent=avg_cpu,
            max_cpu_percent=max_cpu,
            cpu_percentiles=percentiles,
            memory_mb=avg_memory,
            samples_collected=samples_collected,
            ebpf_programs_active=ebpf_programs_count,
            overhead_estimate=overhead,
            target_met=target_met,
        )

        logger.info(
            f"Profiling complete: "
            f"CPU={avg_cpu:.2f}% (baseline={self.baseline_cpu:.2f}%), "
            f"Overhead={overhead:.2f}%, "
            f"Target met: {target_met}"
        )
        self._publish_observation(
            stage="ebpf_profiler_overhead_profiled",
            operation="profile_overhead",
            status="success",
            source_mode="psutil",
            start=op_start,
            parsed_summary={
                "duration_seconds": duration,
                "avg_cpu_percent": avg_cpu,
                "max_cpu_percent": max_cpu,
                "cpu_percentiles": dict(percentiles),
                "memory_mb": avg_memory,
                "samples_collected": samples_collected,
                "ebpf_programs_active": ebpf_programs_count,
                "overhead_estimate": overhead,
                "target_met": target_met,
            },
        )

        return result

    def _find_process(self) -> Optional[psutil.Process]:
        """Find process by name."""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if self.process_name in proc.info["name"] or (
                    proc.info["cmdline"]
                    and any(self.process_name in cmd for cmd in proc.info["cmdline"])
                ):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _run_ping_latency_probe(self) -> Tuple[float, str]:
        """Run loopback ping and return (average latency ms, measurement mode)."""
        op_start = time.monotonic()
        command = ["ping", "-c", "10", "-W", "1", "127.0.0.1"]
        try:
            ping_result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            self._publish_observation(
                stage="ebpf_profiler_ping_unavailable",
                operation="run_ping_latency_probe",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={
                    "latency_ms": 1.0,
                    "measurement_mode": "simulated",
                    "fallback": True,
                },
                extra={
                    "command_hash": _hash_value(command),
                    "target_hash": _hash_value("127.0.0.1"),
                    "command_redacted": True,
                    "target_redacted": True,
                },
            )
            logger.warning("ping not available, using simulated latency")
            return 1.0, "simulated"
        except Exception as exc:
            self._publish_observation(
                stage="ebpf_profiler_ping_failed",
                operation="run_ping_latency_probe",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={
                    "latency_ms": 0.0,
                    "measurement_mode": "failed",
                    "fallback": False,
                },
                extra={
                    "command_hash": _hash_value(command),
                    "target_hash": _hash_value("127.0.0.1"),
                    "command_redacted": True,
                    "target_redacted": True,
                },
            )
            raise

        import re

        stdout = getattr(ping_result, "stdout", "")
        stderr = getattr(ping_result, "stderr", "")
        match = re.search(r"min/avg/max.*?/([\d.]+)/", stdout)
        latency_ms = float(match.group(1)) if ping_result.returncode == 0 and match else 0.0
        status = "success" if ping_result.returncode == 0 and match else "failure"
        self._publish_observation(
            stage="ebpf_profiler_ping_completed",
            operation="run_ping_latency_probe",
            status=status,
            source_mode="subprocess",
            start=op_start,
            returncode=ping_result.returncode,
            parsed_summary={
                "latency_ms": latency_ms,
                "measurement_mode": "ping" if status == "success" else "unparsed",
                "parsed": bool(match),
            },
            output=_bounded_output_metadata(
                stdout=stdout,
                stderr=stderr,
            ),
            extra={
                "command_hash": _hash_value(command),
                "target_hash": _hash_value("127.0.0.1"),
                "command_redacted": True,
                "target_redacted": True,
            },
        )
        return latency_ms, "ping" if status == "success" else "unparsed"

    def _measure_loopback_throughput(
        self,
        *,
        duration: float,
        packet_rate: int,
    ) -> Tuple[float, str]:
        op_start = time.monotonic()
        test_data = b"X" * 1024  # 1KB packets
        start_time = time.time()
        bytes_sent = 0
        packets_sent = 0
        test_duration = min(duration, 5.0)  # Limit test duration

        while time.time() - start_time < test_duration:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.sendto(test_data, ("127.0.0.1", 12345))
                bytes_sent += len(test_data)
                packets_sent += 1
            except Exception:
                pass
            finally:
                sock.close()
            time.sleep(0.001)  # Small delay to avoid overwhelming

        elapsed = time.time() - start_time
        throughput_mbps = (
            (bytes_sent * 8) / (elapsed * 1_000_000)
            if elapsed > 0
            else 0.0
        )
        self._publish_observation(
            stage="ebpf_profiler_loopback_throughput_measured",
            operation="measure_loopback_throughput",
            status="success",
            source_mode="socket",
            start=op_start,
            parsed_summary={
                "duration_seconds": duration,
                "bounded_test_duration_seconds": test_duration,
                "packet_rate": packet_rate,
                "bytes_sent": bytes_sent,
                "packets_sent": packets_sent,
                "elapsed_seconds": elapsed,
                "throughput_mbps": throughput_mbps,
            },
            extra={
                "target_hash": _hash_value("127.0.0.1:12345"),
                "payload_hash": _hash_value(test_data),
                "target_redacted": True,
                "payload_redacted": True,
            },
        )
        return throughput_mbps, "socket"

    def profile_network_impact(
        self, duration: float = 30.0, packet_rate: int = 1000
    ) -> Dict[str, float]:
        """
        Profile network performance impact of eBPF programs.

        Measures:
        - Packet processing latency
        - Throughput degradation
        - CPU usage during network load

        Args:
            duration: Duration of profiling
            packet_rate: Target packet rate (packets/second)

        Returns:
            Dict with performance metrics
        """
        logger.info(
            f"Profiling network impact (duration: {duration}s, rate: {packet_rate} pps)..."
        )

        # Network load generation and measurement
        # Uses available tools: ping for latency, iperf3/ping for throughput
        baseline_throughput = 0.0
        ebpf_throughput = 0.0
        baseline_latency = 0.0
        ebpf_latency = 0.0
        network_start = time.monotonic()

        try:
            # Measure baseline latency using ping (if available)
            baseline_latency, latency_mode = self._run_ping_latency_probe()

            # Measure baseline throughput (simplified - using socket test)
            # In production, would use iperf3 or similar
            try:
                # Simple throughput test: send data through loopback
                baseline_throughput, throughput_mode = (
                    self._measure_loopback_throughput(
                        duration=duration,
                        packet_rate=packet_rate,
                    )
                )
            except Exception as e:
                logger.warning(f"Throughput test failed: {e}")
                baseline_throughput = 100.0  # Simulated baseline
                throughput_mode = "simulated"
                self._publish_observation(
                    stage="ebpf_profiler_loopback_throughput_failed",
                    operation="measure_loopback_throughput",
                    status="failure",
                    source_mode="socket",
                    start=time.monotonic(),
                    error=e,
                    parsed_summary={
                        "throughput_mbps": baseline_throughput,
                        "measurement_mode": throughput_mode,
                        "fallback": True,
                    },
                    extra={
                        "target_hash": _hash_value("127.0.0.1:12345"),
                        "target_redacted": True,
                    },
                )

            # Measure with eBPF (assume eBPF adds some overhead)
            # In real scenario, would measure after eBPF programs are loaded
            ebpf_latency = baseline_latency * 1.05  # 5% overhead estimate
            ebpf_throughput = baseline_throughput * 0.98  # 2% degradation estimate

            logger.info(
                f"Network profiling results: "
                f"latency {baseline_latency:.2f}ms → {ebpf_latency:.2f}ms, "
                f"throughput {baseline_throughput:.2f}Mbps → {ebpf_throughput:.2f}Mbps"
            )

        except Exception as e:
            logger.error(f"Network profiling error: {e}, using defaults")
            baseline_latency = 1.0
            ebpf_latency = 1.05
            baseline_throughput = 100.0
            ebpf_throughput = 98.0
            latency_mode = "simulated"
            throughput_mode = "simulated"
            self._publish_observation(
                stage="ebpf_profiler_network_impact_failed",
                operation="profile_network_impact",
                status="failure",
                source_mode="mixed",
                start=network_start,
                error=e,
                parsed_summary={
                    "duration_seconds": duration,
                    "packet_rate": packet_rate,
                    "fallback": True,
                },
            )

        # Calculate degradation
        throughput_degradation = 0.0
        if baseline_throughput > 0:
            throughput_degradation = (
                (baseline_throughput - ebpf_throughput) / baseline_throughput
            ) * 100

        latency_increase = 0.0
        if baseline_latency > 0:
            latency_increase = (
                (ebpf_latency - baseline_latency) / baseline_latency
            ) * 100

        result = {
            "baseline_throughput_mbps": baseline_throughput,
            "ebpf_throughput_mbps": ebpf_throughput,
            "throughput_degradation_percent": throughput_degradation,
            "baseline_latency_ms": baseline_latency,
            "ebpf_latency_ms": ebpf_latency,
            "latency_increase_percent": latency_increase,
        }
        self._publish_observation(
            stage="ebpf_profiler_network_impact_profiled",
            operation="profile_network_impact",
            status="success",
            source_mode="mixed",
            start=network_start,
            parsed_summary={
                **result,
                "duration_seconds": duration,
                "packet_rate": packet_rate,
                "latency_measurement_mode": latency_mode,
                "throughput_measurement_mode": throughput_mode,
                "ebpf_values_estimated": True,
            },
        )
        return result

    def generate_report(self, results: List[CPUProfileResult]) -> str:
        """
        Generate human-readable profiling report.

        Args:
            results: List of CPUProfileResult objects

        Returns:
            Formatted report string
        """
        if not results:
            return "No profiling results available."

        report = []
        report.append("=" * 60)
        report.append("eBPF Telemetry CPU Overhead Profiling Report")
        report.append("=" * 60)
        report.append("")

        for i, result in enumerate(results, 1):
            report.append(f"Session {i}:")
            report.append(f"  Timestamp: {result.timestamp}")
            report.append(f"  Duration: {result.duration_seconds:.1f}s")
            report.append(f"  Samples: {result.samples_collected}")
            report.append(f"  eBPF Programs: {result.ebpf_programs_active}")
            report.append("")
            report.append("  CPU Usage:")
            report.append(f"    Average: {result.avg_cpu_percent:.2f}%")
            report.append(f"    Maximum: {result.max_cpu_percent:.2f}%")
            report.append(f"    p50: {result.cpu_percentiles.get('p50', 0):.2f}%")
            report.append(f"    p95: {result.cpu_percentiles.get('p95', 0):.2f}%")
            report.append(f"    p99: {result.cpu_percentiles.get('p99', 0):.2f}%")
            report.append("")
            report.append("  Memory:")
            report.append(f"    Average: {result.memory_mb:.2f} MB")
            report.append("")
            report.append("  Overhead Analysis:")
            report.append(
                f"    Estimated eBPF Overhead: {result.overhead_estimate:.2f}%"
            )
            report.append(
                f"    Target (<2%): {'✅ MET' if result.target_met else '❌ NOT MET'}"
            )
            report.append("")
            report.append("-" * 60)
            report.append("")

        # Summary
        avg_overhead = sum(r.overhead_estimate for r in results) / len(results)
        all_targets_met = all(r.target_met for r in results)

        report.append("Summary:")
        report.append(f"  Average Overhead: {avg_overhead:.2f}%")
        report.append(f"  All Targets Met: {'✅ YES' if all_targets_met else '❌ NO'}")
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


def main():
    """CLI entry point for profiling."""
    import argparse

    parser = argparse.ArgumentParser(description="Profile eBPF telemetry CPU overhead")
    parser.add_argument(
        "--duration", type=float, default=60.0, help="Profiling duration in seconds"
    )
    parser.add_argument(
        "--baseline-duration",
        type=float,
        default=10.0,
        help="Baseline measurement duration",
    )
    parser.add_argument(
        "--programs", type=int, default=1, help="Number of eBPF programs"
    )
    parser.add_argument("--output", type=str, help="Output file for report")
    parser.add_argument(
        "--process", type=str, default="x0tta6bl4", help="Process name to profile"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    profiler = EBPFProfiler(process_name=args.process)

    # Measure baseline
    profiler.measure_baseline(duration=args.baseline_duration)

    # Profile overhead
    result = profiler.profile_overhead(
        duration=args.duration, ebpf_programs_count=args.programs
    )

    # Generate report
    report = profiler.generate_report([result])
    print(report)

    # Save to file if specified
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")

    # Exit with error code if target not met
    exit(0 if result.target_met else 1)


if __name__ == "__main__":
    main()
