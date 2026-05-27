"""Unit tests for service event identity resolution."""

from src.services.service_event_identity import (
    service_event_identity,
    service_event_identity_status,
)


def test_service_event_identity_uses_service_specific_env(monkeypatch):
    monkeypatch.setenv("MAAS_SETTLEMENT_SPIFFE_ID", " spiffe://mesh.x0tta6bl4.mesh/workload/settlement ")
    monkeypatch.setenv("MAAS_SETTLEMENT_DID", " did:mesh:pqc:settlement ")
    monkeypatch.setenv("MAAS_SETTLEMENT_WALLET_ADDRESS", " 0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb ")
    monkeypatch.setenv("SERVICE_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/generic")
    monkeypatch.setenv("SERVICE_DID", "did:mesh:pqc:generic")
    monkeypatch.setenv("SERVICE_WALLET_ADDRESS", "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    assert service_event_identity(service_name="maas-settlement") == {
        "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/settlement",
        "did": "did:mesh:pqc:settlement",
        "wallet_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    }


def test_service_event_identity_falls_back_to_generic_env(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_SERVICE_SPIFFE_ID", "spiffe://mesh.x0tta6bl4.mesh/workload/service")
    monkeypatch.setenv("X0TTA6BL4_SERVICE_DID", "did:mesh:pqc:service")
    monkeypatch.setenv("X0TTA6BL4_SERVICE_WALLET_ADDRESS", "0xcccccccccccccccccccccccccccccccccccccccc")

    assert service_event_identity(service_name="maas-janitor") == {
        "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/service",
        "did": "did:mesh:pqc:service",
        "wallet_address": "0xcccccccccccccccccccccccccccccccccccccccc",
    }


def test_service_event_identity_returns_none_for_missing_values(monkeypatch):
    for name in (
        "MAAS_JANITOR_SPIFFE_ID",
        "MAAS_JANITOR_DID",
        "MAAS_JANITOR_WALLET_ADDRESS",
        "X0TTA6BL4_SERVICE_SPIFFE_ID",
        "X0TTA6BL4_SERVICE_DID",
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "SERVICE_SPIFFE_ID",
        "SERVICE_DID",
        "SERVICE_WALLET_ADDRESS",
        "SPIFFE_ID",
        "DID",
        "GHOST_WALLET_ADDRESS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert service_event_identity(service_name="maas-janitor") == {
        "spiffe_id": None,
        "did": None,
        "wallet_address": None,
    }


def test_service_event_identity_status_is_redacted_and_reports_source(monkeypatch):
    monkeypatch.setenv(
        "MAAS_SETTLEMENT_SPIFFE_ID",
        "spiffe://mesh.x0tta6bl4.mesh/workload/settlement-secret",
    )
    monkeypatch.setenv("X0TTA6BL4_SERVICE_DID", "did:mesh:pqc:generic-secret")
    monkeypatch.setenv(
        "SERVICE_WALLET_ADDRESS",
        "0xdddddddddddddddddddddddddddddddddddddddd",
    )

    status = service_event_identity_status(service_name="maas-settlement")

    assert status["redacted"] is True
    assert status["configured_fields"] == 3
    assert status["complete"] is True
    assert status["fields"]["spiffe_id"] == {
        "configured": True,
        "source": "service_specific",
        "env_var": "MAAS_SETTLEMENT_SPIFFE_ID",
    }
    assert status["fields"]["did"] == {
        "configured": True,
        "source": "x0tta6bl4_generic",
        "env_var": "X0TTA6BL4_SERVICE_DID",
    }
    assert status["fields"]["wallet_address"] == {
        "configured": True,
        "source": "generic",
        "env_var": "SERVICE_WALLET_ADDRESS",
    }

    serialized = repr(status)
    assert "settlement-secret" not in serialized
    assert "generic-secret" not in serialized
    assert "0xdddd" not in serialized
