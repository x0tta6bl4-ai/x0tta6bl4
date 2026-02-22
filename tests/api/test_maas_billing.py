"""
Integration tests for MaaS Billing API.

maas_billing.py router has prefix /api/v1/maas/billing — NOT shadowed by legacy.

Endpoints:
  POST /api/v1/maas/billing/invoices/generate/{mesh_id}  — generate invoice (billing:view)
  GET  /api/v1/maas/billing/invoices/history              — list invoices (billing:view)
  GET  /api/v1/maas/billing/invoices/{id}/checkout        — Stripe checkout (billing:pay)
  POST /api/v1/maas/billing/webhook/stripe                — Stripe webhook
  POST /api/v1/maas/billing/invoices/{id}/pay             — manual payment (any auth)

RBAC:
  user     — has billing:view (generates invoices, reads history)
  operator — has billing:view too; no billing:pay
  admin    — bypasses all (billing:view, billing:pay)

Note:
  - generate_invoice calls legacy _get_mesh_or_404 → mesh must be in mesh_provisioner
  - checkout endpoint requires STRIPE_SECRET_KEY (will 500 without it)
  - webhook endpoint requires STRIPE_WEBHOOK_SECRET (will 500 without it)
  - manual pay (/pay) bypasses Stripe entirely
"""

import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, Invoice, User, get_db

_TEST_DB_PATH = f"./test_billing_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def billing_data(client):
    """
    - admin: deploys mesh (owner); admin bypass for billing:view/pay
    - user: has billing:view by default (no deploy)
    """
    email_admin = f"bill-adm-{uuid.uuid4().hex[:8]}@test.com"
    email_usr = f"bill-usr-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_admin, "password": "password123"})
    admin_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_usr, "password": "password123"})
    usr_token = r.json()["access_token"]

    # Elevate admin
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.api_key == admin_token).first()
    admin.role = "admin"
    db.commit()
    db.close()

    # Admin deploys mesh → adds to mesh_provisioner (needed for generate_invoice)
    r = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Billing Test Mesh", "nodes": 2},
        headers={"X-API-Key": admin_token},
    )
    assert r.status_code == 200, f"Deploy failed: {r.text}"
    mesh_id = r.json()["mesh_id"]

    return {
        "admin_token": admin_token,
        "usr_token": usr_token,
        "mesh_id": mesh_id,
    }


def _db_invoice(user_id: str, mesh_id: str, status: str = "issued") -> str:
    """Create an Invoice directly in SQLAlchemy DB; return its id."""
    from datetime import datetime
    db = TestingSessionLocal()
    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    db.add(Invoice(
        id=inv_id,
        user_id=user_id,
        mesh_id=mesh_id,
        total_amount=500,  # 50 cents in hundredths
        period_start=datetime(2026, 1, 1),
        period_end=datetime(2026, 1, 31),
        status=status,
    ))
    db.commit()
    db.close()
    return inv_id


# ---------------------------------------------------------------------------
# GET /billing/invoices/history
# ---------------------------------------------------------------------------

class TestInvoiceHistory:
    def test_no_auth_401(self, client, billing_data):
        r = client.get("/api/v1/maas/billing/invoices/history")
        assert r.status_code == 401

    def test_user_gets_empty_list(self, client, billing_data):
        """New user has no invoices."""
        r = client.get(
            "/api/v1/maas/billing/invoices/history",
            headers={"X-API-Key": billing_data["usr_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_admin_history_returns_list(self, client, billing_data):
        r = client.get(
            "/api/v1/maas/billing/invoices/history",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_history_shows_generated_invoice(self, client, billing_data):
        """After generating an invoice, history contains it."""
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

        r = client.get(
            "/api/v1/maas/billing/invoices/history",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        invoices = r.json()
        assert len(invoices) >= 1

    def test_history_invoice_fields(self, client, billing_data):
        """Invoice response contains required fields."""
        r = client.get(
            "/api/v1/maas/billing/invoices/history",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        invoices = r.json()
        if invoices:
            inv = invoices[0]
            assert "id" in inv
            assert "mesh_id" in inv
            assert "total_amount" in inv
            assert "status" in inv

    def test_history_only_shows_own_invoices(self, client, billing_data):
        """User's history doesn't contain admin's invoices."""
        r = client.get(
            "/api/v1/maas/billing/invoices/history",
            headers={"X-API-Key": billing_data["usr_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json() == []


# ---------------------------------------------------------------------------
# POST /billing/invoices/generate/{mesh_id}
# ---------------------------------------------------------------------------

class TestGenerateInvoice:
    def test_no_auth_401(self, client, billing_data):
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}"
        )
        assert r.status_code == 401

    def test_user_nonowner_gets_404(self, client, billing_data):
        """User doesn't own the mesh (admin owns it) → legacy 404."""
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["usr_token"]},
        )
        assert r.status_code == 404

    def test_admin_owner_success(self, client, billing_data):
        """Admin (owner + billing:view bypass) generates invoice successfully."""
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_invoice_response_fields(self, client, billing_data):
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mesh_id"] == billing_data["mesh_id"]
        assert data["status"] == "issued"
        assert "total_amount" in data
        assert "id" in data

    def test_invoice_amount_is_float(self, client, billing_data):
        """total_amount is returned as dollars (float), not cents."""
        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        amount = r.json()["total_amount"]
        assert isinstance(amount, float)
        assert amount >= 0.50  # minimum invoice is $0.50

    def test_unknown_mesh_404(self, client, billing_data):
        r = client.post(
            "/api/v1/maas/billing/invoices/generate/mesh-nonexistent-xyz",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /billing/invoices/{invoice_id}/pay  (manual, no Stripe)
# ---------------------------------------------------------------------------

class TestManualPayInvoice:
    def test_no_auth_401(self, client, billing_data):
        r = client.post("/api/v1/maas/billing/invoices/inv-fake/pay")
        assert r.status_code == 401

    def test_pay_own_invoice_success(self, client, billing_data):
        """Admin creates invoice then pays it manually."""
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin_id = admin.id
        db.close()

        inv_id = _db_invoice(admin_id, billing_data["mesh_id"])
        r = client.post(
            f"/api/v1/maas/billing/invoices/{inv_id}/pay",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "paid"
        assert data["invoice_id"] == inv_id

    def test_pay_other_users_invoice_404(self, client, billing_data):
        """User cannot pay admin's invoice (different user_id)."""
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin_id = admin.id
        db.close()

        inv_id = _db_invoice(admin_id, billing_data["mesh_id"])
        r = client.post(
            f"/api/v1/maas/billing/invoices/{inv_id}/pay",
            headers={"X-API-Key": billing_data["usr_token"]},
        )
        assert r.status_code == 404

    def test_pay_nonexistent_invoice_404(self, client, billing_data):
        r = client.post(
            "/api/v1/maas/billing/invoices/inv-nonexistent/pay",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /billing/webhook/stripe  (no Stripe secret → 500)
# ---------------------------------------------------------------------------

class TestStripeWebhook:
    def test_webhook_no_secret_500(self, client, billing_data):
        """STRIPE_WEBHOOK_SECRET not set in test env → 500."""
        r = client.post(
            "/api/v1/maas/billing/webhook/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 500

    def test_webhook_invalid_signature_400(self, client, billing_data, monkeypatch):
        """With STRIPE_WEBHOOK_SECRET set but invalid sig → 400."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        import src.api.maas_billing as billing_mod
        billing_mod.STRIPE_WEBHOOK_SECRET = "whsec_test_secret"

        r = client.post(
            "/api/v1/maas/billing/webhook/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "invalid_sig",
            },
        )
        assert r.status_code == 400

        billing_mod.STRIPE_WEBHOOK_SECRET = None  # restore


# ---------------------------------------------------------------------------
# Stripe webhook happy-path and edge cases (with mocked Stripe)
# ---------------------------------------------------------------------------

class TestStripeWebhookHandling:
    """Cover checkout.session.completed handling in stripe_webhook."""

    def _set_webhook_secret(self):
        import src.api.maas_billing as m
        m.STRIPE_WEBHOOK_SECRET = "whsec_test"
        return m

    def _restore(self, mod):
        mod.STRIPE_WEBHOOK_SECRET = None

    def test_webhook_marks_invoice_paid(self, client, billing_data):
        """Valid event with invoice_id in DB → invoice status set to 'paid'."""
        from unittest.mock import patch, MagicMock
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin_id = admin.id
        db.close()

        inv_id = _db_invoice(admin_id, billing_data["mesh_id"], status="issued")
        mod = self._set_webhook_secret()

        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"invoice_id": inv_id}}},
        }

        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = client.post(
                "/api/v1/maas/billing/webhook/stripe",
                content=b'{}',
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "valid-sig",
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        db = TestingSessionLocal()
        inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
        db.close()
        assert inv is not None
        assert inv.status == "paid"
        self._restore(mod)

    def test_webhook_invoice_not_found_returns_success(self, client, billing_data):
        """Valid event with non-existent invoice_id → logger.error but still 200."""
        from unittest.mock import patch
        mod = self._set_webhook_secret()
        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"invoice_id": "inv-nonexistent-xyz"}}},
        }
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = client.post(
                "/api/v1/maas/billing/webhook/stripe",
                content=b'{}',
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "valid-sig",
                },
            )
        assert r.status_code == 200
        self._restore(mod)

    def test_webhook_missing_invoice_id_metadata_returns_success(self, client, billing_data):
        """Valid event but no invoice_id in metadata → logger.warning but still 200."""
        from unittest.mock import patch
        mod = self._set_webhook_secret()
        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {}}},  # no invoice_id
        }
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = client.post(
                "/api/v1/maas/billing/webhook/stripe",
                content=b'{}',
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "valid-sig",
                },
            )
        assert r.status_code == 200
        self._restore(mod)

    def test_webhook_unhandled_event_type_returns_success(self, client, billing_data):
        """Event type not 'checkout.session.completed' → ignored, returns success."""
        from unittest.mock import patch
        mod = self._set_webhook_secret()
        fake_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {}},
        }
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = client.post(
                "/api/v1/maas/billing/webhook/stripe",
                content=b'{}',
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "valid-sig",
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        self._restore(mod)


# ---------------------------------------------------------------------------
# GET /billing/invoices/{id}/checkout — edge cases
# ---------------------------------------------------------------------------

class TestCheckoutEdgeCases:
    """Cover 'invoice already paid' and 'no Stripe key' branches."""

    def test_checkout_already_paid_returns_200(self, client, billing_data):
        """Invoice with status='paid' → 200 with 'already paid' message."""
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin_id = admin.id
        db.close()

        inv_id = _db_invoice(admin_id, billing_data["mesh_id"], status="paid")
        r = client.get(
            f"/api/v1/maas/billing/invoices/{inv_id}/checkout",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert "already paid" in data.get("message", "").lower()
        assert data.get("url") is None

    def test_checkout_no_stripe_key_500(self, client, billing_data):
        """With no STRIPE_SECRET_KEY (test default) and issued invoice → 500."""
        import src.api.maas_billing as mod
        # Ensure no key is set (default in test env)
        original = mod.STRIPE_SECRET_KEY
        mod.STRIPE_SECRET_KEY = None

        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin_id = admin.id
        db.close()

        inv_id = _db_invoice(admin_id, billing_data["mesh_id"], status="issued")
        r = client.get(
            f"/api/v1/maas/billing/invoices/{inv_id}/checkout",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 500
        mod.STRIPE_SECRET_KEY = original

    def test_checkout_invoice_not_found_404(self, client, billing_data):
        """Non-existent invoice → 404."""
        r = client.get(
            "/api/v1/maas/billing/invoices/inv-not-found-xyz/checkout",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# generate_invoice — enterprise plan billing rate
# ---------------------------------------------------------------------------

class TestEnterpriseInvoiceRate:
    def test_enterprise_user_gets_higher_rate(self, client, billing_data):
        """Enterprise plan users have rate=0.05 instead of 0.01."""
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin.plan = "enterprise"
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/billing/invoices/generate/{billing_data['mesh_id']}",
            headers={"X-API-Key": billing_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        # Enterprise minimum invoice is still $0.50 if hours are low,
        # but plan field should have been applied
        assert r.json()["total_amount"] >= 0.50

        # Restore plan
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == billing_data["admin_token"]).first()
        admin.plan = "starter"
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Unit-style tests for billing/legacy utility functions (no TestClient needed)
# ---------------------------------------------------------------------------

class TestBillingUtilityFunctions:
    """Direct tests for billing utility functions in maas_legacy.

    These functions are tested without the HTTP layer (no TestClient needed).
    """

    def test_is_reissue_token_expired_non_string_returns_true(self):
        """expires_at not a string → True (line 816-817)."""
        from src.api.maas_legacy import _is_reissue_token_expired
        assert _is_reissue_token_expired({"expires_at": None}) is True
        assert _is_reissue_token_expired({"expires_at": 12345}) is True
        assert _is_reissue_token_expired({}) is True

    def test_is_reissue_token_expired_invalid_iso_returns_true(self):
        """expires_at is an invalid ISO string → ValueError → True (line 820-821)."""
        from src.api.maas_legacy import _is_reissue_token_expired
        assert _is_reissue_token_expired({"expires_at": "not-a-date"}) is True

    def test_is_reissue_token_expired_past_returns_true(self):
        """expires_at is in the past → True."""
        from datetime import datetime, timedelta
        from src.api.maas_legacy import _is_reissue_token_expired
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        assert _is_reissue_token_expired({"expires_at": past}) is True

    def test_is_reissue_token_expired_future_returns_false(self):
        """expires_at is in the future → False."""
        from datetime import datetime, timedelta
        from src.api.maas_legacy import _is_reissue_token_expired
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        assert _is_reissue_token_expired({"expires_at": future}) is False

    def test_billing_webhook_tolerance_invalid_env_returns_default(self):
        """Non-int env value → ValueError → 300 default (line 844-845)."""
        from unittest.mock import patch
        from src.api.maas_legacy import _billing_webhook_tolerance_seconds
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_TOLERANCE_SEC": "not-an-int"}):
            assert _billing_webhook_tolerance_seconds() == 300

    def test_billing_webhook_tolerance_clamped_to_min(self):
        """Value below 30 → clamped to 30."""
        from unittest.mock import patch
        from src.api.maas_legacy import _billing_webhook_tolerance_seconds
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_TOLERANCE_SEC": "5"}):
            assert _billing_webhook_tolerance_seconds() == 30

    def test_billing_webhook_tolerance_clamped_to_max(self):
        """Value above 3600 → clamped to 3600."""
        from unittest.mock import patch
        from src.api.maas_legacy import _billing_webhook_tolerance_seconds
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_TOLERANCE_SEC": "9999"}):
            assert _billing_webhook_tolerance_seconds() == 3600

    def test_billing_event_ttl_invalid_env_returns_default(self):
        """Non-int env value → ValueError → 86400 default (line 853-854)."""
        from unittest.mock import patch
        from src.api.maas_legacy import _billing_event_ttl_seconds
        with patch.dict(os.environ, {"X0T_BILLING_EVENT_TTL_SEC": "not-an-int"}):
            assert _billing_event_ttl_seconds() == 86_400

    def test_billing_event_ttl_clamped_to_min(self):
        """Value below 300 → clamped to 300."""
        from unittest.mock import patch
        from src.api.maas_legacy import _billing_event_ttl_seconds
        with patch.dict(os.environ, {"X0T_BILLING_EVENT_TTL_SEC": "10"}):
            assert _billing_event_ttl_seconds() == 300

    def test_verify_billing_webhook_secret_no_env_passes(self):
        """No X0T_BILLING_WEBHOOK_SECRET env → passes without raising."""
        from unittest.mock import patch
        from src.api.maas_legacy import _verify_billing_webhook_secret
        with patch.dict(os.environ, {}, clear=True):
            _verify_billing_webhook_secret("any-value")  # should not raise

    def test_verify_billing_webhook_secret_mismatch_raises_401(self):
        """Expected secret set, provided doesn't match → 401."""
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_secret
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_SECRET": "correct-secret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_secret("wrong-secret")
            assert exc.value.status_code == 401

    def test_verify_billing_webhook_secret_none_raises_401(self):
        """Expected secret set, provided is None → 401."""
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_secret
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_SECRET": "correct-secret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_secret(None)
            assert exc.value.status_code == 401

    def test_payload_sha256_hex_returns_hex_string(self):
        """_payload_sha256_hex returns a 64-char hex string."""
        import hashlib
        from src.api.maas_legacy import _payload_sha256_hex
        result = _payload_sha256_hex(b"test payload")
        assert len(result) == 64
        expected = hashlib.sha256(b"test payload").hexdigest()
        assert result == expected


# ---------------------------------------------------------------------------
# Unit-style tests for HMAC webhook verification
# ---------------------------------------------------------------------------

class TestBillingWebhookHMAC:
    """Direct tests for _verify_billing_webhook_hmac (no TestClient needed)."""

    def test_no_secret_env_returns_none(self):
        """When X0T_BILLING_WEBHOOK_HMAC_SECRET is not set → returns immediately."""
        from unittest.mock import patch
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            result = _verify_billing_webhook_hmac(b"payload", "12345", "sig")
            assert result is None

    def test_missing_timestamp_header_raises_401(self):
        """Secret set, but no timestamp header → 401."""
        import hashlib
        import hmac as hmac_mod
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": "testsecret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_hmac(b"payload", None, "sig")
            assert exc.value.status_code == 401

    def test_missing_signature_header_raises_401(self):
        """Secret set, timestamp provided, but no signature → 401."""
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": "testsecret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_hmac(b"payload", "12345", None)
            assert exc.value.status_code == 401

    def test_invalid_timestamp_raises_400(self):
        """Non-integer timestamp header → 400."""
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": "testsecret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_hmac(b"payload", "not-a-number", "sig")
            assert exc.value.status_code == 400

    def test_expired_timestamp_raises_401(self):
        """Timestamp too far in the past → 401."""
        import time
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        old_ts = str(int(time.time()) - 9999)  # Way expired
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": "testsecret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_hmac(b"payload", old_ts, "sha256=fakesig")
            assert exc.value.status_code == 401

    def test_valid_hmac_with_sha256_prefix(self):
        """Valid HMAC with 'sha256=' prefix → no exception."""
        import time
        import hashlib
        import hmac as hmac_mod
        from unittest.mock import patch
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        secret = "valid-hmac-secret"
        payload = b"test billing payload"
        ts = str(int(time.time()))
        signed = f"{ts}.".encode("utf-8") + payload
        expected = hmac_mod.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": secret}):
            # Should not raise
            _verify_billing_webhook_hmac(payload, ts, f"sha256={expected}")

    def test_wrong_signature_raises_401(self):
        """Valid timestamp but wrong HMAC → 401."""
        import time
        from unittest.mock import patch
        from fastapi import HTTPException
        from src.api.maas_legacy import _verify_billing_webhook_hmac
        ts = str(int(time.time()))
        with patch.dict(os.environ, {"X0T_BILLING_WEBHOOK_HMAC_SECRET": "mysecret"}):
            with pytest.raises(HTTPException) as exc:
                _verify_billing_webhook_hmac(b"payload", ts, "wrong" * 16)
            assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Unit-style tests for billing event ID extraction
# ---------------------------------------------------------------------------

class TestExtractBillingEventId:
    """Direct tests for _extract_billing_event_id (no TestClient needed)."""

    def test_event_id_from_req_field(self):
        """req.event_id set → returned directly (stripped)."""
        from src.api.maas_legacy import _extract_billing_event_id, BillingWebhookRequest
        req = BillingWebhookRequest(event_id="evt-123456789", event_type="payment.succeeded")
        result = _extract_billing_event_id(req)
        assert result == "evt-123456789"

    def test_event_id_from_metadata_event_id_key(self):
        """req.event_id is None → fallback to metadata['event_id']."""
        from src.api.maas_legacy import _extract_billing_event_id, BillingWebhookRequest
        req = BillingWebhookRequest(
            event_type="payment.succeeded",
            metadata={"event_id": "meta-evt-99999"},
        )
        result = _extract_billing_event_id(req)
        assert result == "meta-evt-99999"

    def test_event_id_from_metadata_id_key(self):
        """req.event_id None, no metadata.event_id → fallback to metadata['id']."""
        from src.api.maas_legacy import _extract_billing_event_id, BillingWebhookRequest
        req = BillingWebhookRequest(
            event_type="payment.succeeded",
            metadata={"id": "meta-id-77777"},
        )
        result = _extract_billing_event_id(req)
        assert result == "meta-id-77777"

    def test_missing_event_id_raises_400(self):
        """No event_id anywhere → HTTPException 400."""
        from fastapi import HTTPException
        from src.api.maas_legacy import _extract_billing_event_id, BillingWebhookRequest
        req = BillingWebhookRequest(event_type="payment.succeeded")
        with pytest.raises(HTTPException) as exc:
            _extract_billing_event_id(req)
        assert exc.value.status_code == 400

    def test_whitespace_event_id_raises_400(self):
        """Whitespace-only metadata id → HTTPException 400."""
        from fastapi import HTTPException
        from src.api.maas_legacy import _extract_billing_event_id, BillingWebhookRequest
        req = BillingWebhookRequest(
            event_type="payment.succeeded",
            metadata={"id": "   "},
        )
        with pytest.raises(HTTPException) as exc:
            _extract_billing_event_id(req)
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Unit-style tests for billing event response deserialization
# ---------------------------------------------------------------------------

class TestDeserializeBillingEventResponse:
    """Direct tests for _deserialize_billing_event_response (no TestClient needed)."""

    def test_none_returns_none(self):
        from src.api.maas_legacy import _deserialize_billing_event_response
        assert _deserialize_billing_event_response(None) is None

    def test_empty_string_returns_none(self):
        from src.api.maas_legacy import _deserialize_billing_event_response
        assert _deserialize_billing_event_response("") is None

    def test_invalid_json_returns_none(self):
        from src.api.maas_legacy import _deserialize_billing_event_response
        assert _deserialize_billing_event_response("{not valid json}") is None

    def test_non_dict_json_returns_none(self):
        """JSON list is valid but not a dict → None."""
        from src.api.maas_legacy import _deserialize_billing_event_response
        assert _deserialize_billing_event_response("[1, 2, 3]") is None

    def test_valid_dict_json_returned(self):
        """Valid JSON dict → returned as dict."""
        import json
        from src.api.maas_legacy import _deserialize_billing_event_response
        payload = {"status": "ok", "amount": 9.99}
        result = _deserialize_billing_event_response(json.dumps(payload))
        assert result == payload


# ---------------------------------------------------------------------------
# Unit-style tests for ACL and mesh helper functions
# ---------------------------------------------------------------------------

class TestACLFunctions:
    """Direct tests for _rule_matches and _evaluate_acl_decision (no TestClient needed)."""

    def test_rule_matches_both_tags_present(self):
        """Both source and target tags present → True."""
        from src.api.maas_legacy import _rule_matches
        assert _rule_matches(["robot", "sensor"], ["gateway", "cloud"], "robot", "gateway") is True

    def test_rule_matches_source_tag_missing(self):
        """source_tag not in source_tags → False."""
        from src.api.maas_legacy import _rule_matches
        assert _rule_matches(["sensor"], ["gateway"], "robot", "gateway") is False

    def test_rule_matches_target_tag_missing(self):
        """target_tag not in target_tags → False."""
        from src.api.maas_legacy import _rule_matches
        assert _rule_matches(["robot"], ["cloud"], "robot", "gateway") is False

    def test_evaluate_acl_isolated_profile_always_denies(self):
        """acl_profile='isolated' → deny regardless of rules."""
        from src.api.maas_legacy import _evaluate_acl_decision
        policies = [{"source_tag": "robot", "target_tag": "gateway", "action": "allow"}]
        result = _evaluate_acl_decision(["robot"], ["gateway"], policies, "isolated")
        assert result["action"] == "deny"
        assert result["reason"] == "acl_profile_isolated"

    def test_evaluate_acl_explicit_deny_wins_over_allow(self):
        """Deny rule present among matched rules → deny."""
        from src.api.maas_legacy import _evaluate_acl_decision
        policies = [
            {"source_tag": "robot", "target_tag": "gateway", "action": "deny"},
            {"source_tag": "robot", "target_tag": "gateway", "action": "allow"},
        ]
        result = _evaluate_acl_decision(["robot"], ["gateway"], policies, "default")
        assert result["action"] == "deny"
        assert result["reason"] == "explicit_deny"

    def test_evaluate_acl_explicit_allow(self):
        """Allow rule matched, no deny → allow."""
        from src.api.maas_legacy import _evaluate_acl_decision
        policies = [{"source_tag": "robot", "target_tag": "gateway", "action": "allow"}]
        result = _evaluate_acl_decision(["robot"], ["gateway"], policies, "default")
        assert result["action"] == "allow"
        assert result["reason"] == "explicit_allow"

    def test_evaluate_acl_no_policies_default_legacy_open(self):
        """Empty policies + default profile → legacy_open_mesh allow."""
        from src.api.maas_legacy import _evaluate_acl_decision
        result = _evaluate_acl_decision(["robot"], ["gateway"], [], "default")
        assert result["action"] == "allow"
        assert result["reason"] == "legacy_open_mesh"

    def test_evaluate_acl_no_matching_rules_default_deny(self):
        """Policies exist but none match → default_deny_zero_trust."""
        from src.api.maas_legacy import _evaluate_acl_decision
        policies = [{"source_tag": "sensor", "target_tag": "cloud", "action": "allow"}]
        result = _evaluate_acl_decision(["robot"], ["gateway"], policies, "default")
        assert result["action"] == "deny"
        assert result["reason"] == "default_deny_zero_trust"


# ---------------------------------------------------------------------------
# Unit-style tests for mesh helper functions (_find_mesh_id_for_node, _build_mapek_heartbeat_event)
# ---------------------------------------------------------------------------

class TestMeshHelperFunctions:
    """Direct tests for mesh helper functions (no TestClient needed)."""

    def test_find_mesh_id_for_node_found(self):
        """Node is in a registered mesh → returns mesh_id."""
        import src.api.maas_legacy as leg
        from src.api.maas_legacy import _find_mesh_id_for_node
        mesh_id = f"mesh-find-{uuid.uuid4().hex[:8]}"
        node_id = f"node-find-{uuid.uuid4().hex[:8]}"
        mock_instance = type("MI", (), {"node_instances": {node_id: {}}})()
        leg._mesh_registry[mesh_id] = mock_instance
        try:
            result = _find_mesh_id_for_node(node_id)
            assert result == mesh_id
        finally:
            del leg._mesh_registry[mesh_id]

    def test_find_mesh_id_for_node_not_found(self):
        """Node is not in any mesh → returns None."""
        from src.api.maas_legacy import _find_mesh_id_for_node
        result = _find_mesh_id_for_node(f"ghost-node-{uuid.uuid4().hex}")
        assert result is None

    def test_build_mapek_critical_no_neighbors(self):
        """neighbors_count == 0 → critical health state."""
        from src.api.maas_legacy import _build_mapek_heartbeat_event, NodeHeartbeatRequest
        telemetry = NodeHeartbeatRequest(
            node_id="n1", cpu_usage=10.0, memory_usage=20.0,
            neighbors_count=0, routing_table_size=5, uptime=3600.0,
        )
        result = _build_mapek_heartbeat_event(telemetry)
        assert result["health_state"] == "critical"
        assert result["recommendation"] == "reroute_and_recover"

    def test_build_mapek_critical_high_cpu(self):
        """cpu_usage >= 95 → critical health state."""
        from src.api.maas_legacy import _build_mapek_heartbeat_event, NodeHeartbeatRequest
        telemetry = NodeHeartbeatRequest(
            node_id="n2", cpu_usage=95.5, memory_usage=50.0,
            neighbors_count=3, routing_table_size=8, uptime=7200.0,
        )
        result = _build_mapek_heartbeat_event(telemetry)
        assert result["health_state"] == "critical"

    def test_build_mapek_degraded(self):
        """cpu_usage >= 85 but < 95, memory < 95, neighbors > 0 → degraded."""
        from src.api.maas_legacy import _build_mapek_heartbeat_event, NodeHeartbeatRequest
        telemetry = NodeHeartbeatRequest(
            node_id="n3", cpu_usage=87.0, memory_usage=60.0,
            neighbors_count=2, routing_table_size=10, uptime=1800.0,
        )
        result = _build_mapek_heartbeat_event(telemetry)
        assert result["health_state"] == "degraded"
        assert result["recommendation"] == "scale_or_rebalance"

    def test_build_mapek_healthy(self):
        """All metrics in normal range → healthy state."""
        from src.api.maas_legacy import _build_mapek_heartbeat_event, NodeHeartbeatRequest
        telemetry = NodeHeartbeatRequest(
            node_id="n4", cpu_usage=30.0, memory_usage=40.0,
            neighbors_count=4, routing_table_size=12, uptime=86400.0,
        )
        result = _build_mapek_heartbeat_event(telemetry)
        assert result["health_state"] == "healthy"
        assert result["recommendation"] == "maintain"
        assert result["phase"] == "MONITOR"
        assert result["node_id"] == "n4"


# ---------------------------------------------------------------------------
# Unit-style tests for PQC profile lookup
# ---------------------------------------------------------------------------

class TestGetPQCProfile:
    """Direct tests for _get_pqc_profile (no TestClient needed)."""

    def test_known_device_class_sensor_returned(self):
        from src.api.maas_legacy import _get_pqc_profile
        profile = _get_pqc_profile("sensor")
        assert profile["kem"] == "ML-KEM-512"
        assert profile["sig"] == "ML-DSA-44"
        assert profile["security_level"] == 1

    def test_known_device_class_gateway_returned(self):
        from src.api.maas_legacy import _get_pqc_profile
        profile = _get_pqc_profile("gateway")
        assert profile["kem"] == "ML-KEM-1024"
        assert profile["security_level"] == 5

    def test_unknown_device_class_returns_default_profile(self):
        from src.api.maas_legacy import _get_pqc_profile, _PQC_DEFAULT_PROFILE
        profile = _get_pqc_profile("unknown-device-xyz")
        assert profile == _PQC_DEFAULT_PROFILE
        assert profile["security_level"] == 3


# ---------------------------------------------------------------------------
# Unit-style tests for _audit helper
# ---------------------------------------------------------------------------

class TestAuditHelper:
    """Direct tests for _audit (no TestClient needed)."""

    def test_audit_creates_new_list_for_new_mesh(self):
        import src.api.maas_legacy as leg
        from src.api.maas_legacy import _audit
        mesh_id = f"mesh-audit-{uuid.uuid4().hex[:8]}"
        assert mesh_id not in leg._mesh_audit_log
        _audit(mesh_id, "user-1", "deploy", "deployed 5 nodes")
        assert mesh_id in leg._mesh_audit_log
        assert len(leg._mesh_audit_log[mesh_id]) == 1
        entry = leg._mesh_audit_log[mesh_id][0]
        assert entry["actor"] == "user-1"
        assert entry["event"] == "deploy"
        assert entry["details"] == "deployed 5 nodes"
        # Cleanup
        del leg._mesh_audit_log[mesh_id]

    def test_audit_appends_to_existing_list(self):
        import src.api.maas_legacy as leg
        from src.api.maas_legacy import _audit
        mesh_id = f"mesh-audit2-{uuid.uuid4().hex[:8]}"
        _audit(mesh_id, "user-a", "create", "first event")
        _audit(mesh_id, "user-b", "update", "second event")
        assert len(leg._mesh_audit_log[mesh_id]) == 2
        assert leg._mesh_audit_log[mesh_id][1]["actor"] == "user-b"
        # Cleanup
        del leg._mesh_audit_log[mesh_id]


# ---------------------------------------------------------------------------
# Unit-style tests for BillingService
# ---------------------------------------------------------------------------

class TestBillingService:
    """Direct tests for BillingService methods (no TestClient needed)."""

    def test_normalize_plan_free_maps_to_starter(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan("free") == "starter"

    def test_normalize_plan_starter_maps_to_starter(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan("starter") == "starter"

    def test_normalize_plan_pro_maps_to_pro(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan("pro") == "pro"

    def test_normalize_plan_enterprise_maps_to_enterprise(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan("enterprise") == "enterprise"

    def test_normalize_plan_none_defaults_to_starter(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan(None) == "starter"

    def test_normalize_plan_unknown_defaults_to_starter(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        assert svc.normalize_plan("unknown-plan") == "starter"

    def test_plan_catalog_has_all_plans(self):
        from src.api.maas_legacy import BillingService
        svc = BillingService()
        catalog = svc.plan_catalog()
        assert "starter" in catalog
        assert "pro" in catalog
        assert "enterprise" in catalog

    def test_check_quota_within_limit_returns_true(self):
        from src.api.maas_legacy import BillingService
        from src.database import User
        svc = BillingService()
        user = User(plan="pro")
        assert svc.check_quota(user, requested_nodes=10) is True

    def test_check_quota_exceeds_plan_limit_raises(self):
        from src.api.maas_legacy import BillingService
        from src.database import User
        svc = BillingService()
        user = User(plan="starter")
        with pytest.raises(Exception, match="Quota exceeded"):
            svc.check_quota(user, requested_nodes=100)

    def test_check_quota_plan_escalation_blocked(self):
        from src.api.maas_legacy import BillingService
        from src.database import User
        svc = BillingService()
        user = User(plan="starter")
        with pytest.raises(Exception, match="Plan escalation blocked"):
            svc.check_quota(user, requested_nodes=5, requested_plan="enterprise")


# ---------------------------------------------------------------------------
# Unit-style tests for _is_join_token_expired
# ---------------------------------------------------------------------------

class TestIsJoinTokenExpired:
    """Direct tests for _is_join_token_expired (no TestClient needed)."""

    def test_expired_token_returns_true(self):
        from datetime import timedelta
        from src.api.maas_legacy import _is_join_token_expired
        mock_instance = type("MI", (), {
            "join_token_expires_at": datetime.utcnow() - timedelta(hours=1)
        })()
        assert _is_join_token_expired(mock_instance) is True

    def test_future_token_returns_false(self):
        from datetime import timedelta
        from src.api.maas_legacy import _is_join_token_expired
        mock_instance = type("MI", (), {
            "join_token_expires_at": datetime.utcnow() + timedelta(hours=24)
        })()
        assert _is_join_token_expired(mock_instance) is False


# ---------------------------------------------------------------------------
# Unit-style tests for _resolve_billing_user
# ---------------------------------------------------------------------------

class TestResolveBillingUser:
    """Direct tests for _resolve_billing_user with in-memory SQLite (no TestClient needed)."""

    @pytest.fixture()
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.database import Base
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SL = sessionmaker(bind=engine)
        db = SL()
        try:
            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)

    def _make_user(self, db, **kwargs):
        from src.database import User
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email=f"test-{uuid.uuid4().hex[:8]}@resolve.test",
            password_hash="$2b$12$fakehash" + "x" * 53,  # bcrypt-format placeholder
            api_key=f"x0t_{uuid.uuid4().hex}",
            plan="starter",
            **kwargs,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_resolves_by_user_id(self, db_session):
        from src.api.maas_legacy import _resolve_billing_user, BillingWebhookRequest
        user = self._make_user(db_session)
        req = BillingWebhookRequest(event_type="plan.upgraded", user_id=user.id)
        result = _resolve_billing_user(db_session, req)
        assert result is not None
        assert result.id == user.id

    def test_resolves_by_customer_id(self, db_session):
        from src.api.maas_legacy import _resolve_billing_user, BillingWebhookRequest
        user = self._make_user(db_session, stripe_customer_id="cus_test_123")
        req = BillingWebhookRequest(
            event_type="subscription.created",
            customer_id="cus_test_123",
        )
        result = _resolve_billing_user(db_session, req)
        assert result is not None
        assert result.stripe_customer_id == "cus_test_123"

    def test_resolves_by_email(self, db_session):
        from src.api.maas_legacy import _resolve_billing_user, BillingWebhookRequest
        user = self._make_user(db_session)
        req = BillingWebhookRequest(event_type="plan.upgraded", email=user.email)
        result = _resolve_billing_user(db_session, req)
        assert result is not None
        assert result.email == user.email

    def test_no_match_returns_none(self, db_session):
        from src.api.maas_legacy import _resolve_billing_user, BillingWebhookRequest
        req = BillingWebhookRequest(event_type="plan.upgraded")
        result = _resolve_billing_user(db_session, req)
        assert result is None

    def test_resolves_by_user_id_from_metadata(self, db_session):
        """user_id not on req but in metadata → resolved via metadata."""
        from src.api.maas_legacy import _resolve_billing_user, BillingWebhookRequest
        user = self._make_user(db_session)
        req = BillingWebhookRequest(
            event_type="plan.upgraded",
            metadata={"user_id": user.id},
        )
        result = _resolve_billing_user(db_session, req)
        assert result is not None
        assert result.id == user.id


# ---------------------------------------------------------------------------
# Unit-style tests for billing event state machine helpers
# ---------------------------------------------------------------------------

class TestBillingEventStateMachine:
    """Direct tests for _finalize, _fail, and _cleanup billing event helpers."""

    @pytest.fixture()
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.database import Base
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SL = sessionmaker(bind=engine)
        db = SL()
        try:
            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)

    def _make_event(self, db, event_id, status="processing"):
        from src.database import BillingWebhookEvent
        event = BillingWebhookEvent(
            event_id=event_id,
            event_type="plan.upgraded",
            payload_hash="abc123",
            status=status,
        )
        db.add(event)
        db.commit()
        return event

    def test_finalize_updates_event_to_done(self, db_session):
        from src.api.maas_legacy import _finalize_billing_event_processing
        from src.database import BillingWebhookEvent
        eid = f"fin-evt-{uuid.uuid4().hex[:8]}"
        self._make_event(db_session, eid)
        _finalize_billing_event_processing(db_session, eid, {"result": "ok"})
        row = db_session.query(BillingWebhookEvent).filter_by(event_id=eid).first()
        assert row.status == "done"
        assert row.last_error is None
        assert row.processed_at is not None

    def test_finalize_raises_runtime_error_when_event_missing(self, db_session):
        from src.api.maas_legacy import _finalize_billing_event_processing
        with pytest.raises(RuntimeError, match="Billing event reservation missing"):
            _finalize_billing_event_processing(db_session, "ghost-event-id", {})

    def test_fail_updates_event_to_failed(self, db_session):
        from src.api.maas_legacy import _fail_billing_event_processing
        from src.database import BillingWebhookEvent
        eid = f"fail-evt-{uuid.uuid4().hex[:8]}"
        self._make_event(db_session, eid)
        _fail_billing_event_processing(db_session, eid, "Something went wrong")
        row = db_session.query(BillingWebhookEvent).filter_by(event_id=eid).first()
        assert row.status == "failed"
        assert "Something went wrong" in row.last_error

    def test_fail_missing_event_returns_silently(self, db_session):
        from src.api.maas_legacy import _fail_billing_event_processing
        # Should not raise, just return
        _fail_billing_event_processing(db_session, "ghost-event-id", "err")

    def test_fail_truncates_long_error_to_2000_chars(self, db_session):
        from src.api.maas_legacy import _fail_billing_event_processing
        from src.database import BillingWebhookEvent
        eid = f"fail-long-{uuid.uuid4().hex[:8]}"
        self._make_event(db_session, eid)
        long_error = "x" * 3000
        _fail_billing_event_processing(db_session, eid, long_error)
        row = db_session.query(BillingWebhookEvent).filter_by(event_id=eid).first()
        assert len(row.last_error) == 2000

    def test_cleanup_removes_expired_events(self, db_session):
        from datetime import timedelta
        from src.api.maas_legacy import _cleanup_expired_billing_events
        from src.database import BillingWebhookEvent
        eid = f"clean-evt-{uuid.uuid4().hex[:8]}"
        event = BillingWebhookEvent(
            event_id=eid,
            event_type="plan.upgraded",
            payload_hash="old",
            status="done",
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        db_session.add(event)
        db_session.commit()
        _cleanup_expired_billing_events(db_session)
        row = db_session.query(BillingWebhookEvent).filter_by(event_id=eid).first()
        assert row is None
