import builtins
import importlib.util
import sys
import types
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "verify_system.py"
    spec = importlib.util.spec_from_file_location("verify_system_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_pqc_fails_closed_when_pqc_import_fails(monkeypatch):
    module = _load_module()
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "src.security.pqc.simple":
            raise ImportError("missing pqc")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    assert module.check_pqc() is False


def test_check_mape_k_fails_closed_when_import_fails(monkeypatch):
    module = _load_module()
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "src.self_healing.mape_k":
            raise ImportError("missing mapek")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    assert module.check_mape_k() is False


def test_check_mape_k_uses_real_component_flow(monkeypatch):
    module = _load_module()
    fake_mapek = types.ModuleType("src.self_healing.mape_k")
    calls = {"monitor": 0, "analyze": 0, "plan": 0, "execute": 0}

    class FakeMonitor:
        def check(self, metrics):
            calls["monitor"] += 1
            assert metrics["node_id"] == "unit-node"
            return {"anomaly_detected": False, "issue": "Healthy"}

    class FakeAnalyzer:
        def analyze(self, metrics):
            calls["analyze"] += 1
            assert metrics["cpu_percent"] == 10.0
            return "Healthy"

    class FakePlanner:
        def plan(self, issue):
            calls["plan"] += 1
            assert issue == "Healthy"
            return "No action needed"

    class FakeExecutor:
        @staticmethod
        def _is_noop_action(action):
            return action == "No action needed"

        def execute(self, action, context):
            calls["execute"] += 1
            assert action == "No action needed"
            assert context["verification"] is True
            return True

    fake_mapek.MAPEKMonitor = FakeMonitor
    fake_mapek.MAPEKAnalyzer = FakeAnalyzer
    fake_mapek.MAPEKPlanner = FakePlanner
    fake_mapek.MAPEKExecutor = FakeExecutor
    monkeypatch.setitem(sys.modules, "src.self_healing.mape_k", fake_mapek)
    monkeypatch.setattr(
        module,
        "collect_local_mapek_metrics",
        lambda: {
            "node_id": "unit-node",
            "cpu_percent": 10.0,
            "memory_percent": 20.0,
            "packet_loss_percent": 0.0,
        },
    )

    assert module.check_mape_k() is True
    assert calls == {"monitor": 1, "analyze": 1, "plan": 1, "execute": 1}


def test_check_mape_k_refuses_remediation_without_opt_in(monkeypatch):
    module = _load_module()
    fake_mapek = types.ModuleType("src.self_healing.mape_k")

    class FakeMonitor:
        def check(self, metrics):
            return {"anomaly_detected": True, "issue": "High CPU"}

    class FakeAnalyzer:
        def analyze(self, metrics):
            return "High CPU"

    class FakePlanner:
        def plan(self, issue):
            return "Restart service"

    class FakeExecutor:
        @staticmethod
        def _is_noop_action(action):
            return False

        def execute(self, action, context):
            raise AssertionError("remediation must require explicit opt-in")

    fake_mapek.MAPEKMonitor = FakeMonitor
    fake_mapek.MAPEKAnalyzer = FakeAnalyzer
    fake_mapek.MAPEKPlanner = FakePlanner
    fake_mapek.MAPEKExecutor = FakeExecutor
    monkeypatch.setitem(sys.modules, "src.self_healing.mape_k", fake_mapek)
    monkeypatch.delenv("X0TTA6BL4_VERIFY_ALLOW_REMEDIATION", raising=False)
    monkeypatch.setattr(
        module,
        "collect_local_mapek_metrics",
        lambda: {
            "node_id": "unit-node",
            "cpu_percent": 99.0,
            "memory_percent": 20.0,
            "packet_loss_percent": 0.0,
        },
    )

    assert module.check_mape_k() is False
