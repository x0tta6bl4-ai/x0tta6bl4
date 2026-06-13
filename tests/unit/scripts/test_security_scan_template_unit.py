from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCANNER = ROOT / "templates" / "security" / "security-scan.sh"
README = ROOT / "templates" / "security" / "README.md"


def test_security_scan_template_has_required_markers() -> None:
    source = SCANNER.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    assert "render_json_summary_html" in source
    assert "--trivy" in source
    assert "--snyk" in source
    assert "scan-results" in source
    assert "Локальная самопроверка" in readme


def test_fake_trivy_scan_writes_json_and_html(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_trivy = fake_bin / "trivy"
    fake_trivy.write_text(
        """#!/usr/bin/env bash
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
{"Results":[{"Target":"demo-image","Vulnerabilities":[{"Severity":"CRITICAL"},{"Severity":"HIGH"}]}]}
JSON
""",
        encoding="utf-8",
    )
    fake_trivy.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "SECURITY_SCAN_TOOL_MODE": "native",
    }

    result = subprocess.run(
        [
            "bash",
            str(SCANNER),
            "--trivy",
            "--severity",
            "HIGH",
            "--image",
            "demo-image:latest",
            "--output",
            "security-report.html",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Report:" in result.stdout
    assert (tmp_path / "scan-results" / "trivy-report.json").exists()
    report = tmp_path / "scan-results" / "security-report.html"
    assert report.exists()
    html = report.read_text(encoding="utf-8")
    assert "Security Scan Summary" in html
    assert "CRITICAL=1" in html
