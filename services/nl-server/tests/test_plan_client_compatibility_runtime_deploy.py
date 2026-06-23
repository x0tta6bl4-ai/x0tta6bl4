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
MODULE_PATH = ROOT / "ghost-access" / "plan_client_compatibility_runtime_deploy.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "plan_client_compatibility_runtime_deploy", MODULE_PATH
    )
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
        remote_matches_local: bool = False,
    ) -> None:
        self.module = load_module()
        self.client_http_code = client_http_code
        self.paths_present = paths_present
        self.remote_matches_local = remote_matches_local
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args):
        command = tuple(args)
        self.calls.append(command)
        if command and command[0] == "scp":
            return self.module.CommandResult(0, "", "")
        remote = command[-1]
        if "systemctl is-active" in remote:
            return self.module.CommandResult(0, "active\n", "")
        if "curl -sS -o /dev/null" in remote and "/client-compatibility" in remote:
            return self.module.CommandResult(0, str(self.client_http_code), "")
        if "curl -sS -o /dev/null" in remote and "/transport-usage" in remote:
            return self.module.CommandResult(0, "200", "")
        if remote.startswith("test -e "):
            return self.module.CommandResult(0 if self.paths_present else 1, "", "")
        if remote.startswith("sha256sum "):
            if self.remote_matches_local:
                for item in self.module.DEPLOY_FILES:
                    if item.remote_path in remote:
                        return self.module.CommandResult(
                            0,
                            f"{self.module.sha256(item.local_path)}\n",
                            "",
                        )
            return self.module.CommandResult(0, "", "")
        return self.module.CommandResult(0, "", "")

    def mutation_calls(self) -> list[tuple[str, ...]]:
        return [
            call
            for call in self.calls
            if call
            and (
                call[0] == "scp"
                or "install " in call[-1]
                or "systemctl daemon-reload" in call[-1]
                or "systemctl enable" in call[-1]
                or "systemctl restart" in call[-1]
                or "systemctl stop" in call[-1]
                or "systemctl reload" in call[-1]
            )
        ]


class PlanClientCompatibilityRuntimeDeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_dry_run_plan_is_privacy_safe_and_scoped_to_allowed_targets(self) -> None:
        runner = FakeRunner(client_http_code=404)

        plan = self.module.build_plan("nl", runner)

        self.assertEqual(plan["decision"], "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN")
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["apply_required"])
        self.assertEqual(plan["current_blocker"], "nl_client_compatibility_endpoint_missing")
        self.assertEqual(plan["confirm_required"], self.module.CONFIRM_TOKEN)
        self.assertEqual(
            plan["status_api_restart_confirm_required"],
            self.module.STATUS_API_RESTART_CONFIRM_TOKEN,
        )
        allowed = set(plan["mutation_policy"]["allowed_target_paths"])
        targets = {row["remote_path"] for row in plan["files"]}
        self.assertEqual(targets, allowed)
        rendered = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn("http://", rendered)
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("/sub/", rendered)
        self.assertEqual(self.module.privacy_findings(plan), [])
        self.assertFalse(runner.mutation_calls())

    def test_plan_reports_already_applied_when_endpoint_and_hashes_match(self) -> None:
        runner = FakeRunner(
            client_http_code=200,
            paths_present=True,
            remote_matches_local=True,
        )

        plan = self.module.build_plan("nl", runner)

        self.assertEqual(plan["decision"], "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED")
        self.assertFalse(plan["apply_required"])
        self.assertEqual(plan["current_blocker"], "none")
        self.assertTrue(all(row["remote_matches_local"] for row in plan["files"]))

    def test_apply_without_confirm_is_blocked_before_mutation(self) -> None:
        runner = FakeRunner()

        result = self.module.apply_plan(
            "nl",
            confirm=None,
            restart_status_api=False,
            status_api_restart_confirm=None,
            runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["decision"], "CLIENT_COMPAT_RUNTIME_DEPLOY_BLOCKED")
        self.assertIn("--confirm", " ".join(result["errors"]))
        self.assertFalse(runner.mutation_calls())

    def test_apply_requires_separate_confirm_for_status_api_restart(self) -> None:
        runner = FakeRunner()

        result = self.module.apply_plan(
            "nl",
            confirm=self.module.CONFIRM_TOKEN,
            restart_status_api=True,
            status_api_restart_confirm=None,
            runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertIn("--status-api-restart-confirm", " ".join(result["errors"]))
        self.assertFalse(runner.mutation_calls())

    def test_confirmed_apply_only_restarts_profile_status_api(self) -> None:
        runner = FakeRunner()

        result = self.module.apply_plan(
            "nl",
            confirm=self.module.CONFIRM_TOKEN,
            restart_status_api=True,
            status_api_restart_confirm=self.module.STATUS_API_RESTART_CONFIRM_TOKEN,
            runner=runner,
        )

        self.assertTrue(result["ok"])
        rendered_calls = "\n".join(" ".join(call) for call in runner.calls)
        self.assertIn("systemctl restart x0tta6bl4-profile-status-api.service", rendered_calls)
        for forbidden in self.module.FORBIDDEN_SERVICE_RESTARTS:
            self.assertNotIn(f"systemctl restart {forbidden}", rendered_calls)
            self.assertNotIn(f"systemctl reload {forbidden}", rendered_calls)
            self.assertNotIn(f"systemctl stop {forbidden}", rendered_calls)

    def test_cli_writes_dry_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_out = Path(tmpdir) / "deploy-plan.json"
            md_out = Path(tmpdir) / "deploy-plan.md"
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
        self.assertEqual(payload["decision"], "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN")
        self.assertIn("CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN", markdown)
        self.assertIn("DEPLOY_CLIENT_COMPAT_RUNTIME", markdown)
        self.assertNotIn("http://", markdown)


if __name__ == "__main__":
    unittest.main()
