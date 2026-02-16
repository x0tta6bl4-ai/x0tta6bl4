import types
from types import SimpleNamespace

import pytest


def _make_cycle(monkeypatch, *, observe=None, ebpf=None):
    import sys

    # Prevent heavy/side-effectful import of real GraphSAGE observe mode.
    # The real module registers Prometheus metrics at import time, which can
    # raise duplicated-timeseries errors across tests.
    dummy_observe = types.ModuleType("src.ml.graphsage_observe_mode")

    class _DetectorMode:
        OBSERVE = SimpleNamespace(value="observe")

    class _GraphSAGEObserveMode:
        def __init__(self, *args, **kwargs):
            self.mode = _DetectorMode.OBSERVE

    dummy_observe.DetectorMode = _DetectorMode
    dummy_observe.GraphSAGEObserveMode = _GraphSAGEObserveMode

    monkeypatch.setitem(sys.modules, "src.ml.graphsage_observe_mode", dummy_observe)

    import src.self_healing.mape_k_integrated as mod

    cycle = mod.IntegratedMAPEKCycle(
        enable_observe_mode=False,
        enable_chaos=False,
        enable_ebpf_explainer=False,
    )

    cycle.monitor = SimpleNamespace(check=lambda metrics: False)
    cycle.analyzer = SimpleNamespace(analyze=lambda metrics: "Healthy")
    cycle.planner = SimpleNamespace(plan=lambda issue: "No action needed")
    cycle.executor = SimpleNamespace(execute=lambda strategy, context=None: True)

    class _KB:
        def __init__(self):
            self.record_calls = []

        def record(self, **kwargs):
            self.record_calls.append(kwargs)

        def get_average_mttr(self, issue):
            return None

    cycle.knowledge = _KB()

    cycle.observe_detector = observe
    cycle.ebpf_explainer = ebpf

    # deterministic cycle_id
    monkeypatch.setattr(mod.time, "time", lambda: 1.0)

    return cycle


def test_run_cycle_no_anomaly_returns_early(monkeypatch):
    cycle = _make_cycle(monkeypatch)

    metrics = {"node_id": "n1", "cpu_percent": 10}
    out = cycle.run_cycle(metrics)

    assert out["anomaly_detected"] is False
    assert out["cycle_id"].startswith("cycle_")
    assert cycle.knowledge.record_calls == []


@pytest.mark.parametrize(
    "issue,strategy",
    [("High CPU", "Restart service"), ("Network Loss", "Switch route")],
)
def test_run_cycle_full_path_with_observe_and_ebpf(monkeypatch, issue, strategy):
    class _Event:
        anomaly_score = 0.99
        confidence = 0.95
        mode = SimpleNamespace(value="observe")
        action_taken = "none"

    class _Observe:
        mode = SimpleNamespace(value="observe")

        def detect(self, graph_data, node_id):
            assert node_id == "n1"
            assert "cpu_percent" in graph_data
            return _Event()

        def get_stats(self):
            return {"calls": 1}

    class _EBPF:
        def __init__(self):
            self.calls = []

        def explain_event(self, event):
            self.calls.append(event)
            return {"ex": "ok"}

    obs = _Observe()
    ebpf = _EBPF()

    cycle = _make_cycle(monkeypatch, observe=obs, ebpf=ebpf)
    import src.self_healing.mape_k_integrated as mod

    cycle.monitor = SimpleNamespace(check=lambda metrics: True)
    cycle.analyzer = SimpleNamespace(analyze=lambda metrics: issue)
    cycle.planner = SimpleNamespace(plan=lambda i: strategy)

    seen = {}

    def _exec(strategy_in, context=None):
        seen["strategy"] = strategy_in
        seen["context"] = context
        return True

    cycle.executor = SimpleNamespace(execute=_exec)

    # provide eBPF types so branch can construct EBPFEvent
    monkeypatch.setattr(mod, "EBPF_EXPLAINER_AVAILABLE", True)
    monkeypatch.setattr(mod, "EBPFEvent", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(
        mod, "EBPFEventType", SimpleNamespace(PACKET_DROP="PACKET_DROP")
    )

    metrics = {
        "node_id": "n1",
        "service_name": "svc",
        "cpu_percent": 99,
        "network_events": [{"program_id": "p1"}],
    }

    out = cycle.run_cycle(metrics)

    assert out["anomaly_detected"] is True
    assert out["analyzer_results"]["root_cause"] == issue
    assert out["planner_results"]["strategy"] == strategy
    assert out["executor_results"]["success"] is True

    assert "observe_mode" in out
    assert "observe_mode" in out["explanations"]

    assert "ebpf" in out["explanations"]
    assert ebpf.calls

    assert seen["strategy"] == strategy
    assert seen["context"]["node_id"] == "n1"
    assert seen["context"]["service_name"] == "svc"
    assert seen["context"]["issue"] == issue

    assert len(cycle.knowledge.record_calls) == 1


def test_estimate_recovery_time_uses_historical_mttr(monkeypatch):
    cycle = _make_cycle(monkeypatch)

    def _avg(issue):
        return 100.0

    cycle.knowledge.get_average_mttr = _avg

    est = cycle._estimate_recovery_time("Restart service", "High CPU")
    assert est > 0
    # 70% historical + 30% estimated base
    assert abs(est - (100.0 * 0.7 + 5.0 * 0.3)) < 0.01


@pytest.mark.asyncio
async def test_run_chaos_experiment_returns_error_when_unavailable(monkeypatch):
    cycle = _make_cycle(monkeypatch)

    out = await cycle.run_chaos_experiment("node_failure", duration=1)
    assert out["error"]


def test_get_system_status_reflects_components(monkeypatch):
    obs = SimpleNamespace(
        mode=SimpleNamespace(value="observe"), get_stats=lambda: {"ok": True}
    )

    class _Chaos:
        def get_recovery_stats(self):
            return {"r": 1}

    cycle = _make_cycle(monkeypatch, observe=obs)
    cycle.chaos_controller = _Chaos()

    st = cycle.get_system_status()
    assert st["observe_mode"]["enabled"] is True
    assert st["chaos_engineering"]["enabled"] is True
    assert st["chaos_engineering"]["stats"] == {"r": 1}
