"""Linux deployment preflight checks for first-party VPN rollout."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Callable, Sequence

from .linux_policy import LinuxPolicyCommand
from .ops import CommandPlanEvidence, assert_privacy_safe, hash_identifier

PathExists = Callable[[str], bool]
BinaryExists = Callable[[str], bool]
PlatformReader = Callable[[], str]
UidReader = Callable[[], int]
TextReader = Callable[[], str]
_CAP_NET_ADMIN_BIT = 12


class LinuxPreflightError(ValueError):
    """Raised when deployment preflight evidence is invalid."""


@dataclass(frozen=True)
class LinuxHostFacts:
    """Host facts collected without mutating the host network stack."""

    os_name: str
    kernel_release: str
    effective_uid: int
    has_net_admin: bool
    device_paths: tuple[str, ...] = ("/dev/net/tun",)
    binaries: tuple[str, ...] = ("ip", "nft", "sysctl")
    optional_binaries: tuple[str, ...] = ("resolvectl",)

    def __post_init__(self) -> None:
        if not self.os_name.strip():
            raise ValueError("Linux preflight OS name is required")
        if not self.kernel_release.strip():
            raise ValueError("Linux preflight kernel release is required")
        if self.effective_uid < 0:
            raise ValueError("Linux preflight uid cannot be negative")
        for item in self.device_paths + self.binaries + self.optional_binaries:
            if not item.strip():
                raise ValueError("Linux preflight facts contain an empty item")


@dataclass(frozen=True)
class LinuxPreflightConfig:
    """Deployment preflight requirements."""

    require_root: bool = True
    require_net_admin: bool = True
    require_tun_device: bool = True
    require_rollback_plan: bool = True
    require_apply_plan: bool = True
    min_apply_commands: int = 1
    min_rollback_commands: int = 1

    def __post_init__(self) -> None:
        if self.min_apply_commands < 0 or self.min_rollback_commands < 0:
            raise ValueError("Linux preflight minimum command counts cannot be negative")


@dataclass(frozen=True)
class LinuxPreflightCheck:
    name: str
    passed: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Linux preflight check name is required")
        if self.passed and self.reason is not None:
            raise ValueError("passed Linux preflight checks must not include a reason")
        if not self.passed and not (self.reason or "").strip():
            raise ValueError("failed Linux preflight checks require a reason")

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"name": self.name, "passed": self.passed}
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class LinuxPreflightEvidence:
    """Privacy-safe preflight result for rollout gates."""

    checks: tuple[LinuxPreflightCheck, ...]
    apply_plan: CommandPlanEvidence
    rollback_plan: CommandPlanEvidence
    host_fingerprint: str
    optional_missing: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_reasons(self) -> tuple[str, ...]:
        return tuple(check.reason or check.name for check in self.checks if not check.passed)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-linux-preflight-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "apply_plan": self.apply_plan.to_json_dict(),
            "checks": [check.to_json_dict() for check in self.checks],
            "host_fingerprint": self.host_fingerprint,
            "optional_missing": list(self.optional_missing),
            "passed": self.passed,
            "rollback_plan": self.rollback_plan.to_json_dict(),
        }
        assert_privacy_safe(payload)
        return payload


def collect_linux_host_facts(
    *,
    device_paths: tuple[str, ...] = ("/dev/net/tun",),
    binaries: tuple[str, ...] = ("ip", "nft", "sysctl"),
    optional_binaries: tuple[str, ...] = ("resolvectl",),
    os_name_reader: PlatformReader | None = None,
    kernel_release_reader: PlatformReader | None = None,
    uid_reader: UidReader | None = None,
    proc_status_reader: TextReader | None = None,
) -> LinuxHostFacts:
    """Collect read-only host facts for Linux deployment preflight."""
    read_os_name = os_name_reader or platform.system
    read_kernel_release = kernel_release_reader or platform.release
    read_uid = uid_reader or os.geteuid
    read_proc_status = proc_status_reader or _read_proc_self_status
    return LinuxHostFacts(
        os_name=read_os_name(),
        kernel_release=read_kernel_release(),
        effective_uid=read_uid(),
        has_net_admin=_has_cap_net_admin(read_proc_status()),
        device_paths=device_paths,
        binaries=binaries,
        optional_binaries=optional_binaries,
    )


def evaluate_linux_deployment_preflight(
    *,
    facts: LinuxHostFacts,
    config: LinuxPreflightConfig,
    apply_commands: Sequence[LinuxPolicyCommand],
    rollback_commands: Sequence[LinuxPolicyCommand],
    path_exists: PathExists | None = None,
    binary_exists: BinaryExists | None = None,
) -> LinuxPreflightEvidence:
    path_check = path_exists or (lambda path: Path(path).exists())
    binary_check = binary_exists or _binary_in_path
    checks: list[LinuxPreflightCheck] = []

    checks.append(
        LinuxPreflightCheck(
            "linux_os",
            facts.os_name.lower() == "linux",
            None if facts.os_name.lower() == "linux" else "host_os_not_linux",
        )
    )
    if config.require_root:
        checks.append(
            LinuxPreflightCheck(
                "root_uid",
                facts.effective_uid == 0,
                None if facts.effective_uid == 0 else "root_required",
            )
        )
    if config.require_net_admin:
        checks.append(
            LinuxPreflightCheck(
                "net_admin",
                facts.has_net_admin,
                None if facts.has_net_admin else "net_admin_capability_required",
            )
        )
    if config.require_tun_device:
        tun_exists = all(path_check(path) for path in facts.device_paths)
        checks.append(
            LinuxPreflightCheck(
                "tun_device",
                tun_exists,
                None if tun_exists else "tun_device_missing",
            )
        )
    missing_binaries = tuple(binary for binary in facts.binaries if not binary_check(binary))
    checks.append(
        LinuxPreflightCheck(
            "required_binaries",
            not missing_binaries,
            None if not missing_binaries else "required_binary_missing",
        )
    )
    optional_missing = tuple(
        binary for binary in facts.optional_binaries if not binary_check(binary)
    )
    apply_ok = len(apply_commands) >= config.min_apply_commands
    if config.require_apply_plan:
        checks.append(
            LinuxPreflightCheck(
                "apply_plan",
                apply_ok,
                None if apply_ok else "apply_plan_too_small",
            )
        )
    rollback_ok = len(rollback_commands) >= config.min_rollback_commands
    if config.require_rollback_plan:
        checks.append(
            LinuxPreflightCheck(
                "rollback_plan",
                rollback_ok,
                None if rollback_ok else "rollback_plan_too_small",
            )
        )

    return LinuxPreflightEvidence(
        checks=tuple(checks),
        apply_plan=CommandPlanEvidence.from_commands(apply_commands),
        rollback_plan=CommandPlanEvidence.from_commands(rollback_commands),
        host_fingerprint=_host_fingerprint(facts),
        optional_missing=optional_missing,
    )


def _binary_in_path(binary: str) -> bool:
    if "/" in binary:
        return Path(binary).exists()
    import shutil

    return shutil.which(binary) is not None


def _read_proc_self_status() -> str:
    try:
        return Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return ""


def _has_cap_net_admin(proc_status: str) -> bool:
    for line in proc_status.splitlines():
        if not line.startswith("CapEff:"):
            continue
        value = line.split(":", 1)[1].strip().split()[0]
        try:
            effective = int(value, 16)
        except ValueError:
            return False
        return bool(effective & (1 << _CAP_NET_ADMIN_BIT))
    return False


def _host_fingerprint(facts: LinuxHostFacts) -> str:
    return hash_identifier(
        f"{facts.os_name}|{facts.kernel_release}|{facts.effective_uid}|"
        f"{facts.has_net_admin}",
        namespace="linux-preflight-host",
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
