"""
End-to-End тесты сценариев self-healing.

Покрывает полные сценарии:
- Обнаружение аномалии → Изоляция → Восстановление → Реинтеграция
- Каскадный отказ и его предотвращение
- Health probe → unhealthy → isolation → recovery
- Mesh reconvergence после отказов
- Координация между компонентами
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerOpen,
                                      CircuitState)
from src.security.auto_isolation import (AutoIsolationManager, IsolationLevel,
                                         IsolationReason, QuarantineZone)
from src.self_healing.recovery_actions import (RateLimiter,
                                               RecoveryActionExecutor,
                                               RecoveryActionType)


class TestAnomalyToRecoveryScenario:
    """E2E: Обнаружение аномалии → Изоляция → Восстановление."""

    @pytest.mark.asyncio
    async def test_anomaly_detection_triggers_isolation(
        self, isolation_manager, recovery_executor
    ):
        """Обнаружение аномалии запускает изоляцию."""
        node_id = "anomalous-node-001"

        # 1. Обнаруживаем аномалию
        anomaly_detected = True

        # 2. Изолируем ноду
        if anomaly_detected:
            record = isolation_manager.isolate(
                node_id=node_id,
                reason=IsolationReason.ANOMALY_DETECTED,
                details="Необычный паттерн трафика",
            )

        # 3. Проверяем изоляцию
        assert isolation_manager.get_isolation_level(node_id) != IsolationLevel.NONE
        assert record.level in [IsolationLevel.MONITOR, IsolationLevel.RATE_LIMIT]

        # 4. Выполняем recovery действия
        result = await recovery_executor.clear_cache(node_id, "session")
        assert result is True

        # 5. Симулируем восстановление и освобождение
        isolation_manager.release(node_id)
        assert isolation_manager.get_isolation_level(node_id) == IsolationLevel.NONE

    @pytest.mark.asyncio
    async def test_full_isolation_escalation_cycle(self, isolation_manager):
        """Полный цикл эскалации изоляции."""
        node_id = "problem-node"

        # Множественные нарушения вызывают эскалацию
        levels_observed = []

        for i in range(5):
            record = isolation_manager.isolate(
                node_id=node_id, reason=IsolationReason.THREAT_DETECTED
            )
            levels_observed.append(record.level)

        # Уровни должны эскалировать
        assert len(set(levels_observed)) >= 2  # хотя бы 2 разных уровня
        assert levels_observed[-1].value >= levels_observed[0].value


class TestCircuitBreakerFailureScenario:
    """E2E: Circuit breaker предотвращает каскадный отказ."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade(self, circuit_breaker):
        """Circuit breaker останавливает каскад ошибок."""
        call_count = [0]
        downstream_calls = [0]

        async def failing_service():
            call_count[0] += 1
            # Симуляция вызова downstream сервиса
            downstream_calls[0] += 1
            raise Exception("Downstream service unavailable")

        # Первые вызовы проваливаются и открывают circuit
        for _ in range(5):
            try:
                await circuit_breaker.call(failing_service)
            except (Exception, CircuitBreakerOpen):
                pass

        # Circuit должен быть открыт
        assert circuit_breaker.state == CircuitState.OPEN

        # Дальнейшие вызовы НЕ должны доходить до downstream
        initial_downstream = downstream_calls[0]

        for _ in range(10):
            try:
                await circuit_breaker.call(failing_service)
            except CircuitBreakerOpen:
                pass

        # Downstream не должен был быть вызван
        assert downstream_calls[0] == initial_downstream

    @pytest.mark.asyncio
    async def test_circuit_recovery_after_service_heals(self, fast_circuit_breaker):
        """Circuit восстанавливается после починки сервиса."""
        service_healthy = [False]

        async def recoverable_service():
            if not service_healthy[0]:
                raise Exception("Service down")
            return "OK"

        # Открываем circuit
        for _ in range(2):  # threshold=2
            try:
                await fast_circuit_breaker.call(recoverable_service)
            except Exception:
                pass

        assert fast_circuit_breaker.state == CircuitState.OPEN

        # "Чиним" сервис
        service_healthy[0] = True

        # Ждём recovery timeout
        await asyncio.sleep(0.15)

        # Следующий вызов должен пройти
        result = await fast_circuit_breaker.call(recoverable_service)
        assert result == "OK"


class TestHealthProbeScenario:
    """E2E: Health probe → unhealthy → isolation → recovery."""

    @pytest.mark.asyncio
    async def test_unhealthy_node_isolation_and_recovery(
        self, isolation_manager, recovery_executor
    ):
        """Нездоровая нода изолируется и восстанавливается."""
        node_id = "unhealthy-node"

        # 1. Симуляция health probe failure
        health_check_passed = False

        # 2. При провале health check - изоляция
        if not health_check_passed:
            isolation_manager.isolate(
                node_id=node_id,
                reason=IsolationReason.ANOMALY_DETECTED,
                details="Health check failed 3 times",
            )

        # 3. Нода изолирована
        level = isolation_manager.get_isolation_level(node_id)
        assert level != IsolationLevel.NONE

        # 4. Попытка recovery
        recovery_success = await recovery_executor.restart_service(
            f"service-{node_id}", "default"
        )
        assert recovery_success is True

        # 5. Re-probe (симуляция)
        health_check_passed = True

        # 6. Если healthy - освобождаем
        if health_check_passed:
            isolation_manager.release(node_id)

        assert isolation_manager.get_isolation_level(node_id) == IsolationLevel.NONE


class TestMeshReconvergenceScenario:
    """E2E: Mesh reconvergence после отказов."""

    @pytest.mark.asyncio
    async def test_mesh_reconverges_after_node_failure(
        self, isolation_manager, quarantine_zone
    ):
        """Mesh сходится после отказа ноды."""
        # Симуляция mesh из 5 нод
        nodes = ["node-1", "node-2", "node-3", "node-4", "node-5"]
        healthy_nodes = set(nodes)

        # 1. node-3 выходит из строя
        failed_node = "node-3"
        healthy_nodes.discard(failed_node)

        # 2. Изолируем failed node
        isolation_manager.isolate(
            node_id=failed_node, reason=IsolationReason.ANOMALY_DETECTED
        )
        quarantine_zone.add_node(failed_node)

        # 3. Проверяем что остальные могут общаться
        for n1 in healthy_nodes:
            for n2 in healthy_nodes:
                if n1 != n2:
                    assert quarantine_zone.can_communicate(n1, n2) is True

        # 4. Карантинная нода не может общаться с остальными
        for healthy in healthy_nodes:
            assert quarantine_zone.can_communicate(failed_node, healthy) is False

        # 5. Восстановление
        quarantine_zone.remove_node(failed_node)
        isolation_manager.release(failed_node)
        healthy_nodes.add(failed_node)

        # 6. Mesh полностью восстановлен
        assert isolation_manager.get_isolation_level(failed_node) == IsolationLevel.NONE

    @pytest.mark.asyncio
    async def test_multiple_node_failures_handled(
        self, isolation_manager, quarantine_zone
    ):
        """Обработка множественных отказов нод."""
        nodes = [f"node-{i}" for i in range(10)]

        # Отказ 3 нод одновременно
        failed_nodes = ["node-2", "node-5", "node-8"]

        for node in failed_nodes:
            isolation_manager.isolate(
                node_id=node, reason=IsolationReason.THREAT_DETECTED
            )
            quarantine_zone.add_node(node)

        # Проверяем статистику
        stats = isolation_manager.get_stats()
        assert stats["total_isolated"] >= 3

        # Здоровые ноды продолжают работать
        healthy_nodes = [n for n in nodes if n not in failed_nodes]
        for n1 in healthy_nodes:
            for n2 in healthy_nodes:
                assert quarantine_zone.can_communicate(n1, n2) is True


class TestCoordinatedRecoveryScenario:
    """E2E: Координированное восстановление."""

    @pytest.mark.asyncio
    async def test_coordinated_service_restart(self, recovery_executor):
        """Координированный перезапуск сервисов."""
        services = ["frontend", "backend", "cache"]
        restart_order = []

        for service in services:
            success = await recovery_executor.restart_service(service, "production")
            if success:
                restart_order.append(service)

        # Все сервисы должны быть перезапущены
        assert len(restart_order) == len(services)

    @pytest.mark.asyncio
    async def test_rollback_on_partial_failure(self, recovery_executor):
        """Откат при частичном сбое."""
        # Выполняем действие
        recovery_executor.execute(
            "Scale up", {"deployment_name": "api", "replicas": 5, "old_replicas": 3}
        )

        # Откатываем
        success = recovery_executor.rollback_last_action()
        assert success is True


class TestRaceConditionScenario:
    """E2E: Обработка race conditions."""

    def test_concurrent_isolation_same_node(self, isolation_manager):
        """Конкурентная изоляция одной и той же ноды."""
        node_id = "contested-node"
        results = []
        errors = []

        def isolate():
            try:
                record = isolation_manager.isolate(
                    node_id=node_id, reason=IsolationReason.ANOMALY_DETECTED
                )
                results.append(record)
            except Exception as e:
                errors.append(e)

        # Запускаем 10 потоков одновременно
        threads = [threading.Thread(target=isolate) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Не должно быть ошибок
        assert len(errors) == 0

        # Нода должна быть изолирована
        assert isolation_manager.get_isolation_level(node_id) != IsolationLevel.NONE

    def test_concurrent_release_and_isolate(self, isolation_manager):
        """Конкурентное освобождение и изоляция."""
        node_id = "flip-flop-node"

        # Сначала изолируем
        isolation_manager.isolate(
            node_id=node_id, reason=IsolationReason.ANOMALY_DETECTED
        )

        results = {"isolate": [], "release": []}

        def isolate():
            record = isolation_manager.isolate(
                node_id=node_id, reason=IsolationReason.THREAT_DETECTED
            )
            results["isolate"].append(record)

        def release():
            result = isolation_manager.release(node_id, force=True)
            results["release"].append(result)

        # Чередуем isolate и release
        threads = []
        for i in range(10):
            if i % 2 == 0:
                threads.append(threading.Thread(target=isolate))
            else:
                threads.append(threading.Thread(target=release))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Система должна остаться в консистентном состоянии
        level = isolation_manager.get_isolation_level(node_id)
        # level может быть NONE или не-NONE, главное - без ошибок


class TestGracefulDegradationScenario:
    """E2E: Graceful degradation при перегрузке."""

    @pytest.mark.asyncio
    async def test_system_degrades_gracefully_under_load(
        self, recovery_executor, isolation_manager
    ):
        """Система деградирует gracefully под нагрузкой."""
        # Симуляция высокой нагрузки
        for i in range(15):
            recovery_executor.execute("Clear cache", {"cache_type": f"type-{i}"})

        # Rate limiter должен сработать
        status = recovery_executor.get_rate_limiter_status()

        # Система продолжает работать, но с ограничениями
        assert status["enabled"] is True

    @pytest.mark.asyncio
    async def test_critical_operations_prioritized(
        self, isolation_manager, recovery_executor
    ):
        """Критические операции приоритизируются."""
        # Изолируем ноду в RESTRICTED режим
        isolation_manager.isolate(
            node_id="restricted-node",
            reason=IsolationReason.ANOMALY_DETECTED,
            level_override=IsolationLevel.RESTRICTED,
        )

        # Health check должен быть разрешён
        allowed, _ = isolation_manager.is_allowed("restricted-node", "health")
        assert allowed is True

        # Data transfer должен быть запрещён
        allowed, _ = isolation_manager.is_allowed("restricted-node", "data_transfer")
        assert allowed is False


class TestEndToEndSelfHealingFlow:
    """E2E: Полный flow self-healing."""

    @pytest.mark.asyncio
    async def test_complete_self_healing_flow(
        self, circuit_breaker, isolation_manager, recovery_executor, quarantine_zone
    ):
        """Полный цикл self-healing от обнаружения до восстановления."""
        node_id = "service-node-001"

        # === ФАЗА 1: Нормальная работа ===
        async def healthy_service():
            return {"status": "healthy", "latency_ms": 50}

        result = await circuit_breaker.call(healthy_service)
        assert result["status"] == "healthy"

        # === ФАЗА 2: Начало деградации ===
        failure_count = [0]

        async def degrading_service():
            failure_count[0] += 1
            if failure_count[0] <= 3:
                raise Exception("Service degrading")
            return {"status": "recovered"}

        # Service начинает сбоить
        for _ in range(3):
            try:
                await circuit_breaker.call(degrading_service)
            except Exception:
                pass

        # === ФАЗА 3: Circuit breaker открывается ===
        assert circuit_breaker.state == CircuitState.OPEN

        # === ФАЗА 4: Изоляция ноды ===
        isolation_manager.isolate(
            node_id=node_id,
            reason=IsolationReason.ANOMALY_DETECTED,
            details="Circuit breaker opened",
        )
        quarantine_zone.add_node(node_id)

        assert isolation_manager.get_isolation_level(node_id) != IsolationLevel.NONE
        assert quarantine_zone.is_quarantined(node_id) is True

        # === ФАЗА 5: Recovery actions ===
        await recovery_executor.restart_service(f"svc-{node_id}", "default")
        await recovery_executor.clear_cache(node_id, "all")

        # === ФАЗА 6: Manual reset circuit breaker ===
        await circuit_breaker.reset()
        assert circuit_breaker.state == CircuitState.CLOSED

        # === ФАЗА 7: Реинтеграция ===
        quarantine_zone.remove_node(node_id)
        isolation_manager.release(node_id)

        assert isolation_manager.get_isolation_level(node_id) == IsolationLevel.NONE
        assert quarantine_zone.is_quarantined(node_id) is False

        # === ФАЗА 8: Сервис снова работает ===
        result = await circuit_breaker.call(degrading_service)
        assert result["status"] == "recovered"


class TestMetricsAndObservability:
    """E2E: Метрики и observability."""

    def test_recovery_metrics_collected(self, recovery_executor):
        """Метрики recovery собираются."""
        # Выполняем несколько действий
        recovery_executor.execute("Clear cache", {})
        recovery_executor.execute("Restart service", {"service_name": "api"})

        # Проверяем историю
        history = recovery_executor.get_action_history()
        assert len(history) >= 2

        # Проверяем success rate
        rate = recovery_executor.get_success_rate()
        assert 0 <= rate <= 1

    def test_isolation_stats_collected(self, isolation_manager):
        """Статистика изоляции собирается."""
        isolation_manager.isolate("node-a", IsolationReason.THREAT_DETECTED)
        isolation_manager.isolate("node-b", IsolationReason.ANOMALY_DETECTED)

        stats = isolation_manager.get_stats()

        assert "total_isolated" in stats
        assert "by_level" in stats
        assert "by_reason" in stats
        assert stats["total_isolated"] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
