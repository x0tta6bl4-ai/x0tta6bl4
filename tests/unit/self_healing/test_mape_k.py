"""
Unit tests for MAPE-K Self-Healing Core
"""


from src.self_healing.mape_k import SelfHealingManager, MAPEKMonitor


def test_self_healing_cycle_high_cpu():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get("cpu_percent", 0) > 90)
    metrics = {"cpu_percent": 95}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]["issue"] == "High CPU"
    assert history[-1]["action"] == "Restart service"


def test_self_healing_cycle_high_memory():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get("memory_percent", 0) > 85)
    metrics = {"memory_percent": 90}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]["issue"] == "High Memory"
    assert history[-1]["action"] == "Clear cache"


def test_self_healing_cycle_network_loss():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get("packet_loss_percent", 0) > 5)
    metrics = {"packet_loss_percent": 10}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]["issue"] == "Network Loss"
    assert history[-1]["action"] == "Switch route"


def test_self_healing_cycle_healthy():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: False)
    metrics = {"cpu_percent": 10, "memory_percent": 10, "packet_loss_percent": 0}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert len(history) == 0


# ---------------------------------------------------------------------------
# MAPEKMonitor unit tests (added by Codex session 2026-03-09)
# ---------------------------------------------------------------------------


def test_mapek_monitor_init():
    """Test MAPEKMonitor initialization."""
    monitor = MAPEKMonitor()
    assert monitor.anomaly_detectors == []
    assert monitor.knowledge is None
    assert monitor.threshold_manager is None
    assert monitor.graphsage_detector is None
    assert monitor.use_graphsage is False
    assert "cpu_percent" in monitor.default_thresholds


def test_mapek_monitor_register_detector():
    """Test registering custom detector."""
    monitor = MAPEKMonitor()

    def dummy_detector(metrics):
        return True

    monitor.register_detector(dummy_detector)
    assert len(monitor.anomaly_detectors) == 1
    assert monitor.anomaly_detectors[0] == dummy_detector


def test_mapek_monitor_check_normal():
    """Test check method with normal metrics."""
    monitor = MAPEKMonitor()
    metrics = {
        "node_id": "node1",
        "cpu_percent": 50.0,
        "memory_percent": 60.0,
        "packet_loss_percent": 1.0,
    }
    result = monitor.check(metrics)
    assert result["anomaly_detected"] is False


def test_mapek_monitor_check_high_cpu():
    """Test check method with high CPU."""
    monitor = MAPEKMonitor()
    metrics = {
        "node_id": "node1",
        "cpu_percent": 95.0,
        "memory_percent": 60.0,
        "packet_loss_percent": 1.0,
    }
    result = monitor.check(metrics)
    assert result["anomaly_detected"] is True


def test_mapek_monitor_check_high_memory():
    """Test check method with high memory."""
    monitor = MAPEKMonitor()
    metrics = {
        "node_id": "node1",
        "cpu_percent": 50.0,
        "memory_percent": 90.0,
        "packet_loss_percent": 1.0,
    }
    result = monitor.check(metrics)
    assert result["anomaly_detected"] is True


def test_mapek_monitor_check_packet_loss():
    """Test check method with high packet loss."""
    monitor = MAPEKMonitor()
    metrics = {
        "node_id": "node1",
        "cpu_percent": 50.0,
        "memory_percent": 60.0,
        "packet_loss_percent": 10.0,
    }
    result = monitor.check(metrics)
    assert result["anomaly_detected"] is True
