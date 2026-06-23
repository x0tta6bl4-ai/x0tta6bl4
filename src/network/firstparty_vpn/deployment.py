"""Deployment packet assembly and gated execution for first-party VPN candidates."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
from typing import Callable, Literal, Protocol, TYPE_CHECKING

from .applied_state import (
    LinuxAppliedStateCommandRunner,
    LinuxAppliedStateEvidence,
    collect_linux_applied_state_snapshot,
    evaluate_linux_applied_state,
)
from .dataplane_validation import (
    DataplaneTransport,
    DataplaneValidationEvidence,
    TunDataplaneValidationEvidence,
)
from .linux_policy import (
    LinuxNetworkPolicyConfig,
    LinuxNetworkPolicyPlanner,
    LinuxPolicyCommand,
    LinuxServerNatConfig,
    LinuxServerNatPlanner,
    LinuxServerVpnListener,
)
from .leak_protection import LinuxLeakProtectionEvidence, evaluate_linux_leak_protection
from .mtu import MtuValidationEvidence
from .ops import (
    CommandPlanEvidence,
    OperatorApproval,
    RolloutGateDecision,
    RolloutPlan,
    TestEvidence,
    assert_privacy_safe,
    evaluate_rollout_gate,
    hash_identifier,
)
from .pqc import PqcImplementationManifest, PqcKatResult, PqcProviderGateDecision
from .preflight import (
    BinaryExists,
    LinuxHostFacts,
    LinuxPreflightConfig,
    LinuxPreflightEvidence,
    PathExists,
    evaluate_linux_deployment_preflight,
)
from .production_control import (
    ExternalPolicySnapshotSourceEvidence,
    FirstPartyIdentitySignerManifest,
    IdentitySignerConformanceEvidence,
    IdentitySignerKatResult,
    ProductionIdentitySignerGateDecision,
)
from .production_readiness import (
    FullVpnProductionReadinessDecision,
    FullVpnProductionReadinessEvidence,
    FullVpnProductionReadinessRequirements,
    evaluate_full_vpn_production_readiness,
)
from .rekey_policy import FirstPartyRekeyPolicyDecision
from .source_audit import FirstPartySourceAuditEvidence
from .tun import LinuxTunConfig, LinuxTunDevice
from .zero_trust import ZeroTrustPolicyEvidence

if TYPE_CHECKING:
    from .admission import FirstPartySessionAdmissionRegistry
    from .camouflage import CamouflagePolicy, CamouflageProfile
    from .dataplane_validation import DataplaneEndpointCandidate
    from .fragmentation import PacketFragmenter, PacketReassembler
    from .handshake import FirstPartyHandshakeAccept, FirstPartyHandshakeHello
    from .identity import IdentityVerifier, RevocationList
    from .pqc import PqcSessionSecretMaterial
    from .service import FirstPartyDataplaneBind
    from .session import SessionContext
    from .tun import TunDevice, TunReturnTransport
    from .zero_trust import ZeroTrustPolicy


class FirstPartyVpnDeploymentError(ValueError):
    """Raised when a first-party VPN deployment packet is incomplete."""


class FirstPartyVpnDeploymentMutationBlocked(FirstPartyVpnDeploymentError):
    """Raised when deployment execution is requested without explicit mutation approval."""


DeploymentAction = Literal["apply", "rollback"]
DeploymentCommandRunner = Callable[[LinuxPolicyCommand], None]
DeploymentTunActivationScope = Literal["client", "server", "both"]
DeploymentPostApplyValidator = Callable[
    ["FirstPartyVpnDeploymentPacket"],
    LinuxAppliedStateEvidence,
]


class DeploymentTunActivationResource(Protocol):
    def close(self) -> None: ...


class DeploymentDataplaneActivationResource(Protocol):
    def close(self) -> None: ...


class DeploymentTunActivationDevice(Protocol):
    def open_interface(self) -> None: ...

    def close(self) -> None: ...


DeploymentTunDeviceFactory = Callable[[LinuxTunConfig], DeploymentTunActivationDevice]


@dataclass(frozen=True)
class FirstPartyVpnTunActivationResult:
    """Resources opened before network commands and kept alive by deployment."""

    count: int
    resources: tuple[DeploymentTunActivationResource, ...] = ()

    def __post_init__(self) -> None:
        if self.count < 0:
            raise FirstPartyVpnDeploymentError("TUN activation count cannot be negative")
        if len(self.resources) != self.count:
            raise FirstPartyVpnDeploymentError("TUN activation resources must match count")
        for resource in self.resources:
            if not callable(getattr(resource, "close", None)):
                raise FirstPartyVpnDeploymentError(
                    "TUN activation resources must be closeable"
                )


DeploymentTunActivationOutcome = int | FirstPartyVpnTunActivationResult
DeploymentTunActivator = Callable[
    ["FirstPartyVpnDeploymentPacket"],
    DeploymentTunActivationOutcome,
]


@dataclass(frozen=True)
class FirstPartyVpnDataplaneActivationResult:
    """Dataplane services started before network commands and kept alive."""

    count: int
    resources: tuple[DeploymentDataplaneActivationResource, ...] = ()

    def __post_init__(self) -> None:
        if self.count < 0:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation count cannot be negative"
            )
        if len(self.resources) != self.count:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation resources must match count"
            )
        for resource in self.resources:
            if not callable(getattr(resource, "close", None)):
                raise FirstPartyVpnDeploymentError(
                    "dataplane activation resources must be closeable"
                )


DeploymentDataplaneActivationOutcome = int | FirstPartyVpnDataplaneActivationResult
DeploymentDataplaneActivator = Callable[
    ["FirstPartyVpnDeploymentPacket"],
    DeploymentDataplaneActivationOutcome,
]
DeploymentDataplaneStartFactory = Callable[
    ["FirstPartyDataplaneBind"],
    DeploymentDataplaneActivationResource,
]
DeploymentAdmissionTunFactory = Callable[["SessionContext"], "TunDevice"]
DeploymentAdmissionTunResponseFactory = Callable[
    ["SessionContext"],
    Callable[[bytes], bytes | None] | None,
]
DeploymentAdmissionTunFragmenterFactory = Callable[
    ["SessionContext"],
    "PacketFragmenter | None",
]
DeploymentAdmissionTunReassemblerFactory = Callable[
    ["SessionContext"],
    "PacketReassembler | None",
]
DeploymentActivationPair = tuple[
    DeploymentTunActivator,
    DeploymentDataplaneActivator,
]


@dataclass
class _DeploymentActivatedTunDevice:
    device: DeploymentTunActivationDevice
    on_close: Callable[[], None]
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def mtu(self) -> int:
        return self.device.mtu  # type: ignore[attr-defined]

    async def read_packet(self, timeout: float | None = None) -> bytes:
        return await self.device.read_packet(  # type: ignore[attr-defined]
            timeout=timeout,
        )

    async def write_packet(self, packet: bytes) -> None:
        await self.device.write_packet(packet)  # type: ignore[attr-defined]

    def write_packet_nowait(self, packet: bytes) -> None:
        self.device.write_packet_nowait(packet)  # type: ignore[attr-defined]

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.device.close()
        finally:
            self._closed = True
            self.on_close()


@dataclass
class _DeploymentAdmissionSessionTunPool:
    tun_factory: DeploymentAdmissionTunFactory
    devices: dict[int, "TunDevice"] = field(default_factory=dict, init=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.devices))

    def tun_for(self, session: "SessionContext") -> "TunDevice":
        if self._closed:
            raise FirstPartyVpnDeploymentError("admission TUN pool is closed")
        session_id = session.session_id
        device = self.devices.get(session_id)
        if device is not None:
            return device
        created_device: object | None = None
        try:
            created_device = self.tun_factory(session)
            _assert_tun_capable_device(
                created_device,
                role="admission TUN server",
            )
        except Exception:
            if created_device is not None:
                close = getattr(created_device, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            raise
        self.devices[session_id] = created_device  # type: ignore[assignment]
        return created_device  # type: ignore[return-value]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_error: Exception | None = None
        while self.devices:
            _session_id, device = self.devices.popitem()
            close = getattr(device, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN pool close failed"
            ) from close_error


@dataclass(frozen=True)
class TunResourceCloseResult:
    attempted: int
    closed: int
    failed: int

    def __post_init__(self) -> None:
        if self.attempted < 0 or self.closed < 0 or self.failed < 0:
            raise FirstPartyVpnDeploymentError("TUN close counters cannot be negative")
        if self.closed + self.failed != self.attempted:
            raise FirstPartyVpnDeploymentError("TUN close counters are inconsistent")

    @property
    def attempted_any(self) -> bool:
        return self.attempted > 0


@dataclass(frozen=True)
class FirstPartyVpnDeploymentConfig:
    """Client/server Linux rollout inputs for one first-party VPN target."""

    target: str = "nl"
    client_tun: LinuxTunConfig = field(default_factory=LinuxTunConfig)
    client_network: LinuxNetworkPolicyConfig = field(
        default_factory=LinuxNetworkPolicyConfig
    )
    server_tun: LinuxTunConfig = field(
        default_factory=lambda: LinuxTunConfig(address="10.77.0.1/24")
    )
    server_nat: LinuxServerNatConfig = field(
        default_factory=lambda: LinuxServerNatConfig(
            vpn_listeners=(
                LinuxServerVpnListener(transport="udp", port=443),
                LinuxServerVpnListener(transport="camouflage", port=443),
                LinuxServerVpnListener(transport="tcp", port=8443),
            ),
        )
    )
    linux_preflight: LinuxPreflightConfig = field(default_factory=LinuxPreflightConfig)
    expected_test_count: int = 1
    required_dataplane_paths: frozenset[str] = frozenset(
        {"lan", "vps", "mobile", "restricted-work-wifi"}
    )
    required_dataplane_transports: tuple[tuple[str, DataplaneTransport], ...] = (
        ("restricted-work-wifi", "camouflage"),
    )
    dataplane_probe_matrix_hash: str | None = None
    linux_host_fingerprint: str | None = None
    pqc_manifest_hash: str | None = None
    identity_signer_manifest_hash: str | None = None
    apply_plan_hash: str | None = None
    rollback_plan_hash: str | None = None
    leak_protection_plan_hash: str | None = None
    external_policy_source_hash: str | None = None
    policy_snapshot_hash: str | None = None
    zero_trust_policy_hash: str | None = None
    source_audit_root_hash: str | None = None
    source_audit_tree_hash: str | None = None
    rekey_rollback_plan_hash: str | None = None
    rollout_gate_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise FirstPartyVpnDeploymentError("deployment target is required")
        if self.expected_test_count < 1:
            raise FirstPartyVpnDeploymentError("expected test count must be positive")
        _assert_optional_sha256_hex(
            self.dataplane_probe_matrix_hash,
            "dataplane probe matrix hash",
        )
        _assert_optional_sha256_hex(
            self.linux_host_fingerprint,
            "Linux host fingerprint",
        )
        _assert_optional_sha256_hex(
            self.pqc_manifest_hash,
            "PQC manifest hash",
        )
        _assert_optional_sha256_hex(
            self.identity_signer_manifest_hash,
            "identity signer manifest hash",
        )
        _assert_optional_sha256_hex(
            self.apply_plan_hash,
            "apply plan hash",
        )
        _assert_optional_sha256_hex(
            self.rollback_plan_hash,
            "rollback plan hash",
        )
        _assert_optional_sha256_hex(
            self.leak_protection_plan_hash,
            "leak protection plan hash",
        )
        _assert_optional_sha256_hex(
            self.external_policy_source_hash,
            "external policy source hash",
        )
        _assert_optional_sha256_hex(
            self.policy_snapshot_hash,
            "policy snapshot hash",
        )
        _assert_optional_sha256_hex(
            self.zero_trust_policy_hash,
            "zero trust policy hash",
        )
        _assert_optional_sha256_hex(
            self.source_audit_root_hash,
            "source audit root hash",
        )
        _assert_optional_sha256_hex(
            self.source_audit_tree_hash,
            "source audit tree hash",
        )
        _assert_optional_sha256_hex(
            self.rekey_rollback_plan_hash,
            "rekey rollback plan hash",
        )
        _assert_optional_sha256_hex(
            self.rollout_gate_hash,
            "rollout gate hash",
        )
        if not self.required_dataplane_paths:
            raise FirstPartyVpnDeploymentError("required dataplane paths are required")
        for path, transport in self.required_dataplane_transports:
            if path not in self.required_dataplane_paths:
                raise FirstPartyVpnDeploymentError(
                    "required dataplane transport path must be required"
                )
            if transport not in ("udp", "tcp", "camouflage"):
                raise FirstPartyVpnDeploymentError(
                    "required dataplane transport must be udp, tcp, or camouflage"
                )
            if transport not in self.server_nat.listener_transports:
                raise FirstPartyVpnDeploymentError(
                    "required dataplane transport is not exposed by server NAT"
                )


@dataclass(frozen=True)
class FirstPartyVpnDeploymentEvidence:
    """Already-collected non-Linux evidence needed by the deployment packet."""

    test_evidence: TestEvidence
    approval: OperatorApproval | None
    policy_snapshot_hash: str
    dataplane_validation: DataplaneValidationEvidence
    tun_dataplane_validation: TunDataplaneValidationEvidence
    mtu_validation: MtuValidationEvidence
    pqc_provider_gate: PqcProviderGateDecision
    pqc_manifest: PqcImplementationManifest
    pqc_kat: PqcKatResult
    identity_signer_gate: ProductionIdentitySignerGateDecision
    identity_signer_manifest: FirstPartyIdentitySignerManifest
    identity_signer_kat: IdentitySignerKatResult
    identity_signer_conformance: IdentitySignerConformanceEvidence
    external_policy_source: ExternalPolicySnapshotSourceEvidence
    rekey_policy: FirstPartyRekeyPolicyDecision
    source_audit: FirstPartySourceAuditEvidence
    zero_trust_policy: ZeroTrustPolicyEvidence

    def __post_init__(self) -> None:
        if len(self.policy_snapshot_hash) != 64:
            raise FirstPartyVpnDeploymentError("policy snapshot hash must be sha256 hex")


def _assert_optional_sha256_hex(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if len(value) != 64:
        raise FirstPartyVpnDeploymentError(f"{field_name} must be sha256 hex")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise FirstPartyVpnDeploymentError(
            f"{field_name} must be sha256 hex"
        ) from exc


@dataclass(frozen=True)
class FirstPartyVpnDeploymentPacket:
    """Privacy-safe deployment packet that can be reviewed before OS mutation."""

    target: str
    client_apply_commands: tuple[LinuxPolicyCommand, ...]
    client_rollback_commands: tuple[LinuxPolicyCommand, ...]
    server_apply_commands: tuple[LinuxPolicyCommand, ...]
    server_rollback_commands: tuple[LinuxPolicyCommand, ...]
    linux_preflight: LinuxPreflightEvidence
    leak_protection: LinuxLeakProtectionEvidence
    rollout_plan: RolloutPlan
    rollout_decision: RolloutGateDecision
    readiness_evidence: FullVpnProductionReadinessEvidence
    readiness_decision: FullVpnProductionReadinessDecision

    @property
    def apply_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        return self.client_apply_commands + self.server_apply_commands

    @property
    def rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        return self.server_rollback_commands + self.client_rollback_commands

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "apply": CommandPlanEvidence.from_commands(
                self.apply_commands
            ).to_json_dict(),
            "linux_preflight_hash": self.linux_preflight.evidence_hash(),
            "leak_protection_hash": self.leak_protection.evidence_hash(),
            "readiness": self.readiness_decision.to_json_dict(),
            "rollback": CommandPlanEvidence.from_commands(
                self.rollback_commands
            ).to_json_dict(),
            "rollout_decision": {
                "allowed": self.rollout_decision.allowed,
                "decision_hash": self.rollout_decision.decision_hash(),
                "evidence_hash": self.rollout_decision.evidence_hash,
                "reasons": list(self.rollout_decision.reasons),
            },
            "target": self.target,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class FirstPartyVpnDeploymentPlanHashes:
    """Expected command-plan hashes that production readiness must bind."""

    apply_plan_hash: str
    rollback_plan_hash: str
    leak_protection_plan_hash: str

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "apply_plan_hash": self.apply_plan_hash,
            "leak_protection_plan_hash": self.leak_protection_plan_hash,
            "rollback_plan_hash": self.rollback_plan_hash,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class _DeploymentRolloutEvaluation:
    client_apply_commands: tuple[LinuxPolicyCommand, ...]
    client_rollback_commands: tuple[LinuxPolicyCommand, ...]
    server_apply_commands: tuple[LinuxPolicyCommand, ...]
    server_rollback_commands: tuple[LinuxPolicyCommand, ...]
    linux_preflight: LinuxPreflightEvidence
    leak_protection: LinuxLeakProtectionEvidence
    rollout_plan: RolloutPlan
    rollout_decision: RolloutGateDecision


@dataclass(frozen=True)
class FirstPartyVpnDeploymentExecutionEvidence:
    """Privacy-safe result of one gated deployment execution attempt."""

    target: str
    action: DeploymentAction
    allowed: bool
    succeeded: bool
    command_count: int
    executed_count: int
    rollback_attempted: bool
    rollback_count: int
    readiness_hash: str
    post_apply_hash: str | None = None
    post_apply_validation_attempted: bool = False
    tun_activation_attempted: bool = False
    tun_activation_count: int = 0
    dataplane_activation_attempted: bool = False
    dataplane_activation_count: int = 0
    dataplane_resource_close_attempted: bool = False
    dataplane_resource_close_count: int = 0
    dataplane_resource_close_failed_count: int = 0
    tun_resource_close_attempted: bool = False
    tun_resource_close_count: int = 0
    tun_resource_close_failed_count: int = 0
    reasons: tuple[str, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise FirstPartyVpnDeploymentError("deployment execution target is required")
        if self.action not in ("apply", "rollback"):
            raise FirstPartyVpnDeploymentError("deployment action is invalid")
        if self.command_count < 0 or self.executed_count < 0 or self.rollback_count < 0:
            raise FirstPartyVpnDeploymentError("deployment execution counters cannot be negative")
        if self.tun_activation_count < 0:
            raise FirstPartyVpnDeploymentError("TUN activation count cannot be negative")
        if self.dataplane_activation_count < 0:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation count cannot be negative"
            )
        if (
            self.dataplane_resource_close_count < 0
            or self.dataplane_resource_close_failed_count < 0
        ):
            raise FirstPartyVpnDeploymentError(
                "dataplane close counters cannot be negative"
            )
        if self.tun_resource_close_count < 0 or self.tun_resource_close_failed_count < 0:
            raise FirstPartyVpnDeploymentError("TUN close counters cannot be negative")
        if self.executed_count > self.command_count:
            raise FirstPartyVpnDeploymentError("executed command count exceeds command count")
        if not self.tun_activation_attempted and self.tun_activation_count:
            raise FirstPartyVpnDeploymentError("TUN activation count requires activation attempt")
        if not self.dataplane_activation_attempted and self.dataplane_activation_count:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation count requires activation attempt"
            )
        if (
            not self.dataplane_resource_close_attempted
            and (
                self.dataplane_resource_close_count
                or self.dataplane_resource_close_failed_count
            )
        ):
            raise FirstPartyVpnDeploymentError(
                "dataplane close counters require close attempt"
            )
        if (
            not self.tun_resource_close_attempted
            and (self.tun_resource_close_count or self.tun_resource_close_failed_count)
        ):
            raise FirstPartyVpnDeploymentError("TUN close counters require close attempt")
        if self.succeeded and self.dataplane_resource_close_failed_count:
            raise FirstPartyVpnDeploymentError(
                "successful deployment cannot have dataplane close failures"
            )
        if self.succeeded and self.tun_resource_close_failed_count:
            raise FirstPartyVpnDeploymentError("successful deployment cannot have TUN close failures")
        if self.action != "apply" and self.post_apply_validation_attempted:
            raise FirstPartyVpnDeploymentError("post-apply validation is only valid for apply")
        if self.post_apply_hash is not None and not self.post_apply_validation_attempted:
            raise FirstPartyVpnDeploymentError("post-apply hash requires validation attempt")
        if self.action == "apply" and self.succeeded and not self.post_apply_validation_attempted:
            raise FirstPartyVpnDeploymentError("successful apply requires post-apply validation")
        if self.succeeded and self.failure_reason is not None:
            raise FirstPartyVpnDeploymentError("successful deployment cannot have failure reason")
        if not self.succeeded and not (self.failure_reason or self.reasons):
            raise FirstPartyVpnDeploymentError("failed deployment requires reason")
        if self.post_apply_hash is not None and len(self.post_apply_hash) != 64:
            raise FirstPartyVpnDeploymentError("post-apply hash must be sha256 hex")

    def evidence_hash(self) -> str:
        return hash_identifier(
            json.dumps(self.to_json_dict(), sort_keys=True, separators=(",", ":")),
            namespace="deployment-execution-evidence",
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": self.action,
            "allowed": self.allowed,
            "command_count": self.command_count,
            "dataplane_activation_attempted": self.dataplane_activation_attempted,
            "dataplane_activation_count": self.dataplane_activation_count,
            "dataplane_resource_close_attempted": self.dataplane_resource_close_attempted,
            "dataplane_resource_close_count": self.dataplane_resource_close_count,
            "dataplane_resource_close_failed_count": (
                self.dataplane_resource_close_failed_count
            ),
            "executed_count": self.executed_count,
            "post_apply_validation_attempted": self.post_apply_validation_attempted,
            "readiness_hash": self.readiness_hash,
            "reasons": list(self.reasons),
            "rollback_attempted": self.rollback_attempted,
            "rollback_count": self.rollback_count,
            "succeeded": self.succeeded,
            "target": self.target,
            "tun_activation_attempted": self.tun_activation_attempted,
            "tun_activation_count": self.tun_activation_count,
            "tun_resource_close_attempted": self.tun_resource_close_attempted,
            "tun_resource_close_count": self.tun_resource_close_count,
            "tun_resource_close_failed_count": self.tun_resource_close_failed_count,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        if self.post_apply_hash is not None:
            payload["post_apply_hash"] = self.post_apply_hash
        assert_privacy_safe(payload)
        return payload


class FirstPartyVpnDeploymentExecutor:
    """Execute a reviewed deployment packet only after readiness and explicit approval."""

    def __init__(
        self,
        *,
        packet: FirstPartyVpnDeploymentPacket,
        command_runner: DeploymentCommandRunner,
        allow_os_mutation: bool = False,
        tun_activator: DeploymentTunActivator | None = None,
        dataplane_activator: DeploymentDataplaneActivator | None = None,
        post_apply_validator: DeploymentPostApplyValidator | None = None,
        now_provider: Callable[[], int] | None = None,
    ) -> None:
        self.packet = packet
        self.command_runner = command_runner
        self.allow_os_mutation = allow_os_mutation
        self.tun_activator = tun_activator
        self.dataplane_activator = dataplane_activator
        self.post_apply_validator = post_apply_validator
        self.now_provider = now_provider or _utc_now
        self._tun_activation_resources: list[DeploymentTunActivationResource] = []
        self._dataplane_activation_resources: list[
            DeploymentDataplaneActivationResource
        ] = []

    def apply(self) -> FirstPartyVpnDeploymentExecutionEvidence:
        """Apply commands and roll back already executed commands if a command fails."""
        self._assert_can_mutate()
        apply_started_at = self._now()
        readiness_hash = self.packet.readiness_decision.evidence_hash
        commands = self.packet.apply_commands
        tun_activation_attempted = self.tun_activator is not None
        tun_activation_count = 0
        dataplane_activation_attempted = self.dataplane_activator is not None
        dataplane_activation_count = 0
        if self.tun_activator is not None:
            try:
                tun_activation_count = self._record_tun_activation(
                    self.tun_activator(self.packet)
                )
                if tun_activation_count < 1:
                    raise FirstPartyVpnDeploymentError("TUN activation produced no resources")
            except Exception as exc:
                rollback_count = self._rollback_all()
                dataplane_close_result = self.close_dataplane_resources()
                close_result = self.close_tun_resources()
                return FirstPartyVpnDeploymentExecutionEvidence(
                    target=self.packet.target,
                    action="apply",
                    allowed=True,
                    succeeded=False,
                    command_count=len(commands),
                    executed_count=0,
                    rollback_attempted=True,
                    rollback_count=rollback_count,
                    readiness_hash=readiness_hash,
                    reasons=_with_resource_close_reasons(
                        ("tun_activation_failed",),
                        tun_close_result=close_result,
                        dataplane_close_result=dataplane_close_result,
                    ),
                    failure_reason=type(exc).__name__,
                    tun_activation_attempted=tun_activation_attempted,
                    tun_activation_count=0,
                    dataplane_activation_attempted=dataplane_activation_attempted,
                    dataplane_activation_count=0,
                    **_dataplane_close_evidence_kwargs(dataplane_close_result),
                    **_tun_close_evidence_kwargs(close_result),
                )
        if self.dataplane_activator is not None:
            try:
                dataplane_activation_count = self._record_dataplane_activation(
                    self.dataplane_activator(self.packet)
                )
                if dataplane_activation_count < 1:
                    raise FirstPartyVpnDeploymentError(
                        "dataplane activation produced no resources"
                    )
            except Exception as exc:
                rollback_count = self._rollback_all()
                dataplane_close_result = self.close_dataplane_resources()
                close_result = self.close_tun_resources()
                return FirstPartyVpnDeploymentExecutionEvidence(
                    target=self.packet.target,
                    action="apply",
                    allowed=True,
                    succeeded=False,
                    command_count=len(commands),
                    executed_count=0,
                    rollback_attempted=True,
                    rollback_count=rollback_count,
                    readiness_hash=readiness_hash,
                    reasons=_with_resource_close_reasons(
                        ("dataplane_activation_failed",),
                        tun_close_result=close_result,
                        dataplane_close_result=dataplane_close_result,
                    ),
                    failure_reason=type(exc).__name__,
                    tun_activation_attempted=tun_activation_attempted,
                    tun_activation_count=tun_activation_count,
                    dataplane_activation_attempted=dataplane_activation_attempted,
                    dataplane_activation_count=0,
                    **_dataplane_close_evidence_kwargs(dataplane_close_result),
                    **_tun_close_evidence_kwargs(close_result),
                )
        executed: list[LinuxPolicyCommand] = []
        try:
            for command in commands:
                self.command_runner(command)
                executed.append(command)
        except Exception as exc:
            rollback_count = self._rollback_executed(executed)
            dataplane_close_result = self.close_dataplane_resources()
            close_result = self.close_tun_resources()
            return FirstPartyVpnDeploymentExecutionEvidence(
                target=self.packet.target,
                action="apply",
                allowed=True,
                succeeded=False,
                command_count=len(commands),
                executed_count=len(executed),
                rollback_attempted=True,
                rollback_count=rollback_count,
                readiness_hash=readiness_hash,
                reasons=_with_resource_close_reasons(
                    (),
                    tun_close_result=close_result,
                    dataplane_close_result=dataplane_close_result,
                ),
                failure_reason=type(exc).__name__,
                tun_activation_attempted=tun_activation_attempted,
                tun_activation_count=tun_activation_count,
                dataplane_activation_attempted=dataplane_activation_attempted,
                dataplane_activation_count=dataplane_activation_count,
                **_dataplane_close_evidence_kwargs(dataplane_close_result),
                **_tun_close_evidence_kwargs(close_result),
            )
        post_apply_hash: str | None = None
        if self.post_apply_validator is not None:
            try:
                post_apply = self.post_apply_validator(self.packet)
                post_apply_hash = post_apply.evidence_hash()
                post_apply_checked_at = self._now()
            except Exception as exc:
                rollback_count = self._rollback_executed(executed)
                dataplane_close_result = self.close_dataplane_resources()
                close_result = self.close_tun_resources()
                return FirstPartyVpnDeploymentExecutionEvidence(
                    target=self.packet.target,
                    action="apply",
                    allowed=True,
                    succeeded=False,
                    command_count=len(commands),
                    executed_count=len(executed),
                    rollback_attempted=True,
                    rollback_count=rollback_count,
                    readiness_hash=readiness_hash,
                    reasons=_with_resource_close_reasons(
                        ("post_apply_validator_failed",),
                        tun_close_result=close_result,
                        dataplane_close_result=dataplane_close_result,
                    ),
                    failure_reason=type(exc).__name__,
                    post_apply_validation_attempted=True,
                    tun_activation_attempted=tun_activation_attempted,
                    tun_activation_count=tun_activation_count,
                    dataplane_activation_attempted=dataplane_activation_attempted,
                    dataplane_activation_count=dataplane_activation_count,
                    **_dataplane_close_evidence_kwargs(dataplane_close_result),
                    **_tun_close_evidence_kwargs(close_result),
                )
            timing_reasons = _post_apply_timing_reasons(
                post_apply=post_apply,
                apply_started_at=apply_started_at,
                checked_at=post_apply_checked_at,
            )
            if timing_reasons:
                rollback_count = self._rollback_executed(executed)
                dataplane_close_result = self.close_dataplane_resources()
                close_result = self.close_tun_resources()
                return FirstPartyVpnDeploymentExecutionEvidence(
                    target=self.packet.target,
                    action="apply",
                    allowed=True,
                    succeeded=False,
                    command_count=len(commands),
                    executed_count=len(executed),
                    rollback_attempted=True,
                    rollback_count=rollback_count,
                    readiness_hash=readiness_hash,
                    post_apply_hash=post_apply_hash,
                    post_apply_validation_attempted=True,
                    reasons=_with_resource_close_reasons(
                        timing_reasons,
                        tun_close_result=close_result,
                        dataplane_close_result=dataplane_close_result,
                    ),
                    failure_reason="post_apply_validation_time_invalid",
                    tun_activation_attempted=tun_activation_attempted,
                    tun_activation_count=tun_activation_count,
                    dataplane_activation_attempted=dataplane_activation_attempted,
                    dataplane_activation_count=dataplane_activation_count,
                    **_dataplane_close_evidence_kwargs(dataplane_close_result),
                    **_tun_close_evidence_kwargs(close_result),
                )
            if not post_apply.passed:
                rollback_count = self._rollback_executed(executed)
                dataplane_close_result = self.close_dataplane_resources()
                close_result = self.close_tun_resources()
                return FirstPartyVpnDeploymentExecutionEvidence(
                    target=self.packet.target,
                    action="apply",
                    allowed=True,
                    succeeded=False,
                    command_count=len(commands),
                    executed_count=len(executed),
                    rollback_attempted=True,
                    rollback_count=rollback_count,
                    readiness_hash=readiness_hash,
                    post_apply_hash=post_apply_hash,
                    post_apply_validation_attempted=True,
                    reasons=_with_resource_close_reasons(
                        post_apply.reasons,
                        tun_close_result=close_result,
                        dataplane_close_result=dataplane_close_result,
                    ),
                    failure_reason="post_apply_validation_failed",
                    tun_activation_attempted=tun_activation_attempted,
                    tun_activation_count=tun_activation_count,
                    dataplane_activation_attempted=dataplane_activation_attempted,
                    dataplane_activation_count=dataplane_activation_count,
                    **_dataplane_close_evidence_kwargs(dataplane_close_result),
                    **_tun_close_evidence_kwargs(close_result),
                )
        return FirstPartyVpnDeploymentExecutionEvidence(
            target=self.packet.target,
            action="apply",
            allowed=True,
            succeeded=True,
            command_count=len(commands),
            executed_count=len(executed),
            rollback_attempted=False,
            rollback_count=0,
            readiness_hash=readiness_hash,
            post_apply_hash=post_apply_hash,
            post_apply_validation_attempted=True,
            tun_activation_attempted=tun_activation_attempted,
            tun_activation_count=tun_activation_count,
            dataplane_activation_attempted=dataplane_activation_attempted,
            dataplane_activation_count=dataplane_activation_count,
        )

    def rollback(self) -> FirstPartyVpnDeploymentExecutionEvidence:
        """Run the packet rollback commands after explicit mutation approval."""
        self._assert_mutation_flag()
        readiness_hash = self.packet.readiness_decision.evidence_hash
        commands = self.packet.rollback_commands
        executed = 0
        try:
            for command in commands:
                self.command_runner(command)
                executed += 1
        except Exception as exc:
            dataplane_close_result = self.close_dataplane_resources()
            close_result = self.close_tun_resources()
            return FirstPartyVpnDeploymentExecutionEvidence(
                target=self.packet.target,
                action="rollback",
                allowed=True,
                succeeded=False,
                command_count=len(commands),
                executed_count=executed,
                rollback_attempted=False,
                rollback_count=0,
                readiness_hash=readiness_hash,
                reasons=_with_resource_close_reasons(
                    (),
                    tun_close_result=close_result,
                    dataplane_close_result=dataplane_close_result,
                ),
                failure_reason=type(exc).__name__,
                **_dataplane_close_evidence_kwargs(dataplane_close_result),
                **_tun_close_evidence_kwargs(close_result),
            )
        dataplane_close_result = self.close_dataplane_resources()
        close_result = self.close_tun_resources()
        if close_result.failed or dataplane_close_result.failed:
            return FirstPartyVpnDeploymentExecutionEvidence(
                target=self.packet.target,
                action="rollback",
                allowed=True,
                succeeded=False,
                command_count=len(commands),
                executed_count=executed,
                rollback_attempted=False,
                rollback_count=0,
                readiness_hash=readiness_hash,
                reasons=_with_resource_close_reasons(
                    (),
                    tun_close_result=close_result,
                    dataplane_close_result=dataplane_close_result,
                ),
                failure_reason=(
                    "dataplane_resource_close_failed"
                    if dataplane_close_result.failed
                    else "tun_resource_close_failed"
                ),
                **_dataplane_close_evidence_kwargs(dataplane_close_result),
                **_tun_close_evidence_kwargs(close_result),
            )
        return FirstPartyVpnDeploymentExecutionEvidence(
            target=self.packet.target,
            action="rollback",
            allowed=True,
            succeeded=True,
            command_count=len(commands),
            executed_count=executed,
            rollback_attempted=False,
            rollback_count=0,
            readiness_hash=readiness_hash,
            **_dataplane_close_evidence_kwargs(dataplane_close_result),
            **_tun_close_evidence_kwargs(close_result),
        )

    def _assert_can_mutate(self) -> None:
        self._assert_mutation_flag()
        if not self.packet.readiness_decision.allowed:
            raise FirstPartyVpnDeploymentMutationBlocked(
                "deployment readiness gate blocked OS mutation: "
                + ",".join(self.packet.readiness_decision.reasons)
            )
        if self.post_apply_validator is None:
            raise FirstPartyVpnDeploymentMutationBlocked(
                "deployment post-apply validation is required before OS mutation"
            )
        if self.tun_activator is None:
            raise FirstPartyVpnDeploymentMutationBlocked(
                "deployment TUN activation is required before OS mutation"
            )
        if self.dataplane_activator is None:
            raise FirstPartyVpnDeploymentMutationBlocked(
                "deployment dataplane activation is required before OS mutation"
            )

    def _assert_mutation_flag(self) -> None:
        if not self.allow_os_mutation:
            raise FirstPartyVpnDeploymentMutationBlocked(
                "deployment OS mutation is blocked; set allow_os_mutation=True"
            )

    def _now(self) -> int:
        now = self.now_provider()
        if now < 0:
            raise FirstPartyVpnDeploymentError("deployment clock cannot be negative")
        return now

    def _rollback_executed(self, executed: list[LinuxPolicyCommand]) -> int:
        if not executed:
            return 0
        return self._rollback_all()

    def close_tun_resources(self) -> TunResourceCloseResult:
        attempted = len(self._tun_activation_resources)
        closed = 0
        failed = 0
        while self._tun_activation_resources:
            resource = self._tun_activation_resources.pop()
            try:
                resource.close()
            except Exception:
                failed += 1
                continue
            closed += 1
        return TunResourceCloseResult(attempted=attempted, closed=closed, failed=failed)

    def close_dataplane_resources(self) -> TunResourceCloseResult:
        attempted = len(self._dataplane_activation_resources)
        closed = 0
        failed = 0
        while self._dataplane_activation_resources:
            resource = self._dataplane_activation_resources.pop()
            try:
                resource.close()
            except Exception:
                failed += 1
                continue
            closed += 1
        return TunResourceCloseResult(attempted=attempted, closed=closed, failed=failed)

    def _record_tun_activation(
        self,
        outcome: DeploymentTunActivationOutcome,
    ) -> int:
        if isinstance(outcome, FirstPartyVpnTunActivationResult):
            self._tun_activation_resources.extend(outcome.resources)
            return outcome.count
        if outcome < 0:
            raise FirstPartyVpnDeploymentError("TUN activation count cannot be negative")
        if outcome > 0:
            raise FirstPartyVpnDeploymentError("TUN activation resources are required")
        return outcome

    def _record_dataplane_activation(
        self,
        outcome: DeploymentDataplaneActivationOutcome,
    ) -> int:
        if isinstance(outcome, FirstPartyVpnDataplaneActivationResult):
            self._dataplane_activation_resources.extend(outcome.resources)
            return outcome.count
        if outcome < 0:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation count cannot be negative"
            )
        if outcome > 0:
            raise FirstPartyVpnDeploymentError(
                "dataplane activation resources are required"
            )
        return outcome

    def _rollback_all(self) -> int:
        rollback_count = 0
        for command in self.packet.rollback_commands:
            try:
                self.command_runner(command)
            except Exception:
                continue
            rollback_count += 1
        return rollback_count


def compose_firstparty_tun_activators(
    *activators: DeploymentTunActivator,
) -> DeploymentTunActivator:
    """Compose multiple TUN activators behind the executor's single hook."""
    if not activators:
        raise FirstPartyVpnDeploymentError("TUN activators are required")
    for activator in activators:
        if not callable(activator):
            raise FirstPartyVpnDeploymentError("TUN activators must be callable")

    def activate(
        packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        resources: list[DeploymentTunActivationResource] = []
        count = 0
        try:
            for activator in activators:
                result = _normalize_tun_activation_outcome(activator(packet))
                resources.extend(result.resources)
                count += result.count
        except Exception:
            _close_activation_resources(resources)
            raise
        return FirstPartyVpnTunActivationResult(
            count=count,
            resources=tuple(resources),
        )

    return activate


def compose_firstparty_dataplane_activators(
    *activators: DeploymentDataplaneActivator,
) -> DeploymentDataplaneActivator:
    """Compose multiple dataplane activators behind the executor's single hook."""
    if not activators:
        raise FirstPartyVpnDeploymentError("dataplane activators are required")
    for activator in activators:
        if not callable(activator):
            raise FirstPartyVpnDeploymentError("dataplane activators must be callable")

    def activate(
        packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        resources: list[DeploymentDataplaneActivationResource] = []
        count = 0
        try:
            for activator in activators:
                result = _normalize_dataplane_activation_outcome(activator(packet))
                resources.extend(result.resources)
                count += result.count
        except Exception:
            _close_activation_resources(resources)
            raise
        return FirstPartyVpnDataplaneActivationResult(
            count=count,
            resources=tuple(resources),
        )

    return activate


def _normalize_tun_activation_outcome(
    outcome: DeploymentTunActivationOutcome,
) -> FirstPartyVpnTunActivationResult:
    if isinstance(outcome, FirstPartyVpnTunActivationResult):
        return outcome
    if outcome < 0:
        raise FirstPartyVpnDeploymentError("TUN activation count cannot be negative")
    if outcome > 0:
        raise FirstPartyVpnDeploymentError("TUN activation resources are required")
    return FirstPartyVpnTunActivationResult(count=0, resources=())


def _normalize_dataplane_activation_outcome(
    outcome: DeploymentDataplaneActivationOutcome,
) -> FirstPartyVpnDataplaneActivationResult:
    if isinstance(outcome, FirstPartyVpnDataplaneActivationResult):
        return outcome
    if outcome < 0:
        raise FirstPartyVpnDeploymentError(
            "dataplane activation count cannot be negative"
        )
    if outcome > 0:
        raise FirstPartyVpnDeploymentError(
            "dataplane activation resources are required"
        )
    return FirstPartyVpnDataplaneActivationResult(count=0, resources=())


def _close_activation_resources(
    resources: (
        list[DeploymentTunActivationResource]
        | list[DeploymentDataplaneActivationResource]
    ),
) -> None:
    while resources:
        resource = resources.pop()
        try:
            resource.close()
        except Exception:
            continue


def build_firstparty_dataplane_activator(
    *,
    config: FirstPartyVpnDeploymentConfig,
    start_factory: DeploymentDataplaneStartFactory,
    host: str = "0.0.0.0",
) -> DeploymentDataplaneActivator:
    """Build a deployment activator from the reviewed server NAT listener config."""
    if not callable(start_factory):
        raise FirstPartyVpnDeploymentError("dataplane start factory is required")

    def activate(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        from .service import FirstPartyDataplaneBind

        bind = FirstPartyDataplaneBind.from_server_nat(
            config.server_nat,
            host=host,
        )
        resource = start_factory(bind)
        if not callable(getattr(resource, "close", None)):
            raise FirstPartyVpnDeploymentError(
                "dataplane start factory must return a closeable resource"
            )
        return FirstPartyVpnDataplaneActivationResult(
            count=1,
            resources=(resource,),
        )

    return activate


def build_firstparty_admission_tun_server_activator(
    *,
    config: FirstPartyVpnDeploymentConfig,
    registry: "FirstPartySessionAdmissionRegistry",
    tun_factory: DeploymentAdmissionTunFactory,
    host: str = "0.0.0.0",
    return_transports: tuple["TunReturnTransport", ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: DeploymentAdmissionTunResponseFactory | None = None,
    fragmenter_factory: DeploymentAdmissionTunFragmenterFactory | None = None,
    reassembler_factory: DeploymentAdmissionTunReassemblerFactory | None = None,
    fragmenter: "PacketFragmenter | None" = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> DeploymentDataplaneActivator:
    """Build a deployment activator for the on-demand admission TUN server."""
    if not callable(tun_factory):
        raise FirstPartyVpnDeploymentError("admission TUN factory is required")
    _validate_admission_tun_return_transports(
        config=config,
        return_transports=return_transports,
    )

    def activate(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        from .service import FirstPartyDataplaneBind
        from .tun import open_threaded_firstparty_admission_tun_server

        bind = FirstPartyDataplaneBind.from_server_nat(
            config.server_nat,
            host=host,
        )
        resource = open_threaded_firstparty_admission_tun_server(
            registry=registry,
            tun_factory=tun_factory,
            bind=bind,
            return_transports=return_transports,
            response_factory=response_factory,
            fragmenter_factory=fragmenter_factory,
            reassembler_factory=reassembler_factory,
            fragmenter=fragmenter,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
            start_timeout=start_timeout,
            close_timeout=close_timeout,
        )
        return FirstPartyVpnDataplaneActivationResult(
            count=1,
            resources=(resource,),
        )

    return activate


def _validate_admission_tun_return_transports(
    *,
    config: FirstPartyVpnDeploymentConfig,
    return_transports: tuple["TunReturnTransport", ...],
) -> None:
    if not return_transports:
        raise FirstPartyVpnDeploymentError(
            "admission TUN return transports are required"
        )
    valid_transports = {"udp", "tcp", "camouflage"}
    for transport in return_transports:
        if transport not in valid_transports:
            raise FirstPartyVpnDeploymentError(
                "admission TUN return transport is invalid"
            )
    exposed_transports = config.server_nat.listener_transports
    if not set(return_transports).intersection(exposed_transports):
        raise FirstPartyVpnDeploymentError(
            "admission TUN return transport is not exposed by server NAT"
        )


def build_firstparty_admission_tun_server_activators(
    *,
    config: FirstPartyVpnDeploymentConfig,
    registry: "FirstPartySessionAdmissionRegistry",
    device_factory: DeploymentTunDeviceFactory | None = None,
    host: str = "0.0.0.0",
    return_transports: tuple["TunReturnTransport", ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: DeploymentAdmissionTunResponseFactory | None = None,
    fragmenter_factory: DeploymentAdmissionTunFragmenterFactory | None = None,
    reassembler_factory: DeploymentAdmissionTunReassemblerFactory | None = None,
    fragmenter: "PacketFragmenter | None" = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> DeploymentActivationPair:
    """Build paired activators that open server TUN before admission TUN service."""
    factory = device_factory or (lambda tun_config: LinuxTunDevice(config=tun_config))
    activated_tun: _DeploymentActivatedTunDevice | None = None

    def clear_activated_tun() -> None:
        nonlocal activated_tun
        activated_tun = None

    def tun_activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        nonlocal activated_tun
        if activated_tun is not None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN server TUN is already active"
            )
        raw_device = factory(replace(config.server_tun, allow_os_mutation=True))
        try:
            raw_device.open_interface()
            _assert_tun_capable_device(raw_device, role="admission TUN server")
            activated_tun = _DeploymentActivatedTunDevice(
                device=raw_device,
                on_close=clear_activated_tun,
            )
        except Exception:
            try:
                raw_device.close()
            except Exception:
                pass
            raise
        return FirstPartyVpnTunActivationResult(
            count=1,
            resources=(activated_tun,),
        )

    def tun_factory(_session: "SessionContext") -> "TunDevice":
        if activated_tun is None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN server requires activated TUN"
            )
        return activated_tun

    server_dataplane_activator = build_firstparty_admission_tun_server_activator(
        config=config,
        registry=registry,
        tun_factory=tun_factory,
        host=host,
        return_transports=return_transports,
        response_factory=response_factory,
        fragmenter_factory=fragmenter_factory,
        reassembler_factory=reassembler_factory,
        fragmenter=fragmenter,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        tun_read_timeout=tun_read_timeout,
        max_errors=max_errors,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )

    def dataplane_activator(
        packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        if activated_tun is None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN server requires activated TUN"
            )
        return server_dataplane_activator(packet)

    return tun_activator, dataplane_activator


def build_firstparty_admission_tun_server_pool_activator(
    *,
    config: FirstPartyVpnDeploymentConfig,
    registry: "FirstPartySessionAdmissionRegistry",
    tun_factory: DeploymentAdmissionTunFactory,
    host: str = "0.0.0.0",
    return_transports: tuple["TunReturnTransport", ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: DeploymentAdmissionTunResponseFactory | None = None,
    fragmenter_factory: DeploymentAdmissionTunFragmenterFactory | None = None,
    reassembler_factory: DeploymentAdmissionTunReassemblerFactory | None = None,
    fragmenter: "PacketFragmenter | None" = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> DeploymentDataplaneActivator:
    """Build an admission TUN server activator that owns dynamic session TUNs."""
    if not callable(tun_factory):
        raise FirstPartyVpnDeploymentError("admission TUN factory is required")
    _validate_admission_tun_return_transports(
        config=config,
        return_transports=return_transports,
    )

    def activate(
        packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        pool = _DeploymentAdmissionSessionTunPool(tun_factory=tun_factory)
        server_activator = build_firstparty_admission_tun_server_activator(
            config=config,
            registry=registry,
            tun_factory=pool.tun_for,
            host=host,
            return_transports=return_transports,
            response_factory=response_factory,
            fragmenter_factory=fragmenter_factory,
            reassembler_factory=reassembler_factory,
            fragmenter=fragmenter,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
            start_timeout=start_timeout,
            close_timeout=close_timeout,
        )
        try:
            server_result = server_activator(packet)
        except Exception:
            pool.close()
            raise
        return FirstPartyVpnDataplaneActivationResult(
            count=server_result.count + 1,
            resources=(pool, *server_result.resources),
        )

    return activate


def build_firstparty_admission_tun_client_activators(
    *,
    config: FirstPartyVpnDeploymentConfig,
    hello: "FirstPartyHandshakeHello",
    pqc_material: "PqcSessionSecretMaterial",
    candidates: tuple["DataplaneEndpointCandidate", ...],
    identity_authority: "IdentityVerifier",
    policy: "ZeroTrustPolicy",
    captured_at: int,
    device_factory: DeploymentTunDeviceFactory | None = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    revocations: "RevocationList | None" = None,
    completed_at_provider: "Callable[[FirstPartyHandshakeAccept], int] | None" = None,
    fragmenter: "PacketFragmenter | None" = None,
    reassembler: "PacketReassembler | None" = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> DeploymentActivationPair:
    """Build paired activators that open client TUN before admission TUN pumping."""
    if not candidates:
        raise FirstPartyVpnDeploymentError(
            "admission TUN client candidates are required"
        )
    factory = device_factory or (
        lambda tun_config: LinuxTunDevice(config=tun_config)
    )
    activated_tun: _DeploymentActivatedTunDevice | None = None

    def clear_activated_tun() -> None:
        nonlocal activated_tun
        activated_tun = None

    def tun_activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        nonlocal activated_tun
        if activated_tun is not None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN client TUN is already active"
            )
        raw_device = factory(replace(config.client_tun, allow_os_mutation=True))
        try:
            raw_device.open_interface()
            _assert_tun_capable_device(raw_device)
            activated_tun = _DeploymentActivatedTunDevice(
                device=raw_device,
                on_close=clear_activated_tun,
            )
        except Exception:
            try:
                raw_device.close()
            except Exception:
                pass
            raise
        return FirstPartyVpnTunActivationResult(
            count=1,
            resources=(activated_tun,),
        )

    def dataplane_activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnDataplaneActivationResult:
        if activated_tun is None:
            raise FirstPartyVpnDeploymentError(
                "admission TUN client requires activated TUN"
            )
        from .tun import open_threaded_firstparty_admission_tun_client_pump

        resource = open_threaded_firstparty_admission_tun_client_pump(
            hello=hello,
            pqc_material=pqc_material,
            tun=activated_tun,
            candidates=candidates,
            identity_authority=identity_authority,
            policy=policy,
            captured_at=captured_at,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            fragmenter=fragmenter,
            reassembler=reassembler,
            tun_read_timeout=tun_read_timeout,
            transport_read_timeout=transport_read_timeout,
            max_errors=max_errors,
            start_timeout=start_timeout,
            close_timeout=close_timeout,
        )
        return FirstPartyVpnDataplaneActivationResult(
            count=1,
            resources=(resource,),
        )

    return tun_activator, dataplane_activator


def build_firstparty_admission_vpn_activators(
    *,
    config: FirstPartyVpnDeploymentConfig,
    registry: "FirstPartySessionAdmissionRegistry",
    hello: "FirstPartyHandshakeHello",
    pqc_material: "PqcSessionSecretMaterial",
    candidates: tuple["DataplaneEndpointCandidate", ...],
    identity_authority: "IdentityVerifier",
    policy: "ZeroTrustPolicy",
    captured_at: int,
    server_device_factory: DeploymentTunDeviceFactory | None = None,
    client_device_factory: DeploymentTunDeviceFactory | None = None,
    host: str = "0.0.0.0",
    return_transports: tuple["TunReturnTransport", ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: DeploymentAdmissionTunResponseFactory | None = None,
    server_fragmenter_factory: DeploymentAdmissionTunFragmenterFactory | None = None,
    server_reassembler_factory: DeploymentAdmissionTunReassemblerFactory | None = None,
    server_fragmenter: "PacketFragmenter | None" = None,
    client_fragmenter: "PacketFragmenter | None" = None,
    client_reassembler: "PacketReassembler | None" = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    revocations: "RevocationList | None" = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> DeploymentActivationPair:
    """Build one deployment activation pair for a full admission VPN runtime."""
    server_tun, server_dataplane = build_firstparty_admission_tun_server_activators(
        config=config,
        registry=registry,
        device_factory=server_device_factory,
        host=host,
        return_transports=return_transports,
        response_factory=response_factory,
        fragmenter_factory=server_fragmenter_factory,
        reassembler_factory=server_reassembler_factory,
        fragmenter=server_fragmenter,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        tun_read_timeout=tun_read_timeout,
        max_errors=max_errors,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    client_tun, client_dataplane = build_firstparty_admission_tun_client_activators(
        config=config,
        hello=hello,
        pqc_material=pqc_material,
        candidates=candidates,
        identity_authority=identity_authority,
        policy=policy,
        captured_at=captured_at,
        device_factory=client_device_factory,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        revocations=revocations,
        fragmenter=client_fragmenter,
        reassembler=client_reassembler,
        tun_read_timeout=tun_read_timeout,
        transport_read_timeout=transport_read_timeout,
        max_errors=max_errors,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    return (
        compose_firstparty_tun_activators(server_tun, client_tun),
        compose_firstparty_dataplane_activators(server_dataplane, client_dataplane),
    )


def _assert_tun_capable_device(
    device: object,
    *,
    role: str = "admission TUN client",
) -> None:
    if not isinstance(getattr(device, "mtu", None), int):
        raise FirstPartyVpnDeploymentError(
            f"{role} device must expose MTU"
        )
    for method_name in ("read_packet", "write_packet", "write_packet_nowait"):
        if not callable(getattr(device, method_name, None)):
            raise FirstPartyVpnDeploymentError(
                f"{role} device must implement TUN packet methods"
            )


def _evaluate_deployment_rollout(
    *,
    config: FirstPartyVpnDeploymentConfig,
    facts: LinuxHostFacts,
    evidence: FirstPartyVpnDeploymentEvidence,
    path_exists: PathExists | None = None,
    binary_exists: BinaryExists | None = None,
    now: int | None = None,
) -> _DeploymentRolloutEvaluation:
    client_apply, client_rollback = _client_commands(config)
    server_apply, server_rollback = _server_commands(config)
    apply_commands = client_apply + server_apply
    rollback_commands = server_rollback + client_rollback
    leak_protection = evaluate_linux_leak_protection(
        config=config.client_network,
        commands=client_apply,
    )
    linux_preflight = evaluate_linux_deployment_preflight(
        facts=facts,
        config=config.linux_preflight,
        apply_commands=apply_commands,
        rollback_commands=rollback_commands,
        path_exists=path_exists,
        binary_exists=binary_exists,
    )
    rollout_plan = RolloutPlan(
        target=config.target,
        apply_commands=apply_commands,
        rollback_commands=rollback_commands,
        test_evidence=evidence.test_evidence,
        approval=evidence.approval,
        policy_snapshot_hash=evidence.policy_snapshot_hash,
        preflight_evidence=linux_preflight,
        dataplane_evidence=evidence.dataplane_validation,
        tun_dataplane_evidence=evidence.tun_dataplane_validation,
        mtu_validation_evidence=evidence.mtu_validation,
    )
    rollout_decision = evaluate_rollout_gate(
        rollout_plan,
        expected_test_count=config.expected_test_count,
        required_dataplane_paths=config.required_dataplane_paths,
        now=now,
    )
    return _DeploymentRolloutEvaluation(
        client_apply_commands=client_apply,
        client_rollback_commands=client_rollback,
        server_apply_commands=server_apply,
        server_rollback_commands=server_rollback,
        linux_preflight=linux_preflight,
        leak_protection=leak_protection,
        rollout_plan=rollout_plan,
        rollout_decision=rollout_decision,
    )


def evaluate_firstparty_vpn_deployment_plan_hashes(
    config: FirstPartyVpnDeploymentConfig,
) -> FirstPartyVpnDeploymentPlanHashes:
    """Compute expected command-plan hashes before building readiness evidence."""
    client_apply, client_rollback = _client_commands(config)
    server_apply, server_rollback = _server_commands(config)
    apply_commands = client_apply + server_apply
    rollback_commands = server_rollback + client_rollback
    return FirstPartyVpnDeploymentPlanHashes(
        apply_plan_hash=CommandPlanEvidence.from_commands(
            apply_commands
        ).evidence_hash(),
        rollback_plan_hash=CommandPlanEvidence.from_commands(
            rollback_commands
        ).evidence_hash(),
        leak_protection_plan_hash=CommandPlanEvidence.from_commands(
            client_apply
        ).evidence_hash(),
    )


def evaluate_firstparty_vpn_deployment_host_fingerprint(
    *,
    config: FirstPartyVpnDeploymentConfig,
    facts: LinuxHostFacts,
    path_exists: PathExists | None = None,
    binary_exists: BinaryExists | None = None,
) -> str:
    """Compute the expected Linux host fingerprint for readiness binding."""
    client_apply, client_rollback = _client_commands(config)
    server_apply, server_rollback = _server_commands(config)
    linux_preflight = evaluate_linux_deployment_preflight(
        facts=facts,
        config=config.linux_preflight,
        apply_commands=client_apply + server_apply,
        rollback_commands=server_rollback + client_rollback,
        path_exists=path_exists,
        binary_exists=binary_exists,
    )
    return linux_preflight.host_fingerprint


def evaluate_firstparty_vpn_deployment_rollout_gate(
    *,
    config: FirstPartyVpnDeploymentConfig,
    facts: LinuxHostFacts,
    evidence: FirstPartyVpnDeploymentEvidence,
    path_exists: PathExists | None = None,
    binary_exists: BinaryExists | None = None,
    now: int | None = None,
) -> RolloutGateDecision:
    """Evaluate the rollout gate before binding its hash into deployment config."""
    return _evaluate_deployment_rollout(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=now,
    ).rollout_decision


def build_firstparty_vpn_deployment_packet(
    *,
    config: FirstPartyVpnDeploymentConfig,
    facts: LinuxHostFacts,
    evidence: FirstPartyVpnDeploymentEvidence,
    path_exists: PathExists | None = None,
    binary_exists: BinaryExists | None = None,
    now: int | None = None,
) -> FirstPartyVpnDeploymentPacket:
    """Build a reviewable client/server deployment packet without applying it."""
    rollout_evaluation = _evaluate_deployment_rollout(
        config=config,
        facts=facts,
        evidence=evidence,
        path_exists=path_exists,
        binary_exists=binary_exists,
        now=now,
    )
    client_apply = rollout_evaluation.client_apply_commands
    client_rollback = rollout_evaluation.client_rollback_commands
    server_apply = rollout_evaluation.server_apply_commands
    server_rollback = rollout_evaluation.server_rollback_commands
    linux_preflight = rollout_evaluation.linux_preflight
    leak_protection = rollout_evaluation.leak_protection
    rollout_plan = rollout_evaluation.rollout_plan
    rollout_decision = rollout_evaluation.rollout_decision
    readiness_evidence = FullVpnProductionReadinessEvidence(
        target=config.target,
        linux_preflight=linux_preflight,
        leak_protection=leak_protection,
        dataplane_validation=evidence.dataplane_validation,
        tun_dataplane_validation=evidence.tun_dataplane_validation,
        mtu_validation=evidence.mtu_validation,
        pqc_provider_gate=evidence.pqc_provider_gate,
        pqc_manifest=evidence.pqc_manifest,
        pqc_kat=evidence.pqc_kat,
        identity_signer_gate=evidence.identity_signer_gate,
        identity_signer_manifest=evidence.identity_signer_manifest,
        identity_signer_kat=evidence.identity_signer_kat,
        identity_signer_conformance=evidence.identity_signer_conformance,
        external_policy_source=evidence.external_policy_source,
        rekey_policy=evidence.rekey_policy,
        rollout_gate=rollout_decision,
        source_audit=evidence.source_audit,
        zero_trust_policy=evidence.zero_trust_policy,
        policy_snapshot_hash=evidence.policy_snapshot_hash,
    )
    readiness_decision = evaluate_full_vpn_production_readiness(
        FullVpnProductionReadinessRequirements(
            target=config.target,
            required_dataplane_paths=config.required_dataplane_paths,
            required_dataplane_transports=config.required_dataplane_transports,
            required_dataplane_probe_matrix_hash=config.dataplane_probe_matrix_hash,
            required_linux_host_fingerprint=config.linux_host_fingerprint,
            required_pqc_manifest_hash=config.pqc_manifest_hash,
            required_identity_signer_manifest_hash=config.identity_signer_manifest_hash,
            required_apply_plan_hash=config.apply_plan_hash,
            required_rollback_plan_hash=config.rollback_plan_hash,
            required_leak_protection_plan_hash=config.leak_protection_plan_hash,
            required_external_policy_source_hash=config.external_policy_source_hash,
            required_policy_snapshot_hash=config.policy_snapshot_hash,
            required_zero_trust_policy_hash=config.zero_trust_policy_hash,
            required_source_audit_root_hash=config.source_audit_root_hash,
            required_source_audit_tree_hash=config.source_audit_tree_hash,
            required_rekey_rollback_plan_hash=config.rekey_rollback_plan_hash,
            required_rollout_gate_hash=config.rollout_gate_hash,
            evaluated_at=now,
        ),
        readiness_evidence,
    )
    return FirstPartyVpnDeploymentPacket(
        target=config.target,
        client_apply_commands=client_apply,
        client_rollback_commands=client_rollback,
        server_apply_commands=server_apply,
        server_rollback_commands=server_rollback,
        linux_preflight=linux_preflight,
        leak_protection=leak_protection,
        rollout_plan=rollout_plan,
        rollout_decision=rollout_decision,
        readiness_evidence=readiness_evidence,
        readiness_decision=readiness_decision,
    )


def build_linux_post_apply_validator(
    *,
    config: FirstPartyVpnDeploymentConfig,
    command_runner: LinuxAppliedStateCommandRunner | None = None,
    now: int | None = None,
) -> DeploymentPostApplyValidator:
    """Build a read-only post-apply validator for one deployment config."""

    def validator(_packet: FirstPartyVpnDeploymentPacket) -> LinuxAppliedStateEvidence:
        snapshot = collect_linux_applied_state_snapshot(
            command_runner=command_runner,
            now=now,
        )
        return evaluate_linux_applied_state(
            client_network=config.client_network,
            server_nat=config.server_nat,
            client_tun=config.client_tun,
            server_tun=config.server_tun,
            snapshot=snapshot,
        )

    return validator


def build_linux_tun_activator(
    *,
    config: FirstPartyVpnDeploymentConfig,
    scope: DeploymentTunActivationScope = "both",
    device_factory: DeploymentTunDeviceFactory | None = None,
) -> DeploymentTunActivator:
    """Build a gated TUN activator that opens OS TUN interfaces before commands."""
    if scope not in ("client", "server", "both"):
        raise FirstPartyVpnDeploymentError("TUN activation scope is invalid")
    factory = device_factory or (lambda tun_config: LinuxTunDevice(config=tun_config))

    def activator(
        _packet: FirstPartyVpnDeploymentPacket,
    ) -> FirstPartyVpnTunActivationResult:
        opened: list[DeploymentTunActivationResource] = []
        try:
            for tun_config in _tun_activation_configs(config=config, scope=scope):
                device = factory(replace(tun_config, allow_os_mutation=True))
                device.open_interface()
                opened.append(device)
        except Exception:
            for resource in reversed(opened):
                try:
                    resource.close()
                except Exception:
                    continue
            raise
        return FirstPartyVpnTunActivationResult(
            count=len(opened),
            resources=tuple(opened),
        )

    return activator


def _tun_activation_configs(
    *,
    config: FirstPartyVpnDeploymentConfig,
    scope: DeploymentTunActivationScope,
) -> tuple[LinuxTunConfig, ...]:
    if scope == "client":
        return (config.client_tun,)
    if scope == "server":
        return (config.server_tun,)
    return (config.client_tun, config.server_tun)


def _post_apply_timing_reasons(
    *,
    post_apply: LinuxAppliedStateEvidence,
    apply_started_at: int,
    checked_at: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if checked_at < apply_started_at:
        reasons.append("post_apply_validation_clock_rollback")
    if post_apply.captured_at < apply_started_at:
        reasons.append("post_apply_validation_before_apply")
    if post_apply.captured_at > checked_at:
        reasons.append("post_apply_validation_from_future")
    return tuple(reasons)


def _tun_close_evidence_kwargs(
    close_result: TunResourceCloseResult,
) -> dict[str, object]:
    return {
        "tun_resource_close_attempted": close_result.attempted_any,
        "tun_resource_close_count": close_result.closed,
        "tun_resource_close_failed_count": close_result.failed,
    }


def _dataplane_close_evidence_kwargs(
    close_result: TunResourceCloseResult,
) -> dict[str, object]:
    return {
        "dataplane_resource_close_attempted": close_result.attempted_any,
        "dataplane_resource_close_count": close_result.closed,
        "dataplane_resource_close_failed_count": close_result.failed,
    }


def _with_resource_close_reasons(
    reasons: tuple[str, ...],
    *,
    tun_close_result: TunResourceCloseResult,
    dataplane_close_result: TunResourceCloseResult,
) -> tuple[str, ...]:
    all_reasons = reasons
    if dataplane_close_result.failed:
        all_reasons = (*all_reasons, "dataplane_resource_close_failed")
    if tun_close_result.failed:
        all_reasons = (*all_reasons, "tun_resource_close_failed")
    return tuple(dict.fromkeys(all_reasons))


def _client_commands(
    config: FirstPartyVpnDeploymentConfig,
) -> tuple[tuple[LinuxPolicyCommand, ...], tuple[LinuxPolicyCommand, ...]]:
    network = LinuxNetworkPolicyPlanner(config=config.client_network)
    apply_commands = config.client_tun.network_commands() + network.planned_commands()
    rollback_commands = network.rollback_commands() + (
        ("ip", "link", "delete", config.client_tun.name),
    )
    return apply_commands, rollback_commands


def _server_commands(
    config: FirstPartyVpnDeploymentConfig,
) -> tuple[tuple[LinuxPolicyCommand, ...], tuple[LinuxPolicyCommand, ...]]:
    nat = LinuxServerNatPlanner(config=config.server_nat)
    apply_commands = config.server_tun.network_commands() + nat.planned_commands()
    rollback_commands = nat.rollback_commands() + (
        ("ip", "link", "delete", config.server_tun.name),
    )
    return apply_commands, rollback_commands


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
