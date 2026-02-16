"""Unit tests for production system orchestration."""

from types import SimpleNamespace

from src.core import production_system


class _FakeCardinality:
    def record_metric_sample(self, *_args, **_kwargs):
        return None

    def get_cardinality_report(self):
        return {"total_unique_metrics": 10, "total_cardinality": 1000}


class _FakeLatencyTracker:
    def record(self, *_args, **_kwargs):
        return None


class _FakePerfTuner:
    latency_tracker = _FakeLatencyTracker()

    def analyze_performance(self):
        return {"ok": True}


class _FakeHardening:
    request_auditor = SimpleNamespace(log_request=lambda *a, **k: None)

    def get_security_status(self):
        return {"suspicious_patterns": []}


class _FakeResilientExecutor:
    def get_stats(self):
        return {
            "success_rate": 0.95,
            "circuit_breaker_state": "closed",
            "bulkhead_status": {"utilization": 0.1},
        }


def _inject_fakes(self):
    self.cardinality_optimizer = _FakeCardinality()
    self.performance_tuner = _FakePerfTuner()
    self.hardening_manager = _FakeHardening()
    self.resilient_executor = _FakeResilientExecutor()


def test_record_request_updates_counters(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()

    ps.record_request("GET", "/health", 200, 20.0, {"client_ip": "127.0.0.1"})
    ps.record_request("POST", "/x", 500, 30.0, {"client_ip": "127.0.0.2"})

    assert ps.request_count == 2
    assert ps.error_count == 1
    assert ps.latency_sum == 50.0


def test_get_system_health_contains_expected_sections(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()
    ps.record_request("GET", "/health", 200, 20.0, {"client_ip": "127.0.0.1"})

    health = ps.get_system_health()

    assert "health_score" in health
    assert health["requests"]["total"] == 1
    assert health["cardinality"]["status"] == "healthy"
    assert health["resilience"]["circuit_breaker_state"] == "closed"


def test_get_readiness_level_thresholds(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    ps = production_system.ProductionSystem()

    assert ps._get_readiness_level(96) == "PRODUCTION_READY"
    assert ps._get_readiness_level(90) == "NEAR_PRODUCTION"
    assert ps._get_readiness_level(70) == "STAGING_READY"
    assert ps._get_readiness_level(50) == "DEVELOPMENT"


def test_get_production_system_singleton(monkeypatch):
    monkeypatch.setattr(
        production_system.ProductionSystem, "_import_components", _inject_fakes
    )
    production_system._system = None

    s1 = production_system.get_production_system()
    s2 = production_system.get_production_system()

    assert s1 is s2
