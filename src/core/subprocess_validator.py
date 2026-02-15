# Subprocess validation utilities
import subprocess
from typing import List, Optional

ALLOWED_COMMANDS = {"bpftool", "batctl", "yggdrasilctl", "ip", "tc", "which"}


def validate_command(cmd: List[str]) -> bool:
    """
    Validate subprocess command against whitelist.

    Args:
        cmd: Command list to validate

    Returns:
        True if command is allowed, raises ValueError otherwise
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")

    if cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")

    # Additional validation for specific commands
    if cmd[0] == "ip":
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {"link", "addr", "route", "netns"}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"ip subcommand not allowed: {cmd[1]}")

    elif cmd[0] == "tc":
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {"qdisc", "filter", "class"}
        if cmd[1] not in allowed_subcommands:
            raise ValueError(f"tc subcommand not allowed: {cmd[1]}")

    return True


def validate_arguments(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.

    Args:
        cmd: Command list to validate

    Returns:
        True if arguments are safe
    """
    for arg in cmd[1:]:
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]
        if any(char in str(arg) for char in dangerous_chars):
            raise ValueError(f"Dangerous character in argument: {arg}")

    return True


def safe_run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess command with validation.

    Args:
        cmd: Command list to execute
        **kwargs: Additional arguments for subprocess.run

    Returns:
        subprocess.CompletedProcess result
    """
    validate_command(cmd)
    validate_arguments(cmd)
    return subprocess.run(cmd, **kwargs)
