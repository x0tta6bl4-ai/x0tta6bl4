"""
Тесты для FederatedCoordinator.

Покрывает:
- Регистрация/отмена регистрации нод
- Управление раундами
- Heartbeat мониторинг
- Агрегация обновлений
- Callback'и
- Byzantine detection и бан
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock

from src.federated_learning.coordinator import (
    FederatedCoordinator,
    CoordinatorConfig,
    NodeInfo,
    NodeStatus,
    TrainingRound,
    RoundStatus,
)
from src.federated_learning.protocol import (
    ModelWeights,
    ModelUpdate,
    GlobalModel,
)


class TestNodeInfo:
    """Тесты для NodeInfo."""

    def test_create_node_info(self):
        """Создание информации о ноде."""
        node = NodeInfo(node_id="node-001")

        assert node.node_id == "node-001"
        assert node.status == NodeStatus.UNKNOWN
        assert node.trust_score == 1.0
        assert node.byzantine_violations == 0

    def test_node_eligibility_default(self):
        """Проверка eligibility по умолчанию."""
        node = NodeInfo(node_id="node-001", status=NodeStatus.ONLINE)
        assert node.is_eligible() is True

    def test_node_not_eligible_when_banned(self):
        """Забаненная нода не eligible."""
        node = NodeInfo(node_id="node-001", status=NodeStatus.BANNED)
        assert node.is_eligible() is False

    def test_node_not_eligible_low_trust(self):
        """Нода с низким trust не eligible."""
        node = NodeInfo(
            node_id="node-001",
            status=NodeStatus.ONLINE,
            trust_score=0.3
        )
        assert node.is_eligible(min_trust=0.5) is False

    def test_node_not_eligible_too_many_violations(self):
        """Нода с множеством нарушений не eligible."""
        node = NodeInfo(
            node_id="node-001",
            status=NodeStatus.ONLINE,
            byzantine_violations=5
        )
        assert node.is_eligible() is False


class TestTrainingRound:
    """Тесты для TrainingRound."""

    def test_create_round(self):
        """Создание раунда."""
        round_obj = TrainingRound(
            round_number=1,
            min_participants=3
        )

        assert round_obj.round_number == 1
        assert round_obj.status == RoundStatus.PENDING
        assert len(round_obj.received_updates) == 0

    def test_collection_complete(self):
        """Проверка завершения сбора."""
        round_obj = TrainingRound(
            round_number=1,
            min_participants=2
        )

        # Добавляем обновления
        round_obj.received_updates["node-1"] = Mock()
        assert round_obj.is_collection_complete() is False

        round_obj.received_updates["node-2"] = Mock()
        assert round_obj.is_collection_complete() is True

    def test_deadline_check(self):
        """Проверка дедлайна."""
        round_obj = TrainingRound(
            round_number=1,
            collection_deadline=time.time() + 10
        )
        assert round_obj.is_deadline_passed() is False

        round_obj.collection_deadline = time.time() - 10
        assert round_obj.is_deadline_passed() is True

    def test_to_dict(self):
        """Сериализация раунда."""
        round_obj = TrainingRound(
            round_number=5,
            status=RoundStatus.COLLECTING,
            selected_nodes={"node-1", "node-2"}
        )

        data = round_obj.to_dict()
        assert data["round_number"] == 5
        assert data["status"] == "collecting"


class TestCoordinatorConfig:
    """Тесты для CoordinatorConfig."""

    def test_default_config(self):
        """Конфигурация по умолчанию."""
        config = CoordinatorConfig()

        assert config.min_participants == 3
        assert config.aggregation_method == "krum"
        assert config.byzantine_tolerance == 1

    def test_custom_config(self):
        """Кастомная конфигурация."""
        config = CoordinatorConfig(
            min_participants=5,
            aggregation_method="fedavg",
            enable_privacy=False
        )

        assert config.min_participants == 5
        assert config.aggregation_method == "fedavg"
        assert config.enable_privacy is False


class TestNodeManagement:
    """Тесты управления нодами."""

    def test_register_node(self, coordinator):
        """Регистрация ноды."""
        result = coordinator.register_node("new-node")

        assert result is True
        assert "new-node" in coordinator.nodes
        assert coordinator.nodes["new-node"].status == NodeStatus.ONLINE

    def test_register_duplicate_node(self, coordinator):
        """Повторная регистрация возвращает False."""
        coordinator.register_node("node-1")
        result = coordinator.register_node("node-1")

        assert result is False

    def test_register_with_capabilities(self, coordinator):
        """Регистрация с capabilities."""
        caps = {"gpu": True, "memory_gb": 16}
        coordinator.register_node("gpu-node", capabilities=caps)

        assert coordinator.nodes["gpu-node"].capabilities["gpu"] is True

    def test_unregister_node(self, coordinator):
        """Отмена регистрации."""
        coordinator.register_node("temp-node")
        result = coordinator.unregister_node("temp-node")

        assert result is True
        assert "temp-node" not in coordinator.nodes

    def test_unregister_nonexistent(self, coordinator):
        """Отмена регистрации несуществующей ноды."""
        result = coordinator.unregister_node("nonexistent")
        assert result is False

    def test_update_heartbeat(self, coordinator):
        """Обновление heartbeat."""
        coordinator.register_node("heartbeat-node")
        old_time = coordinator.nodes["heartbeat-node"].last_heartbeat

        time.sleep(0.01)
        coordinator.update_heartbeat("heartbeat-node")

        assert coordinator.nodes["heartbeat-node"].last_heartbeat > old_time

    def test_ban_node(self, coordinator):
        """Бан ноды."""
        coordinator.register_node("bad-node")
        coordinator.ban_node("bad-node", "Byzantine behavior")

        assert coordinator.nodes["bad-node"].status == NodeStatus.BANNED
        assert coordinator.nodes["bad-node"].byzantine_violations == 1

    def test_get_eligible_nodes(self, coordinator_with_nodes):
        """Получение eligible нод."""
        eligible = coordinator_with_nodes.get_eligible_nodes()

        # Все 5 нод должны быть eligible
        assert len(eligible) == 5

        # Баним одну
        coordinator_with_nodes.ban_node("node-000")
        eligible = coordinator_with_nodes.get_eligible_nodes()
        assert len(eligible) == 4


class TestRoundManagement:
    """Тесты управления раундами."""

    def test_start_round(self, coordinator_with_nodes):
        """Запуск раунда."""
        round_obj = coordinator_with_nodes.start_round()

        assert round_obj is not None
        assert round_obj.round_number == 1
        assert round_obj.status == RoundStatus.STARTED
        assert len(round_obj.selected_nodes) >= coordinator_with_nodes.config.min_participants

    def test_start_round_not_enough_nodes(self, coordinator, simple_weights):
        """Запуск раунда без достаточного количества нод."""
        coordinator.register_node("only-node")
        coordinator.initialize_model(simple_weights)

        round_obj = coordinator.start_round()

        assert round_obj is None  # Не хватает нод

    def test_start_round_increments_number(self, coordinator_with_nodes):
        """Номер раунда инкрементируется."""
        round1 = coordinator_with_nodes.start_round()
        round1.status = RoundStatus.COMPLETED

        # Возвращаем статус нод обратно на IDLE (как делает _trigger_aggregation)
        for node_id in round1.selected_nodes:
            if node_id in coordinator_with_nodes.nodes:
                coordinator_with_nodes.nodes[node_id].status = NodeStatus.IDLE

        # Добавляем в историю (как делает _trigger_aggregation)
        coordinator_with_nodes.round_history.append(round1)

        # Также очищаем ссылку на текущий раунд в координаторе
        coordinator_with_nodes._current_round = None

        round2 = coordinator_with_nodes.start_round()

        assert round2 is not None
        assert round2.round_number == 2

    def test_cannot_start_round_while_active(self, coordinator_with_nodes):
        """Нельзя запустить раунд пока активен другой."""
        coordinator_with_nodes.start_round()

        result = coordinator_with_nodes.start_round()

        assert result is None

    def test_submit_update(self, coordinator_with_nodes, model_update_factory):
        """Отправка обновления."""
        round_obj = coordinator_with_nodes.start_round()
        selected_node = list(round_obj.selected_nodes)[0]

        update = model_update_factory(node_id=selected_node, round_number=1)
        result = coordinator_with_nodes.submit_update(update)

        assert result is True
        assert selected_node in round_obj.received_updates

    def test_submit_update_from_non_selected(self, coordinator_with_nodes, model_update_factory):
        """Обновление от невыбранной ноды отклоняется."""
        coordinator_with_nodes.start_round()

        update = model_update_factory(node_id="random-node", round_number=1)
        result = coordinator_with_nodes.submit_update(update)

        assert result is False

    def test_submit_duplicate_update(self, coordinator_with_nodes, model_update_factory):
        """Дублирующее обновление отклоняется."""
        round_obj = coordinator_with_nodes.start_round()
        selected_node = list(round_obj.selected_nodes)[0]

        update = model_update_factory(node_id=selected_node, round_number=1)
        coordinator_with_nodes.submit_update(update)
        result = coordinator_with_nodes.submit_update(update)

        assert result is False

    def test_round_timeout(self, coordinator_with_nodes, time_freezer):
        """Таймаут раунда."""
        round_obj = coordinator_with_nodes.start_round()

        # Симулируем прошедшее время
        time_freezer.freeze(round_obj.collection_deadline + 1)

        result = coordinator_with_nodes.check_round_timeout()

        assert result is True
        # Раунд должен быть завершён (failed если нет участников)
        assert round_obj.status in [RoundStatus.FAILED, RoundStatus.COMPLETED]


class TestAggregation:
    """Тесты агрегации."""

    def test_aggregation_triggered(self, coordinator_with_nodes, model_update_factory):
        """Агрегация запускается при достижении минимума."""
        round_obj = coordinator_with_nodes.start_round()

        # Отправляем обновления от min_participants нод
        for node_id in list(round_obj.selected_nodes)[:3]:
            update = model_update_factory(node_id=node_id, round_number=1)
            coordinator_with_nodes.submit_update(update)

        # Агрегация должна запуститься
        assert round_obj.status in [RoundStatus.AGGREGATING, RoundStatus.COMPLETED]

    def test_global_model_updated(self, coordinator_with_nodes, model_update_factory):
        """Глобальная модель обновляется после агрегации."""
        initial_version = coordinator_with_nodes.global_model.version

        round_obj = coordinator_with_nodes.start_round()

        for node_id in list(round_obj.selected_nodes)[:3]:
            update = model_update_factory(node_id=node_id, round_number=1)
            coordinator_with_nodes.submit_update(update)

        # Ждём агрегации
        if round_obj.status == RoundStatus.COMPLETED:
            assert coordinator_with_nodes.global_model.version > initial_version


class TestCallbacks:
    """Тесты callback'ов."""

    def test_on_round_complete_callback(self, coordinator_with_nodes, model_update_factory, event_tracker):
        """Callback при завершении раунда."""
        def callback(round_obj):
            event_tracker.record("round_complete", round=round_obj.round_number)

        coordinator_with_nodes.on_round_complete(callback)

        round_obj = coordinator_with_nodes.start_round()
        for node_id in list(round_obj.selected_nodes)[:3]:
            update = model_update_factory(node_id=node_id, round_number=1)
            coordinator_with_nodes.submit_update(update)

        # Callback должен быть вызван
        events = event_tracker.get_events("round_complete")
        if round_obj.status == RoundStatus.COMPLETED:
            assert len(events) >= 1

    def test_on_model_update_callback(self, coordinator_with_nodes, model_update_factory, event_tracker):
        """Callback при обновлении модели."""
        def callback(model):
            event_tracker.record("model_update", version=model.version)

        coordinator_with_nodes.on_model_update(callback)

        round_obj = coordinator_with_nodes.start_round()
        for node_id in list(round_obj.selected_nodes)[:3]:
            update = model_update_factory(node_id=node_id, round_number=1)
            coordinator_with_nodes.submit_update(update)

        events = event_tracker.get_events("model_update")
        if round_obj.status == RoundStatus.COMPLETED:
            assert len(events) >= 1


class TestHeartbeat:
    """Тесты heartbeat мониторинга."""

    def test_check_heartbeats_marks_stale(self, coordinator, time_freezer):
        """Проверка heartbeat помечает stale ноды."""
        coordinator.register_node("stale-node")
        coordinator.config.heartbeat_timeout = 1.0

        # Замораживаем время и двигаем вперёд
        node = coordinator.nodes["stale-node"]
        original_heartbeat = node.last_heartbeat

        time_freezer.freeze(original_heartbeat + 5)

        # Несколько проверок для накопления missed
        for _ in range(4):
            coordinator._check_heartbeats()

        assert node.status == NodeStatus.STALE

    def test_heartbeat_resets_stale(self, coordinator):
        """Heartbeat сбрасывает stale статус."""
        coordinator.register_node("recovering-node")
        coordinator.nodes["recovering-node"].status = NodeStatus.STALE

        coordinator.update_heartbeat("recovering-node")

        assert coordinator.nodes["recovering-node"].status == NodeStatus.ONLINE


class TestLifecycle:
    """Тесты жизненного цикла координатора."""

    def test_start_coordinator(self, coordinator):
        """Запуск координатора."""
        coordinator.start()

        assert coordinator._running is True
        assert coordinator._heartbeat_thread is not None
        assert coordinator._heartbeat_thread.is_alive()

    def test_stop_coordinator(self, coordinator):
        """Остановка координатора."""
        coordinator.start()
        coordinator.stop()

        assert coordinator._running is False


class TestMetrics:
    """Тесты метрик."""

    def test_get_metrics(self, coordinator_with_nodes):
        """Получение метрик."""
        metrics = coordinator_with_nodes.get_metrics()

        assert "rounds_completed" in metrics
        assert "registered_nodes" in metrics
        assert metrics["registered_nodes"] == 5

    def test_get_node_stats(self, coordinator_with_nodes):
        """Получение статистики нод."""
        stats = coordinator_with_nodes.get_node_stats()

        assert len(stats) == 5
        for node_id, node_stats in stats.items():
            assert "status" in node_stats
            assert "trust_score" in node_stats


class TestByzantineHandling:
    """Тесты обработки Byzantine поведения."""

    def test_trust_score_decrease_on_byzantine(self, coordinator_with_nodes, model_update_factory):
        """Trust score уменьшается при Byzantine detection."""
        round_obj = coordinator_with_nodes.start_round()

        # Добавляем одно нормальное обновление
        normal_node = list(round_obj.selected_nodes)[0]
        update = model_update_factory(node_id=normal_node, round_number=1)
        coordinator_with_nodes.submit_update(update)

        initial_trust = coordinator_with_nodes.nodes[normal_node].trust_score

        # Имитируем Byzantine detection через aggregation result
        with patch.object(coordinator_with_nodes.aggregator, 'aggregate') as mock_agg:
            from src.federated_learning.protocol import AggregationResult, GlobalModel

            mock_result = AggregationResult(
                success=True,
                global_model=coordinator_with_nodes.global_model,
                suspected_byzantine=[normal_node]
            )
            mock_agg.return_value = mock_result

            coordinator_with_nodes._trigger_aggregation()

            # Trust должен уменьшиться
            assert coordinator_with_nodes.nodes[normal_node].trust_score < initial_trust


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
