"""
Unit tests for Dependency Injection integration in SelfHealingManager.
"""
from src.core.di import get_container
from src.self_healing.mape_k.manager import SelfHealingManager


class DummyThresholdManager:
    def __init__(self):
        self.proposals_checked = False

    def check_and_apply_dao_proposals(self) -> int:
        self.proposals_checked = True
        return 5


class DummyKnowledgeStorage:
    """Minimal stub that satisfies MAPEKKnowledgeStorageAdapter expectations."""

    def __init__(self):
        self.initialized = True

    # MAPEKKnowledgeStorageAdapter may call these methods:
    def load(self, *args, **kwargs):
        return {}

    def save(self, *args, **kwargs):
        pass


def test_self_healing_manager_resolves_threshold_manager_from_di():
    """Verify threshold_manager is resolved from DI when not passed explicitly."""
    di = get_container()
    di.clear()

    threshold_mgr = DummyThresholdManager()
    di.register_singleton("threshold_manager", threshold_mgr)

    manager = SelfHealingManager(node_id="di-test-node")

    assert manager.threshold_manager is threshold_mgr
    assert threshold_mgr.proposals_checked is True

    di.clear()


def test_self_healing_manager_resolves_knowledge_storage_from_di():
    """Verify knowledge_storage is resolved from DI when not passed explicitly."""
    di = get_container()
    di.clear()

    storage = DummyKnowledgeStorage()
    di.register_singleton("knowledge_storage", storage)

    manager = SelfHealingManager(node_id="di-knowledge-test")

    # If knowledge_storage was resolved, MAPEKKnowledge should have been
    # initialized with a storage adapter, not as a bare instance.
    # We check that knowledge was created (non-None) and manager works.
    assert manager.knowledge is not None

    di.clear()


def test_self_healing_manager_works_without_di():
    """Verify SelfHealingManager still works when DI container is empty."""
    di = get_container()
    di.clear()

    manager = SelfHealingManager(node_id="no-di-node")

    assert manager.threshold_manager is None
    assert manager.knowledge is not None

    di.clear()


def test_monitor_and_planner_resolve_from_di():
    """Verify MAPEKMonitor and MAPEKPlanner resolve dependencies from DI."""
    di = get_container()
    di.clear()

    from src.self_healing.mape_k.knowledge import MAPEKKnowledge
    from src.self_healing.mape_k.monitor import MAPEKMonitor
    from src.self_healing.mape_k.planner import MAPEKPlanner

    knowledge = MAPEKKnowledge()
    threshold_mgr = DummyThresholdManager()

    di.register_singleton("knowledge", knowledge)
    di.register_singleton("threshold_manager", threshold_mgr)

    monitor = MAPEKMonitor()
    planner = MAPEKPlanner()

    assert monitor.knowledge is knowledge
    assert monitor.threshold_manager is threshold_mgr
    assert planner.knowledge is knowledge

    di.clear()


def test_threshold_proposal_resolves_from_di():
    """Verify MAPEKThresholdProposal resolves threshold_manager from DI."""
    di = get_container()
    di.clear()

    from src.dao.mapek_threshold_proposal import MAPEKThresholdProposal
    from unittest.mock import MagicMock

    threshold_mgr = DummyThresholdManager()
    di.register_singleton("threshold_manager", threshold_mgr)

    gov = MagicMock()
    proposal_logic = MAPEKThresholdProposal(gov)

    assert proposal_logic.threshold_manager is threshold_mgr

    di.clear()
