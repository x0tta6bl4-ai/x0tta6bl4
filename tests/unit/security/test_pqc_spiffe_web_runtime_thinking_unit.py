import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import src.security.pqc_ca as pqc_ca_mod
from src.security.pqc_mtls import PQCmTLSController
from src.security.spiffe.mtls.mtls_controller_production import (
    MTLSControllerProduction,
)
from src.security.spiffe.production_integration import (
    MTLSContextManager,
    ProductionSPIREIntegration,
    SPIREConfig,
)
from src.security.web_security_hardening import (
    MD5ToModernMigration,
    PasswordHasher,
    SessionTokenManager,
    WebSecurityHeaders,
)


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


class _FakeSecurity:
    def __init__(self, node_id):
        self.node_id = node_id
        self.pq_backend = SimpleNamespace(sig_algorithm="ML-DSA-65")

    def get_public_keys(self):
        return {"sig_public_key": "secret-public-key-hex"}


class _FakeNodeIdentity:
    def __init__(self, node_id):
        self.node_id = node_id
        self.did = f"did:mesh:pqc:{node_id}:secret-did-fragment"
        self.security = _FakeSecurity(node_id)
        self.rotated = False

    def sign_manifest(self, manifest):
        return {"proof": {"signatureValue": "secret-signature-value"}}

    def verify_remote_node(self, signed_manifest, issuer_public_key_hex):
        return issuer_public_key_hex == "secret-issuer-public-key"

    def rotate_keys(self):
        self.rotated = True


def test_pqc_ca_and_identity_manager_thinking_status_redacts_identity_material(
    monkeypatch,
):
    monkeypatch.setattr(pqc_ca_mod, "PQCNodeIdentity", _FakeNodeIdentity)

    ca = pqc_ca_mod.PQCCertificateAuthority("secret-ca-node")
    svid = ca.issue_pqc_svid(
        "spiffe://x0tta6bl4.mesh/node/secret-worker",
        "secret-node-public-key",
        ttl_days=7,
    )
    assert ca.verify_pqc_svid(svid, "secret-issuer-public-key") is True
    ca_status = ca.get_thinking_status()
    _assert_redacted(
        ca_status,
        "secret-ca-node",
        "spiffe://x0tta6bl4.mesh/node/secret-worker",
        "secret-worker",
        "secret-node-public-key",
        "secret-signature-value",
        "secret-issuer-public-key",
        "secret-did-fragment",
    )

    manager = pqc_ca_mod.PQCIdentityManager("secret-node-id")
    manager.rotate_identity(ca)
    manager_status = manager.get_thinking_status()
    _assert_redacted(
        manager_status,
        "secret-node-id",
        "secret-public-key-hex",
        "secret-signature-value",
        "secret-did-fragment",
    )


class _DummyKEM:
    def generate_keypair(self, key_id, validity_days):
        return SimpleNamespace(
            key_id=f"secret-{key_id}",
            secret_key=b"secret-kem-private",
            public_key=b"secret-kem-public",
            expires_at=datetime.utcnow() + timedelta(days=validity_days),
        )


class _DummyDSA:
    def generate_keypair(self, key_id, validity_days):
        return SimpleNamespace(
            key_id=f"secret-{key_id}",
            secret_key=b"secret-dsa-private",
            public_key=b"secret-dsa-public",
            expires_at=datetime.utcnow() + timedelta(days=validity_days),
        )

    def sign(self, data, secret_key, key_id):
        return SimpleNamespace(
            algorithm="ML-DSA-65",
            signature_bytes=b"secret-signature-bytes",
            signer_key_id=key_id,
        )

    def verify(self, data, signature_bytes, public_key):
        return signature_bytes == b"secret-signature-bytes"


class _DummyHybrid:
    enable_pqc = True
    kem = _DummyKEM()
    dsa = _DummyDSA()

    def setup_secure_channel(self):
        return {"shared_secret_len": 32}


def test_pqc_mtls_thinking_status_redacts_payload_keys_and_common_name(monkeypatch):
    import src.security.pqc_mtls as shim

    shim._pqc_mtls_controller = None
    monkeypatch.setattr(shim, "get_pqc_hybrid", lambda: _DummyHybrid())
    controller = PQCmTLSController(enable_hybrid=True)

    controller.initialize_pqc_keys(validity_days=30)
    controller.sign_request(b"secret-request-payload")
    controller.verify_response(b"secret-response-payload", b"secret-signature-bytes")
    controller.create_pqc_certificate("secret-common-name.local", validity_days=30)

    status = controller.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        status,
        "secret-request-payload",
        "secret-response-payload",
        "secret-signature-bytes",
        "secret-common-name.local",
        "secret-mtls_kem",
        "secret-mtls_dsa",
        "secret-dsa-private",
        "secret-dsa-public",
    )


def test_web_security_thinking_status_redacts_passwords_tokens_and_user_ids():
    with patch("src.security.web_security_hardening.secrets") as mock_secrets:
        mock_secrets.token_urlsafe.return_value = "secret-session-token-value"
        token = SessionTokenManager.generate_session_token()
        assert token == "secret-session-token-value"

    with patch("src.security.web_security_hardening.bcrypt") as mock_bcrypt:
        mock_bcrypt.gensalt.return_value = b"secret-salt"
        mock_bcrypt.hashpw.return_value = b"secret-bcrypt-hash"
        assert PasswordHasher.hash_password("SecretStrongPass924!") == (
            "secret-bcrypt-hash"
        )

    with patch(
        "src.security.web_security_hardening.PasswordHasher.hash_password",
        return_value="secret-new-modern-hash",
    ):
        success, new_hash = MD5ToModernMigration.migrate_user_password(
            "secret-user-id",
            "d41d8cd98f00b204e9800998ecf8427e",
            "SecretStrongPass924!",
        )
        assert success is True
        assert new_hash == "secret-new-modern-hash"

    WebSecurityHeaders.get_security_headers()
    status = SessionTokenManager.get_thinking_status()
    _assert_redacted(
        status,
        "secret-session-token-value",
        "SecretStrongPass924!",
        "secret-bcrypt-hash",
        "secret-user-id",
        "d41d8cd98f00b204e9800998ecf8427e",
        "secret-new-modern-hash",
    )


def test_mtls_controller_and_spire_integration_thinking_status_redacts_context(tmp_path):
    class _Workload:
        async def fetch_x509_svid(self):
            return SimpleNamespace(
                cert_pem=b"secret-cert-pem",
                private_key_pem=b"secret-private-key-pem",
                cert_chain=[b"secret-ca-pem"],
            )

    controller = MTLSControllerProduction(_Workload(), enable_optimizations=False)
    cert_path = controller._write_temp_cert(b"secret-cert-pem")
    key_path = controller._write_temp_key(b"secret-private-key-pem")
    ca_path = controller._write_temp_ca(b"secret-ca-pem")
    status = controller.get_thinking_status()
    _assert_redacted(
        status,
        "secret-cert-pem",
        "secret-private-key-pem",
        "secret-ca-pem",
        cert_path,
        key_path,
        ca_path,
    )
    for path in (cert_path, key_path, ca_path):
        if os.path.exists(path):
            os.unlink(path)

    config = SPIREConfig(
        server_address="secret-spire-server:8081",
        agent_address="secret-spire-agent:8082",
        workload_socket=str(tmp_path / "secret-workload.sock"),
        trust_domain="secret.trust.domain",
        node_name="secret-node-name",
        workload_namespace="secret-namespace",
    )
    manager = MTLSContextManager(config, _Workload())
    manager_status = manager.get_thinking_status()
    _assert_redacted(
        manager_status,
        "secret.trust.domain",
        "secret-workload.sock",
        "secret-node-name",
        "secret-namespace",
    )

    integration = ProductionSPIREIntegration(config)
    integration.get_status()
    integration_status = integration.get_thinking_status()
    _assert_redacted(
        integration_status,
        "secret-spire-server:8081",
        "secret-spire-agent:8082",
        "secret.trust.domain",
        "secret-workload.sock",
        "secret-node-name",
        "secret-namespace",
    )
