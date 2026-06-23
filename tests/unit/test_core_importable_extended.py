"""
Tests for additional importable modules: crypto, licensing, repositories, database.

Covers:
- PQC Crypto (encrypt/decrypt roundtrip)
- Licensing (lazy imports)
- Database models (with SQLite test DB)
- Repository pattern (CRUD operations)
"""

import os
import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# PQC Crypto
# ---------------------------------------------------------------------------

class TestPQCCrypto:
    def test_import(self):
        import src.crypto.pqc_crypto as mod
        assert hasattr(mod, 'PQCCrypto')

    @pytest.mark.skipif(
        not os.getenv("PQC_FAIL_CLOSED", "true").lower() == "false",
        reason="PQC requires liboqs or PQC_FAIL_CLOSED=false"
    )
    def test_encrypt_decrypt_roundtrip(self):
        from src.crypto.pqc_crypto import PQCCrypto
        crypto = PQCCrypto()
        plaintext = b"hello x0tta6bl4 post-quantum world"
        encrypted = crypto.encrypt(plaintext)
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == plaintext

    @pytest.mark.skipif(
        not os.getenv("PQC_FAIL_CLOSED", "true").lower() == "false",
        reason="PQC requires liboqs or PQC_FAIL_CLOSED=false"
    )
    def test_encrypt_empty(self):
        from src.crypto.pqc_crypto import PQCCrypto
        crypto = PQCCrypto()
        encrypted = crypto.encrypt(b"")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == b""


# ---------------------------------------------------------------------------
# Licensing (lazy imports)
# ---------------------------------------------------------------------------

class TestLicensing:
    def test_lazy_exports(self):
        import src.licensing as mod
        expected = [
            "DeviceFingerprint",
            "HardwareFingerprinter",
            "IdentityCertificate",
            "LicenseActivationError",
            "LicenseAuthority",
            "MeshNetworkValidator",
            "NodeLicenseManager",
        ]
        for name in expected:
            assert name in mod.__all__

    def test_getattr_nonexistent_raises(self):
        import src.licensing as mod
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = mod.NonExistentClass

    def test_dir_includes_exports(self):
        import src.licensing as mod
        d = dir(mod)
        assert "DeviceFingerprint" in d
        assert "NodeLicenseManager" in d


# ---------------------------------------------------------------------------
# Database Models (with SQLite test DB)
# ---------------------------------------------------------------------------

class TestDatabaseModels:
    @pytest.fixture(autouse=True)
    def _setup_db(self, tmp_path):
        """Create a fresh SQLite DB for each test."""
        self.db_url = f"sqlite:///{tmp_path}/test.db"
        os.environ["DATABASE_URL"] = self.db_url

    def _get_engine(self):
        from sqlalchemy import create_engine
        from src.database import Base
        engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        return engine

    def test_user_model_creation(self):
        from sqlalchemy.orm import Session
        from src.database import User
        engine = self._get_engine()
        with Session(engine) as db:
            user = User(
                id="user-test-001",
                email="test@example.com",
                password_hash="hashed123",
                full_name="Test User",
                plan="free",
                role="user",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            assert user.id == "user-test-001"
            assert user.email == "test@example.com"

    def test_mesh_instance_model(self):
        from sqlalchemy.orm import Session
        from src.database import MeshInstance
        engine = self._get_engine()
        with Session(engine) as db:
            instance = MeshInstance(
                id="mesh-test-001",
                name="test-mesh",
                owner_id="user-1",
                status="active",
            )
            db.add(instance)
            db.commit()
            db.refresh(instance)
            assert instance.id == "mesh-test-001"
            assert instance.name == "test-mesh"

    def test_payment_model(self):
        from sqlalchemy.orm import Session
        from src.database import Payment
        engine = self._get_engine()
        with Session(engine) as db:
            payment = Payment(
                id="pay-test-001",
                user_id="user-1",
                order_id="order-test-001",
                amount=999,
                currency="USD",
                payment_method="STRIPE",
                status="completed",
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            assert payment.id == "pay-test-001"
            assert payment.amount == 999


# ---------------------------------------------------------------------------
# Repository Pattern (with test DB)
# ---------------------------------------------------------------------------

class TestRepositories:
    @pytest.fixture(autouse=True)
    def _setup_db(self, tmp_path):
        """Create a fresh SQLite DB and session for each test."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.database import Base
        self.db_url = f"sqlite:///{tmp_path}/test.db"
        engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        self.db = SessionLocal()

    def teardown_method(self):
        self.db.close()

    def test_user_repository_create_and_get(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        user = User(
            id="repo-test-001",
            email="repo@test.com",
            password_hash="hash",
            plan="free",
        )
        created = repo.create(user)
        assert created.id == "repo-test-001"
        fetched = repo.get_by_id(created.id)
        assert fetched.email == "repo@test.com"

    def test_user_repository_get_all(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        for i in range(5):
            repo.create(User(
                id=f"user-{i}",
                email=f"user_{i}@test.com",
                password_hash="hash",
                plan="free",
            ))
        all_users = repo.get_all()
        assert len(all_users) == 5

    def test_user_repository_update(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        user = repo.create(User(
            id="update-test-001",
            email="update@test.com",
            password_hash="hash",
            plan="free",
        ))
        updated = repo.update(user.id, full_name="Updated Name")
        assert updated.full_name == "Updated Name"

    def test_user_repository_delete(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        user = repo.create(User(
            id="delete-test-001",
            email="delete@test.com",
            password_hash="hash",
            plan="free",
        ))
        assert repo.delete(user.id) is True
        assert repo.get_by_id(user.id) is None

    def test_user_repository_count(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        assert repo.count() == 0
        repo.create(User(
            id="count-test-001",
            email="count@test.com",
            password_hash="hash",
            plan="free",
        ))
        assert repo.count() == 1

    def test_user_repository_get_by_email(self):
        from src.repositories.base import UserRepository
        from src.database import User
        repo = UserRepository(self.db)
        repo.create(User(
            id="email-test-001",
            email="find@test.com",
            password_hash="hash",
            plan="free",
        ))
        found = repo.get_by_email("find@test.com")
        assert found is not None
        assert found.id == "email-test-001"


# ---------------------------------------------------------------------------
# Circuit Breaker advanced patterns
# ---------------------------------------------------------------------------

class TestCircuitBreakerAdvanced:
    def test_is_open_property(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1)
        assert cb.is_open() is False
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        state = cb.get_state()
        assert state in ("open", "half_open")

    def test_success_count_resets_on_failure(self):
        from src.resilience.advanced_patterns import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, success_threshold=2)
        cb.call(lambda: "ok")
        cb.call(lambda: "ok")
        assert cb.success_count == 0  # success_count only tracked in HALF_OPEN
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.failure_count == 1

    def test_custom_config(self):
        from src.resilience.advanced_patterns import CircuitBreaker, CircuitBreakerConfig
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout_seconds=120,
            success_threshold=5,
        )
        cb = CircuitBreaker(config=config, name="custom")
        assert cb.name == "custom"
        assert cb.config.failure_threshold == 10
        assert cb.config.recovery_timeout_seconds == 120


# ---------------------------------------------------------------------------
# Event Bus persistence
# ---------------------------------------------------------------------------

class TestEventBusPersistence:
    def test_events_persisted_to_disk(self, tmp_path):
        from src.coordination.events import EventBus, EventType
        bus = EventBus(project_root=str(tmp_path))
        bus.publish(EventType.AGENT_REGISTERED, "agent-1", {"role": "worker"})
        bus.publish(EventType.TASK_CREATED, "agent-2", {"task_id": "T1"})

        # Create new bus - should load from disk
        bus2 = EventBus(project_root=str(tmp_path))
        history = bus2.get_event_history()
        assert len(history) == 2

    def test_event_history_filtered(self, tmp_path):
        from src.coordination.events import EventBus, EventType
        bus = EventBus(project_root=str(tmp_path))
        bus.publish(EventType.AGENT_REGISTERED, "agent-1", {})
        bus.publish(EventType.TASK_CREATED, "agent-1", {})
        bus.publish(EventType.AGENT_HEARTBEAT, "agent-2", {})

        history = bus.get_event_history(event_type=EventType.AGENT_REGISTERED)
        assert len(history) == 1

    def test_event_ack(self, tmp_path):
        from src.coordination.events import EventBus, EventType
        bus = EventBus(project_root=str(tmp_path))
        event = bus.publish(
            EventType.TASK_ASSIGNED, "coordinator",
            {"task_id": "T1"},
            target_agents={"worker-1"},
            requires_ack=True,
        )
        assert bus.ack_event(event.event_id, "worker-1") is True
        pending = bus.get_pending_acks("worker-1")
        assert len(pending) == 0
