from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ops/run_external_dpi_intake_local.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_external_dpi_intake_local_test",
        RUNNER,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeScript:
    def __init__(self, name: str, responses: list[tuple[int, dict[str, Any]]]) -> None:
        self.__name__ = name
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def main(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        rc, payload = self.responses.pop(0)
        print(json.dumps(payload))
        return rc


def test_dry_run_reports_safe_local_command_shape_without_raw_values() -> None:
    module = _load()
    args = module.parse_args(["--dry-run"])

    report = module._plan(args)
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "DRY_RUN"
    assert report["raw_private_values_in_report"] is False
    assert report["claim_boundary"]["external_dpi_tested"] is False
    assert report["claim_boundary"]["production_ready"] is False
    assert "<authorized target URL; local input only>" in report["collector_command_shape"]
    assert "<authorized proxy URL; local input only>" in report["collector_command_shape"]
    assert "REPLACE_WITH" not in rendered
    assert "blocked.example" not in rendered
    assert "127.0.0.1" not in rendered


def test_cancelled_run_does_not_prompt_for_private_values(monkeypatch) -> None:
    module = _load()
    args = module.parse_args([])
    prompts: list[str] = []

    def fake_prompt(label: str, *, secret: bool = False, required: bool = True) -> str:
        prompts.append(label)
        return "no"

    monkeypatch.setattr(module, "_prompt", fake_prompt)

    report = module.run(args)

    assert report["status"] == "CANCELLED"
    assert report["blocking_reasons"] == ["operator_confirmation_missing"]
    assert prompts == ["Confirmation"]
    assert report["claim_boundary"]["external_dpi_tested"] is False


def test_cli_dry_run_json_is_machine_readable() -> None:
    module = _load()
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert result.stderr == ""
    assert report["status"] == "DRY_RUN"
    assert report["import_preflight_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    assert report["post_import_refresh_commands"] == module._post_import_refresh_commands()
    assert report["post_import_refresh_commands"][-1] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
        "--write-report",
        "--json",
    ]


def test_ready_run_redacts_child_reports_without_hiding_collector_inputs(monkeypatch) -> None:
    module = _load()
    private = {
        "Confirmation": module.CONFIRM_PHRASE,
        "Authorized target URL": "https://private-target.example/path",
        "Authorized treatment proxy URL": "https://private-proxy.example:8443",
        "Operator/lab ID": "operator-secret-123",
        "Authorization scope ID": "scope-secret-456",
        "Bounded scope summary": "scope summary private",
        "Network region bucket": "region-private-1",
        "Network type": "authorized lab network",
        "ISP/lab profile": "isp-profile-secret",
        "Egress location bucket": "egress-private-1",
        "Policy context": "policy-private-1",
    }
    prompts: list[tuple[str, bool, bool]] = []

    def fake_prompt(label: str, *, secret: bool = False, required: bool = True) -> str:
        prompts.append((label, secret, required))
        return private[label]

    collector = _FakeScript(
        "collector",
        [
            (
                0,
                {
                    "status": "VERIFIED",
                    "echoed_url": private["Authorized target URL"],
                    "nested": {
                        "operator": private["Operator/lab ID"],
                        "message": f"used {private['Authorization scope ID']} locally",
                    },
                },
            )
        ],
    )
    validator = _FakeScript(
        "validator",
        [
            (
                0,
                {
                    "decision": "READY_TO_IMPORT",
                    "summary": {
                        "dpi_bypass_confirmed": True,
                        "dataplane_confirmed": True,
                    },
                    "leaked_proxy": private["Authorized treatment proxy URL"],
                },
            )
        ],
    )
    importer = _FakeScript(
        "importer",
        [
            (0, {"decision": "READY_TO_IMPORT", "scope": private["Bounded scope summary"]}),
            (0, {"written": True, "policy": private["Policy context"]}),
        ],
    )
    scripts = {
        "collect_external_dpi_proxy_reachability_evidence.py": collector,
        "verify_external_dpi_proxy_reachability_evidence.py": validator,
        "import_ghost_pulse_external_evidence.py": importer,
    }

    monkeypatch.setattr(module, "_prompt", fake_prompt)
    monkeypatch.setattr(module, "_load_script", lambda name: scripts[name])

    report = module.run(module.parse_args(["--write-ready"]))
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "READY_TO_IMPORT"
    assert report["written"] is True
    assert report["blocking_reasons"] == []
    assert report["claim_boundary"] == {
        "local_runner_completed": True,
        "external_dpi_tested": True,
        "dpi_bypass_confirmed": True,
        "dataplane_confirmed": True,
        "production_ready": False,
        "raw_private_values_retained": False,
    }
    assert report["post_import_refresh_commands"] == module._post_import_refresh_commands()
    assert module.REDACTED_LOCAL_INPUT in rendered
    for value in private.values():
        if value != module.CONFIRM_PHRASE:
            assert value not in rendered
    assert "--target-url" in collector.calls[0]
    assert private["Authorized target URL"] in collector.calls[0]
    assert "--treatment-proxy" in collector.calls[0]
    assert private["Authorized treatment proxy URL"] in collector.calls[0]
    assert len(importer.calls) == 2
    assert [label for label, _secret, _required in prompts] == [
        "Confirmation",
        "Authorized target URL",
        "Authorized treatment proxy URL",
        "Operator/lab ID",
        "Authorization scope ID",
        "Bounded scope summary",
        "Network region bucket",
        "Network type",
        "ISP/lab profile",
        "Egress location bucket",
        "Policy context",
    ]


def test_not_ready_run_does_not_write_and_redacts_failures(monkeypatch) -> None:
    module = _load()
    private_target = "https://not-ready-private.example/path"
    private_scope = "scope-secret-not-ready"
    values = {
        "Confirmation": module.CONFIRM_PHRASE,
        "Authorized target URL": private_target,
        "Authorized treatment proxy URL": "",
        "Operator/lab ID": "operator-not-ready",
        "Authorization scope ID": private_scope,
        "Bounded scope summary": "not-ready scope summary",
        "Network region bucket": "region-not-ready",
        "Network type": "field-network-not-ready",
        "ISP/lab profile": "isp-not-ready",
        "Egress location bucket": "egress-not-ready",
        "Policy context": "policy-not-ready",
    }

    collector = _FakeScript(
        "collector",
        [(1, {"status": "INCOMPLETE", "failure": f"blocked {private_target}"})],
    )
    validator = _FakeScript(
        "validator",
        [(1, {"decision": "REJECTED", "failure": private_scope})],
    )
    importer = _FakeScript("importer", [(1, {"decision": "REJECTED"})])
    scripts = {
        "collect_external_dpi_proxy_reachability_evidence.py": collector,
        "verify_external_dpi_proxy_reachability_evidence.py": validator,
        "import_ghost_pulse_external_evidence.py": importer,
    }

    monkeypatch.setattr(module, "_prompt", lambda label, **_kwargs: values[label])
    monkeypatch.setattr(module, "_load_script", lambda name: scripts[name])

    report = module.run(module.parse_args(["--write-ready"]))
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "ACTION_REQUIRED"
    assert report["written"] is False
    assert report["blocking_reasons"] == [
        "collector_did_not_verify",
        "validator_not_ready",
        "import_preflight_not_ready",
        "write_import_not_performed",
    ]
    assert report["post_import_refresh_commands"] == module._post_import_refresh_commands()
    assert len(importer.calls) == 1
    assert "--treatment-proxy" not in collector.calls[0]
    assert module.REDACTED_LOCAL_INPUT in rendered
    assert private_target not in rendered
    assert private_scope not in rendered
