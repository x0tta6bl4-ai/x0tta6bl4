"""
Extended Prometheus metrics for ML, DAO, and eBPF components.

Expands on the base prometheus_metrics.py with specialized metrics for:
- ML Model Performance (GraphSAGE, LoRA, RAG)
- DAO Governance (Voting, Proposals, Quadratic Voting)
- eBPF Network Programs (Compilation, Execution, Telemetry)
"""

import logging
from typing import Optional

from prometheus_client import (CollectorRegistry, Counter, Gauge, Histogram,
                               Summary)

logger = logging.getLogger(__name__)

# Global registry for extended metrics
_extended_registry = None


def get_extended_registry():
    """Get or create the extended metrics registry."""
    global _extended_registry
    if _extended_registry is None:
        _extended_registry = CollectorRegistry()
    return _extended_registry


# ============================================================================
# ML METRICS: GraphSAGE Anomaly Detection
# ============================================================================

graphsage_inference_latency_ms = Histogram(
    "x0tta6bl4_graphsage_inference_latency_ms",
    "GraphSAGE anomaly detection inference latency in milliseconds",
    buckets=(5, 10, 25, 50, 100, 250),
    registry=get_extended_registry(),
)
"""Inference latency for anomaly detection."""

graphsage_anomalies_detected_total = Counter(
    "x0tta6bl4_graphsage_anomalies_detected_total",
    "Total anomalies detected by GraphSAGE",
    labelnames=["severity", "anomaly_type"],
    registry=get_extended_registry(),
)
"""Track detected anomalies by severity and type."""

graphsage_model_accuracy = Gauge(
    "x0tta6bl4_graphsage_model_accuracy",
    "Current GraphSAGE model accuracy percentage",
    labelnames=["model_version"],
    registry=get_extended_registry(),
)
"""Current model accuracy."""

graphsage_false_positive_rate = Gauge(
    "x0tta6bl4_graphsage_false_positive_rate",
    "GraphSAGE false positive rate percentage",
    labelnames=["model_version"],
    registry=get_extended_registry(),
)
"""FPR for anomaly detection."""

graphsage_model_size_mb = Gauge(
    "x0tta6bl4_graphsage_model_size_mb",
    "GraphSAGE model size in megabytes",
    labelnames=["quantization_type"],
    registry=get_extended_registry(),
)
"""Model size (FP32, INT8 quantized, etc)."""

graphsage_predictions_per_second = Gauge(
    "x0tta6bl4_graphsage_predictions_per_second",
    "Predictions per second throughput",
    labelnames=["node_id"],
    registry=get_extended_registry(),
)
"""Inference throughput."""


# ============================================================================
# ML METRICS: LoRA Fine-Tuning
# ============================================================================

lora_training_loss = Gauge(
    "x0tta6bl4_lora_training_loss",
    "LoRA adapter training loss",
    labelnames=["adapter_name", "model_name"],
    registry=get_extended_registry(),
)
"""Current training loss."""

lora_training_epochs_total = Counter(
    "x0tta6bl4_lora_training_epochs_total",
    "Total LoRA training epochs completed",
    labelnames=["adapter_name"],
    registry=get_extended_registry(),
)
"""Epochs completed."""

lora_adapter_rank = Gauge(
    "x0tta6bl4_lora_adapter_rank",
    "LoRA adapter rank dimension",
    labelnames=["adapter_name"],
    registry=get_extended_registry(),
)
"""Rank used for low-rank decomposition."""

lora_parameters_count = Gauge(
    "x0tta6bl4_lora_parameters_count",
    "Number of trainable parameters in LoRA adapter",
    labelnames=["adapter_name"],
    registry=get_extended_registry(),
)
"""Trainable parameters (should be much less than full model)."""

lora_inference_speedup = Gauge(
    "x0tta6bl4_lora_inference_speedup",
    "Inference speedup compared to full model retraining",
    labelnames=["adapter_name"],
    registry=get_extended_registry(),
)
"""Performance improvement multiplier."""


# ============================================================================
# ML METRICS: RAG Pipeline
# ============================================================================

rag_retrieval_latency_ms = Histogram(
    "x0tta6bl4_rag_retrieval_latency_ms",
    "RAG document retrieval latency from HNSW index",
    buckets=(5, 10, 25, 50, 100, 500, 1000),
    registry=get_extended_registry(),
)
"""Time to retrieve documents from vector index."""

rag_generation_latency_ms = Histogram(
    "x0tta6bl4_rag_generation_latency_ms",
    "RAG answer generation latency",
    buckets=(50, 100, 250, 500, 1000, 2000),
    registry=get_extended_registry(),
)
"""Time to generate answer given context."""

rag_index_size_mb = Gauge(
    "x0tta6bl4_rag_index_size_mb",
    "HNSW vector index size in megabytes",
    labelnames=["dataset_name"],
    registry=get_extended_registry(),
)
"""Vector index size."""

rag_documents_indexed_total = Gauge(
    "x0tta6bl4_rag_documents_indexed_total",
    "Total documents in RAG knowledge base",
    labelnames=["dataset_name"],
    registry=get_extended_registry(),
)
"""Documents indexed."""

rag_retrieval_accuracy = Gauge(
    "x0tta6bl4_rag_retrieval_accuracy",
    "Percentage of relevant documents retrieved (top-5)",
    labelnames=["dataset_name"],
    registry=get_extended_registry(),
)
"""Retrieval quality metric."""

rag_generation_errors_total = Counter(
    "x0tta6bl4_rag_generation_errors_total",
    "Failed RAG generation attempts",
    labelnames=["error_type"],
    registry=get_extended_registry(),
)
"""Track generation failures."""


# ============================================================================
# DAO METRICS: Governance & Voting
# ============================================================================

dao_proposals_total = Counter(
    "x0tta6bl4_dao_proposals_total",
    "Total governance proposals created",
    labelnames=["proposal_type", "outcome"],
    registry=get_extended_registry(),
)
"""Track proposal lifecycle."""

dao_votes_cast_total = Counter(
    "x0tta6bl4_dao_votes_cast_total",
    "Total votes cast in governance",
    labelnames=["vote_type", "proposal_type"],
    registry=get_extended_registry(),
)
"""Counter for: FOR, AGAINST, ABSTAIN votes."""

dao_voting_participation_rate = Gauge(
    "x0tta6bl4_dao_voting_participation_rate",
    "Percentage of token holders participating in voting",
    registry=get_extended_registry(),
)
"""Governance engagement metric."""

dao_active_proposals = Gauge(
    "x0tta6bl4_dao_active_proposals",
    "Number of proposals currently in voting period",
    labelnames=["proposal_type"],
    registry=get_extended_registry(),
)
"""Current active proposals."""

dao_quadratic_voting_cost = Gauge(
    "x0tta6bl4_dao_quadratic_voting_cost",
    "Current cost of voting power (tokens per vote^2)",
    registry=get_extended_registry(),
)
"""Quadratic voting cost function."""

dao_governance_decisions_executed = Counter(
    "x0tta6bl4_dao_governance_decisions_executed",
    "Governance decisions successfully executed on-chain",
    labelnames=["decision_type"],
    registry=get_extended_registry(),
)
"""Track executed governance outcomes."""

dao_voter_participation_hours = Histogram(
    "x0tta6bl4_dao_voter_participation_hours",
    "Hours from proposal start to first vote cast",
    buckets=(0.1, 1, 6, 12, 24, 72),
    registry=get_extended_registry(),
)
"""Voter engagement timing."""


# ============================================================================
# eBPF METRICS: Network Programs
# ============================================================================

ebpf_programs_loaded_total = Counter(
    "x0tta6bl4_ebpf_programs_loaded_total",
    "eBPF programs successfully loaded",
    labelnames=["program_type", "kernel_version"],
    registry=get_extended_registry(),
)
"""Track program loading."""

ebpf_program_attachment_errors = Counter(
    "x0tta6bl4_ebpf_program_attachment_errors",
    "Failed eBPF program attachment attempts",
    labelnames=["program_type", "error_reason"],
    registry=get_extended_registry(),
)
"""Track attachment failures."""

ebpf_program_execution_time_us = Histogram(
    "x0tta6bl4_ebpf_program_execution_time_us",
    "eBPF program execution time in microseconds",
    buckets=(1, 10, 100, 1000, 10000),
    labelnames=["program_type"],
    registry=get_extended_registry(),
)
"""Kernel program latency."""

ebpf_events_processed_total = Counter(
    "x0tta6bl4_ebpf_events_processed_total",
    "Total eBPF events processed",
    labelnames=["event_type", "program_type"],
    registry=get_extended_registry(),
)
"""Event throughput."""

ebpf_buffer_drops_total = Counter(
    "x0tta6bl4_ebpf_buffer_drops_total",
    "Events dropped due to perf/ring buffer overflow",
    labelnames=["program_type"],
    registry=get_extended_registry(),
)
"""Buffer overflow counter (indicates overload)."""

ebpf_memory_usage_kb = Gauge(
    "x0tta6bl4_ebpf_memory_usage_kb",
    "eBPF program memory usage in kilobytes",
    labelnames=["program_type", "node_id"],
    registry=get_extended_registry(),
)
"""Memory footprint."""

ebpf_compilation_latency_ms = Histogram(
    "x0tta6bl4_ebpf_compilation_latency_ms",
    "Time to compile C to eBPF bytecode",
    buckets=(100, 500, 1000, 2000, 5000),
    registry=get_extended_registry(),
)
"""Compilation performance."""

ebpf_bytecode_size_kb = Gauge(
    "x0tta6bl4_ebpf_bytecode_size_kb",
    "Compiled eBPF bytecode size in kilobytes",
    labelnames=["program_type"],
    registry=get_extended_registry(),
)
"""Binary size."""

ebpf_cilium_integration_status = Gauge(
    "x0tta6bl4_ebpf_cilium_integration_status",
    "Cilium integration health (1=healthy, 0=unhealthy)",
    labelnames=["node_id"],
    registry=get_extended_registry(),
)
"""Integration status."""


# ============================================================================
# FEDERATED LEARNING METRICS
# ============================================================================

fl_model_updates_received = Counter(
    "x0tta6bl4_fl_model_updates_received",
    "Model updates received from participating nodes",
    labelnames=["round", "node_id"],
    registry=get_extended_registry(),
)
"""Update tracking."""

fl_aggregation_latency_ms = Histogram(
    "x0tta6bl4_fl_aggregation_latency_ms",
    "Time to aggregate model updates from all participants",
    buckets=(100, 500, 1000, 2000, 5000),
    registry=get_extended_registry(),
)
"""Aggregation performance."""

fl_model_accuracy_global = Gauge(
    "x0tta6bl4_fl_model_accuracy_global",
    "Global FL model accuracy on validation set",
    labelnames=["round", "dataset"],
    registry=get_extended_registry(),
)
"""Global model quality."""

fl_convergence_loss = Gauge(
    "x0tta6bl4_fl_convergence_loss",
    "FL training loss convergence metric",
    labelnames=["round"],
    registry=get_extended_registry(),
)
"""Loss trajectory."""

fl_byzantine_attacks_detected = Counter(
    "x0tta6bl4_fl_byzantine_attacks_detected",
    "Malicious node updates detected and filtered",
    labelnames=["detection_method"],
    registry=get_extended_registry(),
)
"""Security metric."""


# ============================================================================
# PERFORMANCE & OPTIMIZATION METRICS
# ============================================================================

query_execution_time_ms = Summary(
    "x0tta6bl4_query_execution_time_ms",
    "Database query execution time",
    labelnames=["query_type"],
    registry=get_extended_registry(),
)
"""Query performance."""

mesh_routing_hops = Histogram(
    "x0tta6bl4_mesh_routing_hops",
    "Number of hops in mesh routing path",
    buckets=(1, 2, 3, 5, 10, 20),
    registry=get_extended_registry(),
)
"""Path efficiency."""

mesh_latency_ms = Histogram(
    "x0tta6bl4_mesh_latency_ms",
    "End-to-end latency between mesh nodes",
    buckets=(1, 5, 10, 25, 50, 100),
    labelnames=["source_node", "dest_node"],
    registry=get_extended_registry(),
)
"""Mesh communication latency."""

active_connections = Gauge(
    "x0tta6bl4_active_connections",
    "Number of active mesh connections",
    labelnames=["node_id"],
    registry=get_extended_registry(),
)
"""Connection tracking."""


# ============================================================================
# Recording Functions
# ============================================================================


def record_graphsage_inference(
    latency_ms: float, is_anomaly: bool, severity: Optional[str] = None
):
    """Record GraphSAGE inference."""
    try:
        graphsage_inference_latency_ms.observe(latency_ms)
        if is_anomaly and severity:
            graphsage_anomalies_detected_total.labels(
                severity=severity, anomaly_type="network_topology"
            ).inc()
    except Exception as e:
        logger.error(f"Failed to record GraphSAGE metric: {e}")


def record_lora_training_update(adapter_name: str, loss: float, epoch: int):
    """Record LoRA training progress."""
    try:
        lora_training_loss.labels(adapter_name=adapter_name, model_name="mape_k").set(
            loss
        )
        lora_training_epochs_total.labels(adapter_name=adapter_name).inc()
    except Exception as e:
        logger.error(f"Failed to record LoRA metric: {e}")


def record_rag_retrieval(latency_ms: float, documents_found: int):
    """Record RAG retrieval performance."""
    try:
        rag_retrieval_latency_ms.observe(latency_ms)
    except Exception as e:
        logger.error(f"Failed to record RAG retrieval metric: {e}")


def record_dao_vote(vote_type: str, proposal_type: str):
    """Record DAO vote."""
    try:
        dao_votes_cast_total.labels(
            vote_type=vote_type, proposal_type=proposal_type
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record DAO vote metric: {e}")


def record_ebpf_event(event_type: str, program_type: str):
    """Record eBPF event processing."""
    try:
        ebpf_events_processed_total.labels(
            event_type=event_type, program_type=program_type
        ).inc()
    except Exception as e:
        logger.error(f"Failed to record eBPF metric: {e}")


def record_ebpf_compilation(
    latency_ms: float, bytecode_size_kb: float, program_type: str
):
    """Record eBPF compilation."""
    try:
        ebpf_compilation_latency_ms.observe(latency_ms)
        ebpf_bytecode_size_kb.labels(program_type=program_type).set(bytecode_size_kb)
    except Exception as e:
        logger.error(f"Failed to record eBPF compilation metric: {e}")


def record_fl_aggregation(latency_ms: float, round_num: int):
    """Record federated learning aggregation."""
    try:
        fl_aggregation_latency_ms.observe(latency_ms)
    except Exception as e:
        logger.error(f"Failed to record FL metric: {e}")


# ============================================================================
# Export
# ============================================================================


def get_extended_metrics_text():
    """Get all extended metrics as Prometheus text format."""
    from prometheus_client import generate_latest

    return generate_latest(get_extended_registry())


__all__ = [
    # GraphSAGE metrics
    "graphsage_inference_latency_ms",
    "graphsage_anomalies_detected_total",
    "graphsage_model_accuracy",
    "graphsage_false_positive_rate",
    "graphsage_model_size_mb",
    "graphsage_predictions_per_second",
    # LoRA metrics
    "lora_training_loss",
    "lora_training_epochs_total",
    "lora_adapter_rank",
    "lora_parameters_count",
    "lora_inference_speedup",
    # RAG metrics
    "rag_retrieval_latency_ms",
    "rag_generation_latency_ms",
    "rag_index_size_mb",
    "rag_documents_indexed_total",
    "rag_retrieval_accuracy",
    "rag_generation_errors_total",
    # DAO metrics
    "dao_proposals_total",
    "dao_votes_cast_total",
    "dao_voting_participation_rate",
    "dao_active_proposals",
    "dao_quadratic_voting_cost",
    "dao_governance_decisions_executed",
    "dao_voter_participation_hours",
    # eBPF metrics
    "ebpf_programs_loaded_total",
    "ebpf_program_attachment_errors",
    "ebpf_program_execution_time_us",
    "ebpf_events_processed_total",
    "ebpf_buffer_drops_total",
    "ebpf_memory_usage_kb",
    "ebpf_compilation_latency_ms",
    "ebpf_bytecode_size_kb",
    "ebpf_cilium_integration_status",
    # FL metrics
    "fl_model_updates_received",
    "fl_aggregation_latency_ms",
    "fl_model_accuracy_global",
    "fl_convergence_loss",
    "fl_byzantine_attacks_detected",
    # Performance metrics
    "query_execution_time_ms",
    "mesh_routing_hops",
    "mesh_latency_ms",
    "active_connections",
    # Functions
    "record_graphsage_inference",
    "record_lora_training_update",
    "record_rag_retrieval",
    "record_dao_vote",
    "record_ebpf_event",
    "record_ebpf_compilation",
    "record_fl_aggregation",
    "get_extended_metrics_text",
]
