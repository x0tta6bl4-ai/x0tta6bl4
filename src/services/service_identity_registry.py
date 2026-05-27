"""Registry of event-producing services that resolve canonical identity."""

from __future__ import annotations

from typing import Dict, List, Tuple

from src.services.service_event_identity import service_event_identity_status


IDENTITY_STATUS_CLAIM_BOUNDARY = (
    "Configuration presence only. The status surface reports whether identity "
    "fields are configured and which environment tier supplied them; it does "
    "not expose SPIFFE IDs, DIDs, wallet addresses, or prove live SPIRE/chain state."
)

KNOWN_EVENT_IDENTITY_SERVICES: Tuple[Dict[str, str], ...] = (
    {
        "service_name": "maas-governance",
        "layer": "api_to_control_plane",
        "entrypoint": "src/api/maas_governance.py",
    },
    {
        "service_name": "dao-executor",
        "layer": "dao_to_control_plane",
        "entrypoint": "src/dao/executor_webhook.py",
    },
    {
        "service_name": "dao-governance",
        "layer": "dao_to_control_plane",
        "entrypoint": "src/dao/governance.py",
    },
    {
        "service_name": "governance-contract",
        "layer": "dao_to_chain_control",
        "entrypoint": "src/dao/governance_contract.py",
    },
    {
        "service_name": "dao-proposal-executor",
        "layer": "dao_to_control_plane",
        "entrypoint": "src/dao/proposal_executor_webhook.py",
    },
    {
        "service_name": "token-bridge",
        "layer": "dao_chain_bridge",
        "entrypoint": "src/dao/token_bridge.py",
    },
    {
        "service_name": "mesh-vpn-bridge",
        "layer": "network_to_rewards",
        "entrypoint": "src/network/mesh_vpn_bridge.py",
    },
    {
        "service_name": "mptcp-manager",
        "layer": "network_to_control_plane",
        "entrypoint": "src/network/mptcp_manager.py",
    },
    {
        "service_name": "spire-agent-manager",
        "layer": "security_identity_to_control_plane",
        "entrypoint": "src/security/spiffe/agent/manager.py",
    },
    {
        "service_name": "spire-server-client",
        "layer": "security_identity_to_control_plane",
        "entrypoint": "src/security/spiffe/server/client.py",
    },
    {
        "service_name": "ebpf-self-healing",
        "layer": "self_healing_to_control_plane",
        "entrypoint": "src/self_healing/ebpf_anomaly_detector.py",
    },
    {
        "service_name": "spiffe-mapek-loop",
        "layer": "self_healing_identity_loop",
        "entrypoint": "src/self_healing/mape_k_spiffe_integration.py",
    },
    {
        "service_name": "pqc-zero-trust-executor",
        "layer": "self_healing_pqc_identity",
        "entrypoint": "src/self_healing/pqc_zero_trust_healer.py",
    },
    {
        "service_name": "recovery-action-executor",
        "layer": "self_healing_to_control_plane",
        "entrypoint": "src/self_healing/recovery/executor.py",
    },
    {
        "service_name": "ghost-l3-server",
        "layer": "server_to_control_plane",
        "entrypoint": "src/server/ghost_server.py",
    },
    {
        "service_name": "maas-janitor",
        "layer": "commerce_maintenance_to_events",
        "entrypoint": "src/services/marketplace_janitor.py",
    },
    {
        "service_name": "maas-settlement",
        "layer": "commerce_settlement_to_events",
        "entrypoint": "src/services/marketplace_settlement.py",
    },
    {
        "service_name": "pqc-rotator",
        "layer": "security_service_to_control_plane",
        "entrypoint": "src/services/pqc_rotator_service.py",
    },
    {
        "service_name": "share-to-earn",
        "layer": "network_usage_to_rewards",
        "entrypoint": "src/services/share_to_earn_service.py",
    },
    {
        "service_name": "swarm-mapek",
        "layer": "swarm_to_control_plane",
        "entrypoint": "src/swarm/intelligence.py",
    },
    {
        "service_name": "swarm-pbft",
        "layer": "swarm_consensus_to_control_plane",
        "entrypoint": "src/swarm/pbft.py",
    },
)


def service_identity_registry_status() -> Dict[str, object]:
    """Return redacted identity configuration status for all known services."""
    services: List[Dict[str, object]] = []
    for registration in KNOWN_EVENT_IDENTITY_SERVICES:
        status = service_event_identity_status(
            service_name=registration["service_name"]
        )
        services.append({**registration, **status})

    return {
        "status": "ok",
        "claim_boundary": IDENTITY_STATUS_CLAIM_BOUNDARY,
        "redacted": True,
        "identity_fields": [
            "spiffe_id",
            "did",
            "wallet_address",
        ],
        "services_total": len(services),
        "services_with_any_identity": sum(
            1 for service in services if service["configured_fields"]
        ),
        "services_complete": sum(1 for service in services if service["complete"]),
        "services": services,
    }
