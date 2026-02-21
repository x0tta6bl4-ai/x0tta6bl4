from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.network.vpn_obfuscation_manager as mod


class _FakeTrafficShaper:
    def __init__(self, profile):
        self.profile = profile

    def shape_packet(self, data: bytes) -> bytes:
        return b"TS:" + data

    def unshape_packet(self, data: bytes) -> bytes:
        if data.startswith(b"TS:"):
            return data[3:]
        return data

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


class _FakeStegoMesh:
    def __init__(self, master_key: bytes):
        self.master_key = master_key

    def encode_packet(self, data: bytes) -> bytes:
        return b"SM:" + data

    def decode_packet(self, data: bytes) -> bytes:
        return data[3:] if data.startswith(b"SM:") else data


def _patch_transports(monkeypatch, stego_available: bool = True):
    monkeypatch.setattr(mod, "TrafficShaper", _FakeTrafficShaper)
    monkeypatch.setattr(mod, "FakeTLSTransport", _FakeTLSTransport)
    monkeypatch.setattr(mod, "ShadowsocksTransport", _FakeShadowsocksTransport)
    monkeypatch.setattr(mod, "DomainFrontingTransport", _FakeDomainFrontingTransport)

    if stego_available:
        monkeypatch.setattr(mod, "STEGO_MESH_AVAILABLE", True)
        monkeypatch.setattr(mod, "StegoMeshProtocol", _FakeStegoMesh, raising=False)
    else:
        monkeypatch.setattr(mod, "STEGO_MESH_AVAILABLE", False)

    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(mod.time, "time", lambda: 1000.0)


def test_init_master_key_env_and_production_rules(monkeypatch):
    _patch_transports(monkeypatch, stego_available=True)

    monkeypatch.delenv(mod.OBFUSCATION_MASTER_KEY_ENV, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    dev = mod.VPNObfuscationManager()
    assert isinstance(dev.master_key, bytes)
    assert len(dev.master_key) == 32

    monkeypatch.setenv(mod.OBFUSCATION_MASTER_KEY_ENV, "env-key")
    from_env = mod.VPNObfuscationManager()
    assert from_env.master_key == b"env-key"

    from_arg = mod.VPNObfuscationManager(master_key=b"manual-key")
    assert from_arg.master_key == b"manual-key"

    monkeypatch.delenv(mod.OBFUSCATION_MASTER_KEY_ENV, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError):
        mod.VPNObfuscationManager()


def test_setters_rotation_and_should_rotate(monkeypatch):
    _patch_transports(monkeypatch, stego_available=True)

    monkeypatch.setattr(mod, "ROTATING_SNI_OPTIONS", ["sni1", "sni2"])
    monkeypatch.setattr(mod, "ROTATING_FINGERPRINT_OPTIONS", ["fp1", "fp2"])
    monkeypatch.setattr(mod, "ROTATING_SPIDERX_OPTIONS", ["sp1", "sp2"])

    manager = mod.VPNObfuscationManager(master_key=b"k")
    manager.set_obfuscation_method(mod.ObfuscationMethod.SHADOWSOCKS)
    manager.set_rotation_strategy(mod.RotationStrategy.TIME_BASED)
    manager.set_rotation_interval(10)

    manager.last_rotation_time = 980.0
    monkeypatch.setattr(mod.time, "time", lambda: 1000.0)
    assert manager._should_rotate() is True

    manager.set_rotation_strategy(mod.RotationStrategy.RANDOM)
    manager.rotate_parameters()
    assert manager.current_sni == "sni1"

    manager.current_sni = "sni1"
    manager.current_fingerprint = "fp1"
    manager.current_spiderx = "sp1"
    manager.set_rotation_strategy(mod.RotationStrategy.ROUND_ROBIN)
    manager.rotate_parameters()
    assert manager.current_sni == "sni2"
    assert manager.current_fingerprint == "fp2"
    assert manager.current_spiderx == "sp2"
    assert isinstance(manager.faketls, _FakeTLSTransport)


def test_obfuscate_and_deobfuscate_all_methods(monkeypatch):
    _patch_transports(monkeypatch, stego_available=True)

    manager = mod.VPNObfuscationManager(master_key=b"k")
    monkeypatch.setattr(manager, "_should_rotate", lambda: False)

    payload = b"hello"

    manager.current_method = mod.ObfuscationMethod.FAKETLS
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.SHADOWSOCKS
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.DOMAIN_FRONTING
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.STEGOMESH
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.HYBRID
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.NONE
    shaped = manager.obfuscate(payload)
    assert shaped.startswith(b"TS:")
    assert manager.deobfuscate(shaped) == payload

    manager.stegomesh = None
    manager.current_method = mod.ObfuscationMethod.STEGOMESH
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload

    manager.current_method = mod.ObfuscationMethod.HYBRID
    assert manager.deobfuscate(manager.obfuscate(payload)) == payload


def test_profiles_parameters_effectiveness_and_optimization(monkeypatch):
    _patch_transports(monkeypatch, stego_available=True)

    manager = mod.VPNObfuscationManager(master_key=b"k")

    manager.set_traffic_profile(mod.TrafficProfile.WEB_BROWSING)
    assert "profile" in manager.get_traffic_statistics()

    params = manager.get_current_parameters()
    assert params["method"] == manager.current_method.value
    assert "next_rotation" in params

    monkeypatch.setattr(
        manager,
        "_hybrid_obfuscate",
        lambda _data: (_ for _ in ()).throw(RuntimeError("hybrid fail")),
    )
    metrics = manager.test_obfuscation_effectiveness(b"payload")
    assert metrics["faketls"]["success"] is True
    assert metrics["hybrid"]["success"] is False

    monkeypatch.setattr(
        manager,
        "test_obfuscation_effectiveness",
        lambda _data: {
            "faketls": {"success": True, "entropy_change": 1.0, "compression_ratio": 1.1},
            "shadowsocks": {"success": True, "entropy_change": 2.0, "compression_ratio": 1.0},
            "domain_fronting": {"success": False},
        },
    )
    optimized = manager.optimize_parameters_for_dpi_evasion()
    assert optimized["shadowsocks"]["success"] is True
    assert manager.current_method == mod.ObfuscationMethod.SHADOWSOCKS


def test_global_getter_and_demo_test_function(monkeypatch):
    _patch_transports(monkeypatch, stego_available=True)

    mod._global_obfuscator = None
    first = mod.get_vpn_obfuscator(master_key=b"key")
    second = mod.get_vpn_obfuscator(master_key=b"different")
    assert first is second

    class _DemoManager:
        def __init__(self):
            self.sni = "a"
            self.traffic_shaper = SimpleNamespace(shape_packet=lambda data: b"TS:" + data)

        def get_current_parameters(self):
            return {"sni": self.sni}

        def set_obfuscation_method(self, method):
            self.method = method

        def obfuscate(self, data):
            return b"OBF:" + data

        def deobfuscate(self, data):
            return data.replace(b"OBF:", b"")

        def rotate_parameters(self):
            self.sni = "b"

        def set_traffic_profile(self, profile):
            self.profile = profile

        def optimize_parameters_for_dpi_evasion(self):
            return {
                "faketls": {
                    "success": True,
                    "entropy_change": 1.0,
                    "size_increase": 2,
                    "compression_ratio": 1.1,
                }
            }

    monkeypatch.setattr(mod, "VPNObfuscationManager", _DemoManager)
    mod.test_obfuscation()
