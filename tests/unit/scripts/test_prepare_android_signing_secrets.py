from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/prepare_android_signing_secrets.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_android_signing_secrets_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_redacts_private_values(tmp_path: Path) -> None:
    module = _load()
    args = module.parse_args(["--keystore", str(tmp_path / "release.keystore")])

    report = module.run(args, password_factory=lambda: "super-secret")
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "PLAN"
    assert report["claim_boundary"]["private_values_redacted"] is True
    assert report["will_generate_keystore"] is False
    assert "<redacted>" in "\n".join(report["local_env_preview"])
    assert "super-secret" not in rendered


def test_generate_writes_owner_only_env_without_printing_values(tmp_path: Path) -> None:
    module = _load()
    keystore = tmp_path / "release.keystore"
    env_path = tmp_path / "android-signing.env"
    calls: list[tuple[list[str], str | None]] = []

    def runner(
        args: list[str],
        input: str | None,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((list(args), input))
        keystore.write_bytes(b"fake-keystore")
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--generate",
            "--keystore",
            str(keystore),
            "--write-local-env",
            str(env_path),
        ]
    )
    passwords = iter(["store-secret", "key-secret"])

    report = module.run(args, runner=runner, password_factory=lambda: next(passwords))
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "GENERATED"
    assert report["keystore_generated"] is True
    assert report["local_env_written"] is True
    assert stat.S_IMODE(keystore.stat().st_mode) == 0o600
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert "store-secret" not in rendered
    assert "key-secret" not in rendered
    assert "store-secret" in env_path.read_text(encoding="utf-8")
    assert calls and calls[0][0][0].endswith("keytool")


def test_set_github_secrets_uses_stdin_not_command_args(tmp_path: Path) -> None:
    module = _load()
    keystore = tmp_path / "release.keystore"
    calls: list[tuple[list[str], str | None]] = []

    def runner(
        args: list[str],
        input: str | None,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((list(args), input))
        if args and args[0].endswith("keytool"):
            keystore.write_bytes(b"fake-keystore")
        return subprocess.CompletedProcess(args, 0, "", "")

    args = module.parse_args(
        [
            "--generate",
            "--keystore",
            str(keystore),
            "--set-github-secrets",
            "--repo",
            "x0tta6bl4-ai/x0tta6bl4",
        ]
    )
    passwords = iter(["store-secret", "key-secret"])

    report = module.run(args, runner=runner, password_factory=lambda: next(passwords))
    gh_calls = [call for call in calls if call[0][:3] == ["gh", "secret", "set"]]

    assert report["github_secrets_ready"] is True
    assert len(gh_calls) == 4
    for command, stdin_value in gh_calls:
        rendered_command = " ".join(command)
        assert "--repo x0tta6bl4-ai/x0tta6bl4" in rendered_command
        assert "store-secret" not in rendered_command
        assert "key-secret" not in rendered_command
        assert stdin_value


def test_cli_plan_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["schema"] == "x0tta6bl4.android_signing_setup.v1"
    assert report["status"] == "PLAN"
    assert result.stderr == ""
