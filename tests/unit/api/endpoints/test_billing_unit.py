"""Unit tests for src/api/maas/billing_helpers.py and billing endpoint."""

import asyncio
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.maas.billing_helpers import (
    IdempotencyStore,
    calculate_mesh_cost,
    calculate_node_cost,
    compute_hmac_signature,
    estimate_monthly_cost,
    format_currency,
    generate_invoice,
    verify_hmac_signature,
    verify_webhook_with_timestamp,
)


# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------


def test_compute_hmac_signature_returns_prefixed_hex():
    sig = compute_hmac_signature(b"payload", "secret")
    assert sig.startswith("sha256=")
    assert len(sig) == len("sha256=") + 64


def test_compute_hmac_signature_str_and_bytes_are_equal():
    assert compute_hmac_signature("hello", "s") == compute_hmac_signature(b"hello", "s")


def test_verify_hmac_signature_valid():
    sig = compute_hmac_signature(b"data", "mysecret")
    assert verify_hmac_signature(b"data", sig, "mysecret") is True


def test_verify_hmac_signature_wrong_payload():
    sig = compute_hmac_signature(b"data", "mysecret")
    assert verify_hmac_signature(b"other", sig, "mysecret") is False


def test_verify_hmac_signature_wrong_secret():
    sig = compute_hmac_signature(b"data", "secret1")
    assert verify_hmac_signature(b"data", sig, "secret2") is False


def test_verify_hmac_signature_without_prefix():
    # signature without "sha256=" prefix
    import hashlib
    import hmac as hmac_mod

    raw = hmac_mod.new(b"s", b"p", hashlib.sha256).hexdigest()
    assert verify_hmac_signature(b"p", raw, "s") is True


# ---------------------------------------------------------------------------
# Webhook timestamp verification
# ---------------------------------------------------------------------------


def test_verify_webhook_with_timestamp_valid():
    secret = "webhooksecret"
    ts = str(int(time.time()))
    payload = '{"type":"payment"}'
    signed = f"{ts}.{payload}"
    sig = compute_hmac_signature(signed, secret)
    assert verify_webhook_with_timestamp(payload.encode(), sig, ts, secret) is True


def test_verify_webhook_with_timestamp_expired():
    secret = "s"
    old_ts = str(int(time.time()) - 400)  # > 300s skew
    payload = b"body"
    signed = f"{old_ts}.body"
    sig = compute_hmac_signature(signed, secret)
    assert verify_webhook_with_timestamp(payload, sig, old_ts, secret) is False


def test_verify_webhook_with_timestamp_invalid_ts():
    assert verify_webhook_with_timestamp(b"x", "sig", "not-a-number", "s") is False


def test_verify_webhook_with_timestamp_wrong_sig():
    ts = str(int(time.time()))
    assert verify_webhook_with_timestamp(b"body", "sha256=bad", ts, "secret") is False


# ---------------------------------------------------------------------------
# Billing calculations
# ---------------------------------------------------------------------------


def test_calculate_node_cost_standard_free_us_east():
    # 0.05 * 1.0 * 1.0 * 10h = 0.50
    cost = calculate_node_cost("standard", "free", "us-east-1", 10)
    assert cost == Decimal("0.50")


def test_calculate_node_cost_enterprise_discount():
    # enterprise = 0.6 multiplier → 0.05 * 0.6 * 1.0 * 10 = 0.30
    cost = calculate_node_cost("standard", "enterprise", "us-east-1", 10)
    assert cost == Decimal("0.30")


def test_calculate_node_cost_eu_region_surcharge():
    # eu-central-1 surcharge = 1.1 → 0.05 * 1.0 * 1.1 * 10 = 0.55
    cost = calculate_node_cost("standard", "free", "eu-central-1", 10)
    assert cost == Decimal("0.55")


def test_calculate_node_cost_unknown_type_falls_back_to_standard():
    cost_std = calculate_node_cost("standard", "free", "us-east-1", 1)
    cost_unk = calculate_node_cost("nonexistent_type", "free", "us-east-1", 1)
    assert cost_std == cost_unk


def test_calculate_mesh_cost_multiplies_nodes():
    single = calculate_node_cost("standard", "pro", "us-east-1", 5)
    mesh = calculate_mesh_cost(3, "standard", "pro", "us-east-1", 5)
    assert mesh == single * 3


def test_estimate_monthly_cost_uses_730_hours():
    monthly = estimate_monthly_cost(1, "standard", "free", "us-east-1")
    expected = calculate_mesh_cost(1, "standard", "free", "us-east-1", 730)
    assert monthly == expected


def test_format_currency_formats_correctly():
    assert format_currency(Decimal("12.50")) == "$12.50 USD"
    assert format_currency(Decimal("0.00")) == "$0.00 USD"


# ---------------------------------------------------------------------------
# Invoice generation
# ---------------------------------------------------------------------------


def test_generate_invoice_structure():
    invoice = generate_invoice(
        customer_id="cust-1",
        mesh_usage=[
            {
                "mesh_id": "mesh-abc",
                "node_count": 2,
                "node_type": "standard",
                "plan": "pro",
                "region": "us-east-1",
                "hours": 10,
            }
        ],
    )
    d = invoice.to_dict()
    assert d["customer_id"] == "cust-1"
    assert d["invoice_id"].startswith("inv-")
    assert len(d["line_items"]) == 1
    assert Decimal(d["subtotal"]) > 0
    assert Decimal(d["tax"]) == Decimal("0")
    assert Decimal(d["total"]) == Decimal(d["subtotal"])


def test_generate_invoice_with_tax():
    invoice = generate_invoice(
        customer_id="cust-2",
        mesh_usage=[
            {
                "mesh_id": "m1",
                "node_count": 1,
                "node_type": "standard",
                "plan": "free",
                "region": "us-east-1",
                "hours": 100,
            }
        ],
        tax_rate=Decimal("0.10"),
    )
    d = invoice.to_dict()
    subtotal = Decimal(d["subtotal"])
    tax = Decimal(d["tax"])
    total = Decimal(d["total"])
    assert tax == (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    assert total == subtotal + tax


def test_generate_invoice_multiple_meshes():
    invoice = generate_invoice(
        customer_id="cust-3",
        mesh_usage=[
            {"mesh_id": "m1", "node_count": 1, "node_type": "standard",
             "plan": "free", "region": "us-east-1", "hours": 1},
            {"mesh_id": "m2", "node_count": 1, "node_type": "gpu",
             "plan": "free", "region": "us-east-1", "hours": 1},
        ],
    )
    d = invoice.to_dict()
    assert len(d["line_items"]) == 2
    assert Decimal(d["subtotal"]) > 0


def test_generate_invoice_ids_are_unique():
    i1 = generate_invoice("c", [{"mesh_id": "m", "node_count": 1,
                                  "node_type": "standard", "plan": "free",
                                  "region": "us-east-1", "hours": 1}])
    i2 = generate_invoice("c", [{"mesh_id": "m", "node_count": 1,
                                  "node_type": "standard", "plan": "free",
                                  "region": "us-east-1", "hours": 1}])
    assert i1.invoice_id != i2.invoice_id


# ---------------------------------------------------------------------------
# IdempotencyStore
# ---------------------------------------------------------------------------


def test_idempotency_store_pending_then_completed():
    store = IdempotencyStore()
    key = "op-123"

    store.set_pending(key)
    rec = store.get(key)
    assert rec is not None
    assert rec.status == "pending"

    store.set_completed(key, {"result": "ok"})
    rec = store.get(key)
    assert rec.status == "completed"
    assert rec.result == {"result": "ok"}


def test_idempotency_store_missing_key_returns_none():
    store = IdempotencyStore()
    assert store.get("nonexistent") is None


def test_idempotency_store_set_failed():
    store = IdempotencyStore()
    store.set_pending("k")
    store.set_failed("k", "boom")
    rec = store.get("k")
    assert rec.status == "failed"
    assert rec.result["error"] == "boom"


def test_idempotency_store_cleanup_expired():
    from datetime import timedelta

    store = IdempotencyStore(default_ttl=0)
    store.set_pending("old")
    # Force expiry by backdating created_at
    store._records["old"].created_at -= timedelta(seconds=1)
    removed = store.cleanup_expired()
    assert removed == 1
    assert store.get("old") is None


def test_idempotency_record_to_dict_shape():
    store = IdempotencyStore()
    store.set_pending("x")
    store.set_completed("x", {"v": 1})
    d = store.get("x").to_dict()
    assert "key" in d
    assert "status" in d
    assert "result" in d
    assert d["status"] == "completed"


# ---------------------------------------------------------------------------
# Billing endpoint routes (list_plans, estimate_cost, get_limits)
# ---------------------------------------------------------------------------

from src.api.maas.endpoints import billing as billing_mod
from src.api.maas.auth import UserContext
from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import event_trace_evidence_summary


def _make_billing_client(user: UserContext | None = None) -> TestClient:
    """Build a TestClient with the billing router and optional user override."""
    app = FastAPI()
    app.include_router(billing_mod.router, prefix="/api/v1/maas")
    if user:
        app.dependency_overrides[billing_mod.get_current_user] = lambda: user
    return TestClient(app)


class TestListPlansEndpoint:
    def test_returns_three_plans(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert len(plans) == 3

    def test_plan_names(self):
        client = _make_billing_client()
        plans = client.get("/api/v1/maas/billing/plans").json()
        names = {p["name"] for p in plans}
        assert names == {"free", "pro", "enterprise"}

    def test_each_plan_has_limits(self):
        client = _make_billing_client()
        for plan in client.get("/api/v1/maas/billing/plans").json():
            assert "limits" in plan
            assert "max_nodes" in plan["limits"]


class TestEstimateCostEndpoint:
    def test_returns_cost_fields(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/estimate?node_count=3&node_type=standard&plan=pro&region=us-east-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "hourly_cost" in data
        assert "monthly_cost" in data
        assert "monthly_cost_raw" in data

    def test_reflects_query_params(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/estimate?node_count=5&node_type=standard&plan=starter&region=global")
        data = resp.json()
        assert data["node_count"] == 5
        assert data["node_type"] == "standard"
        assert data["plan"] == "starter"

    def test_missing_node_count_returns_422(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/estimate?node_type=standard")
        assert resp.status_code == 422

    def test_zero_node_count_returns_422(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/estimate?node_count=0")
        assert resp.status_code == 422

    def test_monthly_cost_raw_is_numeric_string(self):
        client = _make_billing_client()
        resp = client.get("/api/v1/maas/billing/estimate?node_count=2&node_type=standard&plan=pro&region=us-east-1")
        raw = resp.json()["monthly_cost_raw"]
        float(raw)  # Should not raise


class TestGetLimitsEndpoint:
    def test_returns_limits_for_user_plan(self):
        user = UserContext(user_id="u-1", plan="pro")
        client = _make_billing_client(user)
        resp = client.get("/api/v1/maas/billing/limits")
        assert resp.status_code == 200
        limits = resp.json()
        assert "max_nodes" in limits

    def test_enterprise_limits_differ_from_starter(self):
        starter_client = _make_billing_client(UserContext(user_id="u-s", plan="starter"))
        enterprise_client = _make_billing_client(UserContext(user_id="u-e", plan="enterprise"))
        starter_limits = starter_client.get("/api/v1/maas/billing/limits").json()
        enterprise_limits = enterprise_client.get("/api/v1/maas/billing/limits").json()
        assert enterprise_limits["max_nodes"] > starter_limits["max_nodes"]

    def test_requires_auth(self):
        client = _make_billing_client()  # no user override
        resp = client.get("/api/v1/maas/billing/limits")
        # Without auth override the dependency raises 401 or similar
        assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# Billing endpoint EventBus evidence
# ---------------------------------------------------------------------------


class _BillingEvidenceRequest:
    def __init__(self, bus: EventBus, payload: dict | bytes | None = None):
        self.state = SimpleNamespace(event_bus=bus)
        self._payload = payload if payload is not None else {}

    async def body(self) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")

    async def json(self) -> dict:
        if isinstance(self._payload, bytes):
            return json.loads(self._payload.decode("utf-8"))
        return self._payload


class _FakeBillingEvidenceService:
    webhook_secret = "modular-billing-webhook-secret"

    def get_plan_limits(self, plan: str) -> dict:
        return {
            "max_nodes": 100 if plan == "enterprise" else 10,
            "api_rate_limit": 10000,
            "features": ["mesh", "billing"],
        }

    async def create_payment_session(self, user_id: str, plan: str) -> dict:
        assert user_id == "modular-payment-user-secret"
        assert plan == "pro"
        return {
            "payment_url": "https://checkout.stripe.test/session/raw-secret",
            "session_id": "cs_modular_payment_secret",
            "status": "created",
        }

    async def create_crypto_payment_session(self, user_id: str, plan: str) -> dict:
        return {
            "payment_url": "bitcoin:raw-secret-address",
            "session_id": "crypto_modular_payment_secret",
            "status": "awaiting_payment",
            "deposit_address": "raw-secret-address",
            "amount_usd": "29.00",
            "network": "bitcoin",
        }

    async def process_webhook(
        self,
        *,
        event_type: str,
        event_data: dict,
        event_id: str,
        include_idempotency_metadata: bool,
    ) -> dict:
        assert event_type == "invoice.paid"
        assert event_id == "evt_modular_webhook_secret"
        assert include_idempotency_metadata is True
        assert event_data["customer"] == "cus_payload_secret"
        return {
            "status": "processed",
            "action": "subscription_extended",
            "customer_id": "cus_result_secret",
            "user_id": "modular-webhook-user-secret",
            "_idempotent": False,
        }


class _FakeUsageEvidenceService:
    def get_usage_report(self, mesh_id: str) -> dict:
        assert mesh_id == "mesh-modular-billing-secret"
        return {
            "mesh_id": mesh_id,
            "requests": 7,
            "bandwidth_bytes": 2048,
            "storage_bytes": 4096,
            "report_time": "2026-05-30T00:00:00",
        }


def _event_payloads(bus: EventBus, source_agent: str) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


def test_create_payment_publishes_redacted_payment_intent_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "modular-payment-user-secret"
    raw_url = "https://checkout.stripe.test/session/raw-secret"
    raw_session_id = "cs_modular_payment_secret"
    bus = EventBus(str(tmp_path))
    request = _BillingEvidenceRequest(bus)

    monkeypatch.setattr(
        billing_mod,
        "get_billing_service",
        lambda: _FakeBillingEvidenceService(),
    )

    response = asyncio.run(
        billing_mod.create_payment(
            plan="pro",
            method="stripe",
            user=UserContext(user_id=user_id, plan="free"),
            request=request,
        )
    )

    assert response == {
        "payment_url": raw_url,
        "session_id": raw_session_id,
        "status": "created",
        "method": "stripe",
        "plan": "pro",
    }

    payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_PAYMENT_SOURCE_AGENT,
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "create_payment"
    assert payload["service_name"] == "maas-modular-billing-payment-intent"
    assert payload["layer"] == "api_modular_billing_payment_intent"
    assert payload["status"] == "success"
    assert payload["source_quality"] == "stripe_payment_session_intent_created"
    assert payload["actor_user_id_hash"]
    assert payload["raw_payment_url_redacted"] is True
    assert payload["raw_session_id_redacted"] is True

    settlement = payload["settlement_evidence"]
    assert settlement["settlement_action"] == "payment_session_intent_only"
    assert settlement["dataplane_confirmed"] is False
    assert settlement["live_provider_settlement_confirmed"] is False
    assert settlement["bank_settlement_confirmed"] is False
    assert settlement["chain_finality_confirmed"] is False
    assert settlement["db_write_evidence"]["committed"] is False
    assert settlement["output_summary"]["payment_url_present"] is True
    assert settlement["output_summary"]["session_id_present"] is True

    trace_summary = event_trace_evidence_summary(payload)
    assert trace_summary["settlement_evidence"]["present"] is True
    assert trace_summary["settlement_evidence"]["provider"] == "stripe"
    assert trace_summary["settlement_evidence"]["settlement_action"] == (
        "payment_session_intent_only"
    )
    assert trace_summary["settlement_evidence"]["live_provider_settlement_confirmed"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, raw_url, raw_session_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_billing_catalog_routes_publish_read_only_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "modular-plan-user-secret"
    bus = EventBus(str(tmp_path))
    request = _BillingEvidenceRequest(bus)

    monkeypatch.setattr(
        billing_mod,
        "get_billing_service",
        lambda: _FakeBillingEvidenceService(),
    )

    estimate = asyncio.run(
        billing_mod.estimate_cost(
            node_count=3,
            node_type="standard",
            plan="pro",
            region="us-east-1",
            request=request,
        )
    )
    plans = asyncio.run(billing_mod.list_plans(request=request))
    limits = asyncio.run(
        billing_mod.get_limits(
            user=UserContext(user_id=user_id, plan="enterprise"),
            request=request,
        )
    )

    assert estimate["monthly_cost_raw"]
    assert len(plans) == 3
    assert limits["max_nodes"] == 100

    estimate_payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_ESTIMATE_SOURCE_AGENT,
    )
    plan_payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_PLAN_SOURCE_AGENT,
    )
    assert len(estimate_payloads) == 1
    assert len(plan_payloads) == 2

    estimate_payload = estimate_payloads[0]
    assert estimate_payload["operation"] == "estimate_cost"
    assert estimate_payload["read_only"] is True
    assert estimate_payload["control_action"] is False
    assert estimate_payload["source_quality"] == "local_billing_estimate_calculated"
    assert estimate_payload["node_count"] == 3
    assert estimate_payload["node_type"] == "standard"
    assert estimate_payload["region"] == "us-east-1"
    assert estimate_payload["settlement_evidence"]["settlement_action"] == (
        "read_only_observed_state_no_settlement"
    )
    assert estimate_payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert estimate_payload["settlement_evidence"][
        "live_provider_settlement_confirmed"
    ] is False

    list_payload = next(
        payload for payload in plan_payloads if payload["operation"] == "list_plans"
    )
    limits_payload = next(
        payload for payload in plan_payloads if payload["operation"] == "get_limits"
    )
    assert list_payload["source_quality"] == "local_plan_catalog_observed_state"
    assert list_payload["result_summary"]["plans_count"] == 3
    assert list_payload["settlement_evidence"]["settlement_action"] == (
        "read_only_observed_state_no_settlement"
    )
    assert limits_payload["source_quality"] == "local_plan_limits_observed_state"
    assert limits_payload["actor_user_id_hash"]
    assert limits_payload["result_summary"]["max_nodes_present"] is True

    trace_summary = event_trace_evidence_summary(limits_payload)
    assert trace_summary["settlement_evidence"]["present"] is True
    assert trace_summary["settlement_evidence"]["settlement_action"] == (
        "read_only_observed_state_no_settlement"
    )

    serialized = json.dumps([*estimate_payloads, *plan_payloads], sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert user_id not in serialized
    assert user_id not in raw_log


def test_billing_usage_and_invoice_publish_redacted_mesh_evidence(
    monkeypatch,
    tmp_path,
):
    from src.api.maas import auth as maas_auth
    from src.api.maas import registry as maas_registry

    user_id = "modular-usage-invoice-user-secret"
    mesh_id = "mesh-modular-billing-secret"
    bus = EventBus(str(tmp_path))
    request = _BillingEvidenceRequest(bus)
    user = UserContext(user_id=user_id, plan="pro")

    async def _require_mesh_access(checked_mesh_id: str, checked_user: UserContext):
        assert checked_mesh_id == mesh_id
        assert checked_user.user_id == user_id
        return checked_user

    monkeypatch.setattr(maas_auth, "require_mesh_access", _require_mesh_access)
    monkeypatch.setattr(
        billing_mod,
        "get_usage_service",
        lambda: _FakeUsageEvidenceService(),
    )
    monkeypatch.setattr(
        maas_registry,
        "get_mesh",
        lambda checked_mesh_id: SimpleNamespace(
            node_instances={"n-raw-secret-1": {}, "n-raw-secret-2": {}},
            plan="pro",
            region="eu-west-1",
        ) if checked_mesh_id == mesh_id else None,
    )

    usage = asyncio.run(
        billing_mod.get_usage_report(mesh_id=mesh_id, user=user, request=request)
    )
    invoice = asyncio.run(
        billing_mod.create_invoice(
            mesh_id=mesh_id,
            user=user,
            hours=2.5,
            request=request,
        )
    )

    assert usage["mesh_id"] == mesh_id
    assert invoice["customer_id"] == user_id
    assert invoice["invoice_id"].startswith("inv-")

    usage_payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_USAGE_SOURCE_AGENT,
    )
    invoice_payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_INVOICE_SOURCE_AGENT,
    )
    assert len(usage_payloads) == 1
    assert len(invoice_payloads) == 1

    usage_payload = usage_payloads[0]
    assert usage_payload["operation"] == "get_usage_report"
    assert usage_payload["read_only"] is True
    assert usage_payload["control_action"] is False
    assert usage_payload["mesh_id_hash"]
    assert usage_payload["source_quality"] == "local_usage_report_observed_state"
    assert usage_payload["settlement_evidence"]["settlement_action"] == (
        "read_only_observed_state_no_settlement"
    )
    assert usage_payload["result_summary"]["requests_bucket"] == "low"

    invoice_payload = invoice_payloads[0]
    assert invoice_payload["operation"] == "create_invoice"
    assert invoice_payload["source_quality"] == "local_invoice_object_generated"
    assert invoice_payload["node_count"] == 2
    assert invoice_payload["hours"] == 2.5
    assert invoice_payload["settlement_evidence"]["settlement_action"] == (
        "invoice_generation_local_only"
    )
    assert invoice_payload["settlement_evidence"]["db_write_evidence"] == {
        "storage_backend": "local_invoice_object_not_persisted",
        "attempted": False,
        "committed": False,
        "payloads_redacted": True,
    }
    assert invoice_payload["result_summary"]["invoice_id_present"] is True
    assert invoice_payload["result_summary"]["line_items_count"] == 1

    trace_summary = event_trace_evidence_summary(invoice_payload)
    assert trace_summary["settlement_evidence"]["present"] is True
    assert trace_summary["settlement_evidence"]["settlement_action"] == (
        "invoice_generation_local_only"
    )
    assert trace_summary["settlement_evidence"][
        "live_provider_settlement_confirmed"
    ] is False

    serialized = json.dumps([*usage_payloads, *invoice_payloads], sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user_id,
        mesh_id,
        invoice["invoice_id"],
        "n-raw-secret-1",
        "n-raw-secret-2",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_billing_webhook_publishes_redacted_local_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    payload_body = {
        "type": "invoice.paid",
        "data": {
            "customer": "cus_payload_secret",
            "subscription": "sub_payload_secret",
        },
    }
    body = json.dumps(payload_body).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = compute_hmac_signature(
        f"{timestamp}.{body.decode('utf-8')}",
        _FakeBillingEvidenceService.webhook_secret,
    )
    bus = EventBus(str(tmp_path))
    request = _BillingEvidenceRequest(bus, body)

    monkeypatch.setattr(
        billing_mod,
        "get_billing_service",
        lambda: _FakeBillingEvidenceService(),
    )

    response = asyncio.run(
        billing_mod.billing_webhook(
            request,
            x_signature=signature,
            x_timestamp=timestamp,
            x_event_id="evt_modular_webhook_secret",
        )
    )

    assert response == {
        "status": "processed",
        "action": "subscription_extended",
        "customer_id": "cus_result_secret",
        "user_id": "modular-webhook-user-secret",
        "_idempotent": False,
    }

    payloads = _event_payloads(
        bus,
        billing_mod._MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "billing_webhook"
    assert payload["service_name"] == "maas-modular-billing-webhook"
    assert payload["layer"] == "api_modular_billing_webhook_lifecycle"
    assert payload["status"] == "success"
    assert payload["signature_verified"] is True
    assert payload["event_type_bucket"] == "invoice.paid"
    assert len(payload["event_id_hash"]) == 16
    assert payload["source_quality"] == "verified_billing_webhook_local_lifecycle"
    assert payload["raw_event_payload_redacted"] is True

    settlement = payload["settlement_evidence"]
    assert settlement["settlement_action"] == "webhook_local_lifecycle_only"
    assert settlement["dataplane_confirmed"] is False
    assert settlement["live_provider_settlement_confirmed"] is False
    assert settlement["bank_settlement_confirmed"] is False
    assert settlement["chain_finality_confirmed"] is False
    assert settlement["db_write_evidence"]["attempted"] is True
    assert settlement["db_write_evidence"]["committed"] is True
    assert settlement["output_summary"]["signature_verified"] is True
    assert settlement["output_summary"]["event_type_bucket"] == "invoice.paid"
    assert settlement["output_summary"]["webhook_action"] == "subscription_extended"

    trace_summary = event_trace_evidence_summary(payload)
    assert trace_summary["settlement_evidence"]["present"] is True
    assert trace_summary["settlement_evidence"]["provider"] == "provider_webhook"
    assert trace_summary["settlement_evidence"]["settlement_action"] == (
        "webhook_local_lifecycle_only"
    )

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        "evt_modular_webhook_secret",
        "cus_payload_secret",
        "sub_payload_secret",
        "cus_result_secret",
        "modular-webhook-user-secret",
        signature,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
