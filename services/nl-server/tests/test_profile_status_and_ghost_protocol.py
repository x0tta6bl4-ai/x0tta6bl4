#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProfileStatusApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(
            "profile_status_api",
            ROOT / "mesh-runtime" / "profile_status_api.py",
        )

    def test_build_health_uses_sanitized_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime = root / "runtime-state.json"
            signal = root / "listener-loss-signal.json"
            hint = root / "client-profile-hint.json"
            runtime.write_text(
                json.dumps({"mode": "advisory", "recommended_action": "observe"}),
                encoding="utf-8",
            )
            signal.write_text(json.dumps({"status": "BASELINE_OK"}), encoding="utf-8")
            hint.write_text(json.dumps({"recommended_profile": "stable-primary"}), encoding="utf-8")

            self.module.RUNTIME_STATE_PATH = runtime
            self.module.SIGNAL_PATH = signal
            self.module.HINT_PATH = hint

            health = self.module.build_health()

        self.assertTrue(health["ok"])
        self.assertEqual(health["runtime_mode"], "advisory")
        self.assertEqual(health["recommended_action"], "observe")
        self.assertEqual(health["listener_signal_status"], "BASELINE_OK")
        self.assertEqual(health["recommended_profile"], "stable-primary")

    def test_load_json_missing_or_invalid_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.json"
            invalid = Path(tmpdir) / "invalid.json"
            invalid.write_text("{not-json", encoding="utf-8")

            self.assertEqual(self.module.load_json(missing), {})
            self.assertEqual(self.module.load_json(invalid), {})


class GhostVpnProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(
            "ghost_vpn_protocol",
            ROOT / "ghost-vpn" / "ghost_vpn_protocol.py",
        )

    def test_protected_message_round_trip_and_tamper_reject(self) -> None:
        key = b"k" * 32
        payload = b"hello"

        frame = self.module.pack_protected_msg(key, self.module.MsgType.PING, payload)
        msg_type, decoded = self.module.unpack_protected_msg(key, frame)

        self.assertEqual(msg_type, self.module.MsgType.PING)
        self.assertEqual(decoded, payload)

        tampered = frame[:-1] + bytes([frame[-1] ^ 0x01])
        bad_type, bad_payload = self.module.unpack_protected_msg(key, tampered)
        self.assertIsNone(bad_type)
        self.assertEqual(bad_payload, b"")

    def test_handshake_init_round_trip(self) -> None:
        profile = self.module.ObfuscationProfile.DNS
        cookie = b"cookie"
        client_pub_key = b"client-public-key"

        payload = self.module.pack_handshake_init(client_pub_key, profile=profile, cookie=cookie)
        decoded_profile, decoded_cookie, decoded_pub_key = self.module.unpack_handshake_init(payload)

        self.assertEqual(decoded_profile, profile)
        self.assertEqual(decoded_cookie, cookie)
        self.assertEqual(decoded_pub_key, client_pub_key)

    def test_handshake_response_round_trip(self) -> None:
        profile = self.module.ObfuscationProfile.STEAM
        ciphertext = b"ciphertext"
        auth_tag = b"a" * 32

        payload = self.module.pack_handshake_resp(
            ciphertext,
            "10.8.0.2",
            profile=profile,
            auth_tag=auth_tag,
        )
        decoded_ciphertext, assigned_ip, decoded_profile, decoded_auth_tag = (
            self.module.unpack_handshake_resp(payload)
        )

        self.assertEqual(decoded_ciphertext, ciphertext)
        self.assertEqual(assigned_ip, "10.8.0.2")
        self.assertEqual(decoded_profile, profile)
        self.assertEqual(decoded_auth_tag, auth_tag)

    def test_strategy_and_profile_switch_round_trips(self) -> None:
        strategy = {"strategy_id": "s1", "profile": "dns", "reason": "latency"}
        strategy_id, decoded_strategy = self.module.unpack_strategy_sync(
            self.module.pack_strategy_sync(strategy)
        )

        self.assertEqual(strategy_id, "s1")
        self.assertEqual(decoded_strategy, strategy)

        profile, reason = self.module.unpack_profile_switch(
            self.module.pack_profile_switch("steam", "dpi_detected")
        )
        self.assertEqual(profile, "steam")
        self.assertEqual(reason, "dpi_detected")


if __name__ == "__main__":
    unittest.main()
