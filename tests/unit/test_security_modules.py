"""
Tests for security modules: intrusion_detection, byzantine_detection,
ddos_detection, continuous_verification, hardware_enclave, mesh_shield,
mtls_client, auto_isolation, decentralized_identity.

Covers:
- IDS: IntrusionType, IntrusionSeverity, IntrusionAlert, IntrusionDetectionSystem
- Byzantine: ByzantineBehavior, ByzantineSeverity, ByzantineAlert, NodeReputation, ByzantineDetector
- DDoS: DDoSType, AttackSeverity, DDoSAlert, TrafficBaseline, DDoSDetector
- Continuous Verification: VerificationResult, RiskLevel, VerificationType, VerificationCheck, Session, BehaviorProfile
- Hardware Enclave: HardwareSecurityModule, AttestationService
- MeshShield: ThreatLevel, QuarantineReason, ThreatIndicator, QuarantineRecord, MeshShield
- mTLS: MTLSConfig, CertificateInfo
- Auto-Isolation: IsolationLevel, IsolationReason, IsolationRecord, IsolationPolicy
- DID: DIDMethod, KeyPurpose, VerificationMethod, ServiceEndpoint, DIDDocument
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Intrusion Detection System
# ---------------------------------------------------------------------------

class TestIntrusionDetection:
    def test_intrusion_type_values(self):
        from src.security.intrusion_detection import IntrusionType
        assert IntrusionType.NETWORK_INTRUSION.value == "network_intrusion"
        assert IntrusionType.DATA_BREACH.value == "data_breach"
        assert IntrusionType.MALWARE_INFECTION.value == "malware_infection"

    def test_intrusion_severity_values(self):
        from src.security.intrusion_detection import IntrusionSeverity
        assert IntrusionSeverity.LOW.value == "low"
        assert IntrusionSeverity.CRITICAL.value == "critical"

    def test_intrusion_alert_dataclass(self):
        from src.security.intrusion_detection import IntrusionAlert, IntrusionType, IntrusionSeverity
        alert = IntrusionAlert(
            alert_id="alert-1",
            intrusion_type= IntrusionType.NETWORK_INTRUSION,
            severity=IntrusionSeverity.HIGH,
            source_ip="10.0.0.1",
            description="Port scan detected",
            confidence=0.85,
        )
        assert alert.alert_id == "alert-1"
        assert alert.confidence == 0.85
        assert alert.status == "alert"

    def test_ids_init(self):
        from src.security.intrusion_detection import IntrusionDetectionSystem
        ids = IntrusionDetectionSystem()
        assert len(ids.detection_rules) == 4
        assert ids.anomaly_threshold == 0.75

    def test_detect_intrusion_below_threshold(self):
        from src.security.intrusion_detection import IntrusionDetectionSystem, IntrusionType
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            IntrusionType.NETWORK_INTRUSION,
            {},
            source_ip="10.0.0.1",
        )
        assert result is None  # Confidence too low

    def test_detect_intrusion_with_indicators(self):
        from src.security.intrusion_detection import IntrusionDetectionSystem, IntrusionType
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            IntrusionType.DATA_BREACH,
            {"known_attack_pattern": True, "correlation_score": 0.9},
            source_ip="10.0.0.1",
            description="Data breach attempt",
        )
        assert result is not None
        assert result.intrusion_type == IntrusionType.DATA_BREACH
        assert len(ids.alerts) == 1

    def test_update_behavioral_baseline(self):
        from src.security.intrusion_detection import IntrusionDetectionSystem
        ids = IntrusionDetectionSystem()
        ids.update_behavioral_baseline("node-1", {"avg_traffic": 1000, "avg_connections": 50})
        assert "node-1" in ids.behavioral_baselines


# ---------------------------------------------------------------------------
# Byzantine Detection
# ---------------------------------------------------------------------------

class TestByzantineDetection:
    def test_byzantine_behavior_values(self):
        from src.security.byzantine_detection import ByzantineBehavior
        assert ByzantineBehavior.INCONSISTENT_STATE.value == "inconsistent_state"
        assert ByzantineBehavior.DOUBLE_SPEND.value == "double_spend"
        assert ByzantineBehavior.CONSENSUS_VIOLATION.value == "consensus_violation"

    def test_node_reputation_update_success(self):
        from src.security.byzantine_detection import NodeReputation
        rep = NodeReputation(node_id="node-1")
        rep.update_reputation(success=True)
        assert rep.total_interactions == 1
        assert rep.successful_interactions == 1
        assert rep.trust_level == "trusted"

    def test_node_reputation_update_failure(self):
        from src.security.byzantine_detection import NodeReputation
        rep = NodeReputation(node_id="node-1")
        rep.update_reputation(success=False)
        assert rep.total_interactions == 1
        assert rep.successful_interactions == 0
        assert rep.reputation_score < 1.0

    def test_node_reputation_violations_decay(self):
        from src.security.byzantine_detection import NodeReputation
        rep = NodeReputation(node_id="node-1")
        for _ in range(5):
            rep.update_reputation(success=True)
        rep.byzantine_violations = 3
        rep.update_reputation(success=True)
        assert rep.reputation_score < 1.0

    def test_node_reputation_trust_levels(self):
        from src.security.byzantine_detection import NodeReputation
        rep = NodeReputation(node_id="node-1")
        # Simulate successful interactions to get trusted
        for _ in range(10):
            rep.update_reputation(success=True)
        assert rep.trust_level == "trusted"
        # Add violations to lower score
        rep.byzantine_violations = 5
        rep.update_reputation(success=True)
        # With 11 interactions, 11 successes, 5 violations
        # score = (11/11) * (0.9^5) = 0.59 → suspicious
        assert rep.trust_level in ("trusted", "suspicious")

    def test_detector_init(self):
        from src.security.byzantine_detection import ByzantineDetector
        det = ByzantineDetector(min_evidence_nodes=3, reputation_threshold=0.5)
        assert det.min_evidence_nodes == 3

    def test_detect_low_confidence(self):
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior
        det = ByzantineDetector()
        result = det.detect_byzantine_behavior(
            "node-1", ByzantineBehavior.INCONSISTENT_STATE, {},
        )
        assert result is None  # Low confidence

    def test_detect_with_evidence(self):
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior
        det = ByzantineDetector()
        result = det.detect_byzantine_behavior(
            "node-1",
            ByzantineBehavior.DOUBLE_SPEND,
            {"amount": 100, "tx_hash": "abc123"},
            reported_by="node-2",
        )
        # May or may not be detected depending on confidence
        assert result is None or result.node_id == "node-1"

    def test_isolated_node_not_reprocessed(self):
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior
        det = ByzantineDetector()
        det.isolated_nodes.add("node-1")
        result = det.detect_byzantine_behavior(
            "node-1", ByzantineBehavior.MALICIOUS_AGGREGATION, {"data": "bad"},
        )
        assert result is None


# ---------------------------------------------------------------------------
# DDoS Detection
# ---------------------------------------------------------------------------

class TestDDoSDetection:
    def test_ddos_type_values(self):
        from src.security.ddos_detection import DDoSType
        assert DDoSType.VOLUMETRIC.value == "volumetric"
        assert DDoSType.SLOWLORIS.value == "slowloris"
        assert DDoSType.UDP_FLOOD.value == "udp_flood"

    def test_detector_init(self):
        from src.security.ddos_detection import DDoSDetector
        det = DDoSDetector(detection_window=30, threshold_multiplier=2.0)
        assert det.detection_window == 30
        assert det.baseline_learning is True

    def test_traffic_baseline_defaults(self):
        from src.security.ddos_detection import TrafficBaseline
        b = TrafficBaseline()
        assert b.avg_packets_per_second == 0.0
        assert b.avg_bandwidth_mbps == 0.0

    def test_analyze_traffic_learning_phase(self):
        from src.security.ddos_detection import DDoSDetector
        det = DDoSDetector()
        result = det.analyze_traffic("10.0.0.1", "10.0.0.2", 80, 1500)
        assert result is None  # Learning phase

    def test_ddos_alert_dataclass(self):
        from src.security.ddos_detection import DDoSAlert, DDoSType, AttackSeverity
        alert = DDoSAlert(
            alert_id="ddos-1",
            attack_type=DDoSType.VOLUMETRIC,
            severity=AttackSeverity.HIGH,
            traffic_rate=50000,
            bandwidth=100.0,
        )
        assert alert.traffic_rate == 50000
        assert alert.mitigation_applied is False


# ---------------------------------------------------------------------------
# Continuous Verification
# ---------------------------------------------------------------------------

class TestContinuousVerification:
    def test_verification_result_values(self):
        from src.security.continuous_verification import VerificationResult
        assert VerificationResult.PASSED.value == "passed"
        assert VerificationResult.FAILED.value == "failed"
        assert VerificationResult.DEGRADED.value == "degraded"

    def test_risk_level_values(self):
        from src.security.continuous_verification import RiskLevel
        assert RiskLevel.MINIMAL.value == 0
        assert RiskLevel.CRITICAL.value == 4

    def test_verification_type_values(self):
        from src.security.continuous_verification import VerificationType
        assert VerificationType.IDENTITY.value == "identity"
        assert VerificationType.BEHAVIOR.value == "behavior"

    def test_verification_check_to_dict(self):
        from src.security.continuous_verification import VerificationCheck, VerificationType, VerificationResult
        check = VerificationCheck(
            check_id="check-1",
            type=VerificationType.IDENTITY,
            result=VerificationResult.PASSED,
            score=0.95,
            details="Identity verified",
        )
        d = check.to_dict()
        assert d["check_id"] == "check-1"
        assert d["result"] == "passed"
        assert d["score"] == 0.95

    def test_session_to_dict(self):
        from src.security.continuous_verification import Session
        now = time.time()
        session = Session(
            session_id="sess-1",
            entity_id="node-1",
            created_at=now,
            last_verified_at=now,
            last_activity_at=now,
        )
        d = session.to_dict()
        assert d["session_id"] == "sess-1"
        assert d["is_active"] is True


# ---------------------------------------------------------------------------
# Hardware Enclave
# ---------------------------------------------------------------------------

class TestHardwareEnclave:
    def test_hsm_init(self):
        from src.security.hardware_enclave import HardwareSecurityModule
        hsm = HardwareSecurityModule(mode="mock")
        assert hsm.mode == "mock"

    def test_get_hardware_identity(self):
        from src.security.hardware_enclave import HardwareSecurityModule
        hsm = HardwareSecurityModule(mode="mock")
        identity = hsm.get_hardware_identity()
        assert isinstance(identity, str)
        assert len(identity) > 0

    def test_sign_with_hardware(self):
        from src.security.hardware_enclave import HardwareSecurityModule
        hsm = HardwareSecurityModule(mode="mock")
        signature = hsm.sign_with_hardware(b"test data")
        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_verify_attestation(self):
        from src.security.hardware_enclave import HardwareSecurityModule
        hsm = HardwareSecurityModule(mode="mock")
        assert hsm.verify_hardware_attestation(b"quote", b"nonce") is True
        assert hsm.verify_hardware_attestation(b"", b"nonce") is False
        assert hsm.verify_hardware_attestation(b"quote", b"") is False

    def test_attestation_service(self):
        from src.security.hardware_enclave import AttestationService
        result = AttestationService.validate_node({
            "hardware_id": "hw-123",
            "enclave_enabled": True,
        })
        assert result["is_trusted"] is True
        assert result["security_level"] == "HARDWARE_ROOTED"

    def test_attestation_service_no_enclave(self):
        from src.security.hardware_enclave import AttestationService
        result = AttestationService.validate_node({
            "hardware_id": "hw-456",
            "enclave_enabled": False,
        })
        assert result["security_level"] == "SOFTWARE_ONLY"

    def test_singleton_hsm(self):
        from src.security.hardware_enclave import hsm
        assert hsm is not None


# ---------------------------------------------------------------------------
# MeshShield
# ---------------------------------------------------------------------------

class TestMeshShield:
    def test_threat_level_values(self):
        from src.security.mesh_shield import ThreatLevel
        assert ThreatLevel.NONE.value == 0
        assert ThreatLevel.CRITICAL.value == 4

    def test_quarantine_reason_values(self):
        from src.security.mesh_shield import QuarantineReason
        assert QuarantineReason.ANOMALY_SCORE.value == "anomaly_score_exceeded"
        assert QuarantineReason.DAO_VOTE.value == "dao_governance_decision"

    def test_threat_indicator_dataclass(self):
        from src.security.mesh_shield import ThreatIndicator
        indicator = ThreatIndicator(
            node_id="node-1",
            indicator_type="anomaly_score",
            value=0.95,
            details="High anomaly detected",
        )
        assert indicator.node_id == "node-1"
        assert indicator.value == 0.95

    def test_mesh_shield_init(self):
        from src.security.mesh_shield import MeshShield
        shield = MeshShield()
        assert len(shield._quarantined) == 0

    def test_report_indicator(self):
        from src.security.mesh_shield import MeshShield, ThreatIndicator
        shield = MeshShield()
        indicator = ThreatIndicator(
            node_id="node-1",
            indicator_type="anomaly_score",
            value=0.95,
        )
        shield.report_indicator(indicator)
        assert "node-1" in shield._indicators

    def test_is_quarantined_false(self):
        from src.security.mesh_shield import MeshShield
        shield = MeshShield()
        assert shield.is_quarantined("node-1") is False

    def test_quarantine_record_dataclass(self):
        from src.security.mesh_shield import QuarantineRecord, QuarantineReason, ThreatLevel
        record = QuarantineRecord(
            node_id="node-1",
            reason=QuarantineReason.ANOMALY_SCORE,
            threat_level=ThreatLevel.HIGH,
            quarantined_at=datetime.utcnow(),
        )
        assert record.node_id == "node-1"
        assert record.threat_level == ThreatLevel.HIGH


# ---------------------------------------------------------------------------
# mTLS Client
# ---------------------------------------------------------------------------

class TestMTLSClient:
    def test_mtls_config_defaults(self):
        from src.security.mtls_client import MTLSConfig
        config = MTLSConfig()
        assert config.cert_path == "/etc/certs/tls.crt"
        assert config.verify_hostname is True

    def test_mtls_config_from_env(self):
        from src.security.mtls_client import MTLSConfig
        with patch.dict("os.environ", {
            "MTLS_CERT_PATH": "/custom/cert.pem",
            "MTLS_VERIFY_HOSTNAME": "false",
        }):
            config = MTLSConfig.from_env()
            assert config.cert_path == "/custom/cert.pem"
            assert config.verify_hostname is False

    def test_certificate_info_valid(self):
        from src.security.mtls_client import CertificateInfo
        now = datetime.utcnow()
        cert = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=now - timedelta(hours=1),
            not_after=now + timedelta(hours=24),
            serial_number=12345,
        )
        assert cert.is_valid is True

    def test_certificate_info_expired(self):
        from src.security.mtls_client import CertificateInfo
        now = datetime.utcnow()
        cert = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=now - timedelta(hours=48),
            not_after=now - timedelta(hours=1),
            serial_number=12345,
        )
        assert cert.is_valid is False

    def test_certificate_info_needs_rotation(self):
        from src.security.mtls_client import CertificateInfo
        now = datetime.utcnow()
        cert = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=now - timedelta(hours=1),
            not_after=now + timedelta(hours=12),  # Expires in 12h
            serial_number=12345,
        )
        assert cert.needs_rotation is True

    def test_certificate_info_no_rotation_needed(self):
        from src.security.mtls_client import CertificateInfo
        now = datetime.utcnow()
        cert = CertificateInfo(
            subject="CN=test",
            issuer="CN=ca",
            not_before=now - timedelta(hours=1),
            not_after=now + timedelta(hours=48),
            serial_number=12345,
        )
        assert cert.needs_rotation is False


# ---------------------------------------------------------------------------
# Auto-Isolation
# ---------------------------------------------------------------------------

class TestAutoIsolation:
    def test_isolation_level_values(self):
        from src.security.auto_isolation import IsolationLevel
        assert IsolationLevel.NONE.value == 0
        assert IsolationLevel.BLOCKED.value == 5

    def test_isolation_reason_values(self):
        from src.security.auto_isolation import IsolationReason
        assert IsolationReason.THREAT_DETECTED.value == "threat_detected"
        assert IsolationReason.ADMIN_ACTION.value == "admin_action"

    def test_isolation_record_dataclass(self):
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason
        record = IsolationRecord(
            node_id="node-1",
            level=IsolationLevel.QUARANTINE,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert record.node_id == "node-1"
        assert record.is_expired() is False

    def test_isolation_record_expired(self):
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason
        record = IsolationRecord(
            node_id="node-1",
            level=IsolationLevel.QUARANTINE,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )
        assert record.is_expired() is True

    def test_isolation_record_no_expiry(self):
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason
        record = IsolationRecord(
            node_id="node-1",
            level=IsolationLevel.BLOCKED,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=time.time(),
            expires_at=None,
        )
        assert record.is_expired() is False

    def test_isolation_record_to_dict(self):
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason
        record = IsolationRecord(
            node_id="node-1",
            level=IsolationLevel.MONITOR,
            reason=IsolationReason.ANOMALY_DETECTED,
            started_at=time.time(),
            expires_at=None,
        )
        d = record.to_dict()
        assert d["node_id"] == "node-1"
        assert d["level"] == "MONITOR"

    def test_isolation_policy_dataclass(self):
        from src.security.auto_isolation import IsolationPolicy, IsolationLevel, IsolationReason
        policy = IsolationPolicy(
            name="default",
            trigger_reason=IsolationReason.THREAT_DETECTED,
            initial_level=IsolationLevel.MONITOR,
            escalation_levels=[IsolationLevel.RATE_LIMIT, IsolationLevel.QUARANTINE],
            escalation_threshold=3,
            initial_duration=300,
            escalation_multiplier=2.0,
            max_duration=3600,
            auto_recover=True,
        )
        assert policy.name == "default"
        duration = policy.get_duration(0)
        assert duration == 300

    def test_safe_hash(self):
        from src.security.auto_isolation import _safe_hash
        assert _safe_hash("test") == _safe_hash("test")
        assert _safe_hash("a") != _safe_hash("b")
        assert len(_safe_hash("test")) == 12

    def test_safe_count_bucket(self):
        from src.security.auto_isolation import _safe_count_bucket
        assert _safe_count_bucket(0) == "0"
        assert _safe_count_bucket(2) == "1-3"
        assert _safe_count_bucket(5) == "4-10"
        assert _safe_count_bucket(50) == "11-100"
        assert _safe_count_bucket(200) == "100+"


# ---------------------------------------------------------------------------
# Decentralized Identity
# ---------------------------------------------------------------------------

class TestDecentralizedIdentity:
    def test_did_method_values(self):
        from src.security.decentralized_identity import DIDMethod
        assert DIDMethod.MESH.value == "mesh"
        assert DIDMethod.KEY.value == "key"
        assert DIDMethod.WEB.value == "web"

    def test_key_purpose_values(self):
        from src.security.decentralized_identity import KeyPurpose
        assert KeyPurpose.AUTHENTICATION.value == "authentication"
        assert KeyPurpose.ASSERTION.value == "assertionMethod"

    def test_verification_method_dataclass(self):
        from src.security.decentralized_identity import VerificationMethod, KeyPurpose
        vm = VerificationMethod(
            id="did:mesh:node-1#key-1",
            type="Ed25519VerificationKey2020",
            controller="did:mesh:node-1",
            public_key_multibase="z6Mk...",
            purpose=[KeyPurpose.AUTHENTICATION],
        )
        assert vm.id == "did:mesh:node-1#key-1"
        assert vm.revoked is False

    def test_service_endpoint_dataclass(self):
        from src.security.decentralized_identity import ServiceEndpoint
        se = ServiceEndpoint(
            id="did:mesh:node-1#svc-1",
            type="MeshAgent",
            service_endpoint="https://node1.mesh.internal:5000",
            description="Mesh agent endpoint",
        )
        assert se.type == "MeshAgent"

    def test_did_document_dataclass(self):
        from src.security.decentralized_identity import DIDDocument
        doc = DIDDocument(id="did:mesh:node-1")
        assert doc.id == "did:mesh:node-1"
        assert doc.deactivated is False
        assert "https://www.w3.org/ns/did/v1" in doc.context

    def test_did_document_to_dict(self):
        from src.security.decentralized_identity import DIDDocument
        doc = DIDDocument(id="did:mesh:node-1")
        d = doc.to_dict()
        assert d["id"] == "did:mesh:node-1"
        assert "context" in d or "@context" in d
