from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "rust_toolchain_preflight.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _link_required_shell_tool(bin_dir: Path, name: str) -> None:
    target = shutil.which(name)
    assert target is not None, f"{name} is required for the shell helper test"
    (bin_dir / name).symlink_to(target)


def _write_version_stub(bin_dir: Path, name: str, version: str) -> None:
    tool = bin_dir / name
    tool.write_text(f"#!/bin/sh\necho '{version}'\n", encoding="utf-8")
    tool.chmod(0o755)


def _base_env(bin_dir: Path, tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    env["HOME"] = str(tmp_path / "home")
    return env


def _prepare_shell_path(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("cat", "dirname", "head"):
        _link_required_shell_tool(bin_dir, tool)
    return bin_dir


def test_json_reports_missing_rust_tools(tmp_path: Path) -> None:
    bin_dir = _prepare_shell_path(tmp_path)
    target_dir = tmp_path / "x0t-linkd"
    target_dir.mkdir()

    result = subprocess.run(
        [BASH, str(SCRIPT), "--json", "--target-dir", str(target_dir)],
        check=False,
        env=_base_env(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ready"] == 0
    assert payload["rustc"]["version"] == "missing"
    assert payload["cargo"]["version"] == "missing"
    assert payload["target_status"] == "directory-without-Cargo.toml"
    assert "rust_toolchain_preflight.sh --install-user" in payload["install_command"]


def test_json_reports_ready_with_fake_rust_tools(tmp_path: Path) -> None:
    bin_dir = _prepare_shell_path(tmp_path)
    target_dir = tmp_path / "x0t-linkd"
    target_dir.mkdir()
    (target_dir / "Cargo.toml").write_text("[package]\nname = \"x0t-linkd\"\n", encoding="utf-8")
    _write_version_stub(bin_dir, "rustc", "rustc 1.95.0-test")
    _write_version_stub(bin_dir, "cargo", "cargo 1.95.0-test")
    _write_version_stub(bin_dir, "rustup", "rustup 1.29.0-test")

    result = subprocess.run(
        [BASH, str(SCRIPT), "--json", "--target-dir", str(target_dir)],
        check=False,
        env=_base_env(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ready"] == 1
    assert payload["rustc"]["path"] == str(bin_dir / "rustc")
    assert payload["cargo"]["path"] == str(bin_dir / "cargo")
    assert payload["rustup"]["version"] == "rustup 1.29.0-test"
    assert payload["target_status"] == "cargo-project"


def test_print_env_is_side_effect_free(tmp_path: Path) -> None:
    bin_dir = _prepare_shell_path(tmp_path)

    result = subprocess.run(
        [BASH, str(SCRIPT), "--print-env"],
        check=False,
        env=_base_env(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert 'export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"' in result.stdout
    assert 'export PATH="$CARGO_HOME/bin:$PATH"' in result.stdout
