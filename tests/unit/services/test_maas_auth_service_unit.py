"""Unit tests for shared MaaS auth service."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.maas_auth_models import UserLoginRequest, UserRegisterRequest
from src.database import Base, User
from src.services.maas_auth_service import MaaSAuthService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_register_creates_user_with_configured_plan(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "test-api-key",
        default_plan="starter",
    )
    req = UserRegisterRequest(
        email=f"user-{uuid.uuid4().hex}@test.local",
        password="StrongPassword123!",
        full_name="Test User",
        company="TestCo",
    )

    user = service.register(db_session, req)

    assert user.email == req.email
    assert user.plan == "starter"
    assert user.api_key == "test-api-key"
    assert user.full_name == "Test User"
    assert user.company == "TestCo"
    assert user.password_hash.startswith("$2")


def test_register_duplicate_email_raises_400(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "dup-key",
        default_plan="starter",
    )
    email = f"dup-{uuid.uuid4().hex}@test.local"
    req = UserRegisterRequest(email=email, password="StrongPassword123!")
    service.register(db_session, req)

    with pytest.raises(HTTPException) as exc:
        service.register(db_session, req)
    assert exc.value.status_code == 400


def test_register_duplicate_email_is_case_insensitive(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "dup-ci-key",
        default_plan="starter",
    )
    email = f"dupci-{uuid.uuid4().hex}@test.local"
    service.register(
        db_session,
        UserRegisterRequest(email=email.upper(), password="StrongPassword123!"),
    )

    with pytest.raises(HTTPException) as exc:
        service.register(
            db_session,
            UserRegisterRequest(email=email.lower(), password="StrongPassword123!"),
        )
    assert exc.value.status_code == 400


def test_login_accepts_legacy_plaintext_and_rehashes(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "legacy-key",
        default_plan="starter",
    )
    email = f"legacy-{uuid.uuid4().hex}@test.local"
    plain_password = "legacy_password_123"
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=plain_password,
        api_key="legacy-key",
        plan="starter",
    )
    db_session.add(user)
    db_session.commit()

    api_key = service.login(
        db_session,
        UserLoginRequest(email=email, password=plain_password),
    )

    assert api_key == "legacy-key"
    refreshed = db_session.query(User).filter(User.email == email).first()
    assert refreshed is not None
    assert refreshed.password_hash != plain_password
    assert refreshed.password_hash.startswith("$2")


def test_register_normalizes_email_and_login_is_case_insensitive(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "case-key",
        default_plan="starter",
    )
    raw_email = f"  User-{uuid.uuid4().hex}@Test.Local  "
    password = "StrongPassword123!"
    user = service.register(
        db_session,
        UserRegisterRequest(email=raw_email, password=password),
    )
    assert user.email == raw_email.strip().lower()

    api_key = service.login(
        db_session,
        UserLoginRequest(email=user.email.upper(), password=password),
    )
    assert api_key == "case-key"


def test_login_invalid_password_raises_401(db_session):
    service = MaaSAuthService(
        api_key_factory=lambda: "invalid-key",
        default_plan="starter",
    )
    req = UserRegisterRequest(
        email=f"invalid-{uuid.uuid4().hex}@test.local",
        password="StrongPassword123!",
    )
    service.register(db_session, req)

    with pytest.raises(HTTPException) as exc:
        service.login(
            db_session,
            UserLoginRequest(email=req.email, password="wrong-password"),
        )
    assert exc.value.status_code == 401


def test_rotate_api_key_updates_user(db_session):
    keys = iter(["first-key", "rotated-key"])
    service = MaaSAuthService(
        api_key_factory=lambda: next(keys),
        default_plan="starter",
    )
    req = UserRegisterRequest(
        email=f"rotate-{uuid.uuid4().hex}@test.local",
        password="StrongPassword123!",
    )
    user = service.register(db_session, req)
    assert user.api_key == "first-key"

    new_key, rotated_at = service.rotate_api_key(db_session, user)
    assert new_key == "rotated-key"
    assert rotated_at is not None

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed is not None
    assert refreshed.api_key == "rotated-key"
