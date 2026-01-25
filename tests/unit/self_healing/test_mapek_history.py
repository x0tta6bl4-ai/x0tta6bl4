from src.self_healing.mape_k import SelfHealingManager


def test_mapek_history_records():
    mgr = SelfHealingManager()
    # register simple detector always true
    mgr.monitor.register_detector(lambda m: True)
    metrics = {'cpu_percent': 95}
    mgr.run_cycle(metrics)
    history = mgr.knowledge.get_history()
    assert len(history) == 1
    assert history[0]['issue'] == 'High CPU'
    assert history[0]['action'] == 'Restart service'
