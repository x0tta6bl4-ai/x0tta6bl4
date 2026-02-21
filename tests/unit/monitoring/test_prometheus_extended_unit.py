import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.monitoring.prometheus_extended as mod


class _RaisesOnObserve:
    def observe(self, *_args, **_kwargs):
        raise RuntimeError("observe failed")


class _RaisesOnLabels:
    def labels(self, **_kwargs):
        raise RuntimeError("labels failed")


class _ObserveRecorder:
    def __init__(self):
        self.values = []

    def observe(self, value):
        self.values.append(value)


class _LabelSetRecorder:
    def __init__(self):
        self.labels_kwargs = []
        self.set_values = []

    def labels(self, **kwargs):
        self.labels_kwargs.append(kwargs)
        return self

    def set(self, value):
        self.set_values.append(value)


def test_registry_singleton_and_metrics_export():
    r1 = mod.get_extended_registry()
    r2 = mod.get_extended_registry()
    assert r1 is r2
    assert isinstance(mod.get_extended_metrics_text(), bytes)


def test_record_graphsage_inference_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "graphsage_inference_latency_ms", _RaisesOnObserve())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_graphsage_inference(10.5, True, "HIGH")
    assert errors and "Failed to record GraphSAGE metric" in errors[0]


def test_record_lora_training_update_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "lora_training_loss", _RaisesOnLabels())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_lora_training_update("adapter", 0.1, 2)
    assert errors and "Failed to record LoRA metric" in errors[0]


def test_record_rag_retrieval_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "rag_retrieval_latency_ms", _RaisesOnObserve())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_rag_retrieval(50.0, 3)
    assert errors and "Failed to record RAG retrieval metric" in errors[0]


def test_record_dao_vote_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "dao_votes_cast_total", _RaisesOnLabels())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_dao_vote("FOR", "upgrade")
    assert errors and "Failed to record DAO vote metric" in errors[0]


def test_record_ebpf_event_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "ebpf_events_processed_total", _RaisesOnLabels())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_ebpf_event("packet_rx", "xdp")
    assert errors and "Failed to record eBPF metric" in errors[0]


def test_record_ebpf_compilation_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "ebpf_compilation_latency_ms", _RaisesOnObserve())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_ebpf_compilation(42.0, 128.0, "xdp")
    assert errors and "Failed to record eBPF compilation metric" in errors[0]


def test_record_ebpf_compilation_success_path(monkeypatch):
    latency_metric = _ObserveRecorder()
    size_metric = _LabelSetRecorder()
    monkeypatch.setattr(mod, "ebpf_compilation_latency_ms", latency_metric)
    monkeypatch.setattr(mod, "ebpf_bytecode_size_kb", size_metric)

    mod.record_ebpf_compilation(12.5, 64.0, "tc")

    assert latency_metric.values == [12.5]
    assert size_metric.labels_kwargs == [{"program_type": "tc"}]
    assert size_metric.set_values == [64.0]


def test_record_fl_aggregation_error_path(monkeypatch):
    errors = []
    monkeypatch.setattr(mod, "fl_aggregation_latency_ms", _RaisesOnObserve())
    monkeypatch.setattr(mod.logger, "error", lambda message: errors.append(message))

    mod.record_fl_aggregation(77.0, 1)
    assert errors and "Failed to record FL metric" in errors[0]
