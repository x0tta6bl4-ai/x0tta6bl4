"""First-party VPN deployment package.

Re-exports from core.py and models.py for the parent package.
"""

from __future__ import annotations

from .core import (
    FirstPartyVpnDeploymentExecutor,
)
from .models import (
    # Errors
    FirstPartyVpnDeploymentError,
    FirstPartyVpnDeploymentMutationBlocked,
    # Config
    FirstPartyVpnDeploymentConfig,
    # Evidence
    FirstPartyVpnDeploymentEvidence,
    FirstPartyVpnDeploymentExecutionEvidence,
    LinuxAppliedStateEvidence,
    # Hashes
    FirstPartyVpnDeploymentPlanHashes,
    # Packet
    FirstPartyVpnDeploymentPacket,
    # Results
    FirstPartyVpnDataplaneActivationResult,
    FirstPartyVpnTunActivationResult,
    # Activators
    DeploymentCommandRunner,
    DeploymentDataplaneActivator,
    DeploymentDataplaneActivationOutcome,
    DeploymentDataplaneActivationResource,
    DeploymentPostApplyValidator,
    DeploymentTunActivator,
    DeploymentTunActivationOutcome,
    DeploymentTunActivationResource,
    TunResourceCloseResult,
    LinuxPolicyCommand,
    # Builder stubs
    build_firstparty_admission_vpn_activators,
    build_firstparty_admission_tun_client_activators,
    build_firstparty_admission_tun_server_activator,
    build_firstparty_admission_tun_server_activators,
    build_firstparty_admission_tun_server_pool_activator,
    build_firstparty_dataplane_activator,
    build_linux_post_apply_validator,
    build_linux_tun_activator,
    build_firstparty_vpn_deployment_packet,
    compose_firstparty_dataplane_activators,
    compose_firstparty_tun_activators,
    evaluate_firstparty_vpn_deployment_host_fingerprint,
    evaluate_firstparty_vpn_deployment_plan_hashes,
    evaluate_firstparty_vpn_deployment_rollout_gate,
)
