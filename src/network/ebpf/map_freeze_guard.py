"""Local eBPF map freeze guard.

This module wraps ``bpftool map freeze`` with strict argument validation and a
bounded claim gate. A successful freeze is evidence of a local hardening action,
not proof that production monitoring cannot be bypassed.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from src.core.security.subprocess_validator import safe_run


EBPF_MAP_FREEZE_CLAIM_GATE_SCHEMA = "x0tta6bl4.ebpf.map_freeze_claim_gate.v1"
EBPF_MAP_FREEZE_CLAIM_BOUNDARY = (
    "Local eBPF map-freeze action evidence only. A successful bpftool freeze "
    "shows a bounded local attempt to make one map read-only; it does not prove "
    "complete kernel tamper resistance, production security coverage, attached "
    "program correctness, or absence of privileged bypass."
)

_MAP_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
Runner = Callable[..., Any]


@dataclass(frozen=True)
class MapFreezeResult:
    map_name: str
    map_name_sha256: str
    attempted: bool
    frozen: bool
    returncode: int | None
    reason: str
    stdout_sha256: str | None
    stderr_sha256: str | None
    claim_gate: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_text(value: str) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _validate_map_name(map_name: str) -> bool:
    return bool(_MAP_NAME_RE.fullmatch(map_name))


def build_bpftool_map_freeze_command(map_name: str) -> list[str]:
    """Build a shell-free bpftool command for a validated eBPF map name."""
    if not _validate_map_name(map_name):
        raise ValueError("invalid_map_name")
    return ["bpftool", "map", "freeze", "name", map_name]


def _claim_gate(
    *,
    attempted: bool,
    frozen: bool,
    reason: str,
) -> dict[str, Any]:
    blockers = [] if frozen else [reason]
    return {
        "schema": EBPF_MAP_FREEZE_CLAIM_GATE_SCHEMA,
        "claim_boundary": EBPF_MAP_FREEZE_CLAIM_BOUNDARY,
        "local_map_freeze_attempted_claim_allowed": attempted,
        "local_map_frozen_claim_allowed": frozen,
        "map_poisoning_prevention_claim_allowed": False,
        "complete_kernel_tamper_resistance_claim_allowed": False,
        "production_security_coverage_claim_allowed": False,
        "fail_closed": True,
        "blockers": blockers,
    }


def _result(
    *,
    map_name: str,
    attempted: bool,
    frozen: bool,
    returncode: int | None,
    reason: str,
    stdout: Any = None,
    stderr: Any = None,
) -> MapFreezeResult:
    safe_stdout = _normalize_text(stdout)
    safe_stderr = _normalize_text(stderr)
    return MapFreezeResult(
        map_name=map_name,
        map_name_sha256=_sha256_text(map_name) or "",
        attempted=attempted,
        frozen=frozen,
        returncode=returncode,
        reason=reason,
        stdout_sha256=_sha256_text(safe_stdout),
        stderr_sha256=_sha256_text(safe_stderr),
        claim_gate=_claim_gate(attempted=attempted, frozen=frozen, reason=reason),
    )


def _run_bpftool(command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return safe_run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def freeze_map_by_name(
    map_name: str,
    *,
    runner: Runner | None = None,
    timeout: float = 5.0,
) -> MapFreezeResult:
    """Freeze one eBPF map by name and return bounded local evidence."""
    try:
        command = build_bpftool_map_freeze_command(map_name)
    except ValueError:
        return _result(
            map_name=map_name,
            attempted=False,
            frozen=False,
            returncode=None,
            reason="invalid_map_name",
        )

    run = runner or _run_bpftool
    try:
        completed = run(command, timeout=timeout)
    except FileNotFoundError as exc:
        return _result(
            map_name=map_name,
            attempted=True,
            frozen=False,
            returncode=None,
            reason="bpftool_unavailable",
            stderr=str(exc),
        )
    except subprocess.TimeoutExpired as exc:
        return _result(
            map_name=map_name,
            attempted=True,
            frozen=False,
            returncode=None,
            reason="bpftool_timeout",
            stdout=exc.stdout,
            stderr=exc.stderr,
        )
    except ValueError as exc:
        reason = (
            "bpftool_unavailable"
            if "not available in trusted system paths" in str(exc)
            else "bpftool_freeze_failed"
        )
        return _result(
            map_name=map_name,
            attempted=True,
            frozen=False,
            returncode=None,
            reason=reason,
            stderr=str(exc),
        )
    except Exception as exc:
        return _result(
            map_name=map_name,
            attempted=True,
            frozen=False,
            returncode=None,
            reason="bpftool_freeze_failed",
            stderr=str(exc),
        )

    returncode = int(getattr(completed, "returncode", 1))
    frozen = returncode == 0
    return _result(
        map_name=map_name,
        attempted=True,
        frozen=frozen,
        returncode=returncode,
        reason="map_frozen" if frozen else "bpftool_freeze_failed",
        stdout=getattr(completed, "stdout", ""),
        stderr=getattr(completed, "stderr", ""),
    )
