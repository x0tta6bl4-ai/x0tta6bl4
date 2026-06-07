#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class DeviceActivitySyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_database_module = sys.modules.get("database")
        self._old_ghost_db_path = os.environ.get("GHOST_ACCESS_DB_PATH")

        fake_database = types.ModuleType("database")
        fake_database.calls = []

        def record_device_seen_by_email(email, source_ip=None, seen_at=None):
            fake_database.calls.append(
                {
                    "email": email,
                    "source_ip": source_ip,
                    "seen_at": seen_at,
                }
            )
            return True

        fake_database.record_device_seen_by_email = record_device_seen_by_email
        sys.modules["database"] = fake_database
        self.fake_database = fake_database

        self.module = load_module(
            "sync_xray_device_activity_test",
            ROOT / "ghost-access" / "sync_xray_device_activity.py",
        )

    def tearDown(self) -> None:
        if self._old_database_module is None:
            sys.modules.pop("database", None)
        else:
            sys.modules["database"] = self._old_database_module

        if self._old_ghost_db_path is None:
            os.environ.pop("GHOST_ACCESS_DB_PATH", None)
        else:
            os.environ["GHOST_ACCESS_DB_PATH"] = self._old_ghost_db_path

    def test_extractors_handle_access_log_shapes(self) -> None:
        self.assertEqual(
            self.module._extract_email(
                "2026/05/27 12:00:00 tcp:1.2.3.4:555 accepted [alice@example.com -> proxy]"
            ),
            "alice@example.com",
        )
        self.assertEqual(self.module._extract_email('email="bob@example.com" connected'), "bob@example.com")
        self.assertEqual(self.module._extract_email("client carol@example.com active"), "carol@example.com")

        self.assertEqual(self.module._extract_ip("tcp:1.2.3.4:555 accepted"), "1.2.3.4")
        self.assertEqual(self.module._extract_ip("accepted from 5.6.7.8"), "5.6.7.8")
        self.assertEqual(self.module._extract_ip("peer 9.10.11.12:443"), "9.10.11.12")

    def test_xui_helpers_parse_last_online_and_latest_ip(self) -> None:
        seen_at = self.module._parse_xui_last_online(1_700_000_000_000)

        self.assertIsNotNone(seen_at)
        self.assertEqual(seen_at.isoformat(), "2023-11-14T22:13:20")
        self.assertEqual(self.module._extract_latest_ip('["1.1.1.1", "2.2.2.2"]'), "2.2.2.2")
        self.assertIsNone(self.module._extract_latest_ip("not-json"))

    def test_run_once_updates_state_and_skips_processed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "access.log"
            state_path = root / "state.json"
            self.module.DEFAULT_XUI_DB_PATH = root / "missing-x-ui.db"
            log_path.write_text(
                "2026/05/27 12:00:00 tcp:1.2.3.4:555 accepted [alice@example.com -> proxy]\n",
                encoding="utf-8",
            )

            code, payload = self.module.run_once(log_path, state_path, full_rescan=False)
            second_code, second_payload = self.module.run_once(log_path, state_path, full_rescan=False)

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["matched"], 1)
        self.assertEqual(payload["updated"], 1)
        self.assertEqual(payload["errors"], 0)
        self.assertEqual(
            payload["thinking"]["contract"]["role"],
            "xray_device_activity_sync_agent",
        )
        self.assertEqual(self.fake_database.calls[0]["email"], "alice@example.com")
        self.assertEqual(self.fake_database.calls[0]["source_ip"], "1.2.3.4")

        self.assertEqual(second_code, 0)
        self.assertEqual(second_payload["matched"], 0)
        self.assertEqual(second_payload["updated"], 0)
        self.assertEqual(len(self.fake_database.calls), 1)
        self.assertEqual(second_payload["offset"], payload["offset"])

    def test_missing_log_is_non_fatal_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, payload = self.module.run_once(
                Path(tmpdir) / "missing-access.log",
                Path(tmpdir) / "state.json",
                full_rescan=False,
            )

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["warning"], "access log missing")
        self.assertEqual(
            payload["thinking"]["applied"]["framing"]["problem"],
            "xray_device_activity_sync",
        )
        self.assertEqual(self.fake_database.calls, [])


class GhostTcpBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(
            "ghost_tcp_bridge_test",
            ROOT / "ghost-vpn" / "ghost_tcp_bridge.py",
        )

    def test_udp_response_is_framed_for_tcp_writer(self) -> None:
        writer = FakeWriter()
        relay = self.module.UDPRelay(writer)

        relay.datagram_received(b"reply", ("127.0.0.1", 4433))

        self.assertEqual(writer.chunks, [struct.pack("!H", 5) + b"reply"])

    def test_udp_response_is_ignored_when_tcp_writer_is_closing(self) -> None:
        writer = FakeWriter(closing=True)
        relay = self.module.UDPRelay(writer)

        relay.datagram_received(b"reply", ("127.0.0.1", 4433))

        self.assertEqual(writer.chunks, [])


class FakeWriter:
    def __init__(self, closing: bool = False) -> None:
        self._closing = closing
        self.chunks: list[bytes] = []

    def is_closing(self) -> bool:
        return self._closing

    def write(self, data: bytes) -> None:
        self.chunks.append(data)


if __name__ == "__main__":
    unittest.main()
