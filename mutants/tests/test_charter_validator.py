"""
Test suite for CharterPolicyValidator
Tests YAML policy loading, validation, and metric enforcement
"""

import pytest
from pathlib import Path
from src.westworld.anti_delos_charter import CharterPolicyValidator


# Test fixtures
@pytest.fixture
def dev_policy_path():
    """Path to development policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_dev.yaml"


@pytest.fixture
def prod_policy_path():
    """Path to production policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_prod.yaml"


@pytest.fixture
def staging_policy_path():
    """Path to staging policy file."""
    return Path(__file__).parent.parent / "src" / "westworld" / "policies_staging.yaml"


class TestCharterPolicyValidator:
    """Test CharterPolicyValidator class"""
    
    def test_load_dev_policy(self, dev_policy_path):
        """Test loading development policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        assert policy is not None
        assert "charter" in policy
        assert policy["charter"]["name"] == "dev-charter"
    
    def test_load_prod_policy(self, prod_policy_path):
        """Test loading production policy"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        assert policy is not None
        assert "charter" in policy
        assert policy["charter"]["name"] == "prod-charter"
    
    def test_load_staging_policy(self, staging_policy_path):
        """Test loading staging policy"""
        policy = CharterPolicyValidator.load_policy(str(staging_policy_path))
        assert policy is not None
        assert "charter" in policy
        assert policy["charter"]["name"] == "staging-charter"
    
    def test_load_nonexistent_policy(self):
        """Test loading nonexistent policy fails gracefully"""
        with pytest.raises(FileNotFoundError):
            CharterPolicyValidator.load_policy("/nonexistent/path/policy.yaml")
    
    def test_validate_dev_policy(self, dev_policy_path):
        """Test validation of development policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        is_valid, errors = CharterPolicyValidator.validate_policy(policy)
        assert is_valid, f"Policy validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_prod_policy(self, prod_policy_path):
        """Test validation of production policy"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        is_valid, errors = CharterPolicyValidator.validate_policy(policy)
        assert is_valid, f"Policy validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_staging_policy(self, staging_policy_path):
        """Test validation of staging policy"""
        policy = CharterPolicyValidator.load_policy(str(staging_policy_path))
        is_valid, errors = CharterPolicyValidator.validate_policy(policy)
        assert is_valid, f"Policy validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_missing_required_key(self):
        """Test validation fails for missing required key"""
        incomplete_policy = {
            "charter": {"version": "1.0.0", "name": "test"}
            # Missing other required keys
        }
        is_valid, errors = CharterPolicyValidator.validate_policy(incomplete_policy)
        assert not is_valid
        assert len(errors) > 0
    
    def test_whitelisted_metrics_dev(self, dev_policy_path):
        """Test getting whitelisted metrics from dev policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        metrics = CharterPolicyValidator.get_whitelisted_metrics(policy)
        assert "latency_p50" in metrics
        assert "latency_p95" in metrics
        assert "cpu_usage_percent" in metrics
        assert "user_location" not in metrics
    
    def test_whitelisted_metrics_count_dev(self, dev_policy_path):
        """Test count of whitelisted metrics in dev policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        metrics = CharterPolicyValidator.get_whitelisted_metrics(policy)
        # 6 network + 4 infrastructure + 3 service = 13 whitelisted
        assert len(metrics) == 13
    
    def test_whitelisted_metrics_count_prod(self, prod_policy_path):
        """Test count of whitelisted metrics in prod policy"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        metrics = CharterPolicyValidator.get_whitelisted_metrics(policy)
        # Same as dev: 13 whitelisted
        assert len(metrics) == 13
    
    def test_forbidden_metrics_dev(self, dev_policy_path):
        """Test getting forbidden metrics from dev policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        metrics = CharterPolicyValidator.get_forbidden_metrics(policy)
        assert "user_location" in metrics
        assert "user_identity" in metrics
        assert "browsing_history" in metrics
        assert "device_hardware_id" in metrics
        assert "user_communication_metadata" in metrics
        assert "system_logs_with_user_data" in metrics
    
    def test_forbidden_metrics_count(self, dev_policy_path):
        """Test count of forbidden metrics"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        metrics = CharterPolicyValidator.get_forbidden_metrics(policy)
        assert len(metrics) == 6
    
    def test_is_metric_allowed_whitelist(self, dev_policy_path):
        """Test checking if metric is allowed (whitelist)"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, "latency_p50")
        assert is_allowed
        assert reason is None
    
    def test_is_metric_allowed_forbidden(self, dev_policy_path):
        """Test checking if metric is forbidden"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, "user_location")
        assert not is_allowed
        assert "FORBIDDEN" in reason
    
    def test_is_metric_allowed_not_whitelisted(self, dev_policy_path):
        """Test checking if metric is not whitelisted"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, "unknown_metric")
        assert not is_allowed
        assert "NOT_WHITELISTED" in reason
    
    def test_policy_to_json_dev(self, dev_policy_path):
        """Test converting policy to JSON"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        json_str = CharterPolicyValidator.policy_to_json(policy)
        assert isinstance(json_str, str)
        assert "dev-charter" in json_str
        assert "latency_p50" in json_str
    
    def test_dev_environment_flag(self, dev_policy_path):
        """Test that dev policy has correct environment flag"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        assert policy["charter"]["metadata"]["environment"] == "development"
        assert policy["charter"]["metadata"]["status"] == "active"
    
    def test_prod_environment_requires_approval(self, prod_policy_path):
        """Test that prod policy requires approval"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        assert policy["charter"]["metadata"]["environment"] == "production"
        assert policy["charter"]["metadata"]["requires_approval"] is True
        assert policy["charter"]["metadata"]["status"] == "pending"
    
    def test_staging_environment_no_approval(self, staging_policy_path):
        """Test that staging policy doesn't require approval"""
        policy = CharterPolicyValidator.load_policy(str(staging_policy_path))
        assert policy["charter"]["metadata"]["environment"] == "staging"
        assert policy["charter"]["metadata"]["requires_approval"] is False
        assert policy["charter"]["metadata"]["status"] == "active"
    
    def test_prod_policy_higher_security(self, prod_policy_path):
        """Test that production policy has stricter access controls"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        ac = policy["access_control"]["read_access"]
        # Find audit_committee_member role
        audit_role = next((r for r in ac if r["role"] == "audit_committee_member"), None)
        assert audit_role is not None
        assert audit_role.get("requires_approval") is True
        assert "approval_ttl_hours" in audit_role
    
    def test_dev_policy_faster_override_renewal(self, dev_policy_path):
        """Test that dev policy has faster emergency override renewal"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        assert policy["emergency_override"]["auto_renewal_hours"] == 2
        assert policy["emergency_override"]["enabled"] is True
        assert policy["emergency_override"]["requires_dao_vote"] is False
    
    def test_prod_policy_requires_dao_vote(self, prod_policy_path):
        """Test that prod policy requires DAO vote for emergency override"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        assert policy["emergency_override"]["requires_dao_vote"] is True
        assert "requires_minimum_quorum_percent" in policy["emergency_override"]
    
    def test_policy_version_consistency(self, dev_policy_path, prod_policy_path, staging_policy_path):
        """Test that all policies have version 1.0.0"""
        dev = CharterPolicyValidator.load_policy(str(dev_policy_path))
        prod = CharterPolicyValidator.load_policy(str(prod_policy_path))
        staging = CharterPolicyValidator.load_policy(str(staging_policy_path))
        
        assert dev["charter"]["version"] == "1.0.0"
        assert prod["charter"]["version"] == "1.0.0"
        assert staging["charter"]["version"] == "1.0.0"
    
    def test_forbidden_metrics_consistent(self, dev_policy_path, prod_policy_path):
        """Test that forbidden metrics are consistent across policies"""
        dev = CharterPolicyValidator.load_policy(str(dev_policy_path))
        prod = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        dev_forbidden = CharterPolicyValidator.get_forbidden_metrics(dev)
        prod_forbidden = CharterPolicyValidator.get_forbidden_metrics(prod)
        
        assert set(dev_forbidden) == set(prod_forbidden)


class TestCharterPolicyScenarios:
    """Test real-world scenarios with policies"""
    
    def test_scenario_normal_metric_collection(self, dev_policy_path):
        """Test normal metric collection scenario"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        
        # Simulating node collecting normal metrics
        metrics_to_collect = ["latency_p50", "cpu_usage_percent", "disk_usage_percent"]
        
        for metric in metrics_to_collect:
            is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, metric)
            assert is_allowed, f"Metric {metric} should be allowed: {reason}"
    
    def test_scenario_forbidden_metric_blocked(self, prod_policy_path):
        """Test that forbidden metrics are blocked in all scenarios"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        forbidden_attempts = [
            "user_location",
            "user_identity",
            "browsing_history",
            "device_hardware_id"
        ]
        
        for metric in forbidden_attempts:
            is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, metric)
            assert not is_allowed, f"Metric {metric} should be forbidden"
            assert "FORBIDDEN" in reason or "NOT_WHITELISTED" in reason
    
    def test_scenario_unauthorized_metric_access(self, prod_policy_path):
        """Test that unauthorized metrics are not accessible"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        # Try accessing a metric that doesn't exist in whitelist
        is_allowed, reason = CharterPolicyValidator.is_metric_allowed(policy, "internal_cache_size")
        assert not is_allowed
        assert "NOT_WHITELISTED" in reason


# Performance tests
class TestCharterPolicyPerformance:
    """Test performance characteristics of policy validation"""
    
    def test_policy_load_performance(self, dev_policy_path):
        """Test that policy loading is fast (<150ms)"""
        import time
        start = time.time()
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        elapsed = (time.time() - start) * 1000  # Convert to ms
        assert elapsed < 150, f"Policy loading took {elapsed}ms, expected <150ms"
    
    def test_metric_validation_performance(self, dev_policy_path):
        """Test that metric validation is fast (<10ms)"""
        import time
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        
        start = time.time()
        for _ in range(100):  # Test 100 checks
            CharterPolicyValidator.is_metric_allowed(policy, "latency_p50")
        elapsed = (time.time() - start) * 1000  # Convert to ms
        avg_per_check = elapsed / 100
        assert avg_per_check < 1, f"Average check took {avg_per_check}ms, expected <1ms"


class TestCharterValidationReport:
    """Test validation report generation"""
    
    def test_generate_validation_report_dev(self, dev_policy_path):
        """Test validation report generation for dev policy"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        report = CharterPolicyValidator.generate_validation_report(policy)
        
        assert 'timestamp' in report
        assert 'policy_name' in report
        assert report['policy_name'] == 'dev-charter'
        assert report['overall_status'] == 'PASS'
        assert report['total_errors'] == 0
        assert report['metrics']['whitelisted'] == 13
        assert report['metrics']['forbidden'] == 6
    
    def test_generate_validation_report_prod(self, prod_policy_path):
        """Test validation report generation for prod policy"""
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        report = CharterPolicyValidator.generate_validation_report(policy)
        
        assert report['policy_name'] == 'prod-charter'
        assert report['environment'] == 'production'
        assert report['overall_status'] == 'PASS'
        assert report['has_emergency_override'] is True
        assert report['has_whistleblower_policy'] is True
    
    def test_validation_report_structure(self, dev_policy_path):
        """Test that validation report has all required fields"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        report = CharterPolicyValidator.generate_validation_report(policy)
        
        required_fields = [
            'timestamp', 'policy_name', 'environment', 'overall_status',
            'total_errors', 'errors', 'metrics', 'access_control',
            'violation_levels', 'has_whistleblower_policy', 'has_emergency_override',
            'recommendations'
        ]
        for field in required_fields:
            assert field in report, f"Report missing field: {field}"
    
    def test_validation_report_metrics_structure(self, dev_policy_path):
        """Test that metrics in report have correct structure"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        report = CharterPolicyValidator.generate_validation_report(policy)
        
        assert 'whitelisted' in report['metrics']
        assert 'forbidden' in report['metrics']
        assert isinstance(report['metrics']['whitelisted'], int)
        assert isinstance(report['metrics']['forbidden'], int)


class TestCharterPolicyComparison:
    """Test policy comparison functionality"""
    
    def test_compare_identical_policies(self, dev_policy_path):
        """Test comparing identical policies"""
        policy1 = CharterPolicyValidator.load_policy(str(dev_policy_path))
        policy2 = CharterPolicyValidator.load_policy(str(dev_policy_path))
        
        comparison = CharterPolicyValidator.compare_policies(policy1, policy2)
        
        assert comparison['is_identical_metrics'] is True
        assert comparison['is_identical_forbidden'] is True
        assert len(comparison['metrics']['added']) == 0
        assert len(comparison['metrics']['removed']) == 0
    
    def test_compare_different_policies(self, dev_policy_path, prod_policy_path):
        """Test comparing different policies"""
        policy1 = CharterPolicyValidator.load_policy(str(dev_policy_path))
        policy2 = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        comparison = CharterPolicyValidator.compare_policies(policy1, policy2)
        
        assert 'metrics' in comparison
        assert 'forbidden_metrics' in comparison
        assert 'versions' in comparison
        assert 'environments' in comparison
    
    def test_comparison_has_required_fields(self, dev_policy_path, prod_policy_path):
        """Test that comparison has all required fields"""
        policy1 = CharterPolicyValidator.load_policy(str(dev_policy_path))
        policy2 = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        comparison = CharterPolicyValidator.compare_policies(policy1, policy2)
        
        required_fields = [
            'policy1_name', 'policy2_name', 'metrics', 'forbidden_metrics',
            'versions', 'environments', 'is_identical_metrics', 'is_identical_forbidden'
        ]
        for field in required_fields:
            assert field in comparison, f"Comparison missing field: {field}"
    
    def test_comparison_metrics_structure(self, dev_policy_path, prod_policy_path):
        """Test that comparison metrics have correct structure"""
        policy1 = CharterPolicyValidator.load_policy(str(dev_policy_path))
        policy2 = CharterPolicyValidator.load_policy(str(prod_policy_path))
        
        comparison = CharterPolicyValidator.compare_policies(policy1, policy2)
        
        assert 'added' in comparison['metrics']
        assert 'removed' in comparison['metrics']
        assert 'unchanged' in comparison['metrics']
        assert isinstance(comparison['metrics']['added'], list)
        assert isinstance(comparison['metrics']['removed'], list)
        assert isinstance(comparison['metrics']['unchanged'], list)


class TestEnhancedValidationMethods:
    """Test enhanced validation methods"""
    
    def test_validate_metric_schema(self, dev_policy_path):
        """Test metric schema validation"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        
        # Get whitelisted metrics and validate schema
        metrics_list = policy.get('whitelisted_metrics', {})
        for category, metrics in metrics_list.items():
            errors = CharterPolicyValidator.validate_metric_schema(metrics)
            assert len(errors) == 0, f"Schema validation failed for {category}: {errors}"
    
    def test_validate_access_control(self, dev_policy_path):
        """Test access control validation"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        ac = policy.get('access_control', {})
        
        errors = CharterPolicyValidator.validate_access_control(ac)
        assert len(errors) == 0, f"Access control validation failed: {errors}"
    
    def test_validate_violation_policy(self, dev_policy_path):
        """Test violation policy validation"""
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        vp = policy.get('violation_policy', {})
        
        errors = CharterPolicyValidator.validate_violation_policy(vp)
        assert len(errors) == 0, f"Violation policy validation failed: {errors}"
    
    def test_validate_metric_schema_all_policies(self, dev_policy_path, prod_policy_path, staging_policy_path):
        """Test metric schema validation for all policies"""
        for policy_path in [dev_policy_path, prod_policy_path, staging_policy_path]:
            policy = CharterPolicyValidator.load_policy(str(policy_path))
            metrics_list = policy.get('whitelisted_metrics', {})
            
            for category, metrics in metrics_list.items():
                errors = CharterPolicyValidator.validate_metric_schema(metrics)
                assert len(errors) == 0, f"Schema validation failed for {category}: {errors}"


class TestMetricEnforcement:
    """Тесты для модуля принудительного применения метрик (MetricEnforcer)."""
    
    @pytest.fixture
    def enforcer_dev(self, dev_policy_path):
        """Enforcer для dev политики."""
        from src.westworld.anti_delos_charter import MetricEnforcer
        policy = CharterPolicyValidator.load_policy(str(dev_policy_path))
        return MetricEnforcer(policy)
    
    @pytest.fixture
    def enforcer_prod(self, prod_policy_path):
        """Enforcer для prod политики."""
        from src.westworld.anti_delos_charter import MetricEnforcer
        policy = CharterPolicyValidator.load_policy(str(prod_policy_path))
        return MetricEnforcer(policy)
    
    # Базовая валидация (3 теста)
    
    def test_validate_whitelisted_metric_success(self, enforcer_dev):
        """Разрешённая метрика проходит валидацию успешно."""
        from datetime import datetime
        metric = {
            'metric_name': 'user_login_count',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is True
        assert result['allowed'] is True
        assert result['enforcement_action'] == 'ALLOW'
        assert len(result['errors']) == 0
    
    def test_validate_missing_required_fields(self, enforcer_dev):
        """Отсутствие обязательных полей вызывает ошибку."""
        metric = {
            'metric_name': 'user_login_count',
            # Отсутствует value, timestamp, source
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        assert any('Missing required field' in e for e in result['errors'])
    
    def test_validate_invalid_timestamp_format(self, enforcer_dev):
        """Неверный формат временной метки вызывает ошибку."""
        metric = {
            'metric_name': 'user_login_count',
            'value': 42,
            'timestamp': 'not-a-valid-timestamp',
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is False
        assert any('Invalid timestamp format' in e for e in result['errors'])
    
    # Блокировка запрещённых (3 теста)
    
    def test_block_forbidden_metric(self, enforcer_dev):
        """Запрещённая метрика блокируется."""
        from datetime import datetime
        metric = {
            'metric_name': 'user_location',  # Запрещённая в dev политике
            'value': 10,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        result = enforcer_dev.validate_metric(metric)
        
        assert result['is_valid'] is True  # Формально валидна
        assert result['allowed'] is False
        assert result['enforcement_action'] == 'BLOCK'
        assert result['reason'] == 'FORBIDDEN_METRIC'
    
    def test_block_multiple_forbidden_metrics(self, enforcer_dev):
        """Несколько запрещённых метрик отклоняются."""
        from datetime import datetime
        metrics = [
            {
                'metric_name': 'user_location',
                'value': 10,
                'timestamp': datetime.now().isoformat(),
                'source': 'node_001',
            },
            {
                'metric_name': 'browsing_history',
                'value': 5,
                'timestamp': datetime.now().isoformat(),
                'source': 'node_002',
            },
            {
                'metric_name': 'latency_p50',  # ОК
                'value': 100,
                'timestamp': datetime.now().isoformat(),
                'source': 'node_003',
            },
        ]
        result = enforcer_dev.validate_metrics(metrics)
        
        assert result['total_metrics'] == 3
        assert result['blocked'] == 2
        assert result['passed'] == 1
    
    def test_allow_whitelisted_with_forbidden_in_batch(self, enforcer_prod):
        """Батч с разрешёнными и запрещёнными метриками корректно обработан."""
        from datetime import datetime
        metrics = [
            {'metric_name': 'latency_p50', 'value': 50, 'timestamp': datetime.now().isoformat(), 'source': 'n1'},
            {'metric_name': 'user_identity', 'value': 1, 'timestamp': datetime.now().isoformat(), 'source': 'n2'},
        ]
        result = enforcer_prod.validate_metrics(metrics)
        
        assert result['total_metrics'] == 2
        assert result['blocked'] == 1
        assert result['passed'] == 1
    
    # Обнаружение нарушений (3 теста)
    
    def test_detect_violation_on_multiple_attempts(self, enforcer_dev):
        """Нарушение определяется при 3+ попытках за 60 сек."""
        from datetime import datetime
        
        # Отправить 3 запрещённые метрики
        for i in range(3):
            metric = {
                'metric_name': 'user_location',
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'node_{i:03d}',
            }
            enforcer_dev.validate_metric(metric)
        
        violations = enforcer_dev.get_violation_events()
        assert len(violations) == 1
        assert violations[0]['metric_name'] == 'user_location'
        assert violations[0]['attempt_count'] == 3
        assert violations[0]['severity'] == 'HIGH'
        assert violations[0]['recommended_action'] == 'ESCALATE_TO_DAO'
    
    def test_detect_critical_violation(self, enforcer_dev):
        """Критическое нарушение при 5+ попытках."""
        from datetime import datetime
        
        # Используем новый enforcer для изолированного теста
        from src.westworld.anti_delos_charter import MetricEnforcer
        from pathlib import Path
        policy = CharterPolicyValidator.load_policy(
            str(Path(__file__).parent.parent / "src" / "westworld" / "policies_dev.yaml")
        )
        enforcer_test = MetricEnforcer(policy)
        
        # Отправить 5 запрещённых метрик
        for i in range(5):
            metric = {
                'metric_name': 'device_hardware_id',  # Разная от предыдущих тестов
                'value': i,
                'timestamp': datetime.now().isoformat(),
                'source': f'attacker_{i:03d}',
            }
            enforcer_test.validate_metric(metric)
        
        violations = enforcer_test.get_violation_events()
        assert len(violations) == 1
        assert violations[0]['severity'] == 'CRITICAL'
        assert violations[0]['recommended_action'] == 'IMMEDIATE_SHUTDOWN'
        assert violations[0]['attempt_count'] == 5
    
    def test_no_violation_on_single_attempt(self, enforcer_dev):
        """Одна попытка не создаёт событие нарушения."""
        from datetime import datetime
        
        metric = {
            'metric_name': 'delos_connection_pool',
            'value': 1,
            'timestamp': datetime.now().isoformat(),
            'source': 'node_001',
        }
        enforcer_dev.validate_metric(metric)
        
        violations = enforcer_dev.get_violation_events()
        assert len(violations) == 0  # Нет события нарушения
    
    # Логирование (2 теста)
    
    def test_violation_log_records_all_attempts(self, enforcer_dev):
        """Все попытки отправки метрик записываются в лог."""
        from datetime import datetime
        
        enforcer_dev.reset_logs()
        metrics = [
            {'metric_name': 'user_login_count', 'value': 1, 'timestamp': datetime.now().isoformat(), 'source': 'n1'},
            {'metric_name': 'delos_heartbeat', 'value': 1, 'timestamp': datetime.now().isoformat(), 'source': 'n2'},
            {'metric_name': 'user_logout_count', 'value': 1, 'timestamp': datetime.now().isoformat(), 'source': 'n3'},
        ]
        
        for metric in metrics:
            enforcer_dev.validate_metric(metric)
        
        log = enforcer_dev.get_violation_log()
        assert len(log) == 3
        assert all('timestamp' in entry and 'metric_name' in entry for entry in log)
    
    def test_violation_log_includes_source_and_timestamp(self, enforcer_dev):
        """Лог содержит source и timestamp для каждой попытки."""
        from datetime import datetime
        
        enforcer_dev.reset_logs()
        metric = {
            'metric_name': 'user_login_count',
            'value': 42,
            'timestamp': datetime.now().isoformat(),
            'source': 'critical_node_987',
        }
        enforcer_dev.validate_metric(metric)
        
        log = enforcer_dev.get_violation_log()
        assert len(log) == 1
        assert log[0]['source'] == 'critical_node_987'
        assert 'timestamp' in log[0]
        assert 'action' in log[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
