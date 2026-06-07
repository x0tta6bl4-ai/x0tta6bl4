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
                json.dumps(
                    {
                        "mode": "advisory",
                        "recommended_action": "observe",
                        "probes": {
                            "ghost_xhttp_ready": True,
                            "ghost_https_ws_ready": True,
                            "subscription_health_status": "healthy",
                            "transport_usage_evidence": {
                                "generated_at": "2026-06-01T21:06:42Z",
                                "summary_60m": {
                                    "privacy_ok": True,
                                    "ghost_xhttp_dataplane_events": 2,
                                    "ghost_https_ws_dataplane_events": 77,
                                },
                            },
                        },
                    }
                ),
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
        self.assertTrue(health["ghost_xhttp_ready"])
        self.assertTrue(health["ghost_https_ws_ready"])
        self.assertEqual(health["subscription_health_status"], "healthy")
        self.assertTrue(health["transport_usage_ok"])
        self.assertEqual(health["transport_usage_60m"]["ghost_xhttp_dataplane_events"], 2)
        self.assertEqual(health["listener_signal_status"], "BASELINE_OK")
        self.assertEqual(health["recommended_profile"], "stable-primary")

    def test_build_transport_usage_returns_operator_safe_summary_only(self) -> None:
        runtime = {
            "generated_at": "2026-06-01T21:15:33Z",
            "mode": "advisory",
            "recommended_action": "observe",
            "hot_path_summary": {
                "transport_usage_60m": {
                    "window": "60m",
                    "privacy_ok": True,
                    "ghost_xhttp_dataplane_events": 2,
                    "ghost_xhttp_unique_clients": 2,
                    "ghost_https_ws_dataplane_events": 77,
                    "ghost_https_ws_unique_clients": 2,
                }
            },
            "probes": {
                "ghost_xhttp_ready": True,
                "ghost_https_ws_ready": True,
                "subscription_health_status": "healthy",
                "transport_usage_evidence": {
                    "generated_at": "2026-06-01T21:14:33Z",
                    "window_60m": {
                        "xray": {
                            "ghost_xhttp": {
                                "client_hashes_sample": ["0123456789abcdef"],
                                "raw_email": "user@example.test",
                                "raw_ip": "203.0.113.10",
                                "raw_target_host": "api.example.test",
                            }
                        }
                    },
                },
            },
        }

        usage = self.module.build_transport_usage(runtime)
        rendered = json.dumps(usage, ensure_ascii=False)

        self.assertTrue(usage["ok"])
        self.assertTrue(usage["ghost_xhttp_ready"])
        self.assertTrue(usage["ghost_https_ws_ready"])
        self.assertEqual(usage["subscription_health_status"], "healthy")
        self.assertEqual(usage["usage_generated_at"], "2026-06-01T21:14:33Z")
        self.assertEqual(
            usage["transport_usage_60m"]["ghost_https_ws_dataplane_events"],
            77,
        )
        self.assertNotIn("client_hashes_sample", rendered)
        self.assertNotIn("user@example.test", rendered)
        self.assertNotIn("203.0.113.10", rendered)
        self.assertNotIn("api.example.test", rendered)

    def test_build_client_compatibility_returns_summary_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix = Path(tmpdir) / "client-matrix.json"
            matrix.write_text(
                json.dumps(
                    {
                        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
                        "last_updated_utc": "2026-06-02T02:00:00Z",
                        "completion_rule": {
                            "current_status": "not_complete",
                            "evidence": {
                                "desktop_v2rayn": True,
                                "android_happ_or_hiddify": False,
                                "mobile_network": False,
                                "restricted_or_work_wifi": False,
                            },
                            "missing_requirements": [
                                "android_happ_or_hiddify",
                                "mobile_network",
                            ],
                            "next_required_checks": [
                                {
                                    "requirement": "android_happ_or_hiddify",
                                    "client": "Happ",
                                    "network_type": "mobile",
                                    "transport": "xhttp",
                                    "port": 8443,
                                }
                            ],
                            "evidence_session": {
                                "id": "nl-anti-block-2026-06-02",
                                "started_at": "2026-06-02T00:00:00Z",
                                "required_transport": "xhttp",
                                "required_port": 8443,
                                "required_for_network_types": [
                                    "mobile",
                                    "restricted-wifi",
                                    "work-wifi",
                                ],
                                "session_bound_current_passing_checks": 0,
                                "session_bound_requirements": {
                                    "android_happ_or_hiddify": False,
                                    "mobile_network": False,
                                    "restricted_or_work_wifi": False,
                                },
                            },
                        },
                        "real_client_checks": [
                            {
                                "client": "v2rayN",
                                "network_type": "desktop",
                                "transport": "xhttp",
                                "port": 8443,
                                "status": "pass",
                                "symptom": "connected",
                            },
                            {
                                "client": "Happ",
                                "network_type": "mobile",
                                "transport": "xhttp",
                                "port": 8443,
                                "status": "fail",
                                "symptom": "timeout",
                            },
                        ],
                        "local_v2rayn_dataplane_probe": {
                            "checked_at": "2026-06-01T23:03:50Z",
                            "ok": True,
                            "passed_transports": ["ws", "xhttp"],
                            "profile_count": 2,
                            "target_url_class": "https_generate_204",
                            "results": [
                                {
                                    "transport": "xhttp",
                                    "port": 8443,
                                    "ok": True,
                                    "http_code": 204,
                                    "total_s": 0.49,
                                    "raw_uuid": "123e4567-e89b-12d3-a456-426614174000",
                                    "raw_ip": "203.0.113.10",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.module.CLIENT_COMPATIBILITY_PATH = matrix

            payload = self.module.build_client_compatibility()
            rendered = json.dumps(payload, ensure_ascii=False)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["real_client_checks"], 2)
        self.assertEqual(payload["passing_real_client_checks"], 1)
        self.assertEqual(
            payload["missing_requirements"],
            ["android_happ_or_hiddify", "mobile_network"],
        )
        self.assertEqual(payload["next_required_checks"][0]["client"], "Happ")
        self.assertEqual(
            payload["evidence_session"]["id"],
            "nl-anti-block-2026-06-02",
        )
        self.assertEqual(payload["evidence_session"]["required_transport"], "xhttp")
        self.assertEqual(payload["evidence_session"]["required_port"], 8443)
        self.assertTrue(payload["local_v2rayn_dataplane_probe"]["ok"])
        self.assertFalse(payload["privacy"]["raw_real_client_rows_returned"])
        self.assertNotIn("symptom", rendered)
        self.assertNotIn("123e4567-e89b-12d3-a456-426614174000", rendered)
        self.assertNotIn("203.0.113.10", rendered)

    def test_build_client_compatibility_serves_prebuilt_runtime_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = Path(tmpdir) / "latest.json"
            summary.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "service": "vps-profile-status-api",
                        "generated_at": "2026-06-02T00:35:25Z",
                        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
                        "current_status": "not_complete",
                        "complete": False,
                        "completion": {
                            "desktop_v2rayn": True,
                            "android_happ_or_hiddify": False,
                            "mobile_network": False,
                            "restricted_or_work_wifi": False,
                        },
                        "missing_requirements": [
                            "android_happ_or_hiddify",
                            "mobile_network",
                            "restricted_or_work_wifi",
                        ],
                        "next_required_checks": [
                            {
                                "requirement": "android_happ_or_hiddify",
                                "client": "Happ",
                                "network_type": "mobile",
                                "transport": "xhttp",
                                "port": 8443,
                            }
                        ],
                        "evidence_session": {
                            "id": "nl-anti-block-2026-06-02",
                            "started_at": "2026-06-02T00:00:00Z",
                            "required_transport": "xhttp",
                            "required_port": 8443,
                            "required_for_network_types": [
                                "mobile",
                                "restricted-wifi",
                                "work-wifi",
                            ],
                            "session_bound_current_passing_checks": 0,
                            "session_bound_requirements": {
                                "android_happ_or_hiddify": False,
                                "mobile_network": False,
                                "restricted_or_work_wifi": False,
                            },
                        },
                        "real_client_checks": 9,
                        "passing_real_client_checks": 2,
                        "privacy": {
                            "output_privacy_ok": True,
                            "raw_real_client_rows_returned": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.module.CLIENT_COMPATIBILITY_PATH = summary

            payload = self.module.build_client_compatibility()
            rendered = json.dumps(payload, ensure_ascii=False)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["real_client_checks"], 9)
        self.assertEqual(payload["passing_real_client_checks"], 2)
        self.assertEqual(
            payload["missing_requirements"],
            [
                "android_happ_or_hiddify",
                "mobile_network",
                "restricted_or_work_wifi",
            ],
        )
        self.assertEqual(payload["next_required_checks"][0]["client"], "Happ")
        self.assertEqual(payload["evidence_session"]["required_transport"], "xhttp")
        self.assertEqual(payload["evidence_session"]["required_port"], 8443)
        self.assertFalse(payload["privacy"]["raw_real_client_rows_returned"])
        self.assertNotIn("vless://", rendered)

    def test_build_client_compatibility_missing_file_is_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.module.CLIENT_COMPATIBILITY_PATH = Path(tmpdir) / "missing.json"

            payload = self.module.build_client_compatibility()

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["error"], "client compatibility summary missing")

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
