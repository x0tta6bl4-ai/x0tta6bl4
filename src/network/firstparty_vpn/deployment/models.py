"""First-party VPN deployment models — types used by deployment core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# === Error ===

class FirstPartyVpnDeploymentError(Exception):
    """Base error for deployment operations."""


class FirstPartyVpnDeploymentMutationBlocked(Exception):
    """Raised when OS mutation is not allowed."""


# === Config ===

@dataclass
class FirstPartyVpnDeploymentConfig:
    """Deployment configuration."""
    target: str = ""


# === Evidence ===

@dataclass
class FirstPartyVpnDeploymentEvidence:
    """Evidence from deployment operations."""
    success: bool = False
    target: str = ""


@dataclass
class FirstPartyVpnDeploymentExecutionEvidence:
    """Evidence produced by executing a deployment packet."""
    target: str = ""
    action: str = ""
    allowed: bool = False
    succeeded: bool = False
    command_count: int = 0
    executed_count: int = 0
    rollback_attempted: bool = False
    rollback_count: int = 0
    readiness_hash: str = ""
    reasons: tuple[str, ...] = ()
    failure_reason: str | None = None
    tun_activation_attempted: bool = False
    tun_activation_count: int = 0
    dataplane_activation_attempted: bool = False
    dataplane_activation_count: int = 0


@dataclass
class LinuxAppliedStateEvidence:
    """Evidence from Linux applied state."""
    success: bool = False
    output: str = ""


# === Plan Hashes ===

@dataclass
class FirstPartyVpnDeploymentPlanHashes:
    """Hashes of a deployment plan."""
    plan_hash: str = ""


# === Packets ===

@dataclass
class FirstPartyVpnDeploymentPacket:
    """A reviewed deployment packet."""
    target: str
    apply_commands: list[Any] = field(default_factory=list)
    rollback_commands: list[Any] = field(default_factory=list)
    readiness_decision: Any = None


# === Results ===

@dataclass
class FirstPartyVpnDataplaneActivationResult:
    """Result of a dataplane activation."""
    success: bool = False
    resources: list[Any] = field(default_factory=list)
    evidence: Any = None


@dataclass
class FirstPartyVpnTunActivationResult:
    """Result of a TUN activation."""
    success: bool = False
    resources: list[Any] = field(default_factory=list)
    evidence: Any = None


# === Activators ===

@dataclass
class DeploymentCommandRunner:
    """Runs deployment commands."""
    run: Callable[..., Any]


@dataclass
class DeploymentDataplaneActivator:
    """Activates a dataplane."""
    activate: Callable[..., Any]


@dataclass
class DeploymentDataplaneActivationOutcome:
    """Outcome of dataplane activation."""
    success: bool = False
    resources: list[Any] = field(default_factory=list)


@dataclass
class DeploymentDataplaneActivationResource:
    """A resource produced by dataplane activation."""
    kind: str = ""
    id: str = ""


@dataclass
class DeploymentPostApplyValidator:
    """Validates state after apply."""
    validate: Callable[..., Any]


@dataclass
class DeploymentTunActivator:
    """Activates a TUN interface."""
    activate: Callable[..., Any]


@dataclass
class DeploymentTunActivationOutcome:
    """Outcome of TUN activation."""
    success: bool = False
    resources: list[Any] = field(default_factory=list)


@dataclass
class DeploymentTunActivationResource:
    """A resource produced by TUN activation."""
    kind: str = ""
    id: str = ""


@dataclass
class TunResourceCloseResult:
    """Result of closing a TUN resource."""
    success: bool = False


class LinuxPolicyCommand:
    """A Linux policy command."""
    pass


# ============================================
# Stub builder functions for deployment package
# ============================================

def build_firstparty_admission_vpn_activators(*args: Any, **kwargs: Any) -> Any:
    """Stub: build admission VPN activators."""
    return None


def build_firstparty_admission_tun_client_activators(*args: Any, **kwargs: Any) -> Any:
    """Stub: build admission TUN client activators."""
    return None


def build_firstparty_admission_tun_server_activator(*args: Any, **kwargs: Any) -> Any:
    """Stub: build admission TUN server activator."""
    return None


def build_firstparty_admission_tun_server_activators(*args: Any, **kwargs: Any) -> Any:
    """Stub: build admission TUN server activators."""
    return None


def build_firstparty_admission_tun_server_pool_activator(*args: Any, **kwargs: Any) -> Any:
    """Stub: build admission TUN server pool activator."""
    return None


def build_firstparty_dataplane_activator(*args: Any, **kwargs: Any) -> Any:
    """Stub: build dataplane activator."""
    return None


def build_linux_post_apply_validator(*args: Any, **kwargs: Any) -> Any:
    """Stub: build Linux post-apply validator."""
    return None


def build_linux_tun_activator(*args: Any, **kwargs: Any) -> Any:
    """Stub: build Linux TUN activator."""
    return None


def build_firstparty_vpn_deployment_packet(*args: Any, **kwargs: Any) -> Any:
    """Stub: build a deployment packet."""
    return None


def compose_firstparty_dataplane_activators(*args: Any, **kwargs: Any) -> Any:
    """Stub: compose dataplane activators."""
    return None


def compose_firstparty_tun_activators(*args: Any, **kwargs: Any) -> Any:
    """Stub: compose TUN activators."""
    return None


def evaluate_firstparty_vpn_deployment_host_fingerprint(*args: Any, **kwargs: Any) -> Any:
    """Stub: evaluate host fingerprint."""
    return None


def evaluate_firstparty_vpn_deployment_plan_hashes(*args: Any, **kwargs: Any) -> Any:
    """Stub: evaluate plan hashes."""
    return None


def evaluate_firstparty_vpn_deployment_rollout_gate(*args: Any, **kwargs: Any) -> Any:
    """Stub: evaluate rollout gate."""
    return None
