from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "check_live_subscription_payload.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_live_subscription_payload", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("module spec missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_args(db_path: Path, env_file: Path, **overrides):
    values = {
        "db_path": db_path,
        "env_file": env_file,
        "subscription_base_url": "https://vpn.example",
        "expected_ports": None,
        "limit": 10,
        "expired_limit": 20,
        "timeout": 1.0,
        "include_expired": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def create_db(path: Path, token: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                subscription_token TEXT,
                expires_at TEXT,
                subscription_updated_at TEXT
            );
            CREATE TABLE devices (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at, subscription_updated_at) VALUES (1, ?, '2027-06-05T00:00:00Z', '2026-06-05T00:00:00Z')",
            (token,),
        )
        conn.execute("INSERT INTO devices(user_id) VALUES (1)")
        conn.commit()


class LiveSubscriptionPayloadCheckTests(unittest.TestCase):
    def test_payload_summary_accepts_reality_443_and_2083_without_secrets(self) -> None:
        module = load_module()
        uuid_one = "378042ee-5c74-43dd-9156-826fed6e6b66"
        uuid_two = "752de297-019b-4fe9-ad19-932e5391e7ef"
        body = "\n".join(
            [
                f"vless://{uuid_one}@example.test:443?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main",
                f"vless://{uuid_two}@example.test:2083?security=reality&type=tcp&pbk=pub&sid=abcd&fp=qq&sni=example.test&flow=xtls-rprx-vision#secondary",
            ]
        ).encode()
        report = module.summarize_payload(base64.b64encode(body), {443, 2083})

        serialized = json.dumps(report, sort_keys=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["transport_counts"], {"reality": 2})
        self.assertEqual(report["ports"], [443, 2083])
        self.assertEqual(report["anti_dpi"]["status"], "ready")
        self.assertTrue(report["anti_dpi"]["ready"])
        self.assertTrue(report["anti_dpi"]["primary_reality_443_ready"])
        self.assertTrue(report["anti_dpi"]["secondary_reality_port_ready"])
        self.assertEqual(report["anti_dpi"]["recommended_port_order"], [443, 2083])
        self.assertEqual(report["anti_dpi"]["warnings"], [])
        self.assertNotIn(uuid_one, serialized)
        self.assertNotIn(uuid_two, serialized)
        self.assertFalse(report["raw_tokens_or_uris_printed"])

    def test_payload_summary_rejects_xhttp_8443(self) -> None:
        module = load_module()
        body = "\n".join(
            [
                "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main",
                "vless://752de297-019b-4fe9-ad19-932e5391e7ef@example.test:8443?security=tls&type=xhttp#bad",
            ]
        ).encode()
        report = module.summarize_payload(base64.b64encode(body), {443, 2083})

        self.assertFalse(report["ok"])
        self.assertIn("subscription_disallowed_transport", report["failures"])
        self.assertIn("subscription_unexpected_port", report["failures"])
        self.assertIn("anti_dpi_legacy_transports_in_subscription", report["failures"])
        self.assertEqual(report["transport_counts"], {"reality": 1, "xhttp": 1})
        self.assertEqual(report["unexpected_ports"], [8443])
        self.assertEqual(report["anti_dpi"]["status"], "unsafe")
        self.assertFalse(report["anti_dpi"]["ready"])

    def test_payload_summary_rejects_unsafe_fingerprint_and_bad_short_id(self) -> None:
        module = load_module()
        body = (
            "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443"
            "?security=reality&type=tcp&pbk=pub&sid=bad-short-id&fp=unsafe&sni=example.test"
            "&flow=xtls-rprx-vision#bad"
        ).encode()
        report = module.summarize_payload(base64.b64encode(body), {443, 2083})

        self.assertFalse(report["ok"])
        self.assertEqual(report["anti_dpi"]["status"], "unsafe")
        self.assertIn("anti_dpi_tls_fingerprint_unsafe", report["failures"])
        self.assertIn("anti_dpi_short_id_invalid_format", report["failures"])
        self.assertEqual(report["anti_dpi"]["unsafe_tls_fingerprint_count"], 1)
        self.assertEqual(report["anti_dpi"]["invalid_short_id_count"], 1)

    def test_run_check_reads_tokens_and_sanitizes_output(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "ghost.db"
            env_file = tmp_path / ".env"
            token = "secret-subscription-token"
            create_db(db_path, token)
            env_file.write_text("SUBSCRIPTION_BASE_URL=https://vpn.example\n", encoding="utf-8")
            body = (
                "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443"
                "?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main"
            ).encode()

            def fetcher(base_url: str, fetched_token: str, timeout: float):
                self.assertEqual(base_url, "https://vpn.example")
                self.assertEqual(fetched_token, token)
                self.assertEqual(timeout, 1.0)
                return 200, base64.b64encode(body)

            report = module.run_check(
                make_args(db_path, env_file, subscription_base_url="", expired_limit=0),
                fetcher=fetcher,
            )

        serialized = json.dumps(report, sort_keys=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "LIVE_SUBSCRIPTION_PAYLOAD_SAFE")
        self.assertTrue(report["generated_at"].endswith("Z"))
        self.assertEqual(report["checked_subscription_count"], 1)
        self.assertEqual(report["anti_dpi"]["status"], "ready_with_warnings")
        self.assertEqual(report["anti_dpi"]["ready_subscription_count"], 1)
        self.assertTrue(report["anti_dpi"]["all_checked_have_primary_reality_443"])
        self.assertFalse(report["anti_dpi"]["all_checked_have_secondary_reality_port"])
        self.assertIn(
            "anti_dpi_secondary_reality_port_missing",
            report["anti_dpi"]["warning_counts"],
        )
        self.assertNotIn(token, serialized)
        self.assertFalse(report["privacy"]["raw_tokens_printed"])

    def test_run_check_ignores_expired_tokens_by_default(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "ghost.db"
            env_file = tmp_path / ".env"
            create_db(db_path, "active-token")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT INTO users(user_id, subscription_token, expires_at, subscription_updated_at) VALUES (2, 'expired-token', '2026-01-01T00:00:00Z', '2026-06-05T00:00:00Z')"
                )
                conn.execute("INSERT INTO devices(user_id) VALUES (2)")
                conn.commit()
            env_file.write_text("SUBSCRIPTION_BASE_URL=https://vpn.example\n", encoding="utf-8")
            fetched_tokens = []

            def fetcher(base_url: str, fetched_token: str, timeout: float):
                fetched_tokens.append(fetched_token)
                body = (
                    "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443"
                    "?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main"
                ).encode()
                return 200, base64.b64encode(body)

            report = module.run_check(
                make_args(db_path, env_file, subscription_base_url="", expired_limit=0),
                fetcher=fetcher,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(fetched_tokens, ["active-token"])
        self.assertFalse(report["include_expired"])

    def test_run_check_verifies_expired_tokens_return_errors_without_profiles(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "ghost.db"
            env_file = tmp_path / ".env"
            create_db(db_path, "active-token")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT INTO users(user_id, subscription_token, expires_at, subscription_updated_at) VALUES (2, 'expired-token', '2026-01-01T00:00:00Z', '2026-06-05T00:00:00Z')"
                )
                conn.execute("INSERT INTO devices(user_id) VALUES (2)")
                conn.commit()
            env_file.write_text("SUBSCRIPTION_BASE_URL=https://vpn.example\n", encoding="utf-8")

            def fetcher(base_url: str, fetched_token: str, timeout: float):
                if fetched_token == "expired-token":
                    return 403, b"Subscription expired\\n"
                body = (
                    "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443"
                    "?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main"
                ).encode()
                return 200, base64.b64encode(body)

            report = module.run_check(
                make_args(db_path, env_file, subscription_base_url=""),
                fetcher=fetcher,
            )

        self.assertTrue(report["ok"])
        expired = report["expired_error_check"]
        self.assertTrue(expired["ok"])
        self.assertEqual(expired["status_counts"], {"403": 1})
        self.assertEqual(expired["max_profile_count"], 0)
        self.assertEqual(expired["ports_seen"], [])
        self.assertFalse(expired["raw_tokens_or_uris_printed"])

    def test_run_check_rejects_expired_tokens_that_return_fake_profiles(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "ghost.db"
            env_file = tmp_path / ".env"
            create_db(db_path, "active-token")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT INTO users(user_id, subscription_token, expires_at, subscription_updated_at) VALUES (2, 'expired-token', '2026-01-01T00:00:00Z', '2026-06-05T00:00:00Z')"
                )
                conn.execute("INSERT INTO devices(user_id) VALUES (2)")
                conn.commit()
            env_file.write_text("SUBSCRIPTION_BASE_URL=https://vpn.example\n", encoding="utf-8")

            def fetcher(base_url: str, fetched_token: str, timeout: float):
                if fetched_token == "expired-token":
                    body = (
                        "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:1"
                        "?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#fake"
                    ).encode()
                    return 200, base64.b64encode(body)
                body = (
                    "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example.test:443"
                    "?security=reality&type=tcp&pbk=pub&sid=b2c4&fp=qq&sni=example.test&flow=xtls-rprx-vision#main"
                ).encode()
                return 200, base64.b64encode(body)

            report = module.run_check(
                make_args(db_path, env_file, subscription_base_url=""),
                fetcher=fetcher,
            )

        self.assertFalse(report["ok"])
        self.assertIn(
            "expired:expired_subscription_returned_vpn_profile",
            report["failures"],
        )
        self.assertIn(
            "expired:expired_subscription_http_not_error",
            report["failures"],
        )
        expired = report["expired_error_check"]
        self.assertFalse(expired["ok"])
        self.assertEqual(expired["max_profile_count"], 1)
        self.assertEqual(expired["ports_seen"], [1])


if __name__ == "__main__":
    unittest.main()
