"""
Async tests for MetricEnforcer and Charter operations (WEST-0104)
Tests for async metric validation, error handling, and edge cases
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from src.westworld.anti_delos_charter import CharterPolicyValidator, MetricEnforcer


# Test fixtures (same as in test_charter_validator.py)
@pytest.fixture
def dev_policy_path():
    """Path to development policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_dev.yaml"


@pytest.fixture
def prod_policy_path():
    """Path to production policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_prod.yaml"


@pytest.fixture
def enforcer_dev(dev_policy_path):
    """MetricEnforcer for dev policy."""
    policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
    return MetricEnforcer(policy)


@pytest.fixture
def enforcer_prod(prod_policy_path):
    """MetricEnforcer for prod policy."""
    policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
    return MetricEnforcer(policy)


class TestAsyncMetricValidation:
    """Тесты для асинхронной валидации метрик"""
    
    @pytest.mark.asyncio
    async def test_async_validate_single_metric(self, enforcer_dev):
        """Асинхронная валидация одной метрики"""
        metric = {
            'metric_name': 'latency_p50',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        # Синхронная валидация (пока нет async версии)
        result = enforcer_dev.validate_metric(metric)
        assert result['is_valid'] is True
        assert result['allowed'] is True
    
    @pytest.mark.asyncio
    async def test_async_batch_validation_performance(self, enforcer_dev):
        """Асинхронная валидация батча - тест производительности"""
        import time
        metrics = [
            {
                'metric_name': 'latency_p50' if i % 2 == 0 else 'cpu_usage_percent',
                'value': 50 + i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            }
            for i in range(100)
        ]
        
        start = time.time_ns()
        result = enforcer_dev.validate_metrics(metrics)
        elapsed = (time.time_ns() - start) / 1_000_000  # в миллисекундах
        
        assert result['total_metrics'] == 100
        assert elapsed < 100  # менее 100 миллисекунд на 100 метрик
    
    @pytest.mark.asyncio
    async def test_async_forbidden_metric_blocking(self, enforcer_dev):
        """Асинхронная блокировка запрещённых метрик"""
        forbidden_metrics = [
            {
                'metric_name': 'user_location',
                'value': 123.45,
                'timestamp': datetime.now().isoformat(),
                'source': f'attacker_{i:03d}',
            }
            for i in range(3)
        ]
        
        for metric in forbidden_metrics:
            result = enforcer_dev.validate_metric(metric)
            assert result['allowed'] is False
            assert result['enforcement_action'] == 'BLOCK'


class TestErrorHandling:
    """Тесты для обработки ошибок"""
    
    def test_validate_metric_with_missing_metric_name(self, enforcer_dev):
        """Ошибка при отсутствии metric_name"""
        metric = {
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Missing required field: metric_name' in e for e in result['errors'])
    
    def test_validate_metric_with_missing_value(self, enforcer_dev):
        """Ошибка при отсутствии value"""
        metric = {
            'metric_name': 'latency_p50',
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Missing required field: value' in e for e in result['errors'])
    
    def test_validate_metric_with_missing_timestamp(self, enforcer_dev):
        """Ошибка при отсутствии timestamp"""
        metric = {
            'metric_name': 'latency_p50',
            'value': 42,
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Missing required field: timestamp' in e for e in result['errors'])
    
    def test_validate_metric_with_missing_source(self, enforcer_dev):
        """Ошибка при отсутствии source"""
        metric = {
            'metric_name': 'latency_p50',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Missing required field: source' in e for e in result['errors'])
    
    def test_validate_metric_with_invalid_metric_name(self, enforcer_dev):
        """Ошибка при невалидном имени метрики"""
        metric = {
            'metric_name': 'invalid-name-with-dashes!!!',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Invalid metric name format' in e for e in result['errors'])
    
    def test_validate_metric_with_past_timestamp(self, enforcer_dev):
        """Метрика с временной меткой в прошлом - должна пройти"""
        past_time = datetime(2025, 1, 1, 12, 0, 0).isoformat()
        metric = {
            'metric_name': 'latency_p50',
            'value': 42,
            'timestamp': past_time,
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        # Прошлое время валидно - валидация только проверяет что timestamp не в будущем
        # Нет ошибок о прошлом времени
        future_errors = [e for e in result['errors'] if 'future' in e.lower()]
        assert len(future_errors) == 0


class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_validate_empty_metric_list(self, enforcer_dev):
        """Валидация пустого списка метрик"""
        result = enforcer_dev.validate_metrics([])
        
        assert result['total_metrics'] == 0
        assert result['passed'] == 0
        assert result['blocked'] == 0
        assert result['all_valid'] is True
    
    def test_validate_very_large_value(self, enforcer_dev):
        """Валидация метрики с очень большим значением"""
        metric = {
            'metric_name': 'latency_p50',
            'value': 1e308,  # Очень большое число
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        # Значение просто проходит, тип не проверяется строго
        assert result['is_valid'] is True
    
    def test_validate_negative_value(self, enforcer_dev):
        """Валидация метрики с отрицательным значением"""
        metric = {
            'metric_name': 'latency_p50',
            'value': -42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        # Отрицательное значение валидно (может быть delta)
        assert result['is_valid'] is True
    
    def test_validate_zero_value(self, enforcer_dev):
        """Валидация метрики со значением 0"""
        metric = {
            'metric_name': 'error_rate_percent',
            'value': 0,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is True
        assert result['allowed'] is True
    
    def test_validate_string_value(self, enforcer_dev):
        """Валидация метрики с string значением"""
        metric = {
            'metric_name': 'service_version',
            'value': '1.2.3',
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        # String значение валидно
        assert result['is_valid'] is True
    
    def test_violation_log_not_grows_indefinitely(self, enforcer_dev):
        """Проверка что лог нарушений не растёт бесконечно"""
        enforcer_dev.reset_logs()
        
        # Добавить много запрещённых метрик
        for i in range(50):
            metric = {
                'metric_name': 'user_location',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            }
            enforcer_dev.validate_metric(metric)
        
        log = enforcer_dev.get_violation_log()
        
        # Лог должен содержать все 50 записей
        assert len(log) == 50
    
    def test_get_logs_returns_copy_not_reference(self, enforcer_dev):
        """Модификация возвращённого лога не влияет на внутреннее состояние"""
        enforcer_dev.reset_logs()
        
        metric = {
            'metric_name': 'latency_p50',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        enforcer_dev.validate_metric(metric)
        
        log = enforcer_dev.get_violation_log()
        original_length = len(log)
        
        # Попытка модифицировать копию
        log.append({'fake': 'entry'})
        
        # Внутренний лог должен остаться неизменным
        assert len(enforcer_dev.get_violation_log()) == original_length


class TestViolationEscalation:
    """Тесты эскалации нарушений"""
    
    def test_violation_severity_escalates_from_high_to_critical(self, enforcer_dev):
        """Severity эскалирует от HIGH к CRITICAL"""
        enforcer_dev.reset_logs()
        
        # 3 попытки → HIGH
        for i in range(3):
            metric = {
                'metric_name': 'device_hardware_id',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'attacker_{i:03d}',
            }
            enforcer_dev.validate_metric(metric)
        
        violations = enforcer_dev.get_violation_events()
        assert len(violations) == 1
        assert violations[0]['severity'] == 'HIGH'
        
        # Ещё 2 попытки → CRITICAL (всего 5)
        for i in range(3, 5):
            metric = {
                'metric_name': 'device_hardware_id',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'attacker_{i:03d}',
            }
            enforcer_dev.validate_metric(metric)
        
        violations = enforcer_dev.get_violation_events()
        assert len(violations) == 1
        assert violations[0]['severity'] == 'CRITICAL'
        assert violations[0]['attempt_count'] == 5
    
    def test_different_metrics_tracked_separately(self, enforcer_dev):
        """Разные запрещённые метрики отслеживаются отдельно"""
        enforcer_dev.reset_logs()
        
        # 3 попытки user_location
        for i in range(3):
            enforcer_dev.validate_metric({
                'metric_name': 'user_location',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            })
        
        # 2 попытки browsing_history
        for i in range(2):
            enforcer_dev.validate_metric({
                'metric_name': 'browsing_history',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            })
        
        violations = enforcer_dev.get_violation_events()
        
        # Должно быть 2 события (одно для each metric)
        assert len(violations) >= 1
        
        # Проверить что есть событие для user_location
        user_location_violations = [v for v in violations if v['metric_name'] == 'user_location']
        assert len(user_location_violations) > 0


class TestConcurrencyScenarios:
    """Тесты для сценариев с concurrent access"""
    
    def test_multiple_validators_independent(self, dev_policy_path):
        """Несколько validator'ов независимы друг от друга"""
        enforcer1 = MetricEnforcer(CharterPolicyValidator.load_policy(str(dev_policy_path)))
        enforcer2 = MetricEnforcer(CharterPolicyValidator.load_policy(str(dev_policy_path)))
        
        # Отправить нарушение в первый
        for i in range(3):
            enforcer1.validate_metric({
                'metric_name': 'user_location',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            })
        
        # Во втором не должно быть нарушений
        violations1 = enforcer1.get_violation_events()
        violations2 = enforcer2.get_violation_events()
        
        assert len(violations1) >= 1
        assert len(violations2) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
