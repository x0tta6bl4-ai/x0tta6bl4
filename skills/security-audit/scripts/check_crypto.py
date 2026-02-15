#!/usr/bin/env python3
"""
Automated cryptographic compliance checker for x0tta6bl4.

Scans source files for known insecure patterns:
- XOR-based "encryption"
- Hardcoded keys/secrets
- Weak hash algorithms (MD5, SHA1 for auth)
- Missing nonce/IV generation
- Insecure random (random.random instead of secrets)

Exit code 0 = all checks passed, 1 = issues found.
"""

import os
import re
import sys
from pathlib import Path

INSECURE_PATTERNS = [
    # XOR cipher patterns
    (r'bytes\(\[.*\^.*for\s', "XOR cipher detected - use AES-256-GCM"),
    (r'xor_encrypt|xor_decrypt|xor_cipher', "XOR cipher function found"),

    # Weak hashing for auth
    (r'hashlib\.md5\(', "MD5 hash used - use bcrypt/scrypt for passwords, SHA-256+ for data"),
    (r'hashlib\.sha1\(', "SHA1 hash used - use SHA-256 or higher"),

    # Hardcoded secrets
    (r'password\s*=\s*["\'][^"\']{4,}["\']', "Possible hardcoded password"),
    (r'secret_key\s*=\s*["\'][^"\']{4,}["\']', "Possible hardcoded secret key"),
    (r'api_key\s*=\s*["\'][A-Za-z0-9]{16,}["\']', "Possible hardcoded API key"),

    # Insecure random
    (r'import random\b(?!.*secrets)', "Using `random` module - use `secrets` for crypto"),
    (r'random\.randint|random\.random\(\)|random\.choice', "Insecure random for crypto context"),

    # Disabled verification
    (r'verify\s*=\s*False', "SSL/TLS verification disabled"),
    (r'shell\s*=\s*True', "subprocess with shell=True - command injection risk"),

    # Issuer-subject matching instead of crypto verification
    (r'issuer.*==.*subject|subject.*==.*issuer', "Name-based cert validation instead of cryptographic"),
]

SAFE_IGNORE_DIRS = {
    '__pycache__', '.git', 'node_modules', '.venv', 'venv',
    'skills', 'docs', 'examples', 'data', 'assets',
}


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Scan a single Python file for insecure patterns."""
    findings = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()
    except Exception:
        return findings

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # Skip test files for some patterns (hardcoded passwords in tests are OK)
        is_test = 'test' in filepath.name.lower()

        for pattern, message in INSECURE_PATTERNS:
            if is_test and 'hardcoded' in message.lower():
                continue
            if re.search(pattern, line, re.IGNORECASE):
                findings.append((line_num, message, stripped[:120]))

    return findings


def main():
    src_dir = Path(__file__).resolve().parent.parent.parent.parent / 'src'
    if not src_dir.exists():
        print(f"ERROR: src directory not found at {src_dir}")
        sys.exit(2)

    total_findings = 0
    files_scanned = 0

    for py_file in sorted(src_dir.rglob('*.py')):
        if any(part in SAFE_IGNORE_DIRS for part in py_file.parts):
            continue

        findings = scan_file(py_file)
        files_scanned += 1

        if findings:
            rel_path = py_file.relative_to(src_dir.parent)
            for line_num, message, code in findings:
                print(f"  [{rel_path}:{line_num}] {message}")
                print(f"    > {code}")
                total_findings += 1

    print(f"\n{'='*60}")
    print(f"Scanned {files_scanned} files, found {total_findings} potential issues")

    if total_findings > 0:
        print("STATUS: ISSUES FOUND - review required")
        sys.exit(1)
    else:
        print("STATUS: ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
