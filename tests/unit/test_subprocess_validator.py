"""
Test for subprocess validation
"""

import pytest

from src.core.subprocess_validator import (safe_run, validate_arguments,
                                           validate_command)


def test_validate_command_allowed():
    """Test that allowed commands pass validation"""
    assert validate_command(["bpftool", "prog", "list"])
    assert validate_command(["batctl", "o"])
    assert validate_command(["yggdrasilctl", "getPeers"])


def test_validate_command_disallowed():
    """Test that disallowed commands are rejected"""
    with pytest.raises(ValueError, match="Command not allowed"):
        validate_command(["rm", "-rf", "/"])

    with pytest.raises(ValueError, match="Command not allowed"):
        validate_command(["cat", "/etc/passwd"])


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


def test_validate_arguments_safe():
    """Test that safe arguments pass validation"""
    assert validate_arguments(["safe", "arg1", "arg2"])


def test_validate_arguments_dangerous():
    """Test that dangerous arguments are rejected"""
    dangerous_args = ["arg; rm -rf /", "arg| cat /etc/passwd", "arg`whoami`"]
    for arg in dangerous_args:
        with pytest.raises(ValueError, match="Dangerous character"):
            validate_arguments(["safe", arg])


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
