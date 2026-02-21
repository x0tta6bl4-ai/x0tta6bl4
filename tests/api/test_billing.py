import hashlib
import hmac
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Mock slowapi.Limiter class globally before any imports that use it
with patch("slowapi.Limiter") as MockLimiter:
    MockLimiter.return_value.limit.return_value = lambda f: f

    from src.api.billing import router as billing_router
    from src.api.billing import stripe_webhook
    from src.core.circuit_breaker import CircuitBreakerOpen, stripe_circuit
    from src.database import Base, License
    from src.database import Session as DB_Session
    from src.database import User, get_db

# Create a minimal FastAPI app for testing purposes
test_app = FastAPI()
test_app.include_router(billing_router)

# Setup for isolated in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in the test database
Base.metadata.create_all(bind=engine)


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Create a test database session for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest_asyncio.fixture(name="client")
async def client_fixture(db_session: Session):
    """Create an asynchronous test client for the FastAPI app."""

    def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac

    test_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_env_vars():
    """Set up and tear down environment variables for Stripe during tests."""
    original_env = os.environ.copy()
    os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_123"
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_123"
    os.environ["STRIPE_PRICE_ID"] = "price_123"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_123"
    yield
    os.environ.clear()
    os.environ.update(original_env)


# --- Tests for GET /api/v1/billing/config ---
@pytest.mark.asyncio
async def test_billing_config_configured(client: AsyncClient):
    """Test retrieving billing config when configured."""
    response = await client.get("/api/v1/billing/config")
    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "publishable_key": "pk_test_123",
        "price_id": "price_123",
    }


@pytest.mark.asyncio
async def test_billing_config_not_configured(client: AsyncClient, setup_env_vars):
    """Test retrieving billing config when not configured."""
    del os.environ["STRIPE_SECRET_KEY"]
    response = await client.get("/api/v1/billing/config")
    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "publishable_key": "pk_test_123",  # Publishable key might still be there
        "price_id": "price_123",
    }


# --- Tests for POST /api/v1/billing/checkout-session ---
@pytest.mark.asyncio
async def test_create_checkout_session_success(client: AsyncClient, mocker):
    """Test successful creation of a checkout session."""
    mock_stripe_response = {
        "id": "cs_test_session123",
        "url": "https://checkout.stripe.com/c/pay/cs_test_session123",
    }

    class _FakeStripeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return MagicMock(status_code=200, json=lambda: mock_stripe_response)

    mocker.patch("src.api.billing.httpx.AsyncClient", return_value=_FakeStripeClient())

    async def _call(func, *args, **kwargs):
        return await func(*args, **kwargs)

    mocker.patch.object(
        stripe_circuit, "call", wraps=_call
    )  # Ensure circuit breaker awaits the function

    response = await client.post(
        "/api/v1/billing/checkout-session",
        json={"email": "user@example.com", "plan": "pro", "quantity": 1},
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": mock_stripe_response["id"],
        "url": mock_stripe_response["url"],
    }


@pytest.mark.asyncio
async def test_create_checkout_session_stripe_api_failure(client: AsyncClient, mocker):
    """Test handling of Stripe API failure during checkout session creation."""

    class _FakeStripeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return MagicMock(
                status_code=400, json=lambda: {"error": {"message": "Stripe error"}}
            )

    mocker.patch("src.api.billing.httpx.AsyncClient", return_value=_FakeStripeClient())

    async def _call(func, *args, **kwargs):
        return await func(*args, **kwargs)

    mocker.patch.object(stripe_circuit, "call", wraps=_call)

    response = await client.post(
        "/api/v1/billing/checkout-session",
        json={"email": "user@example.com", "plan": "pro", "quantity": 1},
    )
    assert response.status_code == 502
    assert "Stripe error" in response.json()["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_create_checkout_session_invalid_email(client: AsyncClient):
    """Test creating a checkout session with an invalid email."""
    response = await client.post(
        "/api/v1/billing/checkout-session",
        json={"email": "invalid-email", "plan": "pro", "quantity": 1},
    )
    assert response.status_code == 400
    assert "Invalid email" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_checkout_session_missing_config(
    client: AsyncClient, setup_env_vars
):
    """Test creating a checkout session with missing Stripe configuration."""
    del os.environ["STRIPE_SECRET_KEY"]
    response = await client.post(
        "/api/v1/billing/checkout-session",
        json={"email": "user@example.com", "plan": "pro", "quantity": 1},
    )
    assert response.status_code == 503
    assert (
        "Missing required configuration: STRIPE_SECRET_KEY" in response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_create_checkout_session_circuit_breaker_open(
    client: AsyncClient, mocker
):
    """Test creating a checkout session when the circuit breaker is open."""
    mocker.patch.object(stripe_circuit, "call", side_effect=CircuitBreakerOpen)
    response = await client.post(
        "/api/v1/billing/checkout-session",
        json={"email": "user@example.com", "plan": "pro", "quantity": 1},
    )
    assert response.status_code == 503
    assert (
        "Payment service temporarily unavailable. Please try again later."
        in response.json()["detail"]
    )


# --- Tests for POST /api/v1/billing/webhook ---
# Helper to generate a valid Stripe-Signature
def generate_stripe_signature(payload: bytes, secret: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    signature = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def build_webhook_request(payload_bytes: bytes, stripe_signature: str | None = None):
    from starlette.requests import Request

    headers = [(b"content-type", b"application/json")]
    if stripe_signature:
        headers.append((b"stripe-signature", stripe_signature.encode("utf-8")))

    async def _receive():
        return {"type": "http.request", "body": payload_bytes, "more_body": False}

    return Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/v1/billing/webhook",
            "headers": headers,
        },
        receive=_receive,
    )


async def call_webhook(
    payload_bytes: bytes, db_session: Session, stripe_signature: str | None
):
    request = build_webhook_request(payload_bytes, stripe_signature)
    return await stripe_webhook(
        request=request, db=db_session, stripe_signature=stripe_signature
    )


@pytest.mark.asyncio
async def test_stripe_webhook_success(
    db_session: Session, setup_env_vars, mocker
):
    """Test successful Stripe webhook processing."""
    # Register a user first
    user_email = "webhook_user@example.com"
    user = User(
        id="user_123", email=user_email, password_hash="hashed_password", plan="free"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Mock TokenGenerator
    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="mock_license_token",
    )
    mocker.patch("src.api.billing.XrayManager.add_user", new=AsyncMock(return_value=True))

    event_payload = {
        "id": "evt_test_webhook",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_123",
                "subscription": "sub_123",
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True

    # Verify user and license updated in DB
    updated_user = db_session.query(User).filter(User.email == user_email).first()
    assert updated_user.plan == "pro"
    assert updated_user.stripe_customer_id == "cus_123"
    assert updated_user.stripe_subscription_id == "sub_123"

    license = (
        db_session.query(License).filter(License.user_id == updated_user.id).first()
    )
    assert license is not None
    assert license.token == "mock_license_token"
    assert license.tier == "pro"
    assert license.is_active == True


@pytest.mark.asyncio
async def test_stripe_webhook_idempotent_replay_by_event_id(
    db_session: Session, setup_env_vars, mocker
):
    """Replay of the same Stripe event_id must not duplicate side effects."""
    user_email = "idem_user@example.com"
    user = User(
        id="user_idem_123", email=user_email, password_hash="hashed_password", plan="free"
    )
    db_session.add(user)
    db_session.commit()

    mock_token = mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="idem_license_token",
    )
    mocker.patch("src.api.billing.XrayManager.add_user", new=AsyncMock(return_value=True))

    event_payload = {
        "id": "evt_idempotent_001",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_idem_123",
                "subscription": "sub_idem_123",
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    first = await call_webhook(payload_bytes, db_session, signature)
    second = await call_webhook(payload_bytes, db_session, signature)
    assert first["received"] is True
    assert second["received"] is True

    # Side effects must be created only once for duplicate event_id.
    assert mock_token.call_count == 1
    licenses = db_session.query(License).filter(License.user_id == user.id).all()
    assert len(licenses) == 1


@pytest.mark.asyncio
async def test_stripe_webhook_event_id_payload_mismatch_returns_409(
    db_session: Session, setup_env_vars, mocker
):
    """Same Stripe event_id with different payload should be rejected."""
    user_email = "idem_conflict@example.com"
    user = User(
        id="user_idem_conflict", email=user_email, password_hash="hashed_password", plan="free"
    )
    db_session.add(user)
    db_session.commit()

    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="idem_conflict_license",
    )
    mocker.patch("src.api.billing.XrayManager.add_user", new=AsyncMock(return_value=True))

    base_payload = {
        "id": "evt_idempotent_conflict",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_conflict_123",
                "subscription": "sub_conflict_123",
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }

    first_bytes = json.dumps(base_payload).encode("utf-8")
    first_sig = generate_stripe_signature(
        first_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], int(time.time())
    )
    first = await call_webhook(first_bytes, db_session, first_sig)
    assert first["received"] is True

    # Same event id, changed payload => conflict.
    altered_payload = dict(base_payload)
    altered_payload["data"] = {
        "object": {
            "customer_email": user_email,
            "customer": "cus_conflict_123",
            "subscription": "sub_conflict_changed",
            "metadata": {"user_email": user_email, "plan": "pro"},
        }
    }
    second_bytes = json.dumps(altered_payload).encode("utf-8")
    second_sig = generate_stripe_signature(
        second_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], int(time.time())
    )

    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(second_bytes, db_session, second_sig)
    assert exc_info.value.status_code == 409
    assert "payload mismatch" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_stripe_webhook_missing_signature(
    db_session: Session, setup_env_vars
):
    """Test Stripe webhook with missing signature header."""
    event_payload = {
        "id": "evt_test_webhook",
        "type": "checkout.session.completed",
        "data": {"object": {"customer_email": "test@example.com"}},
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")

    request = build_webhook_request(payload_bytes, stripe_signature=None)

    with pytest.raises(HTTPException) as exc_info:
        await stripe_webhook(request=request, db=db_session, stripe_signature=None)

    assert exc_info.value.status_code == 400
    assert "Missing Stripe-Signature header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature(
    db_session: Session, setup_env_vars
):
    """Test Stripe webhook with invalid signature."""
    event_payload = {
        "id": "evt_test_webhook",
        "type": "checkout.session.completed",
        "data": {"object": {"customer_email": "test@example.com"}},
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    invalid_signature = generate_stripe_signature(
        payload_bytes, "invalid_secret", timestamp
    )

    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(payload_bytes, db_session, invalid_signature)

    assert exc_info.value.status_code == 400
    assert "Invalid signature" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stripe_webhook_expired_signature(
    db_session: Session, setup_env_vars
):
    """Test Stripe webhook with an expired signature timestamp."""
    event_payload = {
        "id": "evt_test_webhook",
        "type": "checkout.session.completed",
        "data": {"object": {"customer_email": "test@example.com"}},
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    expired_timestamp = int(time.time()) - 3600  # 1 hour ago
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], expired_timestamp
    )

    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(payload_bytes, db_session, signature)

    assert exc_info.value.status_code == 400
    assert "Signature timestamp outside tolerance" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stripe_webhook_malformed_signature_header(
    db_session: Session, setup_env_vars
):
    """Test Stripe webhook with a malformed Stripe-Signature header."""
    event_payload = {
        "id": "evt_test_webhook",
        "type": "some.event",
        "data": {"object": {}},
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())

    # Missing v1
    malformed_signature = f"t={timestamp},v2=abc"
    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(payload_bytes, db_session, malformed_signature)
    assert exc_info.value.status_code == 400
    assert "Invalid Stripe-Signature header" in exc_info.value.detail

    # Missing t
    malformed_signature = f"t=abc,v1=abc"  # Invalid timestamp format
    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(payload_bytes, db_session, malformed_signature)
    assert exc_info.value.status_code == 400
    assert "Invalid signature timestamp" in exc_info.value.detail

    # Completely malformed
    malformed_signature = "just-a-string"
    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(payload_bytes, db_session, malformed_signature)
    assert exc_info.value.status_code == 400
    assert "Invalid Stripe-Signature header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_json(db_session: Session, setup_env_vars):
    """Test Stripe webhook with invalid JSON payload."""
    invalid_payload = b"not a json"
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        invalid_payload, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    with pytest.raises(HTTPException) as exc_info:
        await call_webhook(invalid_payload, db_session, signature)
    assert exc_info.value.status_code == 400
    assert "Invalid JSON" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stripe_webhook_invoice_paid(
    db_session: Session, setup_env_vars, mocker
):
    """Test Stripe webhook processing for 'invoice.paid' event."""
    user_email = "invoice_user@example.com"
    user = User(
        id="user_inv_123",
        email=user_email,
        password_hash="hashed_password",
        plan="free",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="mock_invoice_license",
    )
    mocker.patch("src.api.billing.XrayManager.add_user", new=AsyncMock(return_value=True))

    event_payload = {
        "id": "evt_invoice_paid",
        "type": "invoice.paid",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_invoice_123",
                "subscription": "sub_invoice_123",
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True

    updated_user = db_session.query(User).filter(User.email == user_email).first()
    assert updated_user.plan == "pro"
    assert updated_user.stripe_customer_id == "cus_invoice_123"
    assert updated_user.stripe_subscription_id == "sub_invoice_123"

    license = (
        db_session.query(License).filter(License.user_id == updated_user.id).first()
    )
    assert license is not None
    assert license.token == "mock_invoice_license"


@pytest.mark.asyncio
async def test_stripe_webhook_customer_subscription_created(
    db_session: Session, setup_env_vars, mocker
):
    """Test Stripe webhook processing for 'customer.subscription.created' event."""
    user_email = "sub_user@example.com"
    user = User(
        id="user_sub_123",
        email=user_email,
        password_hash="hashed_password",
        plan="free",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="mock_sub_license",
    )
    mocker.patch("src.api.billing.XrayManager.add_user", new=AsyncMock(return_value=True))

    event_payload = {
        "id": "evt_sub_created",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_sub_123",
                "id": "sub_sub_123",  # Subscription ID is 'id' for this event
                "subscription": "sub_sub_123",  # Added to match current billing.py logic
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True

    updated_user = db_session.query(User).filter(User.email == user_email).first()
    assert updated_user.plan == "pro"
    assert updated_user.stripe_customer_id == "cus_sub_123"
    assert updated_user.stripe_subscription_id == "sub_sub_123"

    license = (
        db_session.query(License).filter(License.user_id == updated_user.id).first()
    )
    assert license is not None
    assert license.token == "mock_sub_license"


@pytest.mark.asyncio
async def test_stripe_webhook_unhandled_event_type(
    db_session: Session, setup_env_vars
):
    """Test Stripe webhook with an unhandled event type."""
    event_payload = {
        "id": "evt_unhandled",
        "type": "unhandled.event",
        "data": {"object": {"customer_email": "test@example.com"}},
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True
    # Assert no user or license changes in DB (would require more complex mocking)


@pytest.mark.asyncio
async def test_stripe_webhook_missing_email_payload(
    db_session: Session, setup_env_vars, mocker
):
    """Test Stripe webhook with missing email in various payload locations."""
    # Ensure no user exists with this email
    user_email = "no_email_user@example.com"
    assert db_session.query(User).filter(User.email == user_email).first() is None

    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        return_value="mock_license_token",
    )

    event_payload = {
        "id": "evt_no_email",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                # No customer_email, no customer_details.email, no metadata.user_email
                "customer": "cus_no_email",
                "subscription": "sub_no_email",
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True
    # Verify no user was updated/created and no license was generated
    assert (
        db_session.query(License).filter_by(token="mock_license_token").first() is None
    )


@pytest.mark.asyncio
async def test_stripe_webhook_db_rollback_on_error(
    db_session: Session, setup_env_vars, mocker
):
    """Test Stripe webhook ensures database rollback if an error occurs during processing."""
    user_email = "rollback_user@example.com"
    user = User(
        id="user_rb_123", email=user_email, password_hash="hashed_password", plan="free"
    )
    db_session.add(user)
    db_session.commit()

    mocker.patch(
        "src.sales.telegram_bot.TokenGenerator.generate",
        side_effect=Exception("DB error"),
    )
    mocker.patch.dict(
        "src.api.users.users_db", {user_email: {"plan": "free"}}
    )  # Correctly patch dictionary

    event_payload = {
        "id": "evt_rb_webhook",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": user_email,
                "customer": "cus_rb_123",
                "subscription": "sub_rb_123",
                "metadata": {"user_email": user_email, "plan": "pro"},
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    timestamp = int(time.time())
    signature = generate_stripe_signature(
        payload_bytes, os.environ["STRIPE_WEBHOOK_SECRET"], timestamp
    )

    response = await call_webhook(payload_bytes, db_session, signature)
    assert response["received"] is True

    # Verify that the user's plan was NOT updated due to rollback
    updated_user = db_session.query(User).filter(User.email == user_email).first()
    assert updated_user.plan == "free"
    assert updated_user.stripe_customer_id is None  # Not updated
    assert updated_user.stripe_subscription_id is None  # Not updated

    # Verify no license was generated
    assert (
        db_session.query(License).filter_by(tier="pro", user_id=user.id).first() is None
    )
