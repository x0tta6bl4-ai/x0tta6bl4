"""
Тесты для AutoIsolationManager.

Покрывает:
- Уровни изоляции (NONE → MONITOR → RATE_LIMIT → RESTRICTED → QUARANTINE → BLOCKED)
- Эскалацию при повторных нарушениях
- Автоматическое восстановление
- Политики изоляции
- Circuit breaker для нод
- Quarantine zone
- Конкурентный доступ
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch

from src.security.auto_isolation import (
    IsolationLevel,
    IsolationReason,
    IsolationRecord,
    IsolationPolicy,
    AutoIsolationManager,
    CircuitBreaker as IsolationCircuitBreaker,
    QuarantineZone,
)


class TestIsolationLevel:
    """Тесты для enum IsolationLevel."""

    def test_isolation_levels_order(self):
        """Уровни изоляции имеют правильный порядок."""
        assert IsolationLevel.NONE.value < IsolationLevel.MONITOR.value
        assert IsolationLevel.MONITOR.value < IsolationLevel.RATE_LIMIT.value
        assert IsolationLevel.RATE_LIMIT.value < IsolationLevel.RESTRICTED.value
        assert IsolationLevel.RESTRICTED.value < IsolationLevel.QUARANTINE.value
        assert IsolationLevel.QUARANTINE.value < IsolationLevel.BLOCKED.value

    def test_all_isolation_levels_exist(self):
        """Все ожидаемые уровни изоляции существуют."""
        levels = [level.name for level in IsolationLevel]
        assert "NONE" in levels
        assert "MONITOR" in levels
        assert "RATE_LIMIT" in levels
        assert "RESTRICTED" in levels
        assert "QUARANTINE" in levels
        assert "BLOCKED" in levels


class TestIsolationReason:
    """Тесты для enum IsolationReason."""

    def test_all_reasons_exist(self):
        """Все причины изоляции существуют."""
        reasons = [reason.value for reason in IsolationReason]
        assert "threat_detected" in reasons
        assert "trust_degraded" in reasons
        assert "anomaly_detected" in reasons
        assert "auth_failure" in reasons
        assert "protocol_violation" in reasons
        assert "admin_action" in reasons
        assert "peer_consensus" in reasons
        assert "resource_abuse" in reasons


class TestIsolationRecord:
    """Тесты для IsolationRecord."""

    def test_record_creation(self):
        """Создание записи об изоляции."""
        record = IsolationRecord(
            node_id="node-001",
            level=IsolationLevel.RESTRICTED,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=time.time(),
            expires_at=time.time() + 300,
            details="Подозрительная активность"
        )

        assert record.node_id == "node-001"
        assert record.level == IsolationLevel.RESTRICTED
        assert record.reason == IsolationReason.THREAT_DETECTED
        assert record.auto_recover is True  # по умолчанию

    def test_is_expired_false(self):
        """Запись не истекла."""
        record = IsolationRecord(
            node_id="node-001",
            level=IsolationLevel.MONITOR,
            reason=IsolationReason.ANOMALY_DETECTED,
            started_at=time.time(),
            expires_at=time.time() + 300  # через 5 минут
        )
        assert record.is_expired() is False

    def test_is_expired_true(self):
        """Запись истекла."""
        record = IsolationRecord(
            node_id="node-001",
            level=IsolationLevel.MONITOR,
            reason=IsolationReason.ANOMALY_DETECTED,
            started_at=time.time() - 600,
            expires_at=time.time() - 300  # истекла 5 минут назад
        )
        assert record.is_expired() is True

    def test_is_expired_no_expiry(self):
        """Запись без срока истечения не истекает."""
        record = IsolationRecord(
            node_id="node-001",
            level=IsolationLevel.BLOCKED,
            reason=IsolationReason.PROTOCOL_VIOLATION,
            started_at=time.time() - 86400,  # сутки назад
            expires_at=None  # бессрочно
        )
        assert record.is_expired() is False

    def test_to_dict(self):
        """Сериализация в словарь."""
        now = time.time()
        record = IsolationRecord(
            node_id="node-001",
            level=IsolationLevel.QUARANTINE,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=now,
            expires_at=now + 3600,
            escalation_count=2,
            details="Обнаружена угроза"
        )

        data = record.to_dict()
        assert data["node_id"] == "node-001"
        assert data["level"] == "QUARANTINE"
        assert data["reason"] == "threat_detected"
        assert data["escalation_count"] == 2


class TestIsolationPolicy:
    """Тесты для IsolationPolicy."""

    def test_policy_creation(self, isolation_policy):
        """Создание политики изоляции."""
        assert isolation_policy.name == "test_policy"
        assert isolation_policy.trigger_reason == IsolationReason.THREAT_DETECTED
        assert isolation_policy.initial_level == IsolationLevel.RATE_LIMIT

    def test_get_duration_initial(self, isolation_policy):
        """Начальная длительность изоляции."""
        duration = isolation_policy.get_duration(0)
        assert duration == 60  # initial_duration

    def test_get_duration_escalation(self, isolation_policy):
        """Длительность увеличивается при эскалации."""
        duration_0 = isolation_policy.get_duration(0)
        duration_1 = isolation_policy.get_duration(1)
        duration_2 = isolation_policy.get_duration(2)

        assert duration_1 > duration_0
        assert duration_2 > duration_1
        # multiplier = 2.0, so duration doubles
        assert duration_1 == duration_0 * 2

    def test_get_duration_respects_max(self, isolation_policy):
        """Длительность не превышает максимум."""
        duration = isolation_policy.get_duration(100)  # очень много эскалаций
        assert duration <= isolation_policy.max_duration

    def test_get_level_initial(self, isolation_policy):
        """Начальный уровень изоляции."""
        level = isolation_policy.get_level(0)
        assert level == IsolationLevel.RATE_LIMIT

    def test_get_level_escalation(self, isolation_policy):
        """Уровень повышается при эскалации."""
        level_0 = isolation_policy.get_level(0)
        level_1 = isolation_policy.get_level(1)
        level_2 = isolation_policy.get_level(2)

        assert level_1.value >= level_0.value
        assert level_2.value >= level_1.value

    def test_get_level_max(self, isolation_policy):
        """Уровень не превышает максимальный."""
        level = isolation_policy.get_level(100)
        assert level == isolation_policy.escalation_levels[-1]


class TestAutoIsolationManager:
    """Тесты для AutoIsolationManager."""

    def test_manager_initialization(self, isolation_manager):
        """Инициализация менеджера."""
        assert isolation_manager.node_id == "manager-node-001"
        assert len(isolation_manager.isolated_nodes) == 0
        assert len(isolation_manager.policies) > 0

    def test_isolate_node_basic(self, isolation_manager):
        """Базовая изоляция ноды."""
        record = isolation_manager.isolate(
            node_id="suspect-node-001",
            reason=IsolationReason.THREAT_DETECTED,
            details="Обнаружена подозрительная активность"
        )

        assert record.node_id == "suspect-node-001"
        assert record.level.value >= IsolationLevel.RESTRICTED.value
        assert isolation_manager.get_isolation_level("suspect-node-001") != IsolationLevel.NONE

    def test_isolate_with_level_override(self, isolation_manager):
        """Изоляция с переопределением уровня."""
        record = isolation_manager.isolate(
            node_id="node-002",
            reason=IsolationReason.ANOMALY_DETECTED,
            level_override=IsolationLevel.BLOCKED
        )

        assert record.level == IsolationLevel.BLOCKED

    def test_isolate_with_duration_override(self, isolation_manager):
        """Изоляция с переопределением длительности."""
        record = isolation_manager.isolate(
            node_id="node-003",
            reason=IsolationReason.ANOMALY_DETECTED,
            duration_override=7200  # 2 часа
        )

        expected_expiry = record.started_at + 7200
        assert abs(record.expires_at - expected_expiry) < 1

    def test_escalation_on_repeated_violations(self, isolation_manager):
        """Эскалация при повторных нарушениях."""
        # Первая изоляция
        record1 = isolation_manager.isolate(
            node_id="repeat-offender",
            reason=IsolationReason.THREAT_DETECTED
        )
        initial_level = record1.level

        # Повторное нарушение - должна быть эскалация
        record2 = isolation_manager.isolate(
            node_id="repeat-offender",
            reason=IsolationReason.THREAT_DETECTED
        )

        # Уровень должен повыситься или остаться тем же (если уже максимальный)
        assert record2.level.value >= initial_level.value
        assert record2.escalation_count >= 1

    def test_release_node(self, isolation_manager):
        """Освобождение ноды из изоляции."""
        isolation_manager.isolate(
            node_id="temp-isolated",
            reason=IsolationReason.ANOMALY_DETECTED
        )

        result = isolation_manager.release("temp-isolated")
        assert result is True
        assert isolation_manager.get_isolation_level("temp-isolated") == IsolationLevel.NONE

    def test_release_nonexistent_node(self, isolation_manager):
        """Освобождение несуществующей ноды возвращает False."""
        result = isolation_manager.release("nonexistent-node")
        assert result is False

    def test_release_force_required_for_manual_only(self, isolation_manager):
        """Принудительное освобождение для записей с auto_recover=False."""
        # Изолируем с протокольным нарушением (auto_recover=False)
        isolation_manager.isolate(
            node_id="protocol-violator",
            reason=IsolationReason.PROTOCOL_VIOLATION
        )

        # Обычное освобождение не работает
        result = isolation_manager.release("protocol-violator", force=False)
        assert result is False

        # Принудительное освобождение работает
        result = isolation_manager.release("protocol-violator", force=True)
        assert result is True

    def test_get_isolation_level(self, isolation_manager):
        """Получение уровня изоляции."""
        # Не изолированная нода
        level = isolation_manager.get_isolation_level("normal-node")
        assert level == IsolationLevel.NONE

        # Изолированная нода
        isolation_manager.isolate(
            node_id="isolated-node",
            reason=IsolationReason.THREAT_DETECTED
        )
        level = isolation_manager.get_isolation_level("isolated-node")
        assert level != IsolationLevel.NONE

    def test_is_allowed_normal_node(self, isolation_manager):
        """Проверка разрешений для обычной ноды."""
        allowed, reason = isolation_manager.is_allowed("normal-node", "any_operation")
        assert allowed is True
        assert reason == "OK"

    def test_is_allowed_monitored_node(self, isolation_manager):
        """Проверка разрешений для мониторируемой ноды."""
        isolation_manager.isolate(
            node_id="monitored-node",
            reason=IsolationReason.ANOMALY_DETECTED,
            level_override=IsolationLevel.MONITOR
        )

        allowed, reason = isolation_manager.is_allowed("monitored-node", "any_operation")
        assert allowed is True
        assert "Monitored" in reason

    def test_is_allowed_restricted_node(self, isolation_manager):
        """Проверка разрешений для ограниченной ноды."""
        isolation_manager.isolate(
            node_id="restricted-node",
            reason=IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.RESTRICTED
        )

        # Essential операции разрешены
        allowed, _ = isolation_manager.is_allowed("restricted-node", "health")
        assert allowed is True

        # Non-essential операции запрещены
        allowed, reason = isolation_manager.is_allowed("restricted-node", "data_transfer")
        assert allowed is False
        assert "not allowed" in reason

    def test_is_allowed_quarantined_node(self, isolation_manager):
        """Проверка разрешений для ноды в карантине."""
        isolation_manager.isolate(
            node_id="quarantined-node",
            reason=IsolationReason.PROTOCOL_VIOLATION,
            level_override=IsolationLevel.QUARANTINE
        )

        # Только health check разрешён
        allowed, _ = isolation_manager.is_allowed("quarantined-node", "health")
        assert allowed is True

        # Всё остальное заблокировано
        allowed, _ = isolation_manager.is_allowed("quarantined-node", "heartbeat")
        assert allowed is False

    def test_is_allowed_blocked_node(self, isolation_manager):
        """Проверка разрешений для заблокированной ноды."""
        isolation_manager.isolate(
            node_id="blocked-node",
            reason=IsolationReason.PROTOCOL_VIOLATION,
            level_override=IsolationLevel.BLOCKED
        )

        # Всё заблокировано
        allowed, reason = isolation_manager.is_allowed("blocked-node", "health")
        assert allowed is False
        assert "Blocked" in reason

    def test_callback_registration(self, isolation_manager, event_tracker):
        """Регистрация и вызов callback при изоляции."""
        def callback(node_id, level):
            event_tracker.record("isolation", node_id=node_id, level=level.name)

        isolation_manager.register_callback(callback)

        isolation_manager.isolate(
            node_id="callback-test-node",
            reason=IsolationReason.THREAT_DETECTED
        )

        events = event_tracker.get_events("isolation")
        assert len(events) >= 1
        assert events[0]["node_id"] == "callback-test-node"

    def test_cleanup_expired(self, isolation_manager):
        """Очистка истёкших записей."""
        # Создаём истёкшую запись
        now = time.time()
        record = IsolationRecord(
            node_id="expired-node",
            level=IsolationLevel.MONITOR,
            reason=IsolationReason.ANOMALY_DETECTED,
            started_at=now - 600,
            expires_at=now - 300,  # истекла
            auto_recover=True
        )
        isolation_manager.isolated_nodes["expired-node"] = record

        # Очищаем
        cleaned = isolation_manager.cleanup_expired()
        assert cleaned >= 1
        assert "expired-node" not in isolation_manager.isolated_nodes

    def test_get_isolated_nodes(self, isolation_manager):
        """Получение списка изолированных нод."""
        isolation_manager.isolate("node-a", IsolationReason.THREAT_DETECTED)
        isolation_manager.isolate("node-b", IsolationReason.ANOMALY_DETECTED)

        nodes = isolation_manager.get_isolated_nodes()
        node_ids = [n["node_id"] for n in nodes]

        assert "node-a" in node_ids
        assert "node-b" in node_ids

    def test_get_stats(self, isolation_manager):
        """Получение статистики изоляции."""
        isolation_manager.isolate(
            "node-1",
            IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.RESTRICTED
        )
        isolation_manager.isolate(
            "node-2",
            IsolationReason.ANOMALY_DETECTED,
            level_override=IsolationLevel.MONITOR
        )

        stats = isolation_manager.get_stats()

        assert stats["total_isolated"] >= 2
        assert "by_level" in stats
        assert "by_reason" in stats


class TestIsolationCircuitBreaker:
    """Тесты для circuit breaker изоляции."""

    def test_initial_state_closed(self, isolation_circuit_breaker):
        """Начальное состояние - CLOSED."""
        assert isolation_circuit_breaker.state == IsolationCircuitBreaker.State.CLOSED

    def test_allows_requests_when_closed(self, isolation_circuit_breaker):
        """CLOSED состояние разрешает запросы."""
        assert isolation_circuit_breaker.allow_request() is True

    def test_opens_after_failure_threshold(self, isolation_circuit_breaker):
        """Открывается после превышения порога ошибок."""
        # failure_threshold=3
        for _ in range(3):
            isolation_circuit_breaker.record_failure()

        assert isolation_circuit_breaker.state == IsolationCircuitBreaker.State.OPEN

    def test_rejects_when_open(self, isolation_circuit_breaker):
        """OPEN состояние отклоняет запросы."""
        # Открываем circuit
        for _ in range(3):
            isolation_circuit_breaker.record_failure()

        assert isolation_circuit_breaker.allow_request() is False

    def test_transitions_to_half_open(self, isolation_circuit_breaker):
        """Переход в HALF_OPEN после timeout."""
        # Открываем
        for _ in range(3):
            isolation_circuit_breaker.record_failure()

        # Симулируем прошедшее время
        isolation_circuit_breaker.last_failure_time = time.time() - 2  # recovery_timeout=1

        # Должен перейти в HALF_OPEN
        assert isolation_circuit_breaker.allow_request() is True
        assert isolation_circuit_breaker.state == IsolationCircuitBreaker.State.HALF_OPEN

    def test_closes_after_successes_in_half_open(self, isolation_circuit_breaker):
        """Закрывается после успехов в HALF_OPEN."""
        isolation_circuit_breaker.state = IsolationCircuitBreaker.State.HALF_OPEN
        isolation_circuit_breaker.half_open_successes = 0

        # half_open_requests=2
        isolation_circuit_breaker.record_success()
        isolation_circuit_breaker.record_success()

        assert isolation_circuit_breaker.state == IsolationCircuitBreaker.State.CLOSED

    def test_reopens_on_failure_in_half_open(self, isolation_circuit_breaker):
        """Переоткрывается при ошибке в HALF_OPEN."""
        isolation_circuit_breaker.state = IsolationCircuitBreaker.State.HALF_OPEN

        isolation_circuit_breaker.record_failure()

        assert isolation_circuit_breaker.state == IsolationCircuitBreaker.State.OPEN

    def test_success_decrements_failure_count(self, isolation_circuit_breaker):
        """Успех уменьшает счётчик ошибок."""
        isolation_circuit_breaker.failure_count = 2

        isolation_circuit_breaker.record_success()

        assert isolation_circuit_breaker.failure_count == 1


class TestQuarantineZone:
    """Тесты для QuarantineZone."""

    def test_zone_creation(self, quarantine_zone):
        """Создание зоны карантина."""
        assert quarantine_zone.zone_id == "test-quarantine-zone"
        assert len(quarantine_zone.nodes) == 0

    def test_add_node_to_quarantine(self, quarantine_zone):
        """Добавление ноды в карантин."""
        quarantine_zone.add_node("infected-node")

        assert quarantine_zone.is_quarantined("infected-node") is True

    def test_remove_node_from_quarantine(self, quarantine_zone):
        """Удаление ноды из карантина."""
        quarantine_zone.add_node("recovering-node")
        quarantine_zone.remove_node("recovering-node")

        assert quarantine_zone.is_quarantined("recovering-node") is False

    def test_communication_both_outside(self, quarantine_zone):
        """Коммуникация разрешена между нодами вне карантина."""
        result = quarantine_zone.can_communicate("normal-a", "normal-b")
        assert result is True

    def test_communication_both_inside(self, quarantine_zone):
        """Коммуникация разрешена между нодами внутри карантина."""
        quarantine_zone.add_node("quarantined-a")
        quarantine_zone.add_node("quarantined-b")

        result = quarantine_zone.can_communicate("quarantined-a", "quarantined-b")
        assert result is True

    def test_communication_mixed_blocked(self, quarantine_zone):
        """Коммуникация запрещена между карантинной и обычной нодой."""
        quarantine_zone.add_node("quarantined")

        result = quarantine_zone.can_communicate("quarantined", "normal")
        assert result is False

    def test_communication_allowed_peer(self, quarantine_zone):
        """Коммуникация разрешена с allowed_peers."""
        quarantine_zone.add_node("quarantined")
        quarantine_zone.allowed_peers.add("monitoring-service")

        result = quarantine_zone.can_communicate("quarantined", "monitoring-service")
        assert result is True

    def test_operation_allowed_in_quarantine(self, quarantine_zone):
        """Проверка разрешённых операций в карантине."""
        assert quarantine_zone.is_operation_allowed("health") is True
        assert quarantine_zone.is_operation_allowed("metrics") is True

    def test_operation_blocked_in_quarantine(self, quarantine_zone):
        """Проверка запрещённых операций в карантине."""
        assert quarantine_zone.is_operation_allowed("data_transfer") is False
        assert quarantine_zone.is_operation_allowed("mesh_sync") is False


class TestConcurrency:
    """Тесты конкурентного доступа."""

    def test_concurrent_isolation(self, isolation_manager):
        """Конкурентная изоляция множества нод."""
        results = []

        def isolate_node(node_id):
            try:
                record = isolation_manager.isolate(
                    node_id=node_id,
                    reason=IsolationReason.ANOMALY_DETECTED
                )
                results.append(record)
            except Exception as e:
                results.append(e)

        threads = [
            threading.Thread(target=isolate_node, args=(f"node-{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все изоляции должны быть успешными
        assert len(results) == 10
        assert all(isinstance(r, IsolationRecord) for r in results)

    def test_concurrent_circuit_breaker_access(self, isolation_circuit_breaker):
        """Конкурентный доступ к circuit breaker."""
        results = []

        def record_operation(is_success):
            try:
                if is_success:
                    isolation_circuit_breaker.record_success()
                else:
                    isolation_circuit_breaker.record_failure()
                results.append(True)
            except Exception as e:
                results.append(e)

        threads = []
        for i in range(20):
            is_success = i % 3 != 0  # ~2/3 успехов
            threads.append(
                threading.Thread(target=record_operation, args=(is_success,))
            )

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все операции должны быть успешными
        assert all(r is True for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
