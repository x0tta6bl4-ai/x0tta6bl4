#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "ghost-access" / "sync_spb_standalone_clients.py"
    spec = importlib.util.spec_from_file_location("sync_spb_standalone_clients_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SpbStandaloneSyncSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_fetch_active_uuids_uses_ssh_sqlite_and_filters_blank_rows(self) -> None:
        calls: list[list[str]] = []

        def fake_run_text(cmd: list[str]) -> str:
            calls.append(cmd)
            return " uuid-a \n\n uuid-b\n"

        self.module.run_text = fake_run_text

        rows = self.module.fetch_active_uuids("nl-readonly", "/tmp/access db.sqlite")

        self.assertEqual(rows, ["uuid-a", "uuid-b"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "ssh")
        self.assertEqual(calls[0][1], "nl-readonly")
        self.assertIn("sqlite3", calls[0][2])
        self.assertIn("'/tmp/access db.sqlite'", calls[0][2])
        self.assertIn("offline_subscriptions", calls[0][2])
        self.assertIn("ORDER BY vpn_uuid", calls[0][2])

    def test_push_clients_to_spb_builds_single_remote_xray_mutation(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_run(cmd, **kwargs):
            calls.append({"cmd": cmd, "kwargs": kwargs})
            if cmd[0] == "python3":
                clients = json.loads(str(kwargs["input"]))
                stdout = base64.b64encode(json.dumps(clients).encode()).decode() + "\n"
                return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="active\n", stderr="")

        self.module.subprocess.run = fake_run

        self.module.push_clients_to_spb("spb-review", 443, ["uuid-a", "uuid-b"], "xtls-rprx-vision")

        self.assertEqual(len(calls), 2)
        ssh_cmd = calls[1]["cmd"]
        self.assertEqual(ssh_cmd[0], "ssh")
        self.assertEqual(ssh_cmd[1], "spb-review")
        remote_script = ssh_cmd[2]
        self.assertIn('/usr/local/etc/xray/config.json', remote_script)
        self.assertIn('if int(inbound.get("port") or 0) == 443', remote_script)
        self.assertIn('cfg_path.write_text', remote_script)
        self.assertIn('xray -test -config /usr/local/etc/xray/config.json', remote_script)
        self.assertIn('systemctl restart xray', remote_script)
        self.assertIn('systemctl is-active xray', remote_script)

    def test_manifest_marks_script_inactive_and_not_deployable(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        rows = manifest["source_promotion_status"]["promoted_files"]
        row = next(
            item
            for item in rows
            if item["path"] == "services/nl-server/ghost-access/sync_spb_standalone_clients.py"
        )

        self.assertFalse(row["deployable_to_nl"])
        self.assertEqual(row["local_review_class"], "C")
        self.assertEqual(row["operational_status"], "inactive_spb_disabled")
        self.assertIn("remote SPB", " ".join(row["local_notes"]))

        inactive = manifest["inactive_integrations"][0]
        self.assertEqual(inactive["name"], "spb_standalone_xray")
        self.assertFalse(inactive["enabled"])


if __name__ == "__main__":
    unittest.main()
