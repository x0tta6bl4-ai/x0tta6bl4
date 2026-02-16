"""Monitoring and observability modules for x0tta6bl4."""

from src.monitoring.opentelemetry_extended import (get_contract_spans,
                                                   get_crdt_spans,
                                                   get_dao_spans,
                                                   get_ebpf_spans,
                                                   get_fl_spans,
                                                   get_ledger_spans,
                                                   get_raft_spans,
                                                   initialize_extended_spans)
from src.monitoring.opentelemetry_tracing import (get_mapek_spans,
                                                  get_ml_spans,
                                                  get_network_spans,
                                                  get_spiffe_spans,
                                                  get_tracer_manager,
                                                  initialize_tracing)
from src.monitoring.prometheus_extended import (get_extended_metrics_text,
                                                get_extended_registry,
                                                record_dao_vote,
                                                record_ebpf_compilation,
                                                record_ebpf_event,
                                                record_fl_aggregation,
                                                record_graphsage_inference,
                                                record_lora_training_update,
                                                record_rag_retrieval)

__all__ = [
    # Prometheus metrics
    "get_extended_registry",
    "get_extended_metrics_text",
    "record_graphsage_inference",
    "record_lora_training_update",
    "record_rag_retrieval",
    "record_dao_vote",
    "record_ebpf_event",
    "record_ebpf_compilation",
    "record_fl_aggregation",
    # OpenTelemetry tracing
    "initialize_tracing",
    "get_tracer_manager",
    "get_mapek_spans",
    "get_network_spans",
    "get_spiffe_spans",
    "get_ml_spans",
    # Extended OpenTelemetry spans
    "initialize_extended_spans",
    "get_ledger_spans",
    "get_dao_spans",
    "get_ebpf_spans",
    "get_fl_spans",
    "get_raft_spans",
    "get_crdt_spans",
    "get_contract_spans",
]
