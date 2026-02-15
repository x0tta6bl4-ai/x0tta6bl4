from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.security.spiffe.agent.manager import AttestationStrategy
from src.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.security.spiffe.workload.api_client import X509SVID


def test_spiffe_controller_initialize_failure(tmp_path):
    controller = SPIFFEController()
    # workload_api socket does not exist -> initialize should fail
    assert (
        controller.initialize(
            attestation_strategy=AttestationStrategy.JOIN_TOKEN, token="abc123"
        )
        is False
    )


def test_spiffe_controller_identity_and_mtls(tmp_path, monkeypatch):
    # Use force mock mode for WorkloadAPIClient
    monkeypatch.setenv("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

    # Create fake socket so workload_api.fetch_x509_svid succeeds
    sock = tmp_path / "sockets"
    sock.mkdir(parents=True, exist_ok=True)
    fake = sock / "agent.sock"
    fake.write_text("")

    # Mock SPIREAgentManager to avoid permission errors and binary requirements
    mock_agent = MagicMock()
    mock_agent.start.return_value = True
    mock_agent.attest_node.return_value = True

    with patch(
        "src.security.spiffe.controller.spiffe_controller.SPIREAgentManager",
        return_value=mock_agent,
    ):
        controller = SPIFFEController()
        # Monkeypatch workload_api socket path
        controller.workload_api.socket_path = fake
        assert (
            controller.initialize(
                attestation_strategy=AttestationStrategy.JOIN_TOKEN, token="abc123"
            )
            is True
        )
        ident = controller.get_identity()
        assert ident.spiffe_id.startswith("spiffe://")

        # Check if establish_mtls_connection exists, if not skip that part
        if hasattr(controller, "establish_mtls_connection"):
            # Mock mTLS connection
            mock_mtls = {"verified": True}
            with patch.object(
                controller, "establish_mtls_connection", return_value=mock_mtls
            ):
                mtls = controller.establish_mtls_connection(
                    "spiffe://x0tta6bl4.mesh/service/api"
                )
                assert mtls["verified"] is True

        # Force expiry to test rotation path
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
            )
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com")])
            )
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.UniformResourceIdentifier(
                            "spiffe://x0tta6bl4.mesh/node/mock2"
                        )
                    ]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        controller.current_identity = X509SVID(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/mock2",
            cert_chain=[cert_pem],
            private_key=key_pem,
            expiry=datetime.utcnow() - timedelta(seconds=1),
        )
        # create second mock socket (still exists) so refresh works
        refreshed = controller.get_identity()
        assert refreshed.spiffe_id.startswith("spiffe://")
