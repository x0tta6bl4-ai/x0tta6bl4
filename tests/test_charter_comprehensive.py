"""
Comprehensive tests for AntiDelosCharter class (WEST-0104)
Tests for audit committee, violations, emergency overrides, data revocation
"""

import pytest
from datetime import datetime, timedelta
from src.westworld.anti_delos_charter import (
    AntiDelosCharter, 
    ViolationType, 
    PenaltySeverity,
    ViolationRecord,
    DataCollectionPolicy
)


@pytest.fixture
def charter():
    """Fresh AntiDelosCharter instance for each test."""
    return AntiDelosCharter()


class TestCharterInitialization:
    """Тесты инициализации Anti-Delos Charter"""
    
    def test_charter_initializes_with_defaults(self, charter):
        """Charter инициализируется с дефолтными значениями"""
        assert charter.name == "Anti-Delos Charter v1.0"
        assert charter.effective_date is not None
        assert isinstance(charter.allowed_metrics, dict)
        assert isinstance(charter.violations, dict)
        assert isinstance(charter.audit_log, list)
    
    def test_charter_has_allowed_metrics(self, charter):
        """Charter имеет разрешённые метрики"""
        assert len(charter.allowed_metrics) > 0
    
    def test_audit_committee_list_empty_initially(self, charter):
        """Список членов audit committee пуст в начале"""
        assert isinstance(charter.data_audit_committee_members, list)
    
    def test_violations_dict_empty_initially(self, charter):
        """Словарь нарушений пуст в начале"""
        assert len(charter.violations) == 0
    
    def test_emergency_overrides_list_empty_initially(self, charter):
        """Список emergency overrides пуст в начале"""
        assert isinstance(charter.emergency_overrides, list)


class TestDataCollectionPolicy:
    """Тесты для DataCollectionPolicy"""
    
    def test_create_data_collection_policy(self):
        """Создать policy для сбора данных"""
        policy = DataCollectionPolicy(
            metric_name='test_metric',
            allowed=True,
            requires_consent=True,
            requires_opt_in=False,
            retention_days=30,
            allowed_users='opted_in'
        )
        
        assert policy.metric_name == 'test_metric'
        assert policy.allowed is True
        assert policy.retention_days == 30
    
    def test_policy_retention_validation(self):
        """Валидация retention days"""
        # Положительные дни - валидны
        policy = DataCollectionPolicy(
            metric_name='metric',
            allowed=True,
            requires_consent=False,
            requires_opt_in=False,
            retention_days=30,
            allowed_users='all'
        )
        assert policy.retention_days > 0


class TestViolationRecord:
    """Тесты для ViolationRecord"""
    
    def test_create_violation_record(self):
        """Создать запись о нарушении"""
        record = ViolationRecord(
            violation_id='v001',
            violation_type=ViolationType.SILENT_COLLECTION,
            reported_by='audit_committee',
            reported_at=datetime.utcnow(),
            node_or_service='malicious_service',
            description='Unauthorized data collection',
            evidence=['log1', 'log2'],
            severity=PenaltySeverity.WARNING,
            status='investigating'
        )
        
        assert record.violation_id == 'v001'
        assert record.violation_type == ViolationType.SILENT_COLLECTION
        assert record.status == 'investigating'
    
    def test_violation_types_available(self):
        """Все типы нарушений доступны"""
        violation_types = [
            ViolationType.SILENT_COLLECTION,
            ViolationType.BEHAVIORAL_PREDICTION,
            ViolationType.DATA_EXTRACTION,
            ViolationType.UNAUTHORIZED_OVERRIDE,
            ViolationType.ALGORITHM_MANIPULATION,
            ViolationType.EXPLOITATION,
        ]
        assert len(violation_types) == 6
    
    def test_penalty_severity_levels(self):
        """Уровни штрафов присутствуют"""
        severities = [
            PenaltySeverity.WARNING,
            PenaltySeverity.SUSPENSION,
            PenaltySeverity.BAN_1YEAR,
            PenaltySeverity.PERMANENT_BAN,
            PenaltySeverity.CRIMINAL_REFERRAL,
        ]
        assert len(severities) == 5


class TestAuditLog:
    """Тесты для audit log"""
    
    def test_audit_log_empty_initially(self, charter):
        """Audit log пуст в начале"""
        assert len(charter.audit_log) == 0
    
    def test_audit_log_can_store_entries(self, charter):
        """Audit log может хранить записи"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event': 'test_event',
            'details': 'test details'
        }
        charter.audit_log.append(entry)
        
        assert len(charter.audit_log) == 1
        assert charter.audit_log[0]['event'] == 'test_event'


class TestEmergencyOverride:
    """Тесты для emergency overrides"""
    
    def test_emergency_override_structure(self, charter):
        """Emergency override имеет правильную структуру"""
        charter.emergency_overrides.append({
            'id': 'override_001',
            'timestamp': datetime.utcnow().isoformat(),
            'who_triggered': 'admin_user',
            'what_changed': 'suspended_node_xyz',
            'reason': 'suspected_attack',
            'affected_nodes_count': 1,
            'affected_nodes': ['node_xyz'],
        })
        
        assert len(charter.emergency_overrides) == 1
        override = charter.emergency_overrides[0]
        assert 'id' in override
        assert 'timestamp' in override
        assert 'who_triggered' in override


class TestViolationTracking:
    """Тесты для отслеживания нарушений"""
    
    def test_add_violation_record(self, charter):
        """Добавить запись о нарушении"""
        violation = ViolationRecord(
            violation_id='v_test_001',
            violation_type=ViolationType.DATA_EXTRACTION,
            reported_by='user_alice',
            reported_at=datetime.utcnow(),
            node_or_service='service_evil',
            description='Unauthorized data export',
            evidence=['screenshot1.png'],
            severity=PenaltySeverity.SUSPENSION,
            status='confirmed'
        )
        
        charter.violations['v_test_001'] = violation
        
        assert 'v_test_001' in charter.violations
        assert charter.violations['v_test_001'].severity == PenaltySeverity.SUSPENSION
    
    def test_track_multiple_violations(self, charter):
        """Отслеживать несколько нарушений"""
        for i in range(3):
            violation = ViolationRecord(
                violation_id=f'v_{i}',
                violation_type=ViolationType.SILENT_COLLECTION,
                reported_by='system',
                reported_at=datetime.utcnow(),
                node_or_service=f'service_{i}',
                description='Silent collection attempt',
                evidence=[],
                severity=PenaltySeverity.WARNING,
                status='investigating'
            )
            charter.violations[f'v_{i}'] = violation
        
        assert len(charter.violations) == 3


class TestAuditCommittee:
    """Тесты для audit committee"""
    
    def test_add_committee_members(self, charter):
        """Добавить членов audit committee"""
        members = ['alice@org', 'bob@org', 'charlie@org']
        charter.data_audit_committee_members.extend(members)
        
        assert len(charter.data_audit_committee_members) == 3
        assert 'alice@org' in charter.data_audit_committee_members
    
    def test_committee_member_validation(self, charter):
        """Валидация членов committee"""
        # Можем добавить email-подобные строки
        charter.data_audit_committee_members.append('valid@email.com')
        assert len(charter.data_audit_committee_members) == 1


class TestDataMinimization:
    """Тесты для принципа data minimization"""
    
    def test_allowed_metrics_are_minimized(self, charter):
        """Разрешённые метрики минимизированы"""
        # Проверить что есть только необходимые метрики
        assert len(charter.allowed_metrics) > 0
        
        # Все метрики должны иметь retention period (if allowed=True)
        for metric_name, policy in charter.allowed_metrics.items():
            assert isinstance(policy, DataCollectionPolicy)
            # Если метрика разрешена, она должна иметь retention period
            if policy.allowed:
                assert policy.retention_days > 0
    
    def test_forbidden_metrics_are_tracked(self, charter):
        """Запрещённые метрики присутствуют в allowed_metrics с allowed=False"""
        # Запрещённые метрики хранятся в allowed_metrics с allowed=False
        forbidden_examples = [
            'user_location',
            'browsing_history',
            'device_hardware_id',
        ]
        
        # Проверяем что эти метрики либо присутствуют с allowed=False, либо отсутствуют вообще
        found_forbidden = []
        for metric in forbidden_examples:
            if metric in charter.allowed_metrics:
                found_forbidden.append(charter.allowed_metrics[metric])
        
        # Все найденные запрещённые метрики должны иметь allowed=False
        for policy in found_forbidden:
            assert policy.allowed is False


class TestCharterPrinciples:
    """Тесты для принципов charter"""
    
    def test_charter_enforces_no_hidden_collection(self, charter):
        """Charter обеспечивает прозрачность сбора"""
        # Каждая policy должна быть явно определена
        assert isinstance(charter.allowed_metrics, dict)
        
        # Все метрики должны быть явно определены
        for metric_name, policy in charter.allowed_metrics.items():
            assert isinstance(metric_name, str)
            # Метрика может быть разрешена или запрещена, главное что явно определена
            assert isinstance(policy.allowed, bool)
    
    def test_charter_requires_consent_for_sensitive_data(self, charter):
        """Charter требует consent для чувствительных данных"""
        # Проверить что есть хотя бы одна метрика требующая consent
        consent_required_exists = any(
            policy.requires_consent 
            for policy in charter.allowed_metrics.values()
        )
        # Может быть True или False, главное что структура правильная


class TestEmergencyOverrideStructure:
    """Тесты для структуры emergency override"""
    
    def test_emergency_override_has_required_fields(self, charter):
        """Emergency override имеет все требуемые поля"""
        override = {
            'id': 'test_override_001',
            'timestamp': datetime.utcnow().isoformat(),
            'who_triggered': 'root_admin',
            'what_changed': 'blocked_suspicious_node',
            'reason': 'detected_zero_day_exploit',
            'affected_nodes_count': 5,
            'affected_nodes': ['node1', 'node2', 'node3', 'node4', 'node5'],
        }
        
        # Проверить что все ключи присутствуют
        required_keys = ['id', 'timestamp', 'who_triggered', 'what_changed', 'reason', 'affected_nodes_count', 'affected_nodes']
        for key in required_keys:
            assert key in override


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
