#!/usr/bin/env python3
"""
x0tta6bl4 BCC eBPF Probes for Network Metrics
Provides latency and congestion monitoring for mesh networking

Requirements:
- bcc (pip install bcc)
- prometheus_client (for metrics export)

Usage:
    python bcc_probes.py --interface eth0 --prometheus-port 9090
"""

import argparse
import hashlib
import logging
import signal
import sys
import time
from typing import Any, Dict, List, Optional

try:
    from bcc import BPF
except ImportError:
    BPF = None  # type: ignore

from prometheus_client import REGISTRY, Counter, Gauge, start_http_server

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BCC_PROBES_SERVICE_NAME = "ebpf-bcc-probes"
BCC_PROBES_LAYER = "network_ebpf_bcc_probes_observed_state"
BCC_PROBES_CLAIM_BOUNDARY = (
    "Local BCC probe evidence only. Events record local Prometheus startup, "
    "BCC/BPF source load attempts, trace_read polling, parsed latency and queue "
    "samples, metric snapshots, and cleanup with hashed interface/program/output "
    "selectors; they do not prove production traffic volume, remote peer identity, "
    "latency correctness, or sustained kernel datapath enforcement."
)

def _registered_metric(name: str):
    base_name = name[:-6] if name.endswith("_total") else name
    candidate_names = {
        name,
        base_name,
        f"{base_name}_total",
        f"{base_name}_created",
    }
    for candidate in candidate_names:
        collector = REGISTRY._names_to_collectors.get(candidate)
        if collector is not None:
            return collector
    for collector in set(REGISTRY._names_to_collectors.values()):
        if getattr(collector, "_name", None) in {name, base_name}:
            return collector
    return None


def _get_or_create_metric(metric_class, name: str, description: str, labels: List[str]):
    existing = _registered_metric(name)
    if existing is not None:
        return existing
    try:
        return metric_class(name, description, labels)
    except ValueError:
        existing = _registered_metric(name)
        if existing is not None:
            return existing
        raise


# Prometheus metrics
PACKET_LATENCY = _get_or_create_metric(
    Gauge,
    "mesh_packet_latency_ns", "Packet latency in nanoseconds", ["interface"]
)
QUEUE_CONGESTION = _get_or_create_metric(
    Gauge,
    "mesh_queue_congestion", "Queue congestion level", ["interface"]
)
PACKET_DROPS = _get_or_create_metric(
    Counter,
    "mesh_packet_drops_total", "Total packet drops", ["interface", "reason"]
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
    identity = service_event_identity(service_name=BCC_PROBES_SERVICE_NAME)
    return {
        "service_name": BCC_PROBES_SERVICE_NAME,
        "layer": BCC_PROBES_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [_hash_value(value) for value in selected],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


class MeshNetworkProbes:
    def __init__(
        self,
        interface: str,
        prometheus_port: int = 9090,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        start_prometheus_server: bool = True,
    ):
        self.interface = interface
        self.prometheus_port = prometheus_port
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = BCC_PROBES_SERVICE_NAME
        self.running = False
        self.latency_bpf = None
        self.congestion_bpf = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="monitoring",
            capabilities=("security", "zero-trust"),
            extra_techniques=("mape_k", "causal_analysis", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        # Current metrics
        self.current_latency = 0.0
        self.current_congestion = 0.0

        # Start Prometheus server
        if start_prometheus_server:
            op_start = time.monotonic()
            try:
                start_http_server(prometheus_port)
            except Exception as exc:
                self._publish_observation(
                    stage="bcc_probes_prometheus_start_failed",
                    operation="start_prometheus_server",
                    status="failure",
                    source_mode="prometheus",
                    start=op_start,
                    read_only=False,
                    returncode=1,
                    error=exc,
                    parsed_summary={"started": False},
                )
                raise
            self._publish_observation(
                stage="bcc_probes_prometheus_started",
                operation="start_prometheus_server",
                status="success",
                source_mode="prometheus",
                start=op_start,
                read_only=False,
                returncode=0,
                parsed_summary={"started": True, "prometheus_port": prometheus_port},
            )
            logger.info(f"Prometheus metrics on port {prometheus_port}")
        else:
            self._publish_observation(
                stage="bcc_probes_prometheus_disabled",
                operation="start_prometheus_server",
                status="success",
                source_mode="prometheus",
                start=time.monotonic(),
                parsed_summary={"started": False, "reason": "disabled"},
            )

        # Load eBPF programs
        self.load_latency_probe()
        self.load_congestion_probe()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize BCC probes EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            coach = AgentThinkingCoach(
                agent_id=getattr(self, "source_agent", BCC_PROBES_SERVICE_NAME),
                role="monitoring",
                capabilities=("security", "zero-trust"),
                extra_techniques=("mape_k", "causal_analysis", "chaos_driven_design"),
            )
            self.thinking_coach = coach
        return coach

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_bcc_probe_observation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local BCC probe evidence, redacted selectors, "
                "hashes, counts, and bounded metadata; do not expose interface "
                "names, BPF source, trace lines, stdout, or stderr."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose BCC probe thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

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
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(self, "source_agent", BCC_PROBES_SERVICE_NAME)
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "interface_hash": _hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.bcc_probes",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:bcc_probes:{operation}",
            "service_name": source_agent,
            "layer": BCC_PROBES_LAYER,
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
            "thinking": thinking,
            "output": _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": BCC_PROBES_CLAIM_BOUNDARY,
            "interface_hash": _hash_value(getattr(self, "interface", None)),
            "interface_redacted": True,
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
            logger.exception("Failed to publish BCC probe observation")
            return None

    def load_latency_probe(self):
        """Load eBPF program for packet latency measurement"""
        op_start = time.monotonic()
        bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>

BPF_HASH(start_time, u64, u64);  // packet_id -> start_time

// Ingress hook
SEC("tracepoint/net/netif_receive_skb")
int ingress_latency(struct trace_event_raw_netif_receive_skb *ctx) {
    u64 packet_id = bpf_ktime_get_ns();  // Simple ID
    u64 ts = packet_id;
    start_time.update(&packet_id, &ts);
    return 0;
}

// Egress hook
SEC("tracepoint/net/net_dev_xmit")
int egress_latency(struct trace_event_raw_net_dev_template *ctx) {
    u64 packet_id = bpf_ktime_get_ns();  // Match with ingress
    u64 *start = start_time.lookup(&packet_id);
    if (start) {
        u64 latency = packet_id - *start;
        // Output latency (in userspace we'll read this)
        bpf_trace_printk("latency: %llu\\n", latency);
        start_time.delete(&packet_id);
    }
    return 0;
}
"""

        if BPF is None:
            self._publish_observation(
                stage="bcc_latency_probe_bcc_unavailable",
                operation="load_latency_probe",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                parsed_summary={"loaded": False, "reason": "bcc_unavailable"},
                extra={
                    "program_name_hash": _hash_value("latency_probe"),
                    "program_name_redacted": True,
                    "bpf_source_hash": _hash_value(bpf_text),
                    "bpf_source_chars": len(bpf_text),
                    "bpf_source_redacted": True,
                },
            )
            return False

        try:
            self.latency_bpf = BPF(text=bpf_text)
        except Exception as exc:
            self._publish_observation(
                stage="bcc_latency_probe_load_failed",
                operation="load_latency_probe",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                error=exc,
                parsed_summary={"loaded": False},
                extra={
                    "program_name_hash": _hash_value("latency_probe"),
                    "program_name_redacted": True,
                    "bpf_source_hash": _hash_value(bpf_text),
                    "bpf_source_chars": len(bpf_text),
                    "bpf_source_redacted": True,
                },
            )
            raise

        self._publish_observation(
            stage="bcc_latency_probe_loaded",
            operation="load_latency_probe",
            status="success",
            source_mode="bcc",
            start=op_start,
            read_only=False,
            returncode=0,
            parsed_summary={"loaded": True},
            extra={
                "program_name_hash": _hash_value("latency_probe"),
                "program_name_redacted": True,
                "bpf_source_hash": _hash_value(bpf_text),
                "bpf_source_chars": len(bpf_text),
                "bpf_source_redacted": True,
            },
        )
        logger.info("Loaded latency probe")
        return True

    def load_congestion_probe(self):
        """Load eBPF program for queue congestion monitoring"""
        op_start = time.monotonic()
        bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/netdevice.h>

BPF_HASH(queue_len, u32, u32);  // ifindex -> queue length

SEC("kprobe/dev_queue_xmit")
int queue_congestion(struct pt_regs *ctx) {
    struct net_device *dev = (struct net_device *)PT_REGS_PARM1(ctx);
    u32 ifindex = dev->ifindex;
    u32 qlen = dev->qdisc->q.qlen;  // Queue length
    queue_len.update(&ifindex, &qlen);
    bpf_trace_printk("queue_len ifindex=%u len=%u\\n", ifindex, qlen);
    return 0;
}
"""

        if BPF is None:
            self._publish_observation(
                stage="bcc_congestion_probe_bcc_unavailable",
                operation="load_congestion_probe",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                parsed_summary={"loaded": False, "reason": "bcc_unavailable"},
                extra={
                    "program_name_hash": _hash_value("congestion_probe"),
                    "program_name_redacted": True,
                    "bpf_source_hash": _hash_value(bpf_text),
                    "bpf_source_chars": len(bpf_text),
                    "bpf_source_redacted": True,
                },
            )
            return False

        try:
            self.congestion_bpf = BPF(text=bpf_text)
        except Exception as exc:
            self._publish_observation(
                stage="bcc_congestion_probe_load_failed",
                operation="load_congestion_probe",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                error=exc,
                parsed_summary={"loaded": False},
                extra={
                    "program_name_hash": _hash_value("congestion_probe"),
                    "program_name_redacted": True,
                    "bpf_source_hash": _hash_value(bpf_text),
                    "bpf_source_chars": len(bpf_text),
                    "bpf_source_redacted": True,
                },
            )
            raise

        self._publish_observation(
            stage="bcc_congestion_probe_loaded",
            operation="load_congestion_probe",
            status="success",
            source_mode="bcc",
            start=op_start,
            read_only=False,
            returncode=0,
            parsed_summary={"loaded": True},
            extra={
                "program_name_hash": _hash_value("congestion_probe"),
                "program_name_redacted": True,
                "bpf_source_hash": _hash_value(bpf_text),
                "bpf_source_chars": len(bpf_text),
                "bpf_source_redacted": True,
            },
        )
        logger.info("Loaded congestion probe")
        return True

    @staticmethod
    def _parse_latency_event(event: Any) -> Optional[int]:
        event_text = _normalize_text(event)
        if "latency:" not in event_text:
            return None
        try:
            return int(event_text.split("latency:", 1)[1].strip().split()[0])
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _parse_congestion_event(event: Any) -> Optional[int]:
        event_text = _normalize_text(event)
        if "queue_len" not in event_text:
            return None
        try:
            for part in event_text.split():
                if part.startswith("len="):
                    return int(part.split("=", 1)[1])
        except (IndexError, TypeError, ValueError):
            return None
        return None

    def _trace_events(self, bpf_obj: Any, probe_name: str) -> List[Any]:
        op_start = time.monotonic()
        if bpf_obj is None:
            return []
        try:
            return list(bpf_obj.trace_read())
        except Exception as exc:
            self._publish_observation(
                stage="bcc_probe_trace_read_failed",
                operation="trace_read",
                status="failure",
                source_mode="bcc",
                start=op_start,
                returncode=1,
                error=exc,
                parsed_summary={"probe": probe_name, "events_read": 0},
                extra={
                    "program_name_hash": _hash_value(probe_name),
                    "program_name_redacted": True,
                },
            )
            return []

    def poll_once(self) -> Dict[str, int]:
        """Read one batch of trace output and update local Prometheus metrics."""
        op_start = time.monotonic()
        latency_events = self._trace_events(self.latency_bpf, "latency_probe")
        congestion_events = self._trace_events(
            self.congestion_bpf,
            "congestion_probe",
        )
        trace_lines = [_normalize_text(event) for event in latency_events]
        trace_lines.extend(_normalize_text(event) for event in congestion_events)

        latency_parsed = 0
        congestion_parsed = 0
        parse_errors = 0

        for event in latency_events:
            latency_ns = self._parse_latency_event(event)
            if latency_ns is None:
                parse_errors += 1
                continue
            PACKET_LATENCY.labels(interface=self.interface).set(latency_ns)
            self.current_latency = latency_ns
            latency_parsed += 1

        for event in congestion_events:
            qlen = self._parse_congestion_event(event)
            if qlen is None:
                parse_errors += 1
                continue
            QUEUE_CONGESTION.labels(interface=self.interface).set(qlen)
            self.current_congestion = qlen
            congestion_parsed += 1

        events_read = len(latency_events) + len(congestion_events)
        both_missing = self.latency_bpf is None and self.congestion_bpf is None
        summary = {
            "latency_events_read": len(latency_events),
            "congestion_events_read": len(congestion_events),
            "events_read": events_read,
            "latency_events_parsed": latency_parsed,
            "congestion_events_parsed": congestion_parsed,
            "parse_errors": parse_errors,
            "latency_bpf_available": self.latency_bpf is not None,
            "congestion_bpf_available": self.congestion_bpf is not None,
        }
        self._publish_observation(
            stage=(
                "bcc_probes_trace_poll_skipped_no_bpf"
                if both_missing
                else "bcc_probes_trace_poll_completed"
            ),
            operation="poll_once",
            status="success" if parse_errors == 0 else "partial",
            source_mode="bcc",
            start=op_start,
            returncode=0 if parse_errors == 0 else 1,
            parsed_summary=summary,
            extra={
                "output": _bounded_output_metadata(stdout="\n".join(trace_lines)),
                "trace_line_hashes": _bounded_hashes(trace_lines),
                "trace_lines_redacted": True,
            },
        )
        return summary

    def run(self):
        """Main monitoring loop"""
        op_start = time.monotonic()
        logger.info("Starting mesh network probes...")
        if self.latency_bpf is None and self.congestion_bpf is None:
            self._publish_observation(
                stage="bcc_probes_run_skipped_no_bpf",
                operation="run",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                parsed_summary={"running": False, "reason": "bpf_uninitialized"},
            )
            return

        self.running = True
        self._publish_observation(
            stage="bcc_probes_run_started",
            operation="run",
            status="success",
            source_mode="bcc",
            start=op_start,
            read_only=False,
            returncode=0,
            parsed_summary={"running": True},
        )

        try:
            while self.running:
                self.poll_once()

                time.sleep(1)  # Poll every second

        except KeyboardInterrupt:
            logger.info("Stopping probes...")
            self.cleanup()
        except Exception as exc:
            self._publish_observation(
                stage="bcc_probes_run_failed",
                operation="run",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                returncode=1,
                error=exc,
                parsed_summary={"running": self.running},
            )
            raise

    def get_current_metrics(self) -> Dict[str, float]:
        """Get current metrics snapshot"""
        # Note: In real implementation, these would be thread-safe shared variables
        op_start = time.monotonic()
        metrics = {
            "avg_latency_ns": getattr(self, "current_latency", 0),
            "queue_congestion": getattr(self, "current_congestion", 0),
        }
        self._publish_observation(
            stage="bcc_probes_metrics_snapshot_read",
            operation="get_current_metrics",
            status="success",
            source_mode="memory",
            start=op_start,
            returncode=0,
            parsed_summary=dict(metrics),
        )
        return metrics

    def cleanup(self):
        """Clean up eBPF programs"""
        op_start = time.monotonic()
        self.running = False
        cleaned: List[str] = []
        skipped: List[str] = []
        for attr_name, probe_name in (
            ("latency_bpf", "latency_probe"),
            ("congestion_bpf", "congestion_probe"),
        ):
            bpf_obj = getattr(self, attr_name, None)
            if bpf_obj is None:
                skipped.append(probe_name)
                continue
            try:
                bpf_obj.cleanup()
            except Exception as exc:
                self._publish_observation(
                    stage="bcc_probe_cleanup_failed",
                    operation="cleanup",
                    status="failure",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    returncode=1,
                    error=exc,
                    parsed_summary={
                        "cleanup": False,
                        "cleaned_count": len(cleaned),
                        "skipped_count": len(skipped),
                    },
                    extra={
                        "program_name_hash": _hash_value(probe_name),
                        "program_name_redacted": True,
                    },
                )
                raise
            cleaned.append(probe_name)

        self._publish_observation(
            stage="bcc_probes_cleanup_completed",
            operation="cleanup",
            status="success",
            source_mode="bcc",
            start=op_start,
            read_only=False,
            returncode=0,
            parsed_summary={
                "cleanup": True,
                "cleaned_count": len(cleaned),
                "skipped_count": len(skipped),
            },
            extra={
                "cleaned_program_hashes": _bounded_hashes(cleaned),
                "skipped_program_hashes": _bounded_hashes(skipped),
                "program_names_redacted": True,
            },
        )


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Network eBPF Probes")
    parser.add_argument(
        "--interface", "-i", required=True, help="Network interface to monitor"
    )
    parser.add_argument(
        "--prometheus-port",
        "-p",
        type=int,
        default=9090,
        help="Prometheus metrics port",
    )

    args = parser.parse_args()

    probes = MeshNetworkProbes(args.interface, args.prometheus_port)

    def signal_handler(sig, frame):
        probes.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    probes.run()


if __name__ == "__main__":
    main()
