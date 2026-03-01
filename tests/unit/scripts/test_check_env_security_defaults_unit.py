from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "check_env_security_defaults.py"
    spec = importlib.util.spec_from_file_location("check_env_security_defaults", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load check_env_security_defaults module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scan_python_file_flags_hardcoded_sensitive_default(tmp_path):
    mod = _load_module()
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        'import os\nsecret = os.getenv("VAULT_TOKEN", "root")\n',
        encoding="utf-8",
    )
    findings = mod.scan_python_file(py_file, tmp_path)
    assert any("VAULT_TOKEN uses hardcoded non-empty default literal" in item.message for item in findings)


def test_scan_python_file_allows_empty_sensitive_default(tmp_path):
    mod = _load_module()
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        'import os\nsecret = os.getenv("VAULT_TOKEN", "")\n',
        encoding="utf-8",
    )
    findings = mod.scan_python_file(py_file, tmp_path)
    assert findings == []


def test_scan_python_file_flags_insecure_bool_default(tmp_path):
    mod = _load_module()
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        'import os\nflag = os.getenv("DB_ENFORCE_SCHEMA", "false")\n',
        encoding="utf-8",
    )
    findings = mod.scan_python_file(py_file, tmp_path)
    assert any("DB_ENFORCE_SCHEMA default must be 'true'" in item.message for item in findings)


def test_scan_shell_file_flags_literal_secret_assignment(tmp_path):
    mod = _load_module()
    shell_file = tmp_path / "sample.sh"
    shell_file.write_text(
        'TELEGRAM_BOT_TOKEN="123456:abcdef"\n',
        encoding="utf-8",
    )
    findings = mod.scan_shell_file(shell_file, tmp_path)
    assert any("TELEGRAM_BOT_TOKEN is hardcoded" in item.message for item in findings)


def test_scan_shell_file_flags_non_empty_parameter_expansion_fallback(tmp_path):
    mod = _load_module()
    shell_file = tmp_path / "sample.sh"
    shell_file.write_text(
        'GRAFANA_API_KEY="${GRAFANA_API_KEY:-admin:admin}"\n',
        encoding="utf-8",
    )
    findings = mod.scan_shell_file(shell_file, tmp_path)
    assert any("uses non-empty default fallback" in item.message for item in findings)


def test_scan_shell_file_allows_empty_parameter_expansion_fallback(tmp_path):
    mod = _load_module()
    shell_file = tmp_path / "sample.sh"
    shell_file.write_text(
        'TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"\n',
        encoding="utf-8",
    )
    findings = mod.scan_shell_file(shell_file, tmp_path)
    assert findings == []


def test_scan_shell_file_ignores_heredoc_content(tmp_path):
    mod = _load_module()
    shell_file = tmp_path / "sample.sh"
    shell_file.write_text(
        "cat <<'EOF'\n"
        "GITHUB_TOKEN=*** scripts/set_required_security_check.sh\n"
        "EOF\n",
        encoding="utf-8",
    )
    findings = mod.scan_shell_file(shell_file, tmp_path)
    assert findings == []
