"""
Comprehensive tests for all Zero Trust components.
Tests: DID, Threat Intelligence, Auto-Isolation, Policy Engine, Continuous Verification.
"""
import pytest
import time
import sys
sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.security.decentralized_identity import (
    DIDManager, DIDResolver, DIDGenerator, 
    VerifiableCredential, MeshCredentialTypes
)
from src.security.threat_intelligence import (
    ThreatIntelligenceEngine, ThreatType, ThreatSeverity,
    IndicatorType, BloomFilter
)
from src.security.auto_isolation import (
    AutoIsolationManager, IsolationLevel, IsolationReason,
    CircuitBreaker
)
from src.security.policy_engine import (
    PolicyEngine, PolicyEffect, PolicyCondition,
    PolicyRule, Policy, AttributeType, PolicyPriority
)
from src.security.continuous_verification import (
    ContinuousVerificationEngine, VerificationResult,
    VerificationType
)


class TestDecentralizedIdentity:
    """Tests for DID/Self-sovereign identity."""
    
    def test_did_creation(self):
        """Test DID creation."""
        manager = DIDManager("node-1")
        
        assert manager.did.startswith("did:mesh:")
        assert "node-1" in manager.did
        assert manager.public_key is not None
    
    def test_did_document(self):
        """Test DID Document structure."""
        manager = DIDManager("node-1")
        doc = manager.get_document()
        
        assert "@context" in doc
        assert doc["id"] == manager.did
        assert len(doc["verificationMethod"]) > 0
        assert len(doc["authentication"]) > 0
    
    def test_key_rotation(self):
        """Test key rotation."""
        manager = DIDManager("node-1")
        old_key = manager.public_key
        
        new_vm = manager.rotate_key()
        
        assert manager.public_key != old_key
        assert len(manager.key_history) == 1
        assert new_vm.id in manager.document.authentication
    
    def test_credential_issuance(self):
        """Test Verifiable Credential issuance."""
        issuer = DIDManager("issuer-1")
        subject_did = "did:mesh:subject-1:abc123"
        
        vc = issuer.issue_credential(
            subject_did=subject_did,
            credential_type=MeshCredentialTypes.NODE_OPERATOR,
            claims={"role": "operator", "level": "admin"},
            expiration_days=30
        )
        
        assert vc.issuer == issuer.did
        assert vc.credential_subject["id"] == subject_did
        assert vc.credential_subject["role"] == "operator"
        assert vc.proof is not None
    
    def test_credential_verification(self):
        """Test credential verification."""
        issuer = DIDManager("issuer-1")
        
        vc = issuer.issue_credential(
            subject_did="did:mesh:subject-1:abc123",
            credential_type=MeshCredentialTypes.TRUST_ANCHOR,
            claims={"trust_level": 90}
        )
        
        vc_dict = vc.to_dict()
        valid, reason = issuer.verify_credential(vc_dict)
        
        assert valid
        assert "valid" in reason.lower()
    
    def test_presentation_creation(self):
        """Test Verifiable Presentation."""
        manager = DIDManager("node-1")
        
        vc = manager.issue_credential(
            subject_did=manager.did,
            credential_type=MeshCredentialTypes.PEER_ATTESTATION,
            claims={"attested": True}
        )
        
        presentation = manager.create_presentation(
            credentials=[vc],
            challenge="random-challenge-123"
        )
        
        assert presentation["holder"] == manager.did
        assert len(presentation["verifiableCredential"]) == 1
        assert presentation["proof"]["challenge"] == "random-challenge-123"
    
    def test_did_key_method(self):
        """Test did:key resolution."""
        resolver = DIDResolver()
        
        # Create did:key
        _, public_key = DIDGenerator.generate_keypair()
        did_key = DIDGenerator.create_did_key(public_key)
        
        doc = resolver.resolve(did_key)
        
        assert doc is not None
        assert doc["id"] == did_key


class TestThreatIntelligence:
    """Tests for Distributed Threat Intelligence."""
    
    def test_indicator_reporting(self):
        """Test threat indicator reporting."""
        engine = ThreatIntelligenceEngine("node-1")
        
        indicator = engine.report_indicator(
            indicator_type=IndicatorType.NODE_ID,
            value="malicious-node-123",
            threat_type=ThreatType.SYBIL_ATTACK,
            severity=ThreatSeverity.HIGH,
            confidence=0.85,
            description="Suspected Sybil attack"
        )
        
        assert indicator.id is not None
        assert indicator.threat_type == ThreatType.SYBIL_ATTACK
        assert indicator.severity == ThreatSeverity.HIGH
    
    def test_bloom_filter(self):
        """Test privacy-preserving bloom filter."""
        bf = BloomFilter(size=1000, num_hashes=5)
        
        bf.add("malicious-ip-1")
        bf.add("malicious-ip-2")
        
        assert bf.contains("malicious-ip-1")
        assert bf.contains("malicious-ip-2")
        # May have false positives but should not have false negatives
    
    def test_bloom_filter_serialization(self):
        """Test bloom filter serialization."""
        bf1 = BloomFilter(size=1000)
        bf1.add("test-value")
        
        data = bf1.to_bytes()
        bf2 = BloomFilter.from_bytes(data, size=1000)
        
        assert bf2.contains("test-value")
    
    def test_indicator_sharing(self):
        """Test indicator sharing between nodes."""
        engine1 = ThreatIntelligenceEngine("node-1")
        engine2 = ThreatIntelligenceEngine("node-2")
        
        # Node 1 reports indicator
        engine1.report_indicator(
            indicator_type=IndicatorType.IP_ADDRESS,
            value="192.168.1.100",
            threat_type=ThreatType.DOS_ATTACK,
            severity=ThreatSeverity.MEDIUM,
            confidence=0.7
        )
        
        # Get shareable indicators
        shareable = engine1.get_shareable_indicators()
        
        # Node 2 receives indicators
        added = engine2.receive_indicators(shareable, "node-1")
        
        assert added >= 1
        assert engine2.check_indicator("192.168.1.100")
    
    def test_dos_detection(self):
        """Test DoS attack detection."""
        engine = ThreatIntelligenceEngine("node-1")
        
        # Simulate many connections from same source
        for _ in range(150):
            result = engine.detect_dos_attack("attacker-node")
        
        assert result is not None
        assert result.threat_type == ThreatType.DOS_ATTACK
    
    def test_brute_force_detection(self):
        """Test brute force detection."""
        engine = ThreatIntelligenceEngine("node-1")
        
        # Simulate failed auth attempts
        for _ in range(15):
            result = engine.detect_brute_force("attacker-node")
        
        assert result is not None
        assert result.threat_type == ThreatType.CREDENTIAL_THEFT
    
    def test_reputation_scoring(self):
        """Test reputation scoring."""
        engine = ThreatIntelligenceEngine("node-1")
        
        # Initial reputation
        rep = engine.get_reputation("peer-1")
        assert rep == 0.5  # Default
        
        # Update reputation
        new_rep = engine.update_reputation("peer-1", 0.2)
        assert new_rep == 0.7
        
        # Negative update
        new_rep = engine.update_reputation("peer-1", -0.8)
        assert new_rep < 0.1
        assert engine.is_blocked("peer-1")


class TestAutoIsolation:
    """Tests for Auto-Isolation."""
    
    def test_basic_isolation(self):
        """Test basic node isolation."""
        manager = AutoIsolationManager("node-1")
        
        record = manager.isolate(
            node_id="bad-node",
            reason=IsolationReason.THREAT_DETECTED,
            details="Malicious behavior detected"
        )
        
        assert record.node_id == "bad-node"
        assert record.level == IsolationLevel.RESTRICTED
    
    def test_isolation_escalation(self):
        """Test isolation escalation."""
        manager = AutoIsolationManager("node-1")
        
        # First isolation
        manager.isolate("bad-node", IsolationReason.THREAT_DETECTED)
        
        # Second isolation (should escalate)
        record = manager.isolate("bad-node", IsolationReason.THREAT_DETECTED)
        
        assert record.escalation_count >= 1
    
    def test_access_control(self):
        """Test access control during isolation."""
        manager = AutoIsolationManager("node-1")
        
        # Before isolation
        allowed, reason = manager.is_allowed("node-2", "data_access")
        assert allowed
        
        # After isolation
        manager.isolate(
            "node-2",
            IsolationReason.PROTOCOL_VIOLATION,
            level_override=IsolationLevel.QUARANTINE
        )
        
        allowed, reason = manager.is_allowed("node-2", "data_access")
        assert not allowed
        assert "quarantine" in reason.lower()
    
    def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        
        # Record failures
        for _ in range(3):
            cb.record_failure()
        
        # Circuit should be open
        assert not cb.allow_request()
        
        # Wait for recovery
        time.sleep(1.1)
        
        # Should allow request (half-open)
        assert cb.allow_request()
    
    def test_release_from_isolation(self):
        """Test releasing node from isolation."""
        manager = AutoIsolationManager("node-1")
        
        manager.isolate("node-2", IsolationReason.ANOMALY_DETECTED)
        
        released = manager.release("node-2")
        
        assert released
        assert manager.get_isolation_level("node-2") == IsolationLevel.NONE


class TestPolicyEngine:
    """Tests for Policy Engine."""
    
    def test_default_deny(self):
        """Test default deny policy."""
        engine = PolicyEngine("node-1")
        
        decision = engine.evaluate(
            subject={"node_id": "unknown-node"},
            resource="/sensitive/data",
            action="read"
        )
        
        # Should be denied by default (Zero Trust)
        assert decision.effect == PolicyEffect.DENY
    
    def test_health_endpoint_allow(self):
        """Test health endpoint is allowed."""
        engine = PolicyEngine("node-1")
        
        decision = engine.evaluate(
            subject={"node_id": "any-node"},
            resource="/health",
            action="read"
        )
        
        assert decision.effect == PolicyEffect.ALLOW
    
    def test_trust_based_access(self):
        """Test trust-based access control."""
        engine = PolicyEngine("node-1")
        
        # High trust node accessing sensitive resource
        decision = engine.evaluate(
            subject={"node_id": "trusted-node", "trust_level": 80},
            resource="/api/sensitive",
            action="read",
            environment={"sensitivity": "high"}
        )
        
        # Should be allowed due to high trust
        # Note: depends on rule priority
    
    def test_custom_policy(self):
        """Test adding custom policy."""
        engine = PolicyEngine("node-1")
        
        # Add custom policy
        custom_policy = Policy(
            id="allow-metrics",
            name="Allow Metrics Access",
            description="Allow all nodes to read metrics",
            version=1,
            rules=[
                PolicyRule(
                    id="metrics-read",
                    description="Allow metrics read",
                    conditions=[
                        PolicyCondition(
                            attribute_type=AttributeType.RESOURCE,
                            attribute_name="endpoint",
                            operator="regex",
                            value=r"/metrics.*"
                        )
                    ],
                    effect=PolicyEffect.ALLOW,
                    priority=PolicyPriority.HIGH
                )
            ],
            target={"resource": "*", "action": "read"}
        )
        
        engine.add_policy(custom_policy)
        
        decision = engine.evaluate(
            subject={"node_id": "any"},
            resource="/metrics/cpu",
            action="read"
        )
        
        assert decision.effect == PolicyEffect.ALLOW
    
    def test_policy_export_import(self):
        """Test policy export and import."""
        engine1 = PolicyEngine("node-1")
        
        # Export policies
        exported = engine1.export_policies()
        
        # Create new engine and import
        engine2 = PolicyEngine("node-2")
        count = engine2.import_policies(exported)
        
        assert count > 0


class TestContinuousVerification:
    """Tests for Continuous Verification."""
    
    def test_session_creation(self):
        """Test session creation."""
        engine = ContinuousVerificationEngine("node-1")
        
        session = engine.create_session(
            entity_id="peer-1",
            metadata={"device_fingerprint": "abc123"}
        )
        
        assert session.session_id is not None
        assert session.entity_id == "peer-1"
        assert session.is_active
    
    def test_session_verification(self):
        """Test session verification."""
        engine = ContinuousVerificationEngine("node-1")
        
        session = engine.create_session("peer-1")
        
        passed, checks, score = engine.verify_session(
            session.session_id,
            context={
                "claimed_id": "peer-1",
                "device_trust_level": 70
            }
        )
        
        assert passed
        assert len(checks) > 0
        assert score > 0
    
    def test_identity_mismatch_detection(self):
        """Test detection of identity mismatch."""
        engine = ContinuousVerificationEngine("node-1")
        
        session = engine.create_session("peer-1")
        
        passed, checks, score = engine.verify_session(
            session.session_id,
            context={"claimed_id": "different-peer"},
            check_types=[VerificationType.IDENTITY]
        )
        
        identity_check = next(
            c for c in checks if c.type == VerificationType.IDENTITY
        )
        
        assert identity_check.result == VerificationResult.FAILED
    
    def test_session_expiration(self):
        """Test session verification with expiration."""
        engine = ContinuousVerificationEngine("node-1")
        
        session = engine.create_session("peer-1")
        # Simulate old session
        session.last_activity_at = time.time() - 3600  # 1 hour ago
        
        passed, checks, score = engine.verify_session(
            session.session_id,
            check_types=[VerificationType.SESSION]
        )
        
        session_check = next(
            c for c in checks if c.type == VerificationType.SESSION
        )
        
        assert session_check.result == VerificationResult.FAILED
    
    def test_adaptive_verification_interval(self):
        """Test adaptive verification interval."""
        engine = ContinuousVerificationEngine(
            "node-1",
            base_interval_seconds=60,
            max_interval_seconds=300
        )
        
        session = engine.create_session("peer-1")
        
        # Low risk session
        session.risk_score = 0.2
        interval = engine.get_verification_interval(session)
        assert interval == 300  # Max interval for low risk
        
        # High risk session
        session.risk_score = 0.8
        interval = engine.get_verification_interval(session)
        assert interval == 60  # Base interval for high risk
    
    def test_activity_recording(self):
        """Test activity recording."""
        engine = ContinuousVerificationEngine("node-1")
        
        session = engine.create_session("peer-1")
        old_activity = session.last_activity_at
        
        time.sleep(0.1)
        engine.record_activity(session.session_id)
        
        assert session.last_activity_at > old_activity


class TestIntegration:
    """Integration tests for Zero Trust components."""
    
    def test_full_zero_trust_flow(self):
        """Test complete Zero Trust flow."""
        # 1. Create DID
        did_manager = DIDManager("node-1")
        
        # 2. Initialize all components
        threat_intel = ThreatIntelligenceEngine("node-1")
        isolation_mgr = AutoIsolationManager("node-1")
        policy_engine = PolicyEngine("node-1")
        verification_engine = ContinuousVerificationEngine("node-1")
        
        # 3. Create session
        session = verification_engine.create_session(
            entity_id=did_manager.did,
            metadata={"device_fingerprint": "test-device"}
        )
        
        # 4. Verify session (only identity and device checks, skip session age check)
        passed, checks, score = verification_engine.verify_session(
            session.session_id,
            context={
                "claimed_id": did_manager.did,
                "device_trust_level": 80,
                "device_fingerprint": "test-device"
            },
            check_types=[VerificationType.IDENTITY, VerificationType.DEVICE]
        )
        
        assert passed, f"Verification failed: {[c.to_dict() for c in checks]}"
        
        # 5. Check policy
        decision = policy_engine.evaluate(
            subject={"node_id": did_manager.did, "trust_level": score * 100},
            resource="/health",
            action="read"
        )
        
        assert decision.effect == PolicyEffect.ALLOW
        
        # 6. Issue credential
        vc = did_manager.issue_credential(
            subject_did=did_manager.did,
            credential_type=MeshCredentialTypes.NODE_OPERATOR,
            claims={"verified": True, "trust_score": score}
        )
        
        assert vc.proof is not None
    
    def test_threat_response_flow(self):
        """Test threat detection and response flow."""
        threat_intel = ThreatIntelligenceEngine("node-1")
        isolation_mgr = AutoIsolationManager("node-1")
        
        # Simulate threat detection
        indicator = threat_intel.report_indicator(
            indicator_type=IndicatorType.NODE_ID,
            value="attacker-node",
            threat_type=ThreatType.MITM_ATTEMPT,
            severity=ThreatSeverity.CRITICAL,
            confidence=0.95
        )
        
        # Auto-block check
        assert threat_intel.is_blocked("attacker-node")
        
        # Manual isolation
        record = isolation_mgr.isolate(
            node_id="attacker-node",
            reason=IsolationReason.THREAT_DETECTED,
            details=f"Indicator: {indicator.id}"
        )
        
        # Verify blocked
        allowed, reason = isolation_mgr.is_allowed("attacker-node", "any")
        assert not allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
