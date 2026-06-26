"""Executable X0T contract package build verification.

This verifier runs the contract package compile/test path with an explicit
Node 22 runtime. It may update local Hardhat cache/artifacts, but it does not
call RPC, deploy contracts, submit transactions, or mutate chain state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.security.subprocess_validator import safe_run


SCHEMA_VERSION = "x0tta6bl4-x0t-contract-build-verification-v1"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/x0t-contract-build-verification-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/x0t-contract-build-verification-2026-05-21.md"
CONTRACT_PACKAGE_DIR = "src/dao/contracts"
REQUIRED_NODE_PACKAGE = "node@22.10.0"
HARDHAT_CLI = "node_modules/hardhat/dist/src/cli.js"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "returncode": self.returncode,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
            "stdout_tail": _tail(self.stdout),
            "stderr_tail": _tail(self.stderr),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _tail(value: str, *, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _node22_command(*args: str) -> List[str]:
    return ["npx", "-y", "-p", REQUIRED_NODE_PACKAGE, "node", *args]


def _run_command(name: str, command: List[str], cwd: Path, timeout: int) -> CommandResult:
    started = time.monotonic()
    try:
        result = safe_run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = (stderr + f"\ncommand timed out after {timeout}s").strip()
    except Exception as exc:
        returncode = 127
        stdout = ""
        stderr = str(exc)
    duration_ms = int((time.monotonic() - started) * 1000)
    return CommandResult(name, command, returncode, stdout, stderr, duration_ms)


def build_report(root: Path, *, timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS) -> Dict[str, Any]:
    package_dir = _resolve(root, CONTRACT_PACKAGE_DIR)
    package_json = package_dir / "package.json"
    hardhat_cli = package_dir / HARDHAT_CLI

    preflight_errors: List[str] = []
    if not package_json.exists():
        preflight_errors.append(f"missing package.json: {CONTRACT_PACKAGE_DIR}/package.json")
    if not hardhat_cli.exists():
        preflight_errors.append(f"missing Hardhat CLI: {CONTRACT_PACKAGE_DIR}/{HARDHAT_CLI}")

    commands: List[CommandResult] = []
    if not preflight_errors:
        commands.append(
            _run_command(
                "node_version",
                _node22_command("--version"),
                package_dir,
                min(timeout, 60),
            )
        )
        if commands[-1].ok:
            commands.append(
                _run_command(
                    "hardhat_compile",
                    _node22_command(HARDHAT_CLI, "compile"),
                    package_dir,
                    timeout,
                )
            )
        if commands and commands[-1].ok:
            commands.append(
                _run_command(
                    "hardhat_test",
                    _node22_command(HARDHAT_CLI, "test", "--no-compile"),
                    package_dir,
                    timeout,
                )
            )

    command_payloads = [item.to_dict() for item in commands]
    command_names_ok = {item.name for item in commands if item.ok}
    node_ready = "node_version" in command_names_ok and any(
        item.name == "node_version" and item.stdout.strip().startswith("v22.10.")
        for item in commands
    )
    compile_ready = "hardhat_compile" in command_names_ok
    test_ready = "hardhat_test" in command_names_ok
    ready = not preflight_errors and node_ready and compile_ready and test_ready

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "X0T_CONTRACT_BUILD_VERIFIED" if ready else "X0T_CONTRACT_BUILD_BLOCKED",
        "contract_build_verified": ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "mutates_local_build_artifacts": True,
        "claim_boundary": (
            "Runs local Hardhat compile/test under Node 22 via npx. This may update local "
            "Hardhat artifacts/cache; the test phase uses --no-compile after the explicit "
            "compile phase. It does not deploy contracts, call live RPC, submit transactions, "
            "mutate chain/runtime state, or close /goal."
        ),
        "source_artifacts": [
            f"{CONTRACT_PACKAGE_DIR}/package.json",
            f"{CONTRACT_PACKAGE_DIR}/package-lock.json",
            f"{CONTRACT_PACKAGE_DIR}/hardhat.config.js",
            f"{CONTRACT_PACKAGE_DIR}/{HARDHAT_CLI}",
        ],
        "preflight_errors": preflight_errors,
        "commands": command_payloads,
        "summary": {
            "required_node_package": REQUIRED_NODE_PACKAGE,
            "required_node_runtime_ready": node_ready,
            "hardhat_compile_ready": compile_ready,
            "hardhat_test_ready": test_ready,
            "commands_total": len(commands),
            "commands_failed": sum(1 for item in commands if not item.ok),
            "preflight_errors_total": len(preflight_errors),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# X0T Contract Build Verification",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Decision: `{report.get('decision', '')}`",
        f"Contract build verified: `{report.get('contract_build_verified')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Summary",
        "",
        f"- required node package: `{summary.get('required_node_package')}`",
        f"- required node runtime ready: `{summary.get('required_node_runtime_ready')}`",
        f"- hardhat compile ready: `{summary.get('hardhat_compile_ready')}`",
        f"- hardhat test ready: `{summary.get('hardhat_test_ready')}`",
        f"- commands failed: `{summary.get('commands_failed')}`",
        "",
        "## Commands",
        "",
    ]
    for item in report.get("commands", []):
        if isinstance(item, dict):
            lines.append(
                f"- `{item.get('name')}`: ok=`{item.get('ok')}`, returncode=`{item.get('returncode')}`"
            )
    if not report.get("commands"):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "X0T Contract Build Verification",
            f"decision: {report.get('decision')}",
            f"contract_build_verified: {report.get('contract_build_verified')}",
            f"required_node_runtime_ready: {summary.get('required_node_runtime_ready')}",
            f"hardhat_compile_ready: {summary.get('hardhat_compile_ready')}",
            f"hardhat_test_ready: {summary.get('hardhat_test_ready')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify X0T contract compile/test under Node 22")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--write-json", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--timeout", type=int, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root, timeout=args.timeout)
    if args.write_json:
        write_json(_resolve(root, args.output_json), report)
    if args.write_md:
        md_path = _resolve(root, args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")

    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_verified and not report["contract_build_verified"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
