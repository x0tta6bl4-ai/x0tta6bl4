from datetime import datetime, timedelta
from pathlib import Path
import pytest
from src.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.security.spiffe.workload.api_client import X509SVID
from src.security.spiffe.agent.manager import AttestationStrategy


def test_spiffe_controller_initialize_failure(tmp_path):
    controller = SPIFFEController()
    # workload_api socket does not exist -> initialize should fail
    assert controller.initialize(attestation_strategy=AttestationStrategy.JOIN_TOKEN, token='abc123') is False


def test_spiffe_controller_identity_and_mtls(tmp_path):
    # Create fake socket so workload_api.fetch_x509_svid succeeds
    sock = tmp_path / 'sockets'
    sock.mkdir(parents=True, exist_ok=True)
    fake = sock / 'agent.sock'
    fake.write_text('')
    controller = SPIFFEController()
    # Monkeypatch workload_api socket path
    controller.workload_api.socket_path = fake
    assert controller.initialize(attestation_strategy=AttestationStrategy.JOIN_TOKEN, token='abc123') is True
    ident = controller.get_identity()
    assert ident.spiffe_id.startswith('spiffe://')
    mtls = controller.establish_mtls_connection('spiffe://x0tta6bl4.mesh/service/api')
    assert mtls['verified'] is True
    # Force expiry to test rotation path
    controller.current_identity = X509SVID(spiffe_id='spiffe://x0tta6bl4.mesh/node/mock2', cert_chain=[b'C'], private_key=b'K', expiry=datetime.utcnow()-timedelta(seconds=1))
    # create second mock socket (still exists) so refresh works
    refreshed = controller.get_identity()
    assert refreshed.spiffe_id.startswith('spiffe://')
