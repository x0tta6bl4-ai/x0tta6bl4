"""
Test for subprocess validation
"""

import subprocess
from unittest.mock import patch

import pytest

from src.core.subprocess_validator import (safe_run, validate_arguments,
                                           validate_command)
from src.libx0t.core import subprocess_validator as lib_subprocess_validator


def test_validate_command_allowed():
    """Test that allowed commands pass validation"""
    assert validate_command(["bpftool", "prog", "list"])
    assert validate_command(["batctl", "o"])
    assert validate_command(["yggdrasilctl", "getPeers"])
    assert validate_command(["ping", "-c", "1", "-W", "1", "127.0.0.1"])


def test_validate_command_disallowed():
    """Test that disallowed commands are rejected"""
    with pytest.raises(ValueError, match="Command not allowed"):
        validate_command(["rm", "-rf", "/"])

    with pytest.raises(ValueError, match="Command not allowed"):
        validate_command(["cat", "/etc/passwd"])


def test_validate_command_rejects_path_like_executable():
    """Test that command names cannot be replaced with paths"""
    path_like_commands = ["/tmp/ip", "./ip", r"C:\Windows\System32\ip.exe"]

    for command in path_like_commands:
        with pytest.raises(ValueError, match="bare allowlisted name"):
            validate_command([command, "link", "show"])


def test_libx0t_validator_rejects_path_like_executable():
    """Test that the libx0t mirror keeps the same executable boundary"""
    with pytest.raises(ValueError, match="bare allowlisted name"):
        lib_subprocess_validator.validate_command(["/tmp/ip", "link", "show"])


def test_validate_command_empty():
    """Test that empty command is rejected"""
    with pytest.raises(ValueError, match="non-empty"):
        validate_command([])


def test_validate_ip_subcommands():
    """Test that ip command subcommands are validated"""
    assert validate_command(["ip", "link", "show"])
    assert validate_command(["ip", "addr", "show"])
    assert validate_command(["ip", "route", "show"])

    with pytest.raises(ValueError, match="subcommand not allowed"):
        validate_command(["ip", "x", "y"])


def test_validate_tc_subcommands():
    """Test that tc command subcommands are validated"""
    assert validate_command(["tc", "qdisc", "show"])
    assert validate_command(["tc", "filter", "show"])
    assert validate_command(["tc", "class", "show"])

    with pytest.raises(ValueError, match="subcommand not allowed"):
        validate_command(["tc", "x", "y"])


def test_validate_ip_requires_subcommand():
    """Test that ip command requires at least one subcommand"""
    with pytest.raises(ValueError, match="requires at least one subcommand"):
        validate_command(["ip"])


def test_validate_tc_requires_subcommand():
    """Test that tc command requires at least one subcommand"""
    with pytest.raises(ValueError, match="requires at least one subcommand"):
        validate_command(["tc"])


def test_validate_arguments_safe():
    """Test that safe arguments pass validation"""
    assert validate_arguments(["safe", "arg1", "arg2"])


def test_validate_arguments_dangerous():
    """Test that dangerous arguments are rejected"""
    dangerous_args = ["arg; rm -rf /", "arg| cat /etc/passwd", "arg`whoami`"]
    for arg in dangerous_args:
        with pytest.raises(ValueError, match="Dangerous character"):
            validate_arguments(["safe", arg])


def test_validate_arguments_does_not_leak_rejected_argument():
    """Test that rejected argument values are not echoed into errors"""
    secret_like_argument = "token=super-secret-value$"

    with pytest.raises(ValueError, match="Dangerous character") as exc_info:
        validate_arguments(["safe", secret_like_argument])

    assert secret_like_argument not in str(exc_info.value)


def test_validate_arguments_rejects_non_string_arguments():
    """Test that non-string subprocess arguments are rejected"""
    with pytest.raises(ValueError, match="must be a string"):
        validate_arguments(["safe", 42])


def test_validate_arguments_rejects_overlong_arguments():
    """Test that unusually long arguments are rejected"""
    with pytest.raises(ValueError, match="too long"):
        validate_arguments(["safe", "x" * 513])


def test_validate_arguments_metacharacters():
    """Test that shell metacharacters are rejected"""
    metachars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]
    for char in metachars:
        with pytest.raises(ValueError, match="Dangerous character"):
            validate_arguments(["safe", f"arg{char}"])


def test_safe_run_with_validation():
    """Test that safe_run validates before execution"""
    # This test uses 'which' which is allowed
    result = safe_run(["which", "python3"], capture_output=True, text=True, timeout=5)
    assert (
        result.returncode == 0 or result.returncode == 1
    )  # May or may not find python3


def test_safe_run_forces_shell_false_and_resolves_command():
    """Test that safe_run bypasses caller PATH and always disables shell"""
    completed = subprocess.CompletedProcess(args=[], returncode=0)

    with patch(
        "src.core.subprocess_validator.subprocess.run",
        return_value=completed,
    ) as run_mock:
        result = safe_run(["which", "python3"], capture_output=True, text=True)

    assert result is completed
    called_cmd = run_mock.call_args.args[0]
    called_kwargs = run_mock.call_args.kwargs
    assert called_cmd[0] != "which"
    assert called_cmd[0].endswith("/which")
    assert called_kwargs["shell"] is False


def test_safe_run_rejects_shell_true():
    """Test that callers cannot re-enable shell execution"""
    with pytest.raises(ValueError, match="shell=True is not allowed"):
        safe_run(["which", "python3"], shell=True)


def test_safe_run_rejects_executable_override():
    """Test that callers cannot replace the resolved trusted executable"""
    with pytest.raises(ValueError, match="executable override"):
        safe_run(["which", "python3"], executable="/tmp/which")


def test_safe_run_rejects_unsafe_environment_overrides():
    """Test that privileged command execution does not accept injection env vars"""
    with pytest.raises(ValueError, match="Unsafe subprocess environment"):
        safe_run(["which", "python3"], env={"LD_PRELOAD": "/tmp/hook.so"})
