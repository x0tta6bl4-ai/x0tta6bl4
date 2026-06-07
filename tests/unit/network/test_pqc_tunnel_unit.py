import os
import struct

import pytest

import src.network.pqc_tunnel as pqc
import src.libx0t.network.pqc_tunnel as pqc_impl

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _Writer:
    def __init__(self):
        self.buf = b""

    def write(self, data):
        self.buf += data

    async def drain(self):
        return None


class _Reader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _n):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def test_handshake_and_encrypt_decrypt_simulated(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.setenv(pqc_impl.SIMULATED_PQC_ENV, "true")
    a = pqc.PQCTunnel("A")
    b = pqc.PQCTunnel("B")
    init = a.create_handshake_init()
    peer_b, secret_b, resp = b.process_handshake_init(init)
    peer_a, secret_a = a.process_handshake_response(resp)
    assert peer_b == "A"
    assert peer_a == "B"
    assert secret_a == secret_b
    payload = b"hello-pqc"
    enc = a.encrypt(payload, "B")
    dec = b.decrypt(enc, "A")
    assert dec == payload


def test_packet_wrap_unwrap_and_errors(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.setenv(pqc_impl.SIMULATED_PQC_ENV, "true")
    t1 = pqc.PQCTunnel("N1")
    t2 = pqc.PQCTunnel("N2")
    _, _, resp = t2.process_handshake_init(t1.create_handshake_init())
    t1.process_handshake_response(resp)
    wrapped = t1.wrap_packet(b"abc", "N2")
    unwrapped = t2.unwrap_packet(wrapped, "N1")
    assert unwrapped == b"abc"
    with pytest.raises(ValueError, match="Invalid PQC packet magic"):
        t2.unwrap_packet(b"BAD!" + wrapped[4:], "N1")
    with pytest.raises(ValueError, match="No session key"):
        t1.encrypt(b"x", "unknown")


@pytest.mark.asyncio
async def test_manager_establish_and_accept(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.setenv(pqc_impl.SIMULATED_PQC_ENV, "true")
    initiator = pqc.PQCTunnelManager("I")
    responder = pqc.PQCTunnelManager("R")

    # Prepare response buffer for establish_tunnel
    init_msg = initiator.tunnel.create_handshake_init()
    peer, secret, response = responder.tunnel.process_handshake_init(init_msg)
    response_buf = struct.pack(">I", len(response)) + response
    reader = _Reader([response_buf[:4], response_buf[4:]])
    writer = _Writer()
    ok = await initiator.establish_tunnel(reader, writer, peer_id="R")
    assert ok is True
    assert initiator.has_tunnel("R") is True

    # Accept path
    init2 = initiator.tunnel.create_handshake_init()
    in_buf = struct.pack(">I", len(init2)) + init2
    reader2 = _Reader([in_buf[:4], in_buf[4:]])
    writer2 = _Writer()
    peer_id = await responder.accept_tunnel(reader2, writer2)
    assert peer_id == "I"
    assert responder.has_tunnel("I") is True


def test_simulated_pqc_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.delenv(pqc_impl.SIMULATED_PQC_ENV, raising=False)

    with pytest.raises(RuntimeError, match="liboqs is required"):
        pqc.PQCTunnel("blocked")


def test_pqc_tunnel_thinking_redacts_nodes_keys_and_payload(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.setenv(pqc_impl.SIMULATED_PQC_ENV, "true")

    initiator = pqc.PQCTunnel("node-secret-alpha")
    responder = pqc.PQCTunnel("node-secret-beta")
    init = initiator.create_handshake_init()
    _peer_b, _secret_b, response = responder.process_handshake_init(init)
    _peer_a, _secret_a = initiator.process_handshake_response(response)

    wrapped = initiator.wrap_packet(b"raw-payload-secret", "node-secret-beta")
    assert responder.unwrap_packet(wrapped, "node-secret-alpha") == b"raw-payload-secret"

    status = initiator.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    assert "zero_trust_review" in status["thinking"]["techniques"]
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "pqc_encrypt"
    )
    assert status["claim_boundary"]

    rendered = repr(status)
    assert "node-secret-alpha" not in rendered
    assert "node-secret-beta" not in rendered
    assert "raw-payload-secret" not in rendered


@pytest.mark.asyncio
async def test_pqc_tunnel_manager_thinking_redacts_failed_peer(monkeypatch):
    monkeypatch.setattr(pqc_impl, "PQC_AVAILABLE", False)
    monkeypatch.setenv(pqc_impl.SIMULATED_PQC_ENV, "true")

    manager = pqc.PQCTunnelManager("manager-secret-node")
    ok = await manager.establish_tunnel(
        _Reader([b""]),
        _Writer(),
        peer_id="peer-secret-id",
    )
    assert ok is False

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    assert "mape_k" in status["thinking"]["techniques"]
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "pqc_manager_establish_failed"
    )

    rendered = repr(status)
    assert "manager-secret-node" not in rendered
    assert "peer-secret-id" not in rendered
