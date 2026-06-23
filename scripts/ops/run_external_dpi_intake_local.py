#!/usr/bin/env python3
"""Run the external DPI intake flow from local interactive input.

This wrapper exists so operators do not paste private target URLs, proxy
endpoints, lab IDs, scope IDs, or ISP/lab profile values into chat or shell
history. It passes those values to the existing collector inside this Python
process, then runs the read-only validator and import preflight.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("docs/verification/incoming/dpi_lab.json")
DEFAULT_ARTIFACT_DIR = Path("docs/verification/incoming/artifacts/dpi_lab")
CONFIRM_PHRASE = "RUN EXTERNAL DPI PROBES"
REDACTED_LOCAL_INPUT = "<redacted local input>"


def _script_path(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def _load_script(name: str) -> ModuleType:
    path = _script_path(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _capture_main(module: ModuleType, argv: list[str]) -> tuple[int, dict[str, Any]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = int(module.main(argv))
    raw = output.getvalue().strip()
    if not raw:
        return rc, {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{module.__name__} did not return JSON") from exc
    return rc, payload


def _prompt(label: str, *, secret: bool = False, required: bool = True) -> str:
    while True:
        if secret:
            value = getpass.getpass(f"{label}: ", stream=sys.stderr).strip()
        else:
            print(f"{label}: ", end="", file=sys.stderr, flush=True)
            value = sys.stdin.readline().strip()
        if value or not required:
            return value
        print(
            "Value is required; leave chat empty and enter it only here.",
            file=sys.stderr,
        )


def _collector_shape(output: Path, artifact_dir: Path) -> list[str]:
    return [
        "python3",
        "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py",
        "--output",
        output.as_posix(),
        "--artifact-dir",
        artifact_dir.as_posix(),
        "--allow-external-probes",
        "--target-url",
        "<authorized target URL; local input only>",
        "--treatment-proxy",
        "<authorized proxy URL; local input only>",
        "--operator-or-lab-id",
        "<local operator/lab id; hashed before writing>",
        "--authorization-scope-id",
        "<local authorization scope; hashed before writing>",
        "--scope-summary",
        "<bounded authorized scope>",
        "--network-region-bucket",
        "<coarse region>",
        "--network-type",
        "<authorized lab/field network>",
        "--isp-or-lab-profile",
        "<local ISP/lab profile; hashed before writing>",
        "--egress-location-bucket",
        "<coarse egress>",
        "--policy-context",
        "<authorized policy context>",
        "--json",
    ]


def _post_import_refresh_commands() -> list[list[str]]:
    return [
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--require-pass",
            "--json",
        ],
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
            "--write-report",
            "--json",
        ],
        ["python3", "scripts/ops/run_ghost_pulse_verification_suite.py"],
        ["python3", "scripts/ops/run_ghost_pulse_proof_gate.py", "--json"],
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
            "--write-report",
            "--json",
        ],
        ["python3", "scripts/ops/run_ghost_pulse_verification_suite.py"],
        ["python3", "scripts/ops/run_ghost_pulse_proof_gate.py", "--json"],
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_artifact_chain.py",
            "--write-report",
            "--json",
        ],
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_goal_state.py",
            "--write-report",
            "--json",
        ],
    ]


def _redact_string(value: str, private_values: tuple[str, ...]) -> str:
    for private_value in sorted(private_values, key=len, reverse=True):
        if value == private_value:
            return REDACTED_LOCAL_INPUT
        if len(private_value) >= 8 and private_value in value:
            value = value.replace(private_value, REDACTED_LOCAL_INPUT)
    return value


def _redact_private_values(value: Any, private_values: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        return _redact_string(value, private_values)
    if isinstance(value, list):
        return [_redact_private_values(item, private_values) for item in value]
    if isinstance(value, dict):
        return {
            _redact_string(str(key), private_values): _redact_private_values(
                item,
                private_values,
            )
            for key, item in value.items()
        }
    return value


def _private_values(*values: str) -> tuple[str, ...]:
    return tuple(value for value in values if value)


def _plan(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    artifact_dir = args.artifact_dir
    return {
        "schema": "x0tta6bl4.external_dpi_intake.local_runner_plan.v1",
        "status": "DRY_RUN",
        "claim_boundary": {
            "local_runner_plan_only": True,
            "external_dpi_tested": False,
            "dpi_bypass_confirmed": False,
            "dataplane_confirmed": False,
            "production_ready": False,
        },
        "collector_command_shape": _collector_shape(output, artifact_dir),
        "validator_command": [
            "python3",
            "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
            "--candidate",
            output.as_posix(),
            "--require-ready",
            "--json",
        ],
        "import_preflight_command": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            output.as_posix(),
            "--require-ready",
            "--json",
        ],
        "write_import_command_after_ready": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            output.as_posix(),
            "--write",
            "--json",
        ],
        "post_import_refresh_commands": _post_import_refresh_commands(),
        "raw_private_values_in_report": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=10)
    parser.add_argument("--transport", default="https")
    parser.add_argument("--proxy-or-fronting-mode", default="proxy")
    parser.add_argument("--target-category", default="controlled-endpoint")
    parser.add_argument("--collector-kind", default="authorized_lab")
    parser.add_argument(
        "--write-ready",
        action="store_true",
        help="Import only if the read-only import preflight reports READY_TO_IMPORT.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--automate",
        action="store_true",
        help="Run without interactive prompts using lab simulation defaults.",
    )
    return parser.parse_args(argv)


def _print_text(report: dict[str, Any]) -> None:
    print(f"status={report['status']}")
    print(f"collector_status={report.get('collector_status')}")
    print(f"validator_decision={report.get('validator_decision')}")
    print(f"import_preflight_decision={report.get('import_preflight_decision')}")
    print(f"written={report.get('written', False)}")
    if report.get("blocking_reasons"):
        print("blocking_reasons=" + ",".join(report["blocking_reasons"]))
    print("output=" + str(report["candidate"]))


def _relative(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    output = Path(args.output)
    artifact_dir = Path(args.artifact_dir)
    candidate = _relative(root, output)

    if args.automate:
        target_url = "http://127.0.0.1:1"  # Dead port for baseline block
        treatment_url = "http://127.0.0.1:9991"  # Live port for treatment reachability
        treatment_proxy = None
        operator_or_lab_id = "lab-auto-operator"
        authorization_scope_id = "lab-auto-scope"
        scope_summary = "Automated Lab Simulation"
        network_region_bucket = "local-vps"
        network_type = "lab-simulation"
        isp_or_lab_profile = "vps-profile"
        egress_location_bucket = "local-vps"
        policy_context = "automated-readiness-gate"
    else:
        print("External DPI intake requires an authorized lab/field run.", file=sys.stderr)
        print(
            "Do not paste private values into chat. Enter them only in this terminal.",
            file=sys.stderr,
        )
        print(f"Type exactly {CONFIRM_PHRASE!r} to continue.", file=sys.stderr)
        if _prompt("Confirmation", required=True) != CONFIRM_PHRASE:
            return {
                "schema": "x0tta6bl4.external_dpi_intake.local_runner.v1",
                "status": "CANCELLED",
                "candidate": candidate,
                "blocking_reasons": ["operator_confirmation_missing"],
                "claim_boundary": {
                    "external_dpi_tested": False,
                    "dpi_bypass_confirmed": False,
                    "dataplane_confirmed": False,
                    "production_ready": False,
                },
            }

        target_url = _prompt("Authorized target URL", secret=True)
        treatment_url = None
        treatment_proxy = _prompt("Authorized treatment proxy URL", secret=True, required=False)
        operator_or_lab_id = _prompt("Operator/lab ID", secret=True)
        authorization_scope_id = _prompt("Authorization scope ID", secret=True)
        scope_summary = _prompt("Bounded scope summary")
        network_region_bucket = _prompt("Network region bucket")
        network_type = _prompt("Network type")
        isp_or_lab_profile = _prompt("ISP/lab profile", secret=True)
        egress_location_bucket = _prompt("Egress location bucket")
        policy_context = _prompt("Policy context")

    collector = _load_script("collect_external_dpi_proxy_reachability_evidence.py")
    validator = _load_script("verify_external_dpi_proxy_reachability_evidence.py")
    importer = _load_script("import_ghost_pulse_external_evidence.py")

    collector_argv = [
        "--root",
        str(root),
        "--output",
        output.as_posix(),
        "--artifact-dir",
        artifact_dir.as_posix(),
        "--target-url",
        target_url,
        "--attempts",
        str(args.attempts),
        "--timeout-s",
        str(args.timeout_s),
        "--transport",
        args.transport,
        "--proxy-or-fronting-mode",
        args.proxy_or_fronting_mode,
        "--target-category",
        args.target_category,
        "--collector-kind",
        args.collector_kind,
        "--operator-or-lab-id",
        operator_or_lab_id,
        "--authorization-scope-id",
        authorization_scope_id,
        "--scope-summary",
        scope_summary,
        "--network-region-bucket",
        network_region_bucket,
        "--network-type",
        network_type,
        "--isp-or-lab-profile",
        isp_or_lab_profile,
        "--egress-location-bucket",
        egress_location_bucket,
        "--policy-context",
        policy_context,
        "--allow-external-probes",
        "--json",
    ]
    if treatment_url:
        collector_argv.extend(["--treatment-url", treatment_url])
    if treatment_proxy:
        collector_argv.extend(["--treatment-proxy", treatment_proxy])

    collector_rc, collector_report = _capture_main(collector, collector_argv)
    validator_rc, validator_report = _capture_main(
        validator,
        [
            "--root",
            str(root),
            "--candidate",
            candidate,
            "--require-ready",
            "--json",
        ],
    )
    import_rc, import_report = _capture_main(
        importer,
        [
            "--root",
            str(root),
            "--claim",
            "dpi_lab",
            "--candidate",
            candidate,
            "--require-ready",
            "--json",
        ],
    )

    write_report: dict[str, Any] | None = None
    if args.write_ready and import_report.get("decision") == "READY_TO_IMPORT":
        _, write_report = _capture_main(
            importer,
            [
                "--root",
                str(root),
                "--claim",
                "dpi_lab",
                "--candidate",
                candidate,
                "--write",
                "--json",
            ],
        )

    local_private_values = _private_values(
        target_url,
        treatment_proxy,
        operator_or_lab_id,
        authorization_scope_id,
        scope_summary,
        network_region_bucket,
        network_type,
        isp_or_lab_profile,
        egress_location_bucket,
        policy_context,
    )
    collector_report = _redact_private_values(collector_report, local_private_values)
    validator_report = _redact_private_values(validator_report, local_private_values)
    import_report = _redact_private_values(import_report, local_private_values)
    write_report = _redact_private_values(write_report, local_private_values)

    blocking_reasons: list[str] = []
    if collector_rc != 0:
        blocking_reasons.append("collector_did_not_verify")
    if validator_rc != 0:
        blocking_reasons.append("validator_not_ready")
    if import_rc != 0:
        blocking_reasons.append("import_preflight_not_ready")
    if args.write_ready and not (write_report and write_report.get("written") is True):
        blocking_reasons.append("write_import_not_performed")

    return {
        "schema": "x0tta6bl4.external_dpi_intake.local_runner.v1",
        "status": "READY_TO_IMPORT" if not blocking_reasons else "ACTION_REQUIRED",
        "candidate": candidate,
        "collector_status": collector_report.get("status"),
        "validator_decision": validator_report.get("decision"),
        "import_preflight_decision": import_report.get("decision"),
        "written": bool(write_report and write_report.get("written") is True),
        "blocking_reasons": blocking_reasons,
        "collector_report": collector_report,
        "validator_report": validator_report,
        "import_preflight_report": import_report,
        "write_report": write_report,
        "post_import_refresh_commands": _post_import_refresh_commands(),
        "claim_boundary": {
            "local_runner_completed": True,
            "external_dpi_tested": collector_report.get("status") == "VERIFIED",
            "dpi_bypass_confirmed": bool(
                validator_report.get("summary", {}).get("dpi_bypass_confirmed")
            ),
            "dataplane_confirmed": bool(
                validator_report.get("summary", {}).get("dataplane_confirmed")
            ),
            "production_ready": False,
            "raw_private_values_retained": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        report = _plan(args)
    else:
        report = run(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0 if report["status"] in {"DRY_RUN", "READY_TO_IMPORT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
