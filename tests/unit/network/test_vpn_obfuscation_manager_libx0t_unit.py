from __future__ import annotations

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import libx0t.network.vpn_obfuscation_manager as mod


class _FakeTrafficShaper:
    def __init__(self, profile):
        self.profile = profile

    def shape_packet(self, data: bytes) -> bytes:
        return b"TS:" + data

    def unshape_packet(self, data: bytes) -> bytes:
        return data[3:] if data.startswith(b"TS:") else data

    def get_profile_info(self):
        value = getattr(self.profile, "value", str(self.profile))
        return {"profile": value}


class _FakeTLSTransport:
    def __init__(self, sni: str = ""):
        self.sni = sni

    def obfuscate(self, data: bytes) -> bytes:
        return b"TLS:" + data

    def deobfuscate(self, data: bytes) -> bytes:
        return data[4:] if data.startswith(b"TLS:") else data


class _FakeShadowsocksTransport:
    def obfuscate(self, data: bytes) -> bytes:
        return b"SS:" + data

    def deobfuscate(self, data: bytes) -> bytes:
        return data[3:] if data.startswith(b"SS:") else data


class _FakeDomainFrontingTransport:
    def __init__(self, front: str, backend: str):
        self.front = front
        self.backend = backend

    def obfuscate(self, data: bytes) -> bytes:
        return b"DF:" + data

    def deobfuscate(self, data: bytes) -> bytes:
        return data[3:] if data.startswith(b"DF:") else data


def test_libx0t_vpn_obfuscation_thinking_redacts_payload_key_and_parameters(
    monkeypatch,
):
    monkeypatch.setattr(mod, "TrafficShaper", _FakeTrafficShaper)
    monkeypatch.setattr(mod, "FakeTLSTransport", _FakeTLSTransport)
    monkeypatch.setattr(mod, "ShadowsocksTransport", _FakeShadowsocksTransport)
    monkeypatch.setattr(mod, "DomainFrontingTransport", _FakeDomainFrontingTransport)
    monkeypatch.setattr(mod, "STEGO_MESH_AVAILABLE", False)
    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(mod.time, "time", lambda: 1000.0)

    manager = mod.VPNObfuscationManager(master_key=b"raw-master-key")
    manager.current_sni = "secret-sni.example"
    manager.current_spiderx = "secret-spiderx-path"
    manager.current_method = mod.ObfuscationMethod.FAKETLS

    encoded = manager.obfuscate(b"raw-payload-secret")
    assert manager.deobfuscate(encoded) == b"raw-payload-secret"

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    assert "zero_trust_review" in status["thinking"]["techniques"]
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "libx0t_vpn_obfuscation_decode"
    )
    assert status["payloads_redacted"] is True
    assert status["master_key_redacted"] is True
    assert status["raw_parameters_redacted"] is True

    rendered = repr(status)
    assert "raw-payload-secret" not in rendered
    assert "raw-master-key" not in rendered
    assert "secret-sni.example" not in rendered
    assert "secret-spiderx-path" not in rendered
