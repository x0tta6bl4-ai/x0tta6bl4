"""Regression tests for fail-closed command resolution and absolute subcommands."""
from unittest.mock import Mock

import pytest

from src.core.security import subprocess_validator as validator


@pytest.mark.parametrize("marker", ["TESTING", "PYTEST_CURRENT_TEST"])
def test_test_environment_does_not_invent_executables(monkeypatch, marker):
    monkeypatch.setenv(marker, "true")
    monkeypatch.setattr(validator.Path, "is_file", lambda _: False)
    monkeypatch.setattr(validator.shutil, "which", lambda _: None)
    run = Mock()
    monkeypatch.setattr(validator.subprocess, "run", run)
    with pytest.raises(ValueError, match="not available"):
        validator.safe_run(["spire-agent", "run"])
    run.assert_not_called()


@pytest.mark.parametrize("command", ["/usr/bin/ip", "/usr/sbin/tc"])
def test_absolute_path_does_not_bypass_subcommand_policy(command):
    with pytest.raises(ValueError, match="subcommand not allowed"):
        validator.validate_command([command, "unsupported"])


def test_explicit_executable_is_preserved(monkeypatch, tmp_path):
    executable = tmp_path / "spire-agent"
    executable.write_text("test fixture; not executed")
    executable.chmod(0o700)
    run = Mock()
    monkeypatch.setattr(validator.subprocess, "run", run)
    validator.safe_run([str(executable), "run"])
    run.assert_called_once_with([str(executable), "run"], shell=False)
