#!/usr/bin/env python3
"""Local release verifier for the Agent Work Receipt Gate product."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DIR = ROOT / "products" / "agent-work-receipt-gate"
POLICY = PRODUCT_DIR / "policy.example.json"
VALID_RECEIPT = PRODUCT_DIR / "receipts" / "valid.json"
INVALID_RECEIPT = PRODUCT_DIR / "receipts" / "invalid-missing-verification.json"
CLI = ROOT / "scripts" / "agents" / "agent_work_receipt_gate.py"
DEFAULT_OUTPUT_BASE = PRODUCT_DIR / "out"
PROTOCOL_DOCS = [
    ROOT / "docs" / "agent-engineering" / "MANIFESTO.md",
    ROOT / "docs" / "agent-engineering" / "VERIFIED_AGENT_WORK_PROTOCOL.md",
    ROOT / "docs" / "agent-engineering" / "DEMO.md",
    ROOT / "docs" / "agent-engineering" / "FAILURE_CASES.md",
]
FAILURE_RECEIPTS = {
    "invalid_forbidden_claim": PRODUCT_DIR / "receipts" / "invalid-forbidden-claim.json",
    "invalid_missing_source_truth": PRODUCT_DIR / "receipts" / "invalid-missing-source-truth.json",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: list[str]
    expected_exit: int
    exit_code: int
    passed: bool
    log_path: str
    details: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "expected_exit": self.expected_exit,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "log_path": self.log_path,
            "details": self.details,
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def run_command(
    name: str,
    command: list[str],
    log_dir: Path,
    *,
    expected_exit: int = 0,
    require_json_ok: bool | None = None,
    required_text: str = "",
    required_json_field: tuple[str, Any] | None = None,
) -> CheckResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    stdout = result.stdout or ""
    parsed = parse_json_stdout(stdout)
    details: list[str] = []
    passed = result.returncode == expected_exit

    if require_json_ok is not None:
        json_ok = parsed.get("ok")
        if json_ok is not require_json_ok:
            passed = False
            details.append(f"json.ok={json_ok!r}, expected {require_json_ok!r}")

    if required_json_field is not None:
        key, expected = required_json_field
        observed = parsed.get(key)
        if observed != expected:
            passed = False
            details.append(f"json.{key}={observed!r}, expected {expected!r}")

    if required_text and required_text not in stdout:
        passed = False
        details.append(f"missing text: {required_text}")

    if result.returncode != expected_exit:
        details.append(f"exit={result.returncode}, expected {expected_exit}")

    log_payload = {
        "name": name,
        "command": command,
        "expected_exit": expected_exit,
        "exit_code": result.returncode,
        "stdout": stdout,
        "parsed_json": parsed,
        "passed": passed,
        "details": details,
    }
    log_path.write_text(json.dumps(log_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    return CheckResult(
        name=name,
        command=command,
        expected_exit=expected_exit,
        exit_code=result.returncode,
        passed=passed,
        log_path=str(log_path),
        details="; ".join(details),
    )


def run_static_artifact_check(log_dir: Path) -> CheckResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "protocol_artifacts.log"
    required_text = {
        PROTOCOL_DOCS[0]: "No agent closes work by assertion.",
        PROTOCOL_DOCS[1]: "Verified Agent Work Protocol",
        PROTOCOL_DOCS[2]: "invalid-missing-verification.json",
        PROTOCOL_DOCS[3]: "handoff.invalid.missing_verification",
    }
    errors: list[str] = []

    for path, needle in required_text.items():
        if not path.exists():
            errors.append(f"missing artifact: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing marker {needle!r} in {path.relative_to(ROOT)}")

    for name, path in FAILURE_RECEIPTS.items():
        if not path.exists():
            errors.append(f"missing failure receipt {name}: {path.relative_to(ROOT)}")
            continue
        parsed = parse_json_stdout(path.read_text(encoding="utf-8"))
        if not parsed:
            errors.append(f"failure receipt is not a JSON object: {path.relative_to(ROOT)}")

    passed = not errors
    log_payload = {
        "name": "protocol_artifacts",
        "command": ["static-artifact-check", "docs/agent-engineering", "products/agent-work-receipt-gate/receipts"],
        "expected_exit": 0,
        "exit_code": 0 if passed else 1,
        "passed": passed,
        "errors": errors,
    }
    log_path.write_text(json.dumps(log_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return CheckResult(
        name="protocol_artifacts",
        command=log_payload["command"],
        expected_exit=0,
        exit_code=0 if passed else 1,
        passed=passed,
        log_path=str(log_path),
        details="; ".join(errors),
    )


def release_decision(results: list[CheckResult]) -> str:
    if all(result.passed for result in results):
        return "READY_FOR_CLIENT_REPO_INSTALL"
    return "BLOCKED"


def build_payload(results: list[CheckResult], output_dir: Path, generated_at: str) -> dict[str, Any]:
    return {
        "product": "Agent Work Receipt Gate",
        "generated_at_utc": generated_at,
        "output_dir": str(output_dir),
        "release_decision": release_decision(results),
        "checks_total": len(results),
        "checks_passed": sum(1 for result in results if result.passed),
        "checks_failed": sum(1 for result in results if not result.passed),
        "checks": [result.to_json() for result in results],
        "claim_boundary": (
            "Local product package is ready to install into a client repo after this verifier passes. "
            "It does not prove production status for Ghost Access, SPB, NL, or any external runtime."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Work Receipt Gate Release Evidence",
        "",
        f"- Product: {payload['product']}",
        f"- Generated: {payload['generated_at_utc']}",
        f"- Decision: {payload['release_decision']}",
        f"- Checks: {payload['checks_passed']}/{payload['checks_total']} passed",
        "",
        "## Checks",
        "",
        "| Check | Exit | Expected | Result |",
        "|---|---:|---:|---|",
    ]
    for check in payload["checks"]:
        result = "PASS" if check["passed"] else "FAIL"
        lines.append(
            f"| {check['name']} | {check['exit_code']} | {check['expected_exit']} | {result} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            payload["claim_boundary"],
            "",
            "## Logs",
            "",
        ]
    )
    lines.extend(f"- `{check['log_path']}`" for check in payload["checks"])
    return "\n".join(lines) + "\n"


def run_release_verification(output_dir: Path) -> dict[str, Any]:
    log_dir = output_dir / "logs"
    python = sys.executable or "python3"

    results = [
        run_command(
            "py_compile",
            [
                python,
                "-m",
                "py_compile",
                str(CLI.relative_to(ROOT)),
                str(Path(__file__).resolve().relative_to(ROOT)),
            ],
            log_dir,
        ),
        run_static_artifact_check(log_dir),
        run_command(
            "valid_receipt",
            [
                python,
                str(CLI.relative_to(ROOT)),
                "validate",
                "--policy",
                str(POLICY.relative_to(ROOT)),
                "--receipt",
                str(VALID_RECEIPT.relative_to(ROOT)),
                "--json",
            ],
            log_dir,
            require_json_ok=True,
        ),
        run_command(
            "invalid_receipt",
            [
                python,
                str(CLI.relative_to(ROOT)),
                "validate",
                "--policy",
                str(POLICY.relative_to(ROOT)),
                "--receipt",
                str(INVALID_RECEIPT.relative_to(ROOT)),
                "--json",
            ],
            log_dir,
            expected_exit=2,
            require_json_ok=False,
            required_json_field=("failure_signature", "handoff.invalid.missing_verification"),
        ),
        run_command(
            "invalid_forbidden_claim",
            [
                python,
                str(CLI.relative_to(ROOT)),
                "validate",
                "--policy",
                str(POLICY.relative_to(ROOT)),
                "--receipt",
                str(FAILURE_RECEIPTS["invalid_forbidden_claim"].relative_to(ROOT)),
                "--json",
            ],
            log_dir,
            expected_exit=2,
            require_json_ok=False,
            required_json_field=("failure_signature", "receipt.invalid.forbidden_claim"),
        ),
        run_command(
            "invalid_missing_source_truth",
            [
                python,
                str(CLI.relative_to(ROOT)),
                "validate",
                "--policy",
                str(POLICY.relative_to(ROOT)),
                "--receipt",
                str(FAILURE_RECEIPTS["invalid_missing_source_truth"].relative_to(ROOT)),
                "--json",
            ],
            log_dir,
            expected_exit=2,
            require_json_ok=False,
            required_json_field=("failure_signature", "receipt.invalid.missing_source_of_truth"),
        ),
        run_command(
            "markdown_report",
            [
                python,
                str(CLI.relative_to(ROOT)),
                "report",
                "--policy",
                str(POLICY.relative_to(ROOT)),
                "--receipt",
                str(VALID_RECEIPT.relative_to(ROOT)),
            ],
            log_dir,
            required_text="Status: PASS",
        ),
        run_command(
            "unit_tests",
            [python, "-m", "pytest", "tests/unit/scripts/test_agent_work_receipt_gate.py", "-q", "--no-cov"],
            log_dir,
        ),
        run_command(
            "claim_hygiene",
            [
                python,
                "scripts/claim_hygiene_scan.py",
                "--zone",
                "active_claim_surface",
                "--fail-on-active",
            ],
            log_dir,
        ),
    ]

    generated_at = utc_stamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(results, output_dir, generated_at)
    (output_dir / "release-evidence.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "release-evidence.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Agent Work Receipt Gate release readiness")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for release-evidence.json, release-evidence.md, and logs",
    )
    parser.add_argument("--json", action="store_true", help="Print the full release payload as JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_BASE / f"release-{utc_stamp()}"
    payload = run_release_verification(output_dir)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(f"decision={payload['release_decision']}")
        print(f"checks={payload['checks_passed']}/{payload['checks_total']}")
        print(f"evidence={output_dir / 'release-evidence.json'}")
    return 0 if payload["release_decision"] == "READY_FOR_CLIENT_REPO_INSTALL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
