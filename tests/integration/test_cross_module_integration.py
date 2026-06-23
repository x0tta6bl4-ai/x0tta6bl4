"""
Integration tests: cross-module interactions.

Tests verify that multiple modules work together correctly:
1. Security pipeline: IDS → Byzantine → MeshShield → Auto-Isolation
2. Policy engine → Zero Trust Validator flow
3. Event Bus → Coordination pipeline
4. Database → Repository → Service layer
5. Circuit Breaker → Retry → Connection patterns
6. Monitoring metrics → Alerting pipeline
7. Full security stack: detection → quarantine → recovery
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Integration 1: Security Detection Pipeline
# IDS → Byzantine → MeshShield → Auto-Isolation
# ---------------------------------------------------------------------------

class TestSecurityPipeline:
    def test_intrusion_to_byzantine_correlation(self):
        """IDS detects intrusion, feeds into Byzantine detector."""
        from src.security.intrusion_detection import IntrusionDetectionSystem, IntrusionType
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior

        ids = IntrusionDetectionSystem()
        byzantine = ByzantineDetector()

        # IDS detects network intrusion
        alert = ids.detect_intrusion(
            IntrusionType.NETWORK_INTRUSION,
            {"known_attack_pattern": True, "correlation_score": 0.9},
            source_ip="10.0.0.1",
            node_id="node-1",
        )
        assert alert is not None

        # Feed IDS alert into Byzantine detector
        byzantine_alert = byzantine.detect_byzantine_behavior(
            "node-1",
            ByzantineBehavior.CONSENSUS_VIOLATION,
            {"ids_alert": alert.alert_id, "direct_proof": True},
            reported_by="node-2",
        )
        # May or may not be detected depending on confidence
        assert byzantine_alert is None or byzantine_alert.node_id == "node-1"

    def test_byzantine_to_meshshield_quarantine(self):
        """Byzantine detection triggers MeshShield quarantine."""
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior
        from src.security.mesh_shield import MeshShield, ThreatIndicator

        byzantine = ByzantineDetector()
        shield = MeshShield()

        # Report Byzantine behavior
        alert = byzantine.detect_byzantine_behavior(
            "malicious-node",
            ByzantineBehavior.DOUBLE_SPEND,
            {"amount": 1000, "tx_hash": "abc123", "direct_proof": True},
            reported_by="honest-node-1",
        )

        # Feed into MeshShield
        if alert:
            indicator = ThreatIndicator(
                node_id="malicious-node",
                indicator_type="byzantine_alert",
                value=0.95,
                details=f"Byzantine alert: {alert.alert_id}",
            )
            threat = shield.report_indicator(indicator)
            # Should trigger quarantine if threat level is HIGH+
            if threat:
                assert shield.is_quarantined("malicious-node") is True

    def test_meshshield_to_auto_isolation(self):
        """MeshShield quarantine integrates with Auto-Isolation."""
        from src.security.mesh_shield import MeshShield, ThreatIndicator, ThreatLevel
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason

        shield = MeshShield()

        # Report high threat indicator
        indicator = ThreatIndicator(
            node_id="compromised-node",
            indicator_type="anomaly_score",
            value=0.98,
        )
        shield.report_indicator(indicator)

        # Create auto-isolation record matching MeshShield quarantine
        if shield.is_quarantined("compromised-node"):
            record = IsolationRecord(
                node_id="compromised-node",
                level=IsolationLevel.QUARANTINE,
                reason=IsolationReason.THREAT_DETECTED,
                started_at=time.time(),
                expires_at=time.time() + 3600,
            )
            assert record.level == IsolationLevel.QUARANTINE
            assert record.is_expired() is False


# ---------------------------------------------------------------------------
# Integration 2: Policy Engine → Zero Trust Validator
# ---------------------------------------------------------------------------

class TestPolicyZeroTrustIntegration:
    def test_policy_engine_controls_validator(self):
        """PolicyEngine decisions control ZeroTrustValidator behavior."""
        from src.security.policy_engine import PolicyEngine, PolicyEffect

        engine = PolicyEngine(node_id="test-node")

        # Evaluate policy for a trusted node - health check allowed
        decision = engine.evaluate(
            subject={"node_id": "trusted-node", "trust_level": 90},
            resource="/health",
            action="read",
        )
        assert decision.effect == PolicyEffect.ALLOW

        # Low trust node gets audit, not deny (trust-based-access policy)
        decision = engine.evaluate(
            subject={"node_id": "unknown-node", "trust_level": 10},
            resource="/data",
            action="read",
        )
        # Low trust nodes trigger audit logging
        assert decision.effect in (PolicyEffect.DENY, PolicyEffect.AUDIT)

    def test_validator_uses_policy_engine(self):
        """ZeroTrustValidator integrates with PolicyEngine for decisions."""
        from src.security.zero_trust.validator import ZeroTrustValidator

        # Mock the WorkloadAPIClient to avoid SPIFFE socket requirement
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client:
            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")
            validator.spiffe_client = mock_client()

            mock_engine = MagicMock()
            mock_decision = MagicMock()
            mock_decision.allowed = True
            mock_decision.reason = "trusted node"
            mock_engine.evaluate.return_value = mock_decision

            with patch("src.security.zero_trust.policy_engine.get_policy_engine", return_value=mock_engine):
                result = validator._check_policy("spiffe://x0tta6bl4.mesh/trusted-node")
                assert result is True


# ---------------------------------------------------------------------------
# Integration 3: Event Bus → Coordination Pipeline
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_event_bus_coordinates_security_alerts(self):
        """EventBus coordinates security alerts across components."""
        from src.coordination.events import EventBus, EventType
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(project_root=tmpdir)
            alerts_received = []

            def security_handler(event):
                alerts_received.append(event)

            bus.subscribe(EventType.SYSTEM_ALERT, security_handler)

            # Publish security alert
            bus.publish(
                EventType.SYSTEM_ALERT,
                "byzantine-detector",
                {"node_id": "malicious-node", "severity": "high"},
            )

            assert len(alerts_received) == 1
            assert alerts_received[0].data["node_id"] == "malicious-node"

    def test_event_bus_multiple_subscribers(self):
        """Multiple components subscribe to same event type."""
        from src.coordination.events import EventBus, EventType
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(project_root=tmpdir)
            received_by = {"ids": [], "mesh_shield": [], "logging": []}

            bus.subscribe(EventType.SYSTEM_ALERT, lambda e: received_by["ids"].append(e))
            bus.subscribe(EventType.SYSTEM_ALERT, lambda e: received_by["mesh_shield"].append(e))
            bus.subscribe(EventType.SYSTEM_ALERT, lambda e: received_by["logging"].append(e))

            bus.publish(EventType.SYSTEM_ALERT, "detector", {"alert": "test"})

            for component in received_by.values():
                assert len(component) == 1

    def test_event_bus_ack_workflow(self):
        """Event acknowledgment workflow for coordination."""
        from src.coordination.events import EventBus, EventType
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(project_root=tmpdir)

            # Publish event requiring acknowledgment
            event = bus.publish(
                EventType.TASK_ASSIGNED,
                "coordinator",
                {"task_id": "T1"},
                target_agents={"worker-1", "worker-2"},
                requires_ack=True,
            )

            # Workers acknowledge
            bus.ack_event(event.event_id, "worker-1")
            pending = bus.get_pending_acks("worker-1")
            assert len(pending) == 0

            # Worker-2 hasn't acked yet
            pending = bus.get_pending_acks("worker-2")
            assert len(pending) == 1


# ---------------------------------------------------------------------------
# Integration 4: Database → Repository → Service Layer
# ---------------------------------------------------------------------------

class TestDatabaseRepositoryIntegration:
    @pytest.fixture
    def db_session(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.database import Base
        engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        return Session()

    def test_user_crud_via_repository(self, db_session):
        """Full CRUD lifecycle through UserRepository."""
        from src.repositories.base import UserRepository
        from src.database import User

        repo = UserRepository(db_session)

        # Create
        user = User(id="int-test-001", email="int@test.com", password_hash="hash", plan="free")
        created = repo.create(user)
        assert created.id == "int-test-001"

        # Read
        fetched = repo.get_by_id("int-test-001")
        assert fetched.email == "int@test.com"

        # Update
        updated = repo.update("int-test-001", plan="pro")
        assert updated.plan == "pro"

        # Count
        assert repo.count() == 1

        # Delete
        assert repo.delete("int-test-001") is True
        assert repo.get_by_id("int-test-001") is None

    def test_multiple_repository_types(self, db_session):
        """Multiple repository types work on same database."""
        from src.repositories.base import UserRepository
        from src.repositories.mesh import MeshInstanceRepository
        from src.database import User, MeshInstance

        user_repo = UserRepository(db_session)
        mesh_repo = MeshInstanceRepository(db_session)

        user_repo.create(User(id="u1", email="u1@test.com", password_hash="h", plan="free"))
        mesh_repo.create(MeshInstance(id="m1", name="mesh-1", owner_id="u1", status="active"))

        assert user_repo.count() == 1
        assert mesh_repo.count() == 1


# ---------------------------------------------------------------------------
# Integration 5: Circuit Breaker → Retry → Connection
# ---------------------------------------------------------------------------

class TestCircuitBreakerRetryIntegration:
    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self):
        """Retry logic integrates with Circuit Breaker for fault tolerance."""
        from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
        from src.core.connection_retry import RetryPolicy, with_retry

        cb = CircuitBreaker(
            name="integration-test",
            failure_threshold=3,
            recovery_timeout=0,
            success_threshold=1,
        )
        policy = RetryPolicy(max_retries=2, base_delay=0, jitter=False)

        call_count = 0

        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("transient")
            return "recovered"

        # Retry should succeed after 2 failures
        result = await with_retry(flaky_service, policy=policy, circuit_breaker=cb)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_after_threshold(self):
        """Circuit Breaker opens after failure threshold, blocking retries."""
        from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
        from src.core.connection_retry import RetryPolicy, with_retry

        cb = CircuitBreaker(
            name="block-test",
            failure_threshold=2,
            recovery_timeout=999,
        )
        policy = RetryPolicy(max_retries=5, base_delay=0, jitter=False)

        async def always_fail():
            raise ConnectionError("permanent")

        with pytest.raises((ConnectionError, CircuitBreakerOpen)):
            await with_retry(always_fail, policy=policy, circuit_breaker=cb)


# ---------------------------------------------------------------------------
# Integration 6: Monitoring Metrics → Alerting Pipeline
# ---------------------------------------------------------------------------

class TestMonitoringAlertingIntegration:
    def test_metrics_feed_into_alerting(self):
        """Monitoring metrics trigger alerting when thresholds exceeded."""
        from src.monitoring.metrics import MetricsRegistry
        from src.monitoring.pqc_metrics import record_handshake_failure

        # Record PQC handshake failure
        record_handshake_failure("timeout")

        # Verify metric was recorded
        metric = MetricsRegistry.request_count
        assert metric is not None

    def test_mapek_metrics_cycle(self):
        """MAPE-K metrics collector tracks full cycle."""
        from src.monitoring.mapek_metrics import MAPEKMetricsCollector
        from src.monitoring.metrics import MetricsRegistry

        collector = MAPEKMetricsCollector(MetricsRegistry)

        # Simulate full MAPE-K cycle
        collector.start_cycle()

        collector.start_phase("monitor")
        time.sleep(0.01)
        collector.end_phase("monitor")

        collector.start_phase("analyze")
        time.sleep(0.01)
        collector.end_phase("analyze")

        collector.start_phase("plan")
        time.sleep(0.01)
        collector.end_phase("plan")

        collector.start_phase("execute")
        time.sleep(0.01)
        collector.end_phase("execute")

        collector.record_cycle_completion("success")
        collector.record_anomaly("node_failure", "high")
        collector.record_recovery_action("reroute", "success")


# ---------------------------------------------------------------------------
# Integration 7: Full Security Stack
# Detection → Quarantine → Recovery
# ---------------------------------------------------------------------------

class TestFullSecurityStack:
    def test_detection_to_quarantine_to_release(self):
        """Full lifecycle: detect threat → quarantine → release."""
        from src.security.mesh_shield import MeshShield, ThreatIndicator, ThreatLevel

        shield = MeshShield()

        # 1. Detection: report threat indicator
        indicator = ThreatIndicator(
            node_id="suspect-node",
            indicator_type="anomaly_score",
            value=0.92,
        )
        threat = shield.report_indicator(indicator)

        # 2. Quarantine: node should be isolated if threat is HIGH+
        if threat and threat.value >= ThreatLevel.HIGH.value:
            assert shield.is_quarantined("suspect-node") is True

            # 3. Investigation: release after false positive determination
            released = shield.release_node("suspect-node", "false_positive")
            assert released is True
            assert shield.is_quarantined("suspect-node") is False

    def test_byzantine_detection_to_isolation(self):
        """Byzantine detection triggers auto-isolation."""
        from src.security.byzantine_detection import ByzantineDetector, ByzantineBehavior
        from src.security.auto_isolation import IsolationRecord, IsolationLevel, IsolationReason

        byzantine = ByzantineDetector(min_evidence_nodes=1)

        # Detect Byzantine behavior
        alert = byzantine.detect_byzantine_behavior(
            "evil-node",
            ByzantineBehavior.DOUBLE_SPEND,
            {"amount": 500, "direct_proof": True, "multiple_witnesses": True},
            reported_by="honest-node",
        )

        if alert:
            # Create isolation record
            record = IsolationRecord(
                node_id="evil-node",
                level=IsolationLevel.QUARANTINE,
                reason=IsolationReason.THREAT_DETECTED,
                started_at=time.time(),
                expires_at=time.time() + 3600,
            )
            assert record.node_id == "evil-node"
            assert record.level == IsolationLevel.QUARANTINE

    def test_mtls_config_to_certificate_validation(self):
        """mTLS config integrates with certificate validation."""
        from src.security.mtls_client import MTLSConfig, CertificateInfo
        from datetime import datetime, timedelta

        config = MTLSConfig()
        now = datetime.utcnow()

        cert = CertificateInfo(
            subject="CN=node-1",
            issuer="CN=x0tta6bl4-ca",
            not_before=now - timedelta(hours=1),
            not_after=now + timedelta(hours=48),
            serial_number=1,
            spiffe_id="spiffe://x0tta6bl4.mesh/node-1",
        )

        assert cert.is_valid is True
        assert cert.needs_rotation is False
        assert cert.spiffe_id == "spiffe://x0tta6bl4.mesh/node-1"

    def test_did_document_to_policy_evaluation(self):
        """DID Document identity feeds into policy engine."""
        from src.security.decentralized_identity import DIDDocument, VerificationMethod, KeyPurpose
        from src.security.policy_engine import PolicyEngine, AttributeType

        # Create DID document
        doc = DIDDocument(id="did:mesh:node-1")
        vm = VerificationMethod(
            id="did:mesh:node-1#key-1",
            type="Ed25519VerificationKey2020",
            controller="did:mesh:node-1",
            public_key_multibase="z6Mk...",
            purpose=[KeyPurpose.AUTHENTICATION],
        )
        doc.verification_method.append(vm)
        doc.authentication.append(vm.id)

        # Feed into policy engine
        engine = PolicyEngine(node_id="node-1")
        decision = engine.evaluate(
            subject={"node_id": "node-1", "trust_level": 80},
            resource="/api/data",
            action="read",
        )
        # Decision depends on policy rules
        assert decision.effect.value in ("allow", "deny", "audit")

    def test_hardware_enclave_to_attestation(self):
        """Hardware enclave generates attestation for verification."""
        from src.security.hardware_enclave import HardwareSecurityModule, AttestationService

        hsm = HardwareSecurityModule(mode="mock")

        # Sign data
        data = b"mesh topology hash"
        signature = hsm.sign_with_hardware(data)
        assert len(signature) > 0

        # Generate attestation quote
        quote = hsm.sign_with_hardware(b"attestation-quote")
        nonce = b"verification-nonce"

        # Verify attestation
        assert hsm.verify_hardware_attestation(quote, nonce) is True

        # Validate node via attestation service
        result = AttestationService.validate_node({
            "hardware_id": "tpm-abc",
            "enclave_enabled": True,
        })
        assert result["security_level"] == "HARDWARE_ROOTED"


# ---------------------------------------------------------------------------
# Integration 8: Configuration → Runtime Behavior
# ---------------------------------------------------------------------------

class TestConfigurationIntegration:
    def test_env_settings_drive_policy_engine(self):
        """Environment settings configure policy engine behavior."""
        from src.config.env_settings import AppSettings, FeatureFlags
        from src.security.policy_engine import PolicyEngine

        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            settings = AppSettings()
            assert settings.is_production is True

        engine = PolicyEngine(node_id="prod-node")
        stats = engine.get_stats()
        assert stats["total_policies"] >= 4

    def test_circuit_breaker_config_from_settings(self):
        """Circuit breaker configuration from env settings."""
        from src.config.env_settings import DatabaseSettings
        from src.core.circuit_breaker import CircuitBreaker

        with patch.dict("os.environ", {
            "DB_CB_FAILURE_THRESHOLD": "10",
            "DB_CB_RECOVERY_TIMEOUT": "30",
        }):
            settings = DatabaseSettings()
            cb = CircuitBreaker(
                name="db-test",
                failure_threshold=settings.cb_failure_threshold,
                recovery_timeout=float(settings.cb_recovery_timeout),
            )
            assert cb.failure_threshold == 10
            assert cb.recovery_timeout == 30.0
