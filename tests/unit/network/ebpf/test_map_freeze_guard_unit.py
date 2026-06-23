from __future__ import annotations

import subprocess
from unittest.mock import patch

from src.network.ebpf.map_freeze_guard import (
    build_bpftool_map_freeze_command,
    freeze_map_by_name,
)


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_build_bpftool_map_freeze_command_uses_shell_free_argv() -> None:
    command = build_bpftool_map_freeze_command("attested_nodes_map")

    assert command == ["bpftool", "map", "freeze", "name", "attested_nodes_map"]


def test_freeze_rejects_invalid_map_name_without_runner_call() -> None:
    calls = []

    def runner(command, *, timeout):
        calls.append((command, timeout))
        return _Completed(0)

    result = freeze_map_by_name("bad map;rm -rf /", runner=runner)

    assert calls == []
    assert result.attempted is False
    assert result.frozen is False
    assert result.reason == "invalid_map_name"
    assert result.claim_gate["fail_closed"] is True
    assert result.claim_gate["production_security_coverage_claim_allowed"] is False


def test_successful_freeze_allows_only_bounded_local_freeze_claim() -> None:
    calls = []

    def runner(command, *, timeout):
        calls.append((command, timeout))
        return _Completed(0, stdout="frozen")

    result = freeze_map_by_name("attested_nodes_map", runner=runner, timeout=3)

    assert calls == [(["bpftool", "map", "freeze", "name", "attested_nodes_map"], 3)]
    assert result.attempted is True
    assert result.frozen is True
    assert result.reason == "map_frozen"
    assert result.stdout_sha256 is not None
    assert result.claim_gate["local_map_frozen_claim_allowed"] is True
    assert result.claim_gate["map_poisoning_prevention_claim_allowed"] is False
    assert result.claim_gate["complete_kernel_tamper_resistance_claim_allowed"] is False


def test_default_runner_uses_safe_subprocess_validator() -> None:
    with patch(
        "src.network.ebpf.map_freeze_guard.safe_run",
        return_value=_Completed(0, stdout="frozen"),
    ) as safe_run:
        result = freeze_map_by_name("attested_nodes_map", timeout=3)

    assert result.frozen is True
    safe_run.assert_called_once_with(
        ["bpftool", "map", "freeze", "name", "attested_nodes_map"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )


def test_bpftool_unavailable_fails_closed() -> None:
    def runner(command, *, timeout):
        raise FileNotFoundError("bpftool")

    result = freeze_map_by_name("attested_nodes_map", runner=runner)

    assert result.attempted is True
    assert result.frozen is False
    assert result.reason == "bpftool_unavailable"
    assert result.claim_gate["blockers"] == ["bpftool_unavailable"]
    assert result.claim_gate["fail_closed"] is True


def test_trusted_path_validation_failure_maps_to_bpftool_unavailable() -> None:
    def runner(command, *, timeout):
        raise ValueError("Allowed command is not available in trusted system paths: bpftool")

    result = freeze_map_by_name("attested_nodes_map", runner=runner)

    assert result.attempted is True
    assert result.frozen is False
    assert result.reason == "bpftool_unavailable"
    assert result.claim_gate["blockers"] == ["bpftool_unavailable"]


def test_bpftool_timeout_fails_closed_with_bounded_output_hashes() -> None:
    def runner(command, *, timeout):
        raise subprocess.TimeoutExpired(command, timeout, output="partial", stderr="late")

    result = freeze_map_by_name("attested_nodes_map", runner=runner)

    assert result.attempted is True
    assert result.frozen is False
    assert result.reason == "bpftool_timeout"
    assert result.stdout_sha256 is not None
    assert result.stderr_sha256 is not None
    assert result.claim_gate["production_security_coverage_claim_allowed"] is False
