from datetime import datetime, timedelta
from pathlib import Path
import pytest
from src.security.spiffe.workload.api_client import WorkloadAPIClient, X509SVID, JWTSVID


def test_fetch_x509_svid_socket_missing(tmp_path):
    client = WorkloadAPIClient(socket_path=tmp_path / 'missing.sock')
    with pytest.raises(ConnectionError):
        client.fetch_x509_svid()


def test_fetch_x509_svid_success(tmp_path):
    sock = tmp_path / 'agent.sock'
    sock.write_text('')  # create fake socket file presence
    client = WorkloadAPIClient(socket_path=sock)
    svid = client.fetch_x509_svid()
    assert svid.spiffe_id.startswith('spiffe://')
    assert svid.is_expired()  # mock expiry is now


def test_fetch_jwt_svid(tmp_path):
    sock = tmp_path / 'agent.sock'
    sock.write_text('')
    client = WorkloadAPIClient(socket_path=sock)
    jwt = client.fetch_jwt_svid(['aud1'])
    assert jwt.spiffe_id.startswith('spiffe://')
    assert jwt.audience == ['aud1']


def test_validate_peer_svid(tmp_path):
    sock = tmp_path / 'agent.sock'
    sock.write_text('')
    client = WorkloadAPIClient(socket_path=sock)
    peer = X509SVID(spiffe_id='spiffe://x0tta6bl4.mesh/peer', cert_chain=[b'C'], private_key=b'K', expiry=datetime.utcnow()+timedelta(hours=1))
    assert client.validate_peer_svid(peer) is True
    assert client.validate_peer_svid(peer, expected_id='spiffe://x0tta6bl4.mesh') is True
    assert client.validate_peer_svid(peer, expected_id='spiffe://other') is False
