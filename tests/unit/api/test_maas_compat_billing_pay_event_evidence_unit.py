"""Unit tests for MaaS compatibility billing/pay EventBus evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import src.api.maas_compat as compat_mod
from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import event_trace_evidence_summary


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-compat-billing-pay",
            limit=10,
        )
    ]


def test_compat_billing_pay_crypto_rejection_publishes_redacted_evidence(tmp_path):
    user_id = "compat-billing-pay-user-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.billing_pay_alias(
                request,
                plan="pro",
                method="crypto",
                current_user=SimpleNamespace(id=user_id, role="admin"),
                db=SimpleNamespace(),
            )
        )

    assert exc.value.status_code == 501
    assert exc.value.headers[
        "X-X0TTA6BL4-Claim-Gate-Schema"
    ] == "x0tta6bl4.maas_compat_billing_pay_claim_boundary_headers.v1"
    assert (
        exc.value.headers["X-X0TTA6BL4-Claim-Surface"]
        == "maas_compat.billing_pay"
    )
    assert (
        exc.value.headers[
            "X-X0TTA6BL4-Local-Crypto-Disabled-Rejection-Claim-Allowed"
        ]
        == "true"
    )
    assert (
        exc.value.headers["X-X0TTA6BL4-Provider-Settlement-Claim-Allowed"]
        == "false"
    )
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_billing_pay"
    assert payload["service_name"] == "maas-compat-billing-pay"
    assert payload["source_alias"] == "maas-compat-billing-pay"
    assert payload["layer"] == "api_compat_billing_pay_intent"
    assert payload["stage"] == "crypto_not_enabled"
    assert payload["status"] == "denied"
    assert payload["request_summary"] == {"plan": "pro", "method": "crypto"}
    assert payload["provider"] == "crypto"
    assert payload["delegated_to_billing"] is False
    assert payload["checkout_url_present"] is False
    assert payload["http_status_code"] == 501
    assert payload["duration_ms"] >= 0
    assert payload["read_only"] is True
    assert payload["control_action"] is True
    assert payload["economy_action"] is True
    assert payload["source_quality"] == "crypto_backend_disabled_local_rejection"
    assert payload["upstream_evidence"] == {}
    assert payload["settlement_evidence"]["settlement_action"] == (
        "compat_payment_intent_only"
    )
    assert payload["settlement_evidence"]["source_quality"] == (
        "crypto_backend_disabled_local_rejection"
    )
    assert payload["settlement_evidence"]["provider"] == "crypto"
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
    assert payload["settlement_evidence"]["db_write_evidence"]["committed"] is False
    assert payload["raw_identifiers_redacted"] is True
    assert payload["reason"] == "crypto_billing_not_enabled"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert user_id not in serialized
    assert user_id not in raw_log
    assert "Use method=stripe" not in serialized
    assert "Use method=stripe" not in raw_log


def test_compat_billing_pay_stripe_success_publishes_alias_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "compat-billing-pay-stripe-user-secret"
    checkout_url = "https://checkout.stripe.test/session/secret"
    stripe_session_id = "cs_compat_billing_pay_secret"
    stripe_customer_id = "cus_compat_billing_pay_secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()

    async def _checkout(*, plan, request, current_user, db):
        request.state.event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            "maas-billing-subscription-checkout",
            {
                "component": "api.maas_billing",
                "stage": "subscription_checkout_created",
                "raw_identifiers_redacted": True,
            },
            priority=6,
        )
        return {
            "url": checkout_url,
            "id": stripe_session_id,
            "customer": stripe_customer_id,
        }

    monkeypatch.setattr(compat_mod, "create_subscription_session", _checkout)

    result = asyncio.run(
        compat_mod.billing_pay_alias(
            request,
            http_response=http_response,
            plan="enterprise",
            method="stripe",
            current_user=SimpleNamespace(id=user_id, role="admin"),
            db=SimpleNamespace(),
        )
    )

    assert result["payment_url"] == checkout_url
    assert result["status"] == "created"
    assert result["method"] == "stripe"
    assert result["plan"] == "enterprise"
    claim_gate = result["compat_billing_pay_claim_gate"]
    assert claim_gate["surface"] == "maas_compat.billing_pay"
    assert claim_gate["delegated_subscription_checkout_intent_claim_allowed"] is True
    assert claim_gate["provider_settlement_claim_allowed"] is False
    assert claim_gate["bank_settlement_claim_allowed"] is False
    assert claim_gate["subscription_activation_claim_allowed"] is False
    assert claim_gate["customer_access_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["traffic_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["production_slo_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    cross_plane_claim_gate = result["cross_plane_claim_gate"]
    assert cross_plane_claim_gate["surface"] == "maas_compat.billing_pay"
    assert cross_plane_claim_gate["allowed"] is False
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_billing_pay_claim_boundary_headers.v1"
    )
    assert (
        http_response.headers[
            "X-X0TTA6BL4-Delegated-Subscription-Checkout-Intent-Claim-Allowed"
        ]
        == "true"
    )
    assert (
        http_response.headers["X-X0TTA6BL4-Provider-Settlement-Claim-Allowed"]
        == "false"
    )
    assert (
        http_response.headers["X-X0TTA6BL4-Customer-Traffic-Claim-Allowed"]
        == "false"
    )
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "subscription_checkout_delegated"
    assert payload["status"] == "success"
    assert payload["request_summary"] == {
        "plan": "enterprise",
        "method": "stripe",
    }
    assert payload["provider"] == "stripe"
    assert payload["delegated_to_billing"] is True
    assert payload["checkout_url_present"] is True
    assert payload["http_status_code"] == 200
    assert payload["read_only"] is False
    assert payload["result_summary"] == {
        "payload_type": "dict",
        "payload_field_count": 6,
        "checkout_url_present": True,
        "status_present": True,
        "provider_present": False,
        "compat_billing_pay_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
        "claim_surface": "maas_compat.billing_pay",
    }
    assert payload["source_quality"] == "delegated_subscription_checkout_intent_created"
    assert payload["upstream_evidence"]["events_total"] == 1
    assert payload["upstream_evidence"]["source_agents"] == [
        "maas-billing-subscription-checkout"
    ]
    assert payload["upstream_evidence"]["payloads_redacted"] is True
    assert payload["settlement_evidence"]["settlement_action"] == (
        "compat_payment_intent_only"
    )
    assert payload["settlement_evidence"]["source_quality"] == (
        "delegated_subscription_checkout_intent_created"
    )
    assert payload["settlement_evidence"]["provider"] == "stripe"
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
    assert payload["settlement_evidence"]["telemetry_evidence"]["events_total"] == 1
    assert payload["settlement_evidence"]["output_summary"]["checkout_url_present"] is True

    trace_summary = event_trace_evidence_summary(payload)
    settlement_summary = trace_summary["settlement_evidence"]
    assert settlement_summary["present"] is True
    assert settlement_summary["source_quality"] == (
        "delegated_subscription_checkout_intent_created"
    )
    assert settlement_summary["settlement_action"] == "compat_payment_intent_only"
    assert settlement_summary["provider"] == "stripe"
    assert settlement_summary["dataplane_confirmed"] is False
    assert settlement_summary["live_provider_settlement_confirmed"] is False
    assert settlement_summary["bank_settlement_confirmed"] is False
    assert settlement_summary["chain_finality_confirmed"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, checkout_url, stripe_session_id, stripe_customer_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_billing_pay_stripe_http_failure_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "compat-billing-pay-http-failure-user-secret"
    private_detail = "private checkout failure detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    async def _checkout(*, plan, request, current_user, db):
        raise HTTPException(status_code=402, detail=private_detail)

    monkeypatch.setattr(compat_mod, "create_subscription_session", _checkout)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.billing_pay_alias(
                request,
                plan="starter",
                method="stripe",
                current_user=SimpleNamespace(id=user_id, role="user"),
                db=SimpleNamespace(),
            )
        )

    assert exc.value.status_code == 402
    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "subscription_checkout_failed"
    assert payload["status"] == "failed"
    assert payload["request_summary"] == {"plan": "starter", "method": "stripe"}
    assert payload["provider"] == "stripe"
    assert payload["delegated_to_billing"] is True
    assert payload["checkout_url_present"] is False
    assert payload["http_status_code"] == 402
    assert payload["read_only"] is False
    assert payload["source_quality"] == "delegated_subscription_checkout_failed"
    assert payload["settlement_evidence"]["settlement_action"] == (
        "compat_payment_intent_only"
    )
    assert payload["settlement_evidence"]["provider"] == "stripe"
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
    assert payload["reason"] == "http_402"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log
