from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "smoke_test.sh"


def test_smoke_test_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(_script_path())],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_smoke_test_dry_run_uses_configurable_runtime_values(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "MAAS_API_URL": "http://127.0.0.1:18000/api/v1/maas",
            "SMOKE_EMAIL": "smoke@example.test",
            "SMOKE_NODE_ID": "node-from-env",
            "SMOKE_PASSWORD": "not-printed",
        }
    )

    result = subprocess.run(
        ["bash", str(_script_path()), "--dry-run"],
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "API_URL=http://127.0.0.1:18000/api/v1/maas" in result.stdout
    assert "EMAIL=smoke@example.test" in result.stdout
    assert "NODE_ID=node-from-env" in result.stdout
    assert "not-printed" not in result.stdout


def test_smoke_test_uses_deploy_join_token_not_placeholder():
    content = _script_path().read_text(encoding="utf-8")

    assert "placeholder-logic" not in content
    assert "JOIN_TOKEN=" in content
    assert "enrollment_token=$JOIN_TOKEN" in content
