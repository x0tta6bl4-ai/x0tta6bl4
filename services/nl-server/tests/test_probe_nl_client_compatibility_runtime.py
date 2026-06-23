#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "probe_nl_client_compatibility_runtime.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_nl_client_compatibility_runtime", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(
        self,
        *,
        client_http_code: int = 404,
        paths_present: bool = False,
        current_contract: bool = True,
    ) -> None:
        self.module = load_module()
        self.client_http_code = client_http_code
        self.paths_present = paths_present
        self.current_contract = current_contract
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args):
        command = tuple(args)
        self.calls.append(command)
        remote = command[-1]
        if "systemctl is-active x0tta6bl4-profile-status-api.service" in remote:
            return self.module.CommandResult(0, "active\n", "")
        if "systemctl is-active ghost-access-client-compatibility-summary.timer" in remote:
            return self.module.CommandResult(0, "active\n" if self.paths_present else "unknown\n", "")
        if "systemctl is-enabled ghost-access-client-compatibility-summary.timer" in remote:
            return self.module.CommandResult(0, "enabled\n" if self.paths_present else "unknown\n", "")
        if "curl -fsS --max-time 3 http://127.0.0.1:9472/transport-usage" in remote:
            return self.module.CommandResult(
                0,
                json.dumps(
                    {
                        "ok": True,
                        "ghost_xhttp_ready": True,
                        "ghost_https_ws_ready": True,
                        "transport_usage_60m": {"privacy_ok": True},
                    }
                ),
                "",
            )
        if "curl -sS -o /dev/null" in remote and "/client-compatibility" in remote:
            return self.module.CommandResult(0, str(self.client_http_code), "")
        if "curl -fsS --max-time 3 http://127.0.0.1:9472/client-compatibility" in remote:
            evidence_session = {
                "id": "nl-anti-block-2026-06-02",
                "started_at": "2026-06-02T00:00:00Z",
                "required_transport": "reality",
                "required_port": 443,
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
            }
            if not self.current_contract:
                evidence_session["required_transport"] = "xhttp"
            return self.module.CommandResult(
                0,
                json.dumps(
                    {
                        "ok": True,
                        "complete": False,
                        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
                        "missing_requirements": [
                            "android_happ_or_hiddify",
                            "mobile_network",
                        ],
                        "evidence_session": evidence_session,
                        "privacy": {
                            "output_privacy_ok": True,
                            "raw_real_client_rows_returned": False,
                        },
                    }
                ),
                "",
            )
        if remote.startswith("test -e "):
            return self.module.CommandResult(0 if self.paths_present else 1, "", "")
        return self.module.CommandResult(0, "", "")


class ProbeNlClientCompatibilityRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_build_report_detects_missing_client_compatibility_endpoint(self) -> None:
        runner = FakeRunner(client_http_code=404, paths_present=False)

        report = self.module.build_report("nl", runner)

        self.assertEqual(report["decision"], "NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING")
        self.assertEqual(report["profile_status_api_unit"]["active"], "active")
        self.assertTrue(report["transport_usage_endpoint"]["ok"])
        self.assertEqual(report["client_compatibility_endpoint"]["http_code"], 404)
        self.assertFalse(report["systemd_wiring"]["summary_present"])
        self.assertEqual(
            report["thinking"]["contract"]["role"],
            "nl_client_compatibility_runtime_probe",
        )
        self.assertIn(
            "deploy_profile_status_api_client_compatibility_endpoint",
            report["required_actions"],
        )
        self.assertTrue(report["privacy"]["output_privacy_ok"])

    def test_build_report_detects_ready_runtime_wiring(self) -> None:
        runner = FakeRunner(client_http_code=200, paths_present=True)

        report = self.module.build_report("nl", runner)

        self.assertEqual(report["decision"], "NL_CLIENT_COMPAT_RUNTIME_READY")
        self.assertTrue(report["client_compatibility_endpoint"]["http_ok"])
        self.assertFalse(report["client_compatibility_endpoint"]["complete"])
        self.assertTrue(
            report["client_compatibility_endpoint"]["evidence_session_contract_ok"]
        )
        self.assertTrue(report["systemd_wiring"]["summary_present"])
        self.assertEqual(report["systemd_wiring"]["timer_enabled"], "enabled")
        self.assertEqual(report["required_actions"], [])

    def test_build_report_rejects_old_runtime_contract(self) -> None:
        runner = FakeRunner(
            client_http_code=200,
            paths_present=True,
            current_contract=False,
        )

        report = self.module.build_report("nl", runner)

        self.assertEqual(report["decision"], "NL_CLIENT_COMPAT_RUNTIME_INCOMPLETE")
        self.assertFalse(
            report["client_compatibility_endpoint"]["evidence_session_contract_ok"]
        )
        self.assertIn(
            "publish_current_client_compatibility_contract",
            report["required_actions"],
        )

    def test_report_does_not_store_raw_endpoint_or_secret_material(self) -> None:
        report = self.module.build_report("nl", FakeRunner(client_http_code=404))
        rendered = json.dumps(report, ensure_ascii=False)

        self.assertNotIn("http://127.0.0.1", rendered)
        self.assertNotIn("89.125", rendered)
        self.assertNotIn("vless://", rendered)
        self.assertEqual(self.module.privacy_findings(report), [])

    def test_cli_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_out = Path(tmpdir) / "probe.json"
            md_out = Path(tmpdir) / "probe.md"
            original = self.module.default_runner
            self.module.default_runner = FakeRunner(client_http_code=404)
            try:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    rc = self.module.run(
                        [
                            "--ssh-host",
                            "nl",
                            "--json-out",
                            str(json_out),
                            "--markdown-out",
                            str(md_out),
                            "--write",
                            "--json",
                        ]
                    )
            finally:
                self.module.default_runner = original
            payload = json.loads(stdout.getvalue())
            markdown = md_out.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING")
        self.assertIn("NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING", markdown)
        self.assertNotIn("vless://", markdown)


if __name__ == "__main__":
    unittest.main()
