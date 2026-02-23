"""Unit tests for src/api/maas/constants.py."""

from src.api.maas.constants import (
    BILLING_WEBHOOK_EVENTS,
    PLAN_ALIASES,
    PLAN_REQUEST_LIMITS,
    PQC_DEFAULT_PROFILE,
    PQC_SEGMENT_PROFILES,
    get_pqc_profile,
)


def test_get_pqc_profile_known_device_class():
    profile = get_pqc_profile("sensor")
    assert profile["kem"] == "ML-KEM-512"
    assert profile["sig"] == "ML-DSA-44"
    assert profile["security_level"] == 1


def test_get_pqc_profile_unknown_device_class_returns_default():
    assert get_pqc_profile("unknown-device") == PQC_DEFAULT_PROFILE


def test_pqc_profiles_have_required_fields():
    required = {"kem", "sig", "security_level", "rationale"}
    for profile in PQC_SEGMENT_PROFILES.values():
        assert required.issubset(profile.keys())
        assert profile["security_level"] in {1, 3, 5}


def test_plan_aliases_map_to_known_limits():
    for alias, normalized in PLAN_ALIASES.items():
        assert normalized in PLAN_REQUEST_LIMITS, f"alias '{alias}' -> unknown plan '{normalized}'"


def test_billing_webhook_events_include_canonical_and_legacy():
    assert "invoice.paid" in BILLING_WEBHOOK_EVENTS
    assert "customer.subscription.updated" in BILLING_WEBHOOK_EVENTS
    assert "subscription.updated" in BILLING_WEBHOOK_EVENTS
    assert "plan.upgraded" in BILLING_WEBHOOK_EVENTS

