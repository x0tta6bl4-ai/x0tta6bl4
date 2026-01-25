"""
Integration tests for Charter operations (WEST-0104)
Tests for PolicyValidator, CLI commands, and cross-module interactions
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timezone
from src.westworld.anti_delos_charter import CharterPolicyValidator, MetricEnforcer
from src.westworld.charter_admin import CharterAdminCLI


@pytest.fixture
def dev_policy_path():
    """Path to development policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_dev.yaml"


@pytest.fixture
def validator_policy(dev_policy_path):
    """Loaded policy for dev environment."""
    return CharterPolicyValidator.load_policy(str(dev_policy_path))


@pytest.fixture
def enforcer(validator_policy):
    """MetricEnforcer instance."""
    return MetricEnforcer(validator_policy)


class TestPolicyLoading:
    """Тесты загрузки политик"""
    
    def test_load_dev_policy(self, validator_policy):
        """Загрузить dev политику"""
        assert validator_policy is not None
        assert isinstance(validator_policy, dict)
    
    def test_policy_has_required_sections(self, validator_policy):
        """Политика имеет требуемые секции"""
        required = ['whitelisted_metrics', 'forbidden_metrics']
        for section in required:
            assert section in validator_policy


class TestMetricValidation:
    """Тесты валидации метрик"""
    
    def test_valid_whitelisted_metric(self, enforcer):
        """Валидная разрешённая метрика"""
        metric = {
            'metric_name': 'cpu_usage_percent',
            'value': 45.5,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer.validate_metric(metric)
        assert result['allowed'] is True
        assert result['enforcement_action'] == 'ALLOW'
    
    def test_forbidden_metric_blocked(self, enforcer):
        """Запрещённая метрика блокируется"""
        metric = {
            'metric_name': 'user_location',
            'value': 123.45,
            'timestamp': datetime.now().isoformat(),
            'source': 'attacker',
        }
        result = enforcer.validate_metric(metric)
        assert result['allowed'] is False
        assert result['enforcement_action'] == 'BLOCK'
    
    def test_batch_validation(self, enforcer):
        """Пакетная валидация"""
        metrics = [
            {
                'metric_name': 'latency_p50',
                'value': 50,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i}',
            }
            for i in range(10)
        ]
        result = enforcer.validate_metrics(metrics)
        assert result['total_metrics'] == 10
        assert result['blocked'] == 0


class TestViolationTracking:
    """Тесты отслеживания нарушений"""
    
    def test_violation_logged_on_forbidden_metric(self, enforcer):
        """Нарушение логируется при запрещённой метрике"""
        enforcer.reset_logs()
        
        metric = {
            'metric_name': 'device_hardware_id',
            'value': 123,
            'timestamp': datetime.now().isoformat(),
            'source': 'attacker_1',
        }
        enforcer.validate_metric(metric)
        
        violations = enforcer.get_violation_log()
        assert len(violations) > 0
    
    def test_violation_escalation(self, enforcer):
        """Эскалация нарушений при повторных попытках"""
        enforcer.reset_logs()
        
        # 3 попытки → HIGH
        for i in range(3):
            metric = {
                'metric_name': 'device_hardware_id',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'attacker_{i}',
            }
            enforcer.validate_metric(metric)
        
        events = enforcer.get_violation_events()
        assert len(events) >= 1
        assert events[0]['severity'] == 'HIGH'


class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    def test_missing_required_field(self, enforcer):
        """Отсутствие обязательного поля"""
        metric = {'metric_name': 'test'}
        result = enforcer.validate_metric(metric)
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
    
    def test_invalid_metric_name(self, enforcer):
        """Невалидное имя метрики"""
        metric = {
            'metric_name': 'invalid-name!!!',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer.validate_metric(metric)
        assert result['is_valid'] is False


class TestPolicyComparison:
    """Тесты сравнения политик"""
    
    def test_compare_same_policy(self, validator_policy):
        """Сравнить политику с собой"""
        diff = CharterPolicyValidator.compare_policies(validator_policy, validator_policy)
        assert isinstance(diff, dict)
        assert len(diff.get('added_forbidden', [])) == 0
        assert len(diff.get('removed_forbidden', [])) == 0


class TestCLIInitialization:
    """Тесты инициализации CLI"""
    
    def test_cli_can_be_created(self):
        """CLI может быть создана"""
        cli = CharterAdminCLI()
        assert cli is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
