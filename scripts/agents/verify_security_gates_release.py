#!/usr/bin/env python3
"""Local release verifier for the Security Gates product templates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DIR = ROOT / "products" / "security-gates"
TEMPLATE_DIR = ROOT / "templates" / "security"
DEFAULT_OUTPUT_BASE = PRODUCT_DIR / "out"

REQUIRED_TEMPLATE_FILES = {
    "scanner": TEMPLATE_DIR / "security-scan.sh",
    "gitlab_ci": TEMPLATE_DIR / "gitlab-ci-security.yml",
    "github_actions": TEMPLATE_DIR / "github-actions-security.yml",
    "trivy_config": TEMPLATE_DIR / "trivy.yaml",
    "template_readme": TEMPLATE_DIR / "README.md",
}

REQUIRED_PRODUCT_FILES = {
    "product_readme": PRODUCT_DIR / "README.md",
    "production_runbook": PRODUCT_DIR / "PRODUCTION.md",
}

REQUIRED_SNIPPETS = {
    "scanner": ["--trivy", "--snyk", "scan-results", "render_json_summary_html"],
    "gitlab_ci": ["scan-results", "security-scan.sh"],
    "github_actions": ["scan-results", "security-scan.sh"],
    "trivy_config": ["CRITICAL", "HIGH"],
    "template_readme": ["GitLab CI", "GitHub Actions", "Локальная самопроверка"],
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


def write_log(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def file_manifest_check(log_dir: Path) -> CheckResult:
    log_path = log_dir / "file_manifest.log"
    missing: list[str] = []
    empty: list[str] = []
    checked: dict[str, str] = {}

    for name, path in {**REQUIRED_TEMPLATE_FILES, **REQUIRED_PRODUCT_FILES}.items():
        checked[name] = str(path.relative_to(ROOT))
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
        elif path.stat().st_size == 0:
            empty.append(str(path.relative_to(ROOT)))

    details = []
    if missing:
        details.append(f"missing={missing}")
    if empty:
        details.append(f"empty={empty}")
    passed = not missing and not empty
    write_log(
        log_path,
        {
            "checked": checked,
            "missing": missing,
            "empty": empty,
            "passed": passed,
        },
    )
    return CheckResult(
        name="file_manifest",
        command=["python3", "scripts/agents/verify_security_gates_release.py", "file_manifest_check"],
        expected_exit=0,
        exit_code=0 if passed else 1,
        passed=passed,
        log_path=str(log_path),
        details="; ".join(details),
    )


def required_snippets_check(log_dir: Path) -> CheckResult:
    log_path = log_dir / "required_snippets.log"
    missing: dict[str, list[str]] = {}
    for name, snippets in REQUIRED_SNIPPETS.items():
        path = REQUIRED_TEMPLATE_FILES[name]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        absent = [snippet for snippet in snippets if snippet not in text]
        if absent:
            missing[str(path.relative_to(ROOT))] = absent

    passed = not missing
    write_log(log_path, {"missing": missing, "passed": passed})
    return CheckResult(
        name="required_snippets",
        command=["python3", "scripts/agents/verify_security_gates_release.py", "required_snippets_check"],
        expected_exit=0,
        exit_code=0 if passed else 1,
        passed=passed,
        log_path=str(log_path),
        details=f"missing={missing}" if missing else "",
    )


def run_command(
    name: str,
    command: list[str],
    log_dir: Path,
    *,
    expected_exit: int = 0,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    required_files: list[Path] | None = None,
    required_text: str = "",
) -> CheckResult:
    log_path = log_dir / f"{name}.log"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    stdout = result.stdout or ""
    details: list[str] = []
    passed = result.returncode == expected_exit
    if result.returncode != expected_exit:
        details.append(f"exit={result.returncode}, expected {expected_exit}")
    if required_text and required_text not in stdout:
        passed = False
        details.append(f"missing text: {required_text}")
    for path in required_files or []:
        if not path.exists():
            passed = False
            details.append(f"missing file: {path}")

    write_log(
        log_path,
        {
            "command": command,
            "cwd": str(cwd),
            "expected_exit": expected_exit,
            "exit_code": result.returncode,
            "stdout": stdout,
            "required_files": [str(path) for path in required_files or []],
            "passed": passed,
            "details": details,
        },
    )
    return CheckResult(
        name=name,
        command=command,
        expected_exit=expected_exit,
        exit_code=result.returncode,
        passed=passed,
        log_path=str(log_path),
        details="; ".join(details),
    )


def fake_trivy_scan_check(log_dir: Path) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="security-gates-release-") as tmp:
        tmp_path = Path(tmp)
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_trivy = fake_bin / "trivy"
        fake_trivy.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                out=""
                while [[ $# -gt 0 ]]; do
                  case "$1" in
                    -o)
                      out="$2"
                      shift 2
                      ;;
                    *)
                      shift
                      ;;
                  esac
                done
                cat >"$out" <<'JSON'
                {
                  "Results": [
                    {
                      "Target": "demo-image",
                      "Vulnerabilities": [
                        {"Severity": "CRITICAL"},
                        {"Severity": "HIGH"},
                        {"Severity": "HIGH"}
                      ]
                    }
                  ]
                }
                JSON
                """
            ),
            encoding="utf-8",
        )
        fake_trivy.chmod(0o755)
        env = {
            **dict(__import__("os").environ),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SECURITY_SCAN_TOOL_MODE": "native",
        }
        report = tmp_path / "scan-results" / "security-report.html"
        trivy_json = tmp_path / "scan-results" / "trivy-report.json"
        return run_command(
            "fake_trivy_scan",
            [
                "bash",
                str(TEMPLATE_DIR / "security-scan.sh"),
                "--trivy",
                "--severity",
                "HIGH",
                "--image",
                "demo-image:latest",
                "--output",
                "security-report.html",
            ],
            log_dir,
            cwd=tmp_path,
            env=env,
            required_files=[report, trivy_json],
            required_text="Report:",
        )


def release_decision(results: list[CheckResult]) -> str:
    if all(result.passed for result in results):
        return "READY_FOR_CLIENT_REPO_INSTALL"
    return "BLOCKED"


def build_payload(results: list[CheckResult], output_dir: Path, generated_at: str) -> dict[str, Any]:
    return {
        "product": "Security Gates",
        "generated_at_utc": generated_at,
        "output_dir": str(output_dir),
        "release_decision": release_decision(results),
        "checks_total": len(results),
        "checks_passed": sum(1 for result in results if result.passed),
        "checks_failed": sum(1 for result in results if not result.passed),
        "checks": [result.to_json() for result in results],
        "claim_boundary": (
            "Local templates are ready to install into a client CI repository after this verifier passes. "
            "This does not certify that the current repository has zero vulnerabilities or that a client CI "
            "environment has Snyk/Trivy credentials configured."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Security Gates Release Evidence",
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
        lines.append(f"| {check['name']} | {check['exit_code']} | {check['expected_exit']} | {result} |")
    lines.extend(["", "## Claim Boundary", "", payload["claim_boundary"], "", "## Logs", ""])
    lines.extend(f"- `{check['log_path']}`" for check in payload["checks"])
    return "\n".join(lines) + "\n"


def run_release_verification(output_dir: Path) -> dict[str, Any]:
    log_dir = output_dir / "logs"
    python = sys.executable or "python3"
    scanner = str((TEMPLATE_DIR / "security-scan.sh").relative_to(ROOT))
    results = [
        file_manifest_check(log_dir),
        required_snippets_check(log_dir),
        run_command("scanner_bash_syntax", ["bash", "-n", scanner], log_dir),
        fake_trivy_scan_check(log_dir),
        run_command(
            "unit_tests",
            [python, "-m", "pytest", "tests/unit/scripts/test_security_scan_template_unit.py", "-q", "--no-cov"],
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
    parser = argparse.ArgumentParser(description="Verify Security Gates release readiness")
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
