import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from pathlib import Path

import src.core.q2_integration as q2


class _RAG:
    def __init__(self, **kwargs):
        self.loaded = None
        self.kwargs = kwargs

    def load(self, path):
        self.loaded = path

    def add_document(self, text, doc_id, meta):
        return ["c1", "c2"]

    def query(self, query, top_k=10):
        return f"context:{query}:{top_k}"

    def retrieve(self, query, top_k=10):
        return {"q": query, "k": top_k}


class _LoRAConfig:
    pass


class _LoRATrainer:
    def __init__(self, base_model_name, config):
        self.base_model_name = base_model_name
        self.config = config

    def train(self, train_dataset, adapter_id, **kwargs):
        return {"adapter_id": adapter_id, "size": len(train_dataset)}


class _Cilium:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.policies = []

    def get_flow_history(self, limit=100):
        return [{"flow": 1, "limit": limit}]

    def get_metrics(self):
        return {"packets": 10}

    def add_network_policy(self, policy):
        self.policies.append(policy)
        return True

    def shutdown(self):
        return None


def _enable_all(monkeypatch):
    monkeypatch.setattr(q2, "RAG_AVAILABLE", True)
    monkeypatch.setattr(q2, "LORA_AVAILABLE", True)
    monkeypatch.setattr(q2, "CILIUM_AVAILABLE", True)
    monkeypatch.setattr(q2, "ENHANCED_AGGREGATORS_AVAILABLE", True)
    monkeypatch.setattr(q2, "RAGPipeline", _RAG)
    monkeypatch.setattr(q2, "LoRAConfig", _LoRAConfig)
    monkeypatch.setattr(q2, "LoRATrainer", _LoRATrainer)
    monkeypatch.setattr(q2, "CiliumLikeIntegration", _Cilium)
    monkeypatch.setattr(
        q2, "get_enhanced_aggregator", lambda method: {"method": method}
    )


def test_init_with_all_components(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration(rag_data_path=Path("/tmp/rag.idx"))
    assert integration.enable_rag is True
    assert integration.enable_lora is True
    assert integration.enable_cilium is True
    assert integration.enable_enhanced_aggregators is True
    assert integration.rag_pipeline.loaded == Path("/tmp/rag.idx")
    assert integration.cilium_integration is not None


def test_rag_methods_success_and_failures(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration()
    assert integration.add_knowledge("t", "d1", {"x": 1}) is True
    assert integration.query_knowledge("hello", top_k=3) == "context:hello:3"
    assert integration.retrieve_knowledge("hello", top_k=2) == {"q": "hello", "k": 2}

    integration.rag_pipeline.query = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("bad")
    )
    assert integration.query_knowledge("x") == ""


def test_rag_methods_when_disabled(monkeypatch):
    monkeypatch.setattr(q2, "RAG_AVAILABLE", False)
    integration = q2.Q2Integration(
        enable_rag=True,
        enable_lora=False,
        enable_cilium=False,
        enable_enhanced_aggregators=False,
    )
    assert integration.add_knowledge("t", "d") is False
    assert integration.query_knowledge("q") == ""
    assert integration.retrieve_knowledge("q") is None


def test_lora_initialize_and_train(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration()
    assert integration.initialize_lora_trainer("model/x") is True
    result = integration.train_lora_adapter([1, 2, 3], "adapter-1")
    assert result == {"adapter_id": "adapter-1", "size": 3}

    integration.lora_trainer.train = lambda **_k: (_ for _ in ()).throw(
        RuntimeError("fail")
    )
    assert integration.train_lora_adapter([1], "adapter-2") is None


def test_lora_when_unavailable(monkeypatch):
    monkeypatch.setattr(q2, "LORA_AVAILABLE", False)
    integration = q2.Q2Integration(
        enable_rag=False,
        enable_lora=True,
        enable_cilium=False,
        enable_enhanced_aggregators=False,
    )
    assert integration.initialize_lora_trainer("model/x") is False
    assert integration.train_lora_adapter([1], "a") is None


def test_network_methods_success_and_error(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration(
        enable_rag=False,
        enable_lora=False,
        enable_cilium=True,
        enable_enhanced_aggregators=False,
    )
    assert integration.get_network_flows(limit=5)[0]["limit"] == 5
    assert integration.get_network_metrics() == {"packets": 10}
    assert integration.add_network_policy({"name": "p1"}) is True

    integration.cilium_integration.get_metrics = lambda: (_ for _ in ()).throw(
        RuntimeError("x")
    )
    assert integration.get_network_metrics() == {}


def test_network_methods_when_disabled(monkeypatch):
    monkeypatch.setattr(q2, "CILIUM_AVAILABLE", False)
    integration = q2.Q2Integration(
        enable_rag=False,
        enable_lora=False,
        enable_cilium=True,
        enable_enhanced_aggregators=False,
    )
    assert integration.get_network_flows() == []
    assert integration.get_network_metrics() == {}
    assert integration.add_network_policy({"x": 1}) is False


def test_enhanced_aggregator_paths(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration(
        enable_rag=False,
        enable_lora=False,
        enable_cilium=False,
        enable_enhanced_aggregators=True,
    )
    assert integration.get_enhanced_aggregator("adaptive") == {"method": "adaptive"}

    monkeypatch.setattr(
        q2,
        "get_enhanced_aggregator",
        lambda _m: (_ for _ in ()).throw(RuntimeError("err")),
    )
    assert integration.get_enhanced_aggregator("adaptive") is None

    integration.enable_enhanced_aggregators = False
    assert integration.get_enhanced_aggregator("adaptive") is None


def test_shutdown_and_global_singleton(monkeypatch):
    _enable_all(monkeypatch)
    integration = q2.Q2Integration(
        enable_rag=False,
        enable_lora=False,
        enable_cilium=True,
        enable_enhanced_aggregators=False,
    )
    integration.shutdown()

    obj = q2.initialize_q2_integration(
        enable_rag=False,
        enable_lora=False,
        enable_cilium=False,
        enable_enhanced_aggregators=False,
    )
    assert q2.get_q2_integration() is obj
