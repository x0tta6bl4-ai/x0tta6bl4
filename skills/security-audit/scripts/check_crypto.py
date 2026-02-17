#!/usr/bin/env python3
"""
Automated cryptographic compliance checker for x0tta6bl4.

Exit code policy:
- 0: no blocking findings (CRITICAL/HIGH)
- 1: one or more blocking findings
- 2: scanner/runtime error
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RegexRule:
    pattern: str
    message: str
    severity: str
    skip_on_tests: bool = False


@dataclass(frozen=True)
class Finding:
    severity: str
    line_num: int
    message: str
    code: str


BLOCKING_SEVERITIES = {"CRITICAL", "HIGH"}

REGEX_RULES = [
    RegexRule(
        r"bytes\(\[.*\^.*for\s",
        "XOR cipher detected - use AES-256-GCM",
        "CRITICAL",
    ),
    RegexRule(
        r"xor_encrypt|xor_decrypt|xor_cipher",
        "XOR cipher function found",
        "CRITICAL",
    ),
    RegexRule(
        r"hashlib\.md5\(",
        "MD5 hash used - use bcrypt/scrypt for passwords, SHA-256+ for data",
        "HIGH",
    ),
    RegexRule(
        r"hashlib\.sha1\(",
        "SHA1 hash used - use SHA-256 or higher",
        "HIGH",
    ),
    RegexRule(
        r"password\s*=\s*['\"][^'\"]{4,}['\"]",
        "Possible hardcoded password",
        "HIGH",
        skip_on_tests=True,
    ),
    RegexRule(
        r"secret_key\s*=\s*['\"][^'\"]{8,}['\"]",
        "Possible hardcoded secret key",
        "HIGH",
        skip_on_tests=True,
    ),
    RegexRule(
        r"api_key\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        "Possible hardcoded API key",
        "HIGH",
        skip_on_tests=True,
    ),
    RegexRule(
        r"verify\s*=\s*False",
        "SSL/TLS verification disabled",
        "HIGH",
    ),
    RegexRule(
        r"shell\s*=\s*True",
        "subprocess with shell=True - command injection risk",
        "HIGH",
    ),
    RegexRule(
        r"issuer.*==.*subject|subject.*==.*issuer",
        "Name-based cert validation instead of cryptographic verification",
        "MEDIUM",
    ),
]

SAFE_IGNORE_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "skills",
    "docs",
    "examples",
    "data",
    "assets",
}

SENSITIVE_PATH_HINTS = (
    "security",
    "crypto",
    "vault",
    "auth",
    "token",
    "jwt",
    "tls",
    "mtls",
    "spiffe",
    "certificate",
    "cert",
    "zero_trust",
)

SENSITIVE_RANDOM_LINE_HINTS = (
    "token",
    "secret",
    "key",
    "nonce",
    "iv",
    "salt",
    "password",
    "session",
    "jwt",
    "signature",
    "packet_id",
    "cipher",
    "crypto",
)

RANDOM_USAGE_RE = re.compile(r"\brandom\.(randint|random|choice|choices)\b")


def _is_test_file(filepath: Path) -> bool:
    return "test" in filepath.name.lower()


def _is_sensitive_path(filepath: Path) -> bool:
    path_lower = str(filepath).lower()
    return any(hint in path_lower for hint in SENSITIVE_PATH_HINTS)


def _scan_random_usage(filepath: Path, line: str, stripped: str) -> Finding | None:
    if stripped.startswith("#"):
        return None

    lower_line = line.lower()
    if "import random" in lower_line:
        if _is_sensitive_path(filepath):
            return Finding(
                severity="MEDIUM",
                line_num=0,
                message="`random` imported in security-sensitive module; verify this is non-cryptographic.",
                code=stripped[:120],
            )
        return None

    if not RANDOM_USAGE_RE.search(line):
        return None

    if "random.seed(" in lower_line:
        return None

    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", lower_line))
    if any(hint in tokens for hint in SENSITIVE_RANDOM_LINE_HINTS):
        severity = "HIGH" if _is_sensitive_path(filepath) else "MEDIUM"
        return Finding(
            severity=severity,
            line_num=0,
            message="`random.*` used for security-sensitive value; use `secrets`/`os.urandom`.",
            code=stripped[:120],
        )

    return None


def scan_file(filepath: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    is_test = _is_test_file(filepath)
    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for rule in REGEX_RULES:
            if rule.skip_on_tests and is_test:
                continue
            if re.search(rule.pattern, line, re.IGNORECASE):
                findings.append(
                    Finding(
                        severity=rule.severity,
                        line_num=line_num,
                        message=rule.message,
                        code=stripped[:120],
                    )
                )

        random_finding = _scan_random_usage(filepath, line, stripped)
        if random_finding is not None:
            findings.append(
                Finding(
                    severity=random_finding.severity,
                    line_num=line_num,
                    message=random_finding.message,
                    code=random_finding.code,
                )
            )

    return findings


def main() -> int:
    src_dir = Path(__file__).resolve().parent.parent.parent.parent / "src"
    if not src_dir.exists():
        print(f"ERROR: src directory not found at {src_dir}")
        return 2

    all_findings: list[tuple[Path, Finding]] = []
    files_scanned = 0

    for py_file in sorted(src_dir.rglob("*.py")):
        if any(part in SAFE_IGNORE_DIRS for part in py_file.parts):
            continue

        files_scanned += 1
        file_findings = scan_file(py_file)
        for finding in file_findings:
            all_findings.append((py_file.relative_to(src_dir.parent), finding))

    severity_counts: Counter[str] = Counter()
    for _, finding in all_findings:
        severity_counts[finding.severity] += 1

    for rel_path, finding in all_findings:
        print(f"  [{rel_path}:{finding.line_num}] [{finding.severity}] {finding.message}")
        print(f"    > {finding.code}")

    blocking_count = sum(severity_counts.get(s, 0) for s in BLOCKING_SEVERITIES)
    total_findings = len(all_findings)

    print(f"\n{'=' * 60}")
    print(f"Scanned {files_scanned} files, found {total_findings} findings")
    print(
        "Severity breakdown: "
        f"critical={severity_counts.get('CRITICAL', 0)} "
        f"high={severity_counts.get('HIGH', 0)} "
        f"medium={severity_counts.get('MEDIUM', 0)} "
        f"low={severity_counts.get('LOW', 0)}"
    )

    if blocking_count > 0:
        print("STATUS: BLOCKING ISSUES FOUND")
        return 1

    if total_findings > 0:
        print("STATUS: No blocking issues. Advisory findings require review.")
        return 0

    print("STATUS: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
