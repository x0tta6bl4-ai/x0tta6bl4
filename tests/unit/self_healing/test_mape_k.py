"""
Unit tests for MAPE-K Self-Healing Core
"""
import pytest
from src.self_healing.mape_k import SelfHealingManager

def test_self_healing_cycle_high_cpu():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get('cpu_percent', 0) > 90)
    metrics = {'cpu_percent': 95}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]['issue'] == 'High CPU'
    assert history[-1]['action'] == 'Restart service'

def test_self_healing_cycle_high_memory():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get('memory_percent', 0) > 85)
    metrics = {'memory_percent': 90}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]['issue'] == 'High Memory'
    assert history[-1]['action'] == 'Clear cache'

def test_self_healing_cycle_network_loss():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: m.get('packet_loss_percent', 0) > 5)
    metrics = {'packet_loss_percent': 10}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert history[-1]['issue'] == 'Network Loss'
    assert history[-1]['action'] == 'Switch route'

def test_self_healing_cycle_healthy():
    manager = SelfHealingManager()
    manager.monitor.register_detector(lambda m: False)
    metrics = {'cpu_percent': 10, 'memory_percent': 10, 'packet_loss_percent': 0}
    manager.run_cycle(metrics)
    history = manager.knowledge.get_history()
    assert len(history) == 0
