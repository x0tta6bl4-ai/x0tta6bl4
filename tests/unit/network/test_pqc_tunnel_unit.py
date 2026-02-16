import os
import struct

import pytest

import src.network.pqc_tunnel as pqc

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
    monkeypatch.setattr(pqc, "PQC_AVAILABLE", False)
    monkeypatch.setattr(pqc, "AES_AVAILABLE", False)
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
    monkeypatch.setattr(pqc, "PQC_AVAILABLE", False)
    monkeypatch.setattr(pqc, "AES_AVAILABLE", False)
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
    monkeypatch.setattr(pqc, "PQC_AVAILABLE", False)
    monkeypatch.setattr(pqc, "AES_AVAILABLE", False)
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
