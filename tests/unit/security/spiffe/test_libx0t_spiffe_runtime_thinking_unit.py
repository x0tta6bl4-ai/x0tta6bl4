import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.libx0t.security.spiffe.agent.manager import (
    AttestationStrategy,
    SPIREAgentManager,
    WorkloadEntry,
)
from src.libx0t.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.libx0t.security.spiffe.workload.api_client import WorkloadAPIClient


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


def test_libx0t_spire_agent_thinking_status_redacts_tokens_and_workload_ids(
    tmp_path,
):
    with patch(
        "src.libx0t.security.spiffe.agent.manager.SPIREAgentManager._find_spire_binary",
        side_effect=lambda binary: f"/usr/bin/{binary}",
    ):
        manager = SPIREAgentManager(
            config_path=tmp_path / "secret-agent.conf",
            socket_path=tmp_path / "secret-agent.sock",
        )

    assert manager.attest_node(
        AttestationStrategy.JOIN_TOKEN,
        token="secret-join-token",
    )

    entry = WorkloadEntry(
        spiffe_id="spiffe://secret.trust/workload/secret-api",
        parent_id="spiffe://secret.trust/node/secret-parent",
        selectors={"unix:uid": "secret-selector-value"},
        ttl=60,
    )
    with patch(
        "src.libx0t.security.spiffe.agent.manager.subprocess.run",
        return_value=SimpleNamespace(stdout="created", returncode=0),
    ):
        assert manager.register_workload(entry)

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        status,
        "secret-join-token",
        "spiffe://secret.trust/workload/secret-api",
        "spiffe://secret.trust/node/secret-parent",
        "secret-selector-value",
        "secret-agent.conf",
        "secret-agent.sock",
    )


def test_libx0t_workload_api_mock_status_never_claims_real_spire(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
    monkeypatch.delenv("X0TTA6BL4_PRODUCTION", raising=False)

    client = WorkloadAPIClient()
    status = client.evidence_status()

    assert status["mock_mode"] is True
    assert status["real_socket_verified"] is False
    assert status["real_spire_evidence"] is False
    assert "not real SPIRE evidence" in status["claim_boundary"]


def test_libx0t_spiffe_controller_thinking_status_redacts_identity_context():
    identity = SimpleNamespace(
        spiffe_id="spiffe://secret.trust/workload/controller",
        cert_chain=[b"secret-cert"],
        private_key=b"secret-private-key",
        expiry=datetime.utcnow() + timedelta(hours=1),
        ttl=3600,
        is_expired=lambda: False,
    )
    mock_agent = MagicMock()
    mock_agent.health_check.return_value = True
    mock_agent.register_workload.return_value = True
    mock_workload_api = MagicMock()
    mock_workload_api._force_mock_spiffe = False
    mock_workload_api._real_socket_verified = True
    mock_workload_api._spiffe_endpoint = "unix:///tmp/secret-agent.sock"
    mock_workload_api.fetch_x509_svid.return_value = identity
    mock_workload_api.validate_peer_svid.return_value = True
    mock_server_client = MagicMock()
    mock_server_client.create_entry.return_value = "secret-entry-id"
    mock_server_client.list_entries.return_value = [SimpleNamespace()]
    mock_server_client.get_server_status.return_value = {"secret_status": True}
    mock_validator = MagicMock()
    mock_validator.validate_certificate.return_value = (True, "secret-peer", "")

    with (
        patch(
            "src.libx0t.security.spiffe.controller.spiffe_controller.SPIREAgentManager",
            return_value=mock_agent,
        ),
        patch(
            "src.libx0t.security.spiffe.controller.spiffe_controller.WorkloadAPIClient",
            return_value=mock_workload_api,
        ),
        patch(
            "src.libx0t.security.spiffe.controller.spiffe_controller.SPIREServerClient",
            return_value=mock_server_client,
        ),
        patch(
            "src.libx0t.security.spiffe.controller.spiffe_controller.CertificateValidator",
            return_value=mock_validator,
        ),
    ):
        controller = SPIFFEController(
            trust_domain="secret.trust",
            server_address="secret-spire-server:8081",
            enable_optimizations=False,
        )

    controller.current_identity = identity
    assert controller.register_workload(
        "spiffe://secret.trust/workload/secret-api",
        {"unix:uid": "secret-selector-value"},
        ttl=60,
    )
    health = controller.health_check()
    assert health["workload_api_real"] is True

    status = controller.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        status,
        "secret.trust",
        "secret-spire-server:8081",
        "spiffe://secret.trust/workload/controller",
        "spiffe://secret.trust/workload/secret-api",
        "secret-selector-value",
        "secret-cert",
        "secret-private-key",
        "secret-agent.sock",
    )
