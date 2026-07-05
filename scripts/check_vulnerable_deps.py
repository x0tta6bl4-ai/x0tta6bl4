#!/usr/bin/env python3
"""Check which Dependabot CVEs affect installed packages."""

import subprocess
import sys
from packaging.version import Version
from packaging.specifiers import SpecifierSet

# Dependabot alerts: package -> (vulnerable_range, severity, summary)
VULNS = {
    "cryptography": {
        "range": ">=0.5.0,<48.0.1",
        "severity": "HIGH",
        "summary": "Vulnerable OpenSSL in wheels + Subgroup Attack",
    },
    "starlette": {
        "range": ">=0.4.1,<1.3.1",
        "severity": "HIGH",
        "summary": "SSRF via UNC paths + DoS via form()",
    },
    "PyJWT": {
        "range": "<2.13.0",
        "severity": "HIGH",
        "summary": "HS256 token forging",
    },
    "transformers": {
        "range": "<5.3.0",
        "severity": "HIGH",
        "summary": "Remote code execution",
    },
    "python-socketio": {
        "range": "<=5.16.1",
        "severity": "HIGH",
        "summary": "DoS via binary attachments",
    },
    "nltk": {
        "range": "<=3.9.4",
        "severity": "HIGH",
        "summary": "Path Traversal → arbitrary file read",
    },
    "golang.org/x/net": {
        "range": "<0.55.0",
        "severity": "MEDIUM",
        "summary": "DoS in HTML parser",
    },
    "js-yaml": {
        "range": ">=4.0.0,<=4.1.1",
        "severity": "MEDIUM",
        "summary": "DoS via merge keys",
    },
    "pyjwt": {
        "range": "<2.13.0",
        "severity": "MEDIUM",
        "summary": "DoS, SSRF, algorithm bypass",
    },
    "diskcache": {
        "range": "<=5.6.3",
        "severity": "MEDIUM",
        "summary": "Unsafe pickle deserialization",
    },
    "node-tar": {
        "range": "<=7.5.15",
        "severity": "MEDIUM",
        "summary": "File smuggling via PAX headers",
    },
    "glib": {
        "range": ">=0.15.0,<0.20.0",
        "severity": "MEDIUM",
        "summary": "Unsoundness in Iterator",
    },
    "torch": {
        "range": "<=2.12.0",
        "severity": "LOW",
        "summary": "Memory corruption via jit.script",
    },
    "@babel/core": {
        "range": "<=7.29.0",
        "severity": "LOW",
        "summary": "Arbitrary file read via sourceMappingURL",
    },
}


def get_installed_version(pkg_name: str) -> str | None:
    """Get installed package version via pip."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", pkg_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def is_vulnerable(installed: str, vuln_range: str) -> bool:
    """Check if installed version matches vulnerable range."""
    try:
        ver = Version(installed)
        spec = SpecifierSet(vuln_range)
        return ver in spec
    except Exception:
        return False


def main():
    print("=" * 70)
    print("DEPENDABOT CVE CHECKER")
    print("=" * 70)
    print()

    found = 0
    vulnerable = 0
    safe = 0

    for pkg, info in sorted(VULNS.items()):
        installed = get_installed_version(pkg)
        if installed is None:
            status = "NOT INSTALLED"
            icon = "⬜"
        elif is_vulnerable(installed, info["range"]):
            status = f"VULNERABLE ({installed})"
            icon = "🔴"
            vulnerable += 1
        else:
            status = f"SAFE ({installed})"
            icon = "✅"
            safe += 1
        found += 1
        print(f"  {icon} {pkg:25s} {status:35s} {info['severity']:8s}")

    print()
    print("=" * 70)
    print(f"Total CVEs checked: {found}")
    print(f"  🔴 Vulnerable: {vulnerable}")
    print(f"  ✅ Safe: {safe}")
    print(f"  ⬜ Not installed: {found - vulnerable - safe}")
    print("=" * 70)

    return 0 if vulnerable == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
