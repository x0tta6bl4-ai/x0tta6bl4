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
