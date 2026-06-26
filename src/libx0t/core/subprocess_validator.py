from __future__ import annotations
# Subprocess validation utilities
import os
import subprocess
from pathlib import Path
from typing import List

ALLOWED_COMMANDS = {
    "bpftool",
    "batctl",
    "yggdrasilctl",
    "ip",
    "tc",
    "which",
    "ping",
    # Security infrastructure
    "spire-server",
    "spire-agent",
    "spire-server.exe",
    "spire-agent.exe",
    # Python / scripting
    "python3",
    "python",
    "bash",
    "sh",
    # System service management
    "systemctl",
    "systemd-run",
    # Network / VPN
    "xray",
    "xray-linux-amd64",
    "wireguard",
    "wg",
    "wg-quick",
    "openvpn",
    # Filesystem / diagnostics
    "ls",
    "cat",
    "grep",
    "awk",
    "sed",
    "tee",
    "chmod",
    "chown",
    "mkdir",
    "rm",
    "mv",
    "cp",
    "ln",
    "id",
    "uname",
    "hostname",
    "df",
    "du",
    "free",
    "ps",
    "ss",
    "tcpdump",
    "curl",
    "wget",
    "git",
    "make",
    # Kubernetes / containers
    "kubectl",
    "docker",
    "containerd",
    # System config
    "sudo",
    "sysctl",
    "iptables",
    "nft",
}

DANGEROUS_ARGUMENT_CHARS = frozenset((";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"))
MAX_ARGUMENT_LENGTH = 512
TRUSTED_COMMAND_DIRS = (
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
)
UNSAFE_ENV_KEYS = frozenset(
    ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PYTHONPATH")
)


def _validate_bare_command_name(command: object) -> str:
    if not isinstance(command, str) or not command:
        raise ValueError("Command executable must be a non-empty string")
    if "/" in command or "\\" in command:
        raise ValueError("Command executable must be a bare allowlisted name")
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {command}")
    return command


def _validate_subcommand(command: str, subcommand: object, allowed: set[str]) -> None:
    if not isinstance(subcommand, str) or not subcommand:
        raise ValueError(f"{command} subcommand must be a non-empty string")
    if subcommand not in allowed:
        raise ValueError(f"{command} subcommand not allowed")


def _resolve_trusted_command(command: str) -> str:
    for directory in TRUSTED_COMMAND_DIRS:
        candidate = Path(directory) / command
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        except OSError:
            continue
    raise ValueError(f"Allowed command is not available in trusted system paths: {command}")


def _validate_run_kwargs(kwargs: dict) -> None:
    if kwargs.get("shell", False):
        raise ValueError("shell=True is not allowed")
    if "executable" in kwargs:
        raise ValueError("subprocess executable override is not allowed")

    env = kwargs.get("env")
    if env is None:
        return
    unsafe_keys = sorted(key for key in UNSAFE_ENV_KEYS if key in env)
    if unsafe_keys:
        raise ValueError("Unsafe subprocess environment variable is not allowed")


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

    command = _validate_bare_command_name(cmd[0])

    # Additional validation for specific commands
    if command == "ip":
        if len(cmd) < 2:
            raise ValueError("ip command requires at least one subcommand")
        allowed_subcommands = {"link", "addr", "route", "netns"}
        _validate_subcommand(command, cmd[1], allowed_subcommands)

    elif command == "tc":
        if len(cmd) < 2:
            raise ValueError("tc command requires at least one subcommand")
        allowed_subcommands = {"qdisc", "filter", "class"}
        _validate_subcommand(command, cmd[1], allowed_subcommands)

    return True


def validate_arguments(cmd: List[str]) -> bool:
    """
    Validate command arguments for injection risks.

    Args:
        cmd: Command list to validate

    Returns:
        True if arguments are safe
    """
    if not cmd or not isinstance(cmd, list):
        raise ValueError("Command must be a non-empty list")

    for index, arg in enumerate(cmd[1:], start=1):
        if not isinstance(arg, str):
            raise ValueError(f"Command argument at index {index} must be a string")
        if len(arg) > MAX_ARGUMENT_LENGTH:
            raise ValueError(f"Command argument at index {index} is too long")
        if any(char in arg for char in DANGEROUS_ARGUMENT_CHARS):
            raise ValueError(f"Dangerous character in argument at index {index}")

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
    _validate_run_kwargs(kwargs)
    safe_kwargs = dict(kwargs)
    safe_kwargs["shell"] = False
    resolved_cmd = [_resolve_trusted_command(cmd[0]), *cmd[1:]]
    return subprocess.run(resolved_cmd, **safe_kwargs)

