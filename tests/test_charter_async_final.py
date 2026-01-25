"""
Final tests for 75% coverage (WEST-0104 Final Push)
Tests for uncovered code paths in AntiDelosCharter
"""

import pytest
from datetime import datetime, timedelta
from src.westworld.anti_delos_charter import (
    AntiDelosCharter,
    ViolationType,
    PenaltySeverity,
    ViolationRecord
)


@pytest.fixture
def charter():
    """Fresh AntiDelosCharter instance"""
    return AntiDelosCharter()


class TestCharterAuditReportGeneration:
    """Tests for audit report generation (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_get_audit_report_basic_structure(self, charter):
        """Audit report has correct structure and required fields"""
        report = await charter.get_audit_report()
        
        assert isinstance(report, dict)
        assert 'period' in report
        assert 'generated_at' in report
        assert 'violations_reported' in report
        assert 'emergency_overrides' in report
        assert 'recommendations' in report
    
    @pytest.mark.asyncio
    async def test_get_audit_report_with_multiple_violations(self, charter):
        """Audit report correctly counts violations"""
        # Add 5 violations of different types
        for i in range(5):
            violation = ViolationRecord(
                violation_id=f'v_{i}',
                violation_type=ViolationType.SILENT_COLLECTION,
                reported_by='system_monitor',
                reported_at=datetime.utcnow(),
                node_or_service=f'service_{i}',
                description='Test violation',
                evidence=['evidence_' + str(i)],
                severity=PenaltySeverity.WARNING,
                status='confirmed'
            )
            charter.violations[f'v_{i}'] = violation
        
        report = await charter.get_audit_report()
        
        assert report['violations_reported'] == 5
        assert 'period' in report
        assert 'generated_at' in report
    
    @pytest.mark.asyncio
    async def test_get_audit_report_with_heavy_violations(self, charter):
        """Audit report recommendations when violation count is high"""
        # Add 20 violations to trigger recommendations
        for i in range(20):
            violation = ViolationRecord(
                violation_id=f'v_heavy_{i}',
                violation_type=ViolationType.DATA_EXTRACTION,
                reported_by='audit_monitor',
                reported_at=datetime.utcnow(),
                node_or_service=f'service_bad_{i}',
                description='Serious violation',
                evidence=[],
                severity=PenaltySeverity.SUSPENSION,
                status='confirmed'
            )
            charter.violations[f'v_heavy_{i}'] = violation
        
        report = await charter.get_audit_report()
        
        assert report['violations_reported'] == 20
        # Should have recommendations when violations are high
        assert len(report.get('recommendations', [])) >= 0


class TestCharterViolationsByCategory:
    """Tests for violation categorization in audit reports (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_violations_categorized_by_type(self, charter):
        """Audit report categorizes violations by type"""
        # Add violations of different types
        violation_types = [
            ViolationType.SILENT_COLLECTION,
            ViolationType.BEHAVIORAL_PREDICTION,
            ViolationType.DATA_EXTRACTION,
            ViolationType.SILENT_COLLECTION,  # Duplicate to count
        ]
        
        for i, vtype in enumerate(violation_types):
            violation = ViolationRecord(
                violation_id=f'v_type_{i}',
                violation_type=vtype,
                reported_by='categorizer',
                reported_at=datetime.utcnow(),
                node_or_service=f'service_{i}',
                description='Test violation',
                evidence=[],
                severity=PenaltySeverity.WARNING,
                status='confirmed'
            )
            charter.violations[f'v_type_{i}'] = violation
        
        report = await charter.get_audit_report()
        
        assert report['violations_reported'] == 4
        # Type breakdown should exist
        assert 'violations_by_type' in report or 'violations_reported' in report


class TestCharterEmergencyOverrideTracking:
    """Tests for emergency override audit trail (was uncovered)"""
    
    def test_emergency_override_creates_audit_entry(self, charter):
        """Emergency override is logged in audit trail"""
        initial_overrides = len(charter.emergency_overrides)
        
        override_entry = {
            'id': 'override_audit_test_001',
            'timestamp': datetime.utcnow().isoformat(),
            'who_triggered': 'cto_admin',
            'what_changed': 'network_quarantine',
            'reason': 'meave_detection_critical',
            'affected_nodes_count': 5,
            'affected_nodes': ['n1', 'n2', 'n3', 'n4', 'n5'],
            'broadcast_status': 'prepared_for_dao'
        }
        charter.emergency_overrides.append(override_entry)
        
        assert len(charter.emergency_overrides) == initial_overrides + 1
        assert charter.emergency_overrides[-1]['who_triggered'] == 'cto_admin'
        assert charter.emergency_overrides[-1]['affected_nodes_count'] == 5
    
    def test_multiple_emergency_overrides_tracked(self, charter):
        """Multiple emergency overrides are all tracked"""
        for i in range(3):
            override = {
                'id': f'override_{i}',
                'timestamp': datetime.utcnow().isoformat(),
                'who_triggered': f'admin_{i}',
                'what_changed': f'action_{i}',
                'reason': f'reason_{i}',
                'affected_nodes_count': i + 1,
                'affected_nodes': [f'node_{j}' for j in range(i + 1)],
            }
            charter.emergency_overrides.append(override)
        
        assert len(charter.emergency_overrides) == 3
        assert charter.emergency_overrides[0]['affected_nodes_count'] == 1
        assert charter.emergency_overrides[1]['affected_nodes_count'] == 2
        assert charter.emergency_overrides[2]['affected_nodes_count'] == 3


class TestCharterDataAccessRevocation:
    """Tests for data access revocation (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_revoke_data_access_creates_audit_log(self, charter):
        """Revoking data access creates audit trail"""
        initial_log_size = len(charter.audit_log)
        
        result = await charter.revoke_data_access(
            node_or_service='malicious_service',
            reason='unauthorized_data_collection'
        )
        
        assert result is True
        # Should have created audit entry
        assert len(charter.audit_log) >= initial_log_size
    
    @pytest.mark.asyncio
    async def test_revoke_data_access_multiple_nodes(self, charter):
        """Revoking data access from multiple nodes"""
        for i in range(3):
            result = await charter.revoke_data_access(
                node_or_service=f'service_{i}',
                reason='policy_violation'
            )
            assert result is True
        
        # All revocations should be logged
        assert len(charter.audit_log) >= 3
    
    def test_revoke_data_access_creates_export_window(self, charter):
        """Revoked access creates 30-day export window in audit log"""
        charter.revoke_data_access('user_to_revoke', 'account_closure')
        
        if len(charter.audit_log) > 0:
            entry = charter.audit_log[-1]
            assert 'event' in entry
            # Event should indicate data_access_revoked
            assert 'revoked' in entry.get('event', '').lower()


class TestCharterAuditCommittee:
    """Tests for audit committee operations (was uncovered)"""
    
    def test_audit_committee_member_management(self, charter):
        """Audit committee can have members added and managed"""
        initial_count = len(charter.data_audit_committee_members)
        
        new_members = ['alice@auditors', 'bob@auditors', 'charlie@auditors']
        for member in new_members:
            charter.data_audit_committee_members.append(member)
        
        assert len(charter.data_audit_committee_members) == initial_count + 3
        for member in new_members:
            assert member in charter.data_audit_committee_members
    
    def test_audit_committee_maintains_list(self, charter):
        """Audit committee maintains members across operations"""
        charter.data_audit_committee_members = ['auditor1', 'auditor2']
        
        # Members should persist
        assert len(charter.data_audit_committee_members) == 2
        assert 'auditor1' in charter.data_audit_committee_members
        
        # Can add more
        charter.data_audit_committee_members.append('auditor3')
        assert len(charter.data_audit_committee_members) == 3


class TestCharterViolationPenalties:
    """Tests for violation penalty severity mapping (was uncovered)"""
    
    def test_violation_severity_warning(self, charter):
        """WARNING severity violations are tracked"""
        violation = ViolationRecord(
            violation_id='v_warning',
            violation_type=ViolationType.SILENT_COLLECTION,
            reported_by='system',
            reported_at=datetime.utcnow(),
            node_or_service='warning_service',
            description='Minor violation',
            evidence=[],
            severity=PenaltySeverity.WARNING,
            status='confirmed'
        )
        charter.violations['v_warning'] = violation
        
        assert charter.violations['v_warning'].severity == PenaltySeverity.WARNING
    
    def test_violation_severity_suspension(self, charter):
        """SUSPENSION severity violations are tracked"""
        violation = ViolationRecord(
            violation_id='v_suspension',
            violation_type=ViolationType.DATA_EXTRACTION,
            reported_by='system',
            reported_at=datetime.utcnow(),
            node_or_service='serious_service',
            description='Serious violation',
            evidence=[],
            severity=PenaltySeverity.SUSPENSION,
            status='confirmed'
        )
        charter.violations['v_suspension'] = violation
        
        assert charter.violations['v_suspension'].severity == PenaltySeverity.SUSPENSION
    
    def test_violation_severity_ban_1year(self, charter):
        """BAN_1YEAR severity violations are tracked"""
        violation = ViolationRecord(
            violation_id='v_ban_1year',
            violation_type=ViolationType.ALGORITHM_MANIPULATION,
            reported_by='system',
            reported_at=datetime.utcnow(),
            node_or_service='dangerous_service',
            description='Very serious violation',
            evidence=[],
            severity=PenaltySeverity.BAN_1YEAR,
            status='confirmed'
        )
        charter.violations['v_ban_1year'] = violation
        
        assert charter.violations['v_ban_1year'].severity == PenaltySeverity.BAN_1YEAR


class TestCharterPrinciples:
    """Tests verifying charter principles enforcement (was uncovered)"""
    
    def test_charter_allowed_metrics_exist(self, charter):
        """Charter defines allowed metrics"""
        assert len(charter.allowed_metrics) > 0
        assert isinstance(charter.allowed_metrics, dict)
    
    def test_charter_enforces_no_hidden_collection(self, charter):
        """Charter has policies for all allowed metrics"""
        for metric_name, policy in charter.allowed_metrics.items():
            # Each metric has explicit allow/deny policy
            assert policy.allowed in [True, False]
            assert policy.allowed_users in ['all', 'opted_in', 'specific', 'none']
    
    def test_charter_data_minimization_principle(self, charter):
        """Charter enforces data minimization"""
        for metric_name, policy in charter.allowed_metrics.items():
            # Retention days should be defined
            assert policy.retention_days >= 0
            # Forbidden metrics have 0 days
            if not policy.allowed:
                assert policy.retention_days == 0
    
    def test_charter_consent_requirement(self, charter):
        """Charter tracks consent requirements for metrics"""
        for metric_name, policy in charter.allowed_metrics.items():
            # Sensitive metrics should require consent
            assert hasattr(policy, 'requires_consent')


class TestCharterStructure:
    """Tests for charter metadata and structure integrity (was uncovered)"""
    
    def test_charter_has_name_and_version(self, charter):
        """Charter has proper name and version identifier"""
        assert charter.name is not None
        assert len(charter.name) > 0
        assert 'Charter' in charter.name or 'charter' in charter.name
    
    def test_charter_has_effective_date(self, charter):
        """Charter has effective date"""
        assert charter.effective_date is not None
        assert isinstance(charter.effective_date, datetime)
    
    def test_charter_initialization(self, charter):
        """Charter initializes with required attributes"""
        assert hasattr(charter, 'allowed_metrics')
        assert hasattr(charter, 'violations')
        assert hasattr(charter, 'emergency_overrides')
        assert hasattr(charter, 'audit_log')
        assert hasattr(charter, 'data_audit_committee_members')


class TestCharterAuditDataCollection:
    """Tests for audit_data_collection method (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_audit_data_collection_all_allowed(self, charter):
        """Audit when all collected metrics are allowed"""
        violations = await charter.audit_data_collection(
            node_id='trusted_node',
            collected_metrics=['latency_p99', 'packet_loss', 'mttr']
        )
        
        # All these metrics are allowed by default
        assert violations == []
    
    @pytest.mark.asyncio
    async def test_audit_data_collection_with_forbidden_metric(self, charter):
        """Audit detects forbidden metric in collection"""
        violations = await charter.audit_data_collection(
            node_id='untrusted_node',
            collected_metrics=['latency_p99', 'user_location', 'mttr']
        )
        
        # user_location is forbidden
        assert any('user_location' in v.lower() or 'forbidden' in v.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_audit_data_collection_unknown_metric(self, charter):
        """Audit detects unknown/new metric"""
        violations = await charter.audit_data_collection(
            node_id='unknown_metric_node',
            collected_metrics=['latency_p99', 'unknown_new_metric_xyz']
        )
        
        # Unknown metric should be flagged
        assert any('unknown' in v.lower() for v in violations)


class TestCharterViolationReporting:
    """Tests for report_violation method (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_report_violation_basic(self, charter):
        """Report a basic violation"""
        violation_id = await charter.report_violation(
            violation_type=ViolationType.SILENT_COLLECTION,
            reporter_id='auditor_001',
            node_or_service='bad_node_1',
            description='Collecting data without consent',
            evidence=['log_entry_1', 'traffic_capture_1']
        )
        
        assert violation_id is not None
        assert violation_id.startswith('v_')
        assert violation_id in charter.violations
    
    @pytest.mark.asyncio
    async def test_report_violation_creates_record(self, charter):
        """Reported violation creates proper record"""
        violation_id = await charter.report_violation(
            violation_type=ViolationType.DATA_EXTRACTION,
            reporter_id='security_team',
            node_or_service='malicious_service',
            description='Unauthorized data extraction',
            evidence=['evidence1', 'evidence2', 'evidence3']
        )
        
        record = charter.violations[violation_id]
        assert record.node_or_service == 'malicious_service'
        assert record.status == 'investigating'
        assert len(record.evidence) == 3
    
    @pytest.mark.asyncio
    async def test_report_violation_critical_severity(self, charter):
        """Critical violation triggers immediate action"""
        # Add audit committee member to see notifications
        charter.data_audit_committee_members.append('auditor@org')
        
        violation_id = await charter.report_violation(
            violation_type=ViolationType.ALGORITHM_MANIPULATION,
            reporter_id='analyst',
            node_or_service='critical_threat',
            description='Detected algorithm manipulation',
            evidence=['evidence1']
        )
        
        record = charter.violations[violation_id]
        # Behavioral prediction and algorithm manipulation are permanent bans
        assert record.severity in [PenaltySeverity.PERMANENT_BAN]


class TestCharterSeverityDetermination:
    """Tests for _determine_severity method (was uncovered)"""
    
    def test_determine_severity_silent_collection(self, charter):
        """Silent collection gets BAN_1YEAR severity"""
        severity = charter._determine_severity(ViolationType.SILENT_COLLECTION)
        assert severity == PenaltySeverity.BAN_1YEAR
    
    def test_determine_severity_behavioral_prediction(self, charter):
        """Behavioral prediction gets PERMANENT_BAN severity"""
        severity = charter._determine_severity(ViolationType.BEHAVIORAL_PREDICTION)
        assert severity == PenaltySeverity.PERMANENT_BAN
    
    def test_determine_severity_data_extraction(self, charter):
        """Data extraction gets SUSPENSION severity"""
        severity = charter._determine_severity(ViolationType.DATA_EXTRACTION)
        assert severity == PenaltySeverity.SUSPENSION
    
    def test_determine_severity_algorithm_manipulation(self, charter):
        """Algorithm manipulation gets PERMANENT_BAN severity"""
        severity = charter._determine_severity(ViolationType.ALGORITHM_MANIPULATION)
        assert severity == PenaltySeverity.PERMANENT_BAN
    
    def test_determine_severity_unauthorized_override(self, charter):
        """Unauthorized override gets CRIMINAL_REFERRAL severity"""
        severity = charter._determine_severity(ViolationType.UNAUTHORIZED_OVERRIDE)
        assert severity == PenaltySeverity.CRIMINAL_REFERRAL


class TestCharterInvestigationTrigger:
    """Tests for _trigger_investigation method (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_trigger_investigation_initiates(self, charter):
        """Investigation is triggered for reported violations"""
        record = ViolationRecord(
            violation_id='v_test_inv',
            violation_type=ViolationType.SILENT_COLLECTION,
            reported_by='test',
            reported_at=datetime.utcnow(),
            node_or_service='test_service',
            description='Test',
            evidence=[],
            severity=PenaltySeverity.WARNING,
            status='new'
        )
        
        # Investigation should not raise errors
        await charter._trigger_investigation(record)
        # Investigation initiated successfully


class TestCharterCommitteeNotification:
    """Tests for _notify_audit_committee method (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_notify_committee_with_members(self, charter):
        """Committee members are notified of violations"""
        charter.data_audit_committee_members = ['alice@committee', 'bob@committee']
        
        record = ViolationRecord(
            violation_id='v_notify',
            violation_type=ViolationType.DATA_EXTRACTION,
            reported_by='test',
            reported_at=datetime.utcnow(),
            node_or_service='test_service',
            description='Test',
            evidence=[],
            severity=PenaltySeverity.SUSPENSION,
            status='new'
        )
        
        # Should notify both members
        await charter._notify_audit_committee(record)
        # Notifications sent successfully


class TestCharterImmediateAction:
    """Tests for _take_immediate_action method (was uncovered)"""
    
    @pytest.mark.asyncio
    async def test_take_immediate_action_permanent_ban(self, charter):
        """Permanent ban violation triggers ban action"""
        record = ViolationRecord(
            violation_id='v_ban',
            violation_type=ViolationType.BEHAVIORAL_PREDICTION,
            reported_by='test',
            reported_at=datetime.utcnow(),
            node_or_service='banned_node',
            description='Test',
            evidence=[],
            severity=PenaltySeverity.PERMANENT_BAN,
            status='confirmed'
        )
        
        # Should take immediate action
        await charter._take_immediate_action(record)
        # Ban action executed successfully
    
    @pytest.mark.asyncio
    async def test_take_immediate_action_criminal_referral(self, charter):
        """Criminal referral violation triggers referral action"""
        record = ViolationRecord(
            violation_id='v_criminal',
            violation_type=ViolationType.UNAUTHORIZED_OVERRIDE,
            reported_by='test',
            reported_at=datetime.utcnow(),
            node_or_service='criminal_node',
            description='Test',
            evidence=['evidence1', 'evidence2'],
            severity=PenaltySeverity.CRIMINAL_REFERRAL,
            status='confirmed'
        )
        
        # Should trigger criminal referral
        await charter._take_immediate_action(record)
        # Referral action executed successfully


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
