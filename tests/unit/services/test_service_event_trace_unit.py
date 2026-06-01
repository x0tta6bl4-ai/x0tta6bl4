from __future__ import annotations

from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import (
    get_service_event_history,
    get_service_event_replay,
    service_event_trace_history,
    service_event_trace_filter,
)
from src.services.service_identity_registry import KNOWN_EVENT_TRACE_SERVICES
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.reward_events import publish_reward_settlement_event


def _source_agent(service: dict[str, str]) -> str:
    return service.get("source_agent") or service["service_name"]


def test_service_event_trace_filter_maps_layer_to_registered_source_agents():
    trace_filter = service_event_trace_filter(layer="dao_to_control_plane")

    expected = sorted(
        _source_agent(service)
        for service in KNOWN_EVENT_TRACE_SERVICES
        if service["layer"] == "dao_to_control_plane"
    )
    assert trace_filter["status"] == "ok"
    assert trace_filter["redacted"] is True
    assert trace_filter["source_agents"] == expected
    assert trace_filter["services_total"] == len(expected)


def test_service_event_trace_filter_reports_unknown_without_values():
    trace_filter = service_event_trace_filter(service_name="missing-service")

    assert trace_filter["status"] == "unknown_filter"
    assert trace_filter["source_agents"] == []
    assert trace_filter["services"] == []


def test_service_event_trace_filter_includes_route_only_marketplace_api():
    trace_filter = service_event_trace_filter(service_name="maas-marketplace")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-marketplace"]
    assert trace_filter["services"][0]["layer"] == "api_to_commerce"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_marketplace.py"
    assert trace_filter["services"][0]["identity_source"] == "request_user_identity"


def test_service_event_trace_filter_includes_maas_auth_register():
    trace_filter = service_event_trace_filter(service_name="maas-auth-register")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-register"]
    assert trace_filter["services"][0]["layer"] == "api_auth_registration_intent"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert trace_filter["services"][0]["identity_source"] == "auth_register_request"


def test_service_event_trace_filter_includes_maas_auth_login():
    trace_filter = service_event_trace_filter(service_name="maas-auth-login")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-login"]
    assert trace_filter["services"][0]["layer"] == "api_auth_login_intent"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert trace_filter["services"][0]["identity_source"] == "auth_login_request"


def test_service_event_trace_filter_includes_maas_auth_api_key_rotation():
    trace_filter = service_event_trace_filter(
        service_name="maas-auth-api-key-rotation"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-api-key-rotation"]
    assert trace_filter["services"][0]["layer"] == "api_auth_credential_rotation"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_api_key_rotation_request"
    )


def test_service_event_trace_filter_includes_maas_auth_admin_promotion():
    trace_filter = service_event_trace_filter(
        service_name="maas-auth-admin-promotion"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-admin-promotion"]
    assert trace_filter["services"][0]["layer"] == (
        "api_auth_admin_privilege_control"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_admin_promotion_request"
    )


def test_service_event_trace_filter_includes_maas_auth_bootstrap_admin():
    trace_filter = service_event_trace_filter(
        service_name="maas-auth-bootstrap-admin"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-bootstrap-admin"]
    assert trace_filter["services"][0]["layer"] == (
        "api_auth_bootstrap_admin_control"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_bootstrap_admin_request"
    )


def test_service_event_trace_filter_includes_maas_auth_oidc_login():
    trace_filter = service_event_trace_filter(service_name="maas-auth-oidc-login")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-oidc-login"]
    assert trace_filter["services"][0]["layer"] == "api_auth_oidc_redirect_intent"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_oidc_redirect_request"
    )


def test_service_event_trace_filter_includes_maas_auth_oidc_callback():
    trace_filter = service_event_trace_filter(
        service_name="maas-auth-oidc-callback"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-oidc-callback"]
    assert trace_filter["services"][0]["layer"] == "api_auth_oidc_callback_control"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_oidc_callback_request"
    )


def test_service_event_trace_filter_includes_maas_auth_credential_resolver():
    trace_filter = service_event_trace_filter(
        service_name="maas-auth-credential-resolver"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-credential-resolver"]
    assert trace_filter["services"][0]["layer"] == "api_auth_credential_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert trace_filter["services"][0]["identity_source"] == "auth_request_credentials"


def test_service_event_trace_filter_includes_maas_auth_profile_read():
    trace_filter = service_event_trace_filter(service_name="maas-auth-profile-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-profile-read"]
    assert trace_filter["services"][0]["layer"] == "api_auth_profile_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert trace_filter["services"][0]["identity_source"] == "auth_profile_request_user"


def test_service_event_trace_filter_includes_maas_auth_api_key_read():
    trace_filter = service_event_trace_filter(service_name="maas-auth-api-key-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-auth-api-key-read"]
    assert trace_filter["services"][0]["layer"] == "api_auth_api_key_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_auth.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "auth_api_key_read_request_user"
    )


def test_service_event_trace_filter_includes_modular_maas_auth():
    trace_filter = service_event_trace_filter(service_name="maas-auth")

    expected = sorted(
        [
            "maas-modular-auth-account-delete",
            "maas-modular-auth-api-key-rotation",
            "maas-modular-auth-login",
            "maas-modular-auth-profile-read",
            "maas-modular-auth-register",
            "maas-modular-auth-session-control",
        ]
    )
    services_by_source = {
        service["source_agent"]: service
        for service in trace_filter["services"]
    }

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == expected
    assert services_by_source["maas-modular-auth-register"]["layer"] == (
        "api_modular_auth_registration_intent"
    )
    assert services_by_source["maas-modular-auth-register"]["entrypoint"] == (
        "src/api/maas/endpoints/auth.py"
    )
    assert services_by_source["maas-modular-auth-register"]["identity_source"] == (
        "modular_auth_register_request"
    )
    assert services_by_source["maas-modular-auth-login"]["layer"] == (
        "api_modular_auth_login_intent"
    )
    assert services_by_source["maas-modular-auth-api-key-rotation"]["layer"] == (
        "api_modular_auth_credential_rotation"
    )
    assert services_by_source["maas-modular-auth-profile-read"]["layer"] == (
        "api_modular_auth_profile_observed_state"
    )
    assert services_by_source["maas-modular-auth-session-control"]["layer"] == (
        "api_modular_auth_session_control_action"
    )
    assert services_by_source["maas-modular-auth-account-delete"]["layer"] == (
        "api_modular_auth_account_delete_control_action"
    )


def test_service_event_trace_filter_includes_maas_dashboard_summary_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-dashboard-summary-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-dashboard-summary-read"]
    assert trace_filter["services"][0]["layer"] == "api_dashboard_summary_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_dashboard.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "dashboard_summary_request_user"
    )


def test_service_event_trace_filter_includes_maas_dashboard_analytics_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-dashboard-analytics-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-dashboard-analytics-read"]
    assert trace_filter["services"][0]["layer"] == (
        "api_dashboard_analytics_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_dashboard.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "dashboard_analytics_request_user"
    )


def test_service_event_trace_filter_includes_maas_dashboard_node_read():
    trace_filter = service_event_trace_filter(service_name="maas-dashboard-node-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-dashboard-node-read"]
    assert trace_filter["services"][0]["layer"] == "api_dashboard_node_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_dashboard.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "dashboard_nodes_request_user"
    )


def test_service_event_trace_filter_includes_maas_analytics_summary_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-analytics-summary-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-analytics-summary-read"]
    assert trace_filter["services"][0]["layer"] == "api_analytics_summary_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_analytics.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "analytics_summary_request_user"
    )


def test_service_event_trace_filter_includes_maas_analytics_timeseries_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-analytics-timeseries-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-analytics-timeseries-read"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_analytics_timeseries_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_analytics.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "analytics_timeseries_request_user"
    )


def test_service_event_trace_filter_includes_maas_analytics_roi_read():
    trace_filter = service_event_trace_filter(service_name="maas-analytics-roi-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-analytics-roi-read"]
    assert trace_filter["services"][0]["layer"] == "api_analytics_roi_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_analytics.py"
    assert trace_filter["services"][0]["identity_source"] == "analytics_roi_request_user"


def test_service_event_trace_filter_includes_maas_policies_list_read():
    trace_filter = service_event_trace_filter(service_name="maas-policies-list-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-policies-list-read"]
    assert trace_filter["services"][0]["layer"] == "api_policy_acl_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_policies.py"
    assert trace_filter["services"][0]["identity_source"] == "policy_list_request_user"


def test_service_event_trace_filter_includes_maas_policies_create():
    trace_filter = service_event_trace_filter(service_name="maas-policies-create")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-policies-create"]
    assert trace_filter["services"][0]["layer"] == "api_policy_acl_control_action"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_policies.py"
    assert trace_filter["services"][0]["identity_source"] == "policy_create_request_user"


def test_service_event_trace_filter_includes_maas_policies_delete():
    trace_filter = service_event_trace_filter(service_name="maas-policies-delete")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-policies-delete"]
    assert trace_filter["services"][0]["layer"] == "api_policy_acl_control_action"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_policies.py"
    assert trace_filter["services"][0]["identity_source"] == "policy_delete_request_user"


def test_service_event_trace_filter_includes_maas_supply_chain_sbom_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-sbom-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-sbom-read"]
    assert trace_filter["services"][0]["layer"] == "api_supply_chain_sbom_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_public_sbom_request"
    )


def test_service_event_trace_filter_includes_maas_supply_chain_sbom_list_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-sbom-list-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-sbom-list-read"]
    assert trace_filter["services"][0]["layer"] == "api_supply_chain_sbom_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_public_sbom_list_request"
    )


def test_service_event_trace_filter_includes_maas_supply_chain_artifact_register():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-artifact-register"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-artifact-register"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_supply_chain_artifact_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_register_request_user"
    )


def test_service_event_trace_filter_includes_maas_supply_chain_binary_verify():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-binary-verify"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-binary-verify"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_supply_chain_binary_attestation_control"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_binary_verify_request"
    )


def test_service_event_trace_filter_includes_maas_supply_chain_node_attestation_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-node-attestation-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-node-attestation-read"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_supply_chain_attestation_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_node_attestation_request_user"
    )


def test_service_event_trace_filter_includes_maas_supply_chain_mesh_attestation_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-supply-chain-mesh-attestation-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-supply-chain-mesh-attestation-read"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_supply_chain_attestation_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_supply_chain.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "supply_chain_mesh_attestation_request_user"
    )


def test_service_event_trace_filter_includes_maas_playbooks_create():
    trace_filter = service_event_trace_filter(service_name="maas-playbooks-create")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-playbooks-create"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_playbook_signed_command_control"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_playbooks.py"
    assert trace_filter["services"][0]["identity_source"] == "playbook_create_request_user"


def test_service_event_trace_filter_includes_maas_playbooks_poll():
    trace_filter = service_event_trace_filter(service_name="maas-playbooks-poll")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-playbooks-poll"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_playbook_signed_command_dispatch"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_playbooks.py"
    assert trace_filter["services"][0]["identity_source"] == "playbook_node_poll_request"


def test_service_event_trace_filter_includes_maas_playbooks_ack():
    trace_filter = service_event_trace_filter(service_name="maas-playbooks-ack")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-playbooks-ack"]
    assert trace_filter["services"][0]["layer"] == "api_playbook_ack_control"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_playbooks.py"
    assert trace_filter["services"][0]["identity_source"] == "playbook_node_ack_request"


def test_service_event_trace_filter_includes_maas_playbooks_list_read():
    trace_filter = service_event_trace_filter(service_name="maas-playbooks-list-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-playbooks-list-read"]
    assert trace_filter["services"][0]["layer"] == "api_playbook_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_playbooks.py"
    assert trace_filter["services"][0]["identity_source"] == "playbook_list_request_user"


def test_service_event_trace_filter_includes_maas_playbooks_status_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-playbooks-status-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-playbooks-status-read"]
    assert trace_filter["services"][0]["layer"] == "api_playbook_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_playbooks.py"
    assert trace_filter["services"][0]["identity_source"] == "playbook_status_request_user"


def test_service_event_trace_filter_includes_maas_governance_proposal_create():
    trace_filter = service_event_trace_filter(
        service_name="maas-governance-proposal-create"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-governance-proposal-create"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_governance_proposal_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_governance.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "governance_proposal_create_request_user"
    )


def test_service_event_trace_filter_includes_maas_governance_vote_cast():
    trace_filter = service_event_trace_filter(
        service_name="maas-governance-vote-cast"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-governance-vote-cast"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_governance_vote_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_governance.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "governance_vote_request_user"
    )


def test_service_event_trace_filter_includes_maas_governance_proposal_execute():
    trace_filter = service_event_trace_filter(
        service_name="maas-governance-proposal-execute"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-governance-proposal-execute"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_governance_execution_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_governance.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "governance_execute_request_user"
    )


def test_service_event_trace_filter_includes_maas_governance_observed_state_reads():
    trace_filter = service_event_trace_filter(layer="api_governance_observed_state")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-governance-proposal-list-read",
        "maas-governance-proposal-read",
    ]
    assert {service["entrypoint"] for service in trace_filter["services"]} == {
        "src/api/maas_governance.py"
    }
    assert {
        service["identity_source"] for service in trace_filter["services"]
    } == {
        "governance_proposal_list_request",
        "governance_proposal_read_request",
    }


def test_service_event_trace_filter_includes_maas_agent_health_status_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-agent-health-status-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-agent-health-status-read"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_agent_mesh_health_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_agent_mesh.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "agent_health_status_request_user"
    )


def test_service_event_trace_filter_includes_maas_agent_health_run():
    trace_filter = service_event_trace_filter(service_name="maas-agent-health-run")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-agent-health-run"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_agent_mesh_health_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_agent_mesh.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "agent_health_run_request_user"
    )


def test_service_event_trace_filter_includes_maas_agent_health_observed_state_layer():
    trace_filter = service_event_trace_filter(
        layer="api_agent_mesh_health_observed_state"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-agent-health-history-read",
        "maas-agent-health-status-read",
    ]
    assert {service["entrypoint"] for service in trace_filter["services"]} == {
        "src/api/maas_agent_mesh.py"
    }
    assert {
        service["identity_source"] for service in trace_filter["services"]
    } == {
        "agent_health_history_request_user",
        "agent_health_status_request_user",
    }


def test_service_event_trace_filter_includes_maas_provisioning_setup_generate():
    trace_filter = service_event_trace_filter(
        service_name="maas-provisioning-setup-generate"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-provisioning-setup-generate"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_provisioning_node_join_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_provisioning.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "provisioning_generate_setup_request_user"
    )


def test_service_event_trace_filter_includes_billing_api_checkout_session():
    trace_filter = service_event_trace_filter(
        service_name="billing-api-checkout-session"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["billing-api-checkout-session"]
    assert trace_filter["services"][0]["layer"] == "api_billing_checkout_intent"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/billing.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "billing_checkout_session_request"
    )


def test_service_event_trace_filter_includes_billing_api_observed_state_reads():
    trace_filter = service_event_trace_filter(
        layer="api_billing_order_status_observed_state"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["billing-api-order-status-read"]
    assert trace_filter["services"][0]["entrypoint"] == "src/api/billing.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "billing_order_status_request"
    )


def test_service_event_trace_filter_includes_maas_compat_audit_read():
    trace_filter = service_event_trace_filter(service_name="maas-compat-audit-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-audit-read"]
    assert trace_filter["services"][0]["layer"] == "api_compat_audit_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_audit_log_request"
    )


def test_service_event_trace_filter_includes_maas_compat_mapek_read():
    trace_filter = service_event_trace_filter(service_name="maas-compat-mapek-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-mapek-read"]
    assert trace_filter["services"][0]["layer"] == "api_compat_mapek_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_mapek_event_read_request"
    )


def test_service_event_trace_filter_includes_maas_compat_lifecycle_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-compat-lifecycle-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-lifecycle-read"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_lifecycle_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_mesh_lifecycle_read_request"
    )


def test_service_event_trace_filter_includes_maas_compat_auth_register():
    trace_filter = service_event_trace_filter(service_name="maas-compat-auth-register")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-auth-register"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_auth_registration_intent"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_auth_register_request"
    )


def test_service_event_trace_filter_includes_maas_compat_deploy():
    trace_filter = service_event_trace_filter(service_name="maas-compat-deploy")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-deploy"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_mesh_deploy_request"
    )


def test_service_event_trace_filter_includes_maas_compat_scale():
    trace_filter = service_event_trace_filter(service_name="maas-compat-scale")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-scale"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_mesh_scale_request"
    )


def test_service_event_trace_filter_includes_maas_compat_terminate():
    trace_filter = service_event_trace_filter(service_name="maas-compat-terminate")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-terminate"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_mesh_terminate_request"
    )


def test_service_event_trace_filter_includes_maas_compat_billing_pay():
    trace_filter = service_event_trace_filter(service_name="maas-compat-billing-pay")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-compat-billing-pay"]
    assert (
        trace_filter["services"][0]["layer"]
        == "api_compat_billing_pay_intent"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_compat.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "compat_billing_pay_request"
    )


def test_service_event_trace_filter_includes_modular_maas_mesh():
    trace_filter = service_event_trace_filter(service_name="maas-mesh")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-modular-mesh-deploy",
        "maas-modular-mesh-read",
        "maas-modular-mesh-scale",
        "maas-modular-mesh-terminate",
    ]
    services_by_source = {
        _source_agent(service): service for service in trace_filter["services"]
    }
    assert services_by_source["maas-modular-mesh-deploy"]["layer"] == (
        "api_modular_mesh_deploy_control_action"
    )
    assert services_by_source["maas-modular-mesh-deploy"]["entrypoint"] == (
        "src/api/maas/endpoints/mesh.py"
    )
    assert services_by_source["maas-modular-mesh-deploy"]["identity_source"] == (
        "modular_mesh_deploy_request"
    )
    assert services_by_source["maas-modular-mesh-read"]["layer"] == (
        "api_modular_mesh_lifecycle_observed_state"
    )
    assert services_by_source["maas-modular-mesh-read"]["entrypoint"] == (
        "src/api/maas/endpoints/mesh.py"
    )
    assert services_by_source["maas-modular-mesh-read"]["identity_source"] == (
        "modular_mesh_read_request"
    )
    assert services_by_source["maas-modular-mesh-scale"]["layer"] == (
        "api_modular_mesh_scale_control_action"
    )
    assert services_by_source["maas-modular-mesh-scale"]["entrypoint"] == (
        "src/api/maas/endpoints/mesh.py"
    )
    assert services_by_source["maas-modular-mesh-scale"]["identity_source"] == (
        "modular_mesh_scale_request"
    )
    assert services_by_source["maas-modular-mesh-terminate"]["layer"] == (
        "api_modular_mesh_terminate_control_action"
    )
    assert services_by_source["maas-modular-mesh-terminate"]["entrypoint"] == (
        "src/api/maas/endpoints/mesh.py"
    )
    assert services_by_source["maas-modular-mesh-terminate"]["identity_source"] == (
        "modular_mesh_terminate_request"
    )


def test_service_event_trace_filter_includes_modular_maas_batman():
    trace_filter = service_event_trace_filter(service_name="maas-batman")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-modular-batman-healing-control",
        "maas-modular-batman-health-read",
        "maas-modular-batman-mapek-control",
        "maas-modular-batman-metrics-read",
        "maas-modular-batman-topology-read",
    ]
    services_by_source = {
        _source_agent(service): service for service in trace_filter["services"]
    }
    assert services_by_source["maas-modular-batman-health-read"]["layer"] == (
        "api_modular_batman_health_observed_state"
    )
    assert services_by_source["maas-modular-batman-health-read"]["entrypoint"] == (
        "src/api/maas/endpoints/batman.py"
    )
    assert services_by_source["maas-modular-batman-health-read"][
        "identity_source"
    ] == "modular_batman_health_request"
    assert services_by_source["maas-modular-batman-metrics-read"]["layer"] == (
        "api_modular_batman_metrics_observed_state"
    )
    assert services_by_source["maas-modular-batman-metrics-read"]["entrypoint"] == (
        "src/api/maas/endpoints/batman.py"
    )
    assert services_by_source["maas-modular-batman-metrics-read"][
        "identity_source"
    ] == "modular_batman_metrics_request"
    assert services_by_source["maas-modular-batman-topology-read"]["layer"] == (
        "api_modular_batman_topology_observed_state"
    )
    assert services_by_source["maas-modular-batman-topology-read"]["entrypoint"] == (
        "src/api/maas/endpoints/batman.py"
    )
    assert services_by_source["maas-modular-batman-topology-read"][
        "identity_source"
    ] == "modular_batman_topology_request"
    assert services_by_source["maas-modular-batman-mapek-control"]["layer"] == (
        "api_modular_batman_mapek_control_action"
    )
    assert services_by_source["maas-modular-batman-mapek-control"]["entrypoint"] == (
        "src/api/maas/endpoints/batman.py"
    )
    assert services_by_source["maas-modular-batman-mapek-control"][
        "identity_source"
    ] == "modular_batman_mapek_request"
    assert services_by_source["maas-modular-batman-healing-control"]["layer"] == (
        "api_modular_batman_healing_control_action"
    )
    assert services_by_source["maas-modular-batman-healing-control"]["entrypoint"] == (
        "src/api/maas/endpoints/batman.py"
    )
    assert services_by_source["maas-modular-batman-healing-control"][
        "identity_source"
    ] == "modular_batman_healing_request"


def test_service_event_trace_filter_includes_modular_maas_pilot():
    trace_filter = service_event_trace_filter(service_name="maas-pilot")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-modular-pilot-activate",
        "maas-modular-pilot-signup",
        "maas-modular-pilot-status-read",
    ]
    services_by_source = {
        _source_agent(service): service for service in trace_filter["services"]
    }
    assert services_by_source["maas-modular-pilot-signup"]["layer"] == (
        "api_modular_pilot_signup_control_action"
    )
    assert services_by_source["maas-modular-pilot-signup"]["entrypoint"] == (
        "src/api/maas/endpoints/pilot.py"
    )
    assert services_by_source["maas-modular-pilot-signup"]["identity_source"] == (
        "modular_pilot_signup_request"
    )
    assert services_by_source["maas-modular-pilot-status-read"]["layer"] == (
        "api_modular_pilot_status_observed_state"
    )
    assert services_by_source["maas-modular-pilot-status-read"]["entrypoint"] == (
        "src/api/maas/endpoints/pilot.py"
    )
    assert services_by_source["maas-modular-pilot-status-read"][
        "identity_source"
    ] == "modular_pilot_status_request"
    assert services_by_source["maas-modular-pilot-activate"]["layer"] == (
        "api_modular_pilot_activation_control_action"
    )
    assert services_by_source["maas-modular-pilot-activate"]["entrypoint"] == (
        "src/api/maas/endpoints/pilot.py"
    )
    assert services_by_source["maas-modular-pilot-activate"][
        "identity_source"
    ] == "modular_pilot_activate_request"


def test_service_event_trace_filter_includes_node_heartbeat_escrow_bridge():
    trace_filter = service_event_trace_filter(service_name="maas-nodes")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-modular-node-heartbeat",
        "maas-modular-node-lifecycle",
        "maas-modular-node-read",
        "maas-modular-node-registration",
        "maas-nodes-heartbeat",
    ]
    services_by_source = {
        _source_agent(service): service for service in trace_filter["services"]
    }
    assert services_by_source["maas-nodes-heartbeat"]["layer"] == "api_mesh_to_commerce"
    assert (
        services_by_source["maas-nodes-heartbeat"]["entrypoint"]
        == "src/api/maas_nodes.py"
    )
    assert (
        services_by_source["maas-nodes-heartbeat"]["identity_source"]
        == "node_heartbeat_auto_release"
    )
    assert services_by_source["maas-modular-node-registration"]["layer"] == (
        "api_modular_node_registration_control_action"
    )
    assert services_by_source["maas-modular-node-registration"]["entrypoint"] == (
        "src/api/maas/endpoints/nodes.py"
    )
    assert services_by_source["maas-modular-node-registration"]["identity_source"] == (
        "modular_node_registration_request"
    )
    assert services_by_source["maas-modular-node-heartbeat"]["layer"] == (
        "api_modular_node_heartbeat_observed_state"
    )
    assert services_by_source["maas-modular-node-heartbeat"]["entrypoint"] == (
        "src/api/maas/endpoints/nodes.py"
    )
    assert services_by_source["maas-modular-node-heartbeat"]["identity_source"] == (
        "modular_node_heartbeat_request"
    )
    assert services_by_source["maas-modular-node-read"]["layer"] == (
        "api_modular_node_observed_state"
    )
    assert services_by_source["maas-modular-node-read"]["entrypoint"] == (
        "src/api/maas/endpoints/nodes.py"
    )
    assert services_by_source["maas-modular-node-read"]["identity_source"] == (
        "modular_node_read_request"
    )
    assert services_by_source["maas-modular-node-lifecycle"]["layer"] == (
        "api_modular_node_lifecycle_control_action"
    )
    assert services_by_source["maas-modular-node-lifecycle"]["entrypoint"] == (
        "src/api/maas/endpoints/nodes.py"
    )
    assert services_by_source["maas-modular-node-lifecycle"]["identity_source"] == (
        "modular_node_lifecycle_request"
    )


def test_service_event_trace_filter_includes_maas_telemetry():
    trace_filter = service_event_trace_filter(service_name="maas-telemetry")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-telemetry"]
    assert trace_filter["services"][0]["layer"] == "api_telemetry_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_telemetry.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "telemetry_helper_or_request"
    )


def test_service_event_trace_filter_includes_legacy_heartbeat():
    trace_filter = service_event_trace_filter(service_name="maas-legacy-heartbeat")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-heartbeat"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_heartbeat_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_heartbeat_request"
    )


def test_service_event_trace_filter_includes_legacy_lifecycle():
    trace_filter = service_event_trace_filter(service_name="maas-legacy-lifecycle")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-lifecycle"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_mesh_lifecycle_request"
    )


def test_service_event_trace_filter_includes_legacy_lifecycle_read():
    trace_filter = service_event_trace_filter(
        service_name="maas-legacy-lifecycle-read"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-lifecycle-read"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_lifecycle_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_mesh_lifecycle_read_request"
    )


def test_service_event_trace_filter_includes_legacy_node_lifecycle():
    trace_filter = service_event_trace_filter(
        service_name="maas-legacy-node-lifecycle"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-node-lifecycle"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_node_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_node_lifecycle_request"
    )


def test_service_event_trace_filter_includes_legacy_node_read():
    trace_filter = service_event_trace_filter(service_name="maas-legacy-node-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-node-read"]
    assert trace_filter["services"][0]["layer"] == "api_legacy_node_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_node_read_request"
    )


def test_service_event_trace_filter_includes_legacy_mapek_read():
    trace_filter = service_event_trace_filter(service_name="maas-legacy-mapek-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-mapek-read"]
    assert trace_filter["services"][0]["layer"] == "api_legacy_mapek_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_mapek_event_read_request"
    )


def test_service_event_trace_filter_includes_legacy_token_lifecycle():
    trace_filter = service_event_trace_filter(
        service_name="maas-legacy-token-lifecycle"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-token-lifecycle"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_token_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_join_token_rotation_request"
    )


def test_service_event_trace_filter_includes_legacy_policy_lifecycle():
    trace_filter = service_event_trace_filter(
        service_name="maas-legacy-policy-lifecycle"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-policy-lifecycle"]
    assert trace_filter["services"][0]["layer"] == (
        "api_legacy_policy_lifecycle_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_policy_lifecycle_request"
    )


def test_service_event_trace_filter_includes_legacy_policy_read():
    trace_filter = service_event_trace_filter(service_name="maas-legacy-policy-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["maas-legacy-policy-read"]
    assert trace_filter["services"][0]["layer"] == "api_legacy_policy_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/api/maas_legacy.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "legacy_policy_read_request"
    )


def test_service_event_trace_filter_includes_route_only_billing_webhook():
    trace_filter = service_event_trace_filter(service_name="maas-billing")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == [
        "maas-billing",
        "maas-billing-checkout",
        "maas-billing-customer-portal",
        "maas-billing-history",
        "maas-billing-invoice",
        "maas-billing-manual-payment",
        "maas-billing-subscription-checkout",
        "maas-billing-subscription-sync",
        "maas-billing-subscription-webhook",
        "maas-legacy-billing",
        "maas-legacy-billing-usage",
        "maas-modular-billing-estimate-read",
        "maas-modular-billing-invoice-generation",
        "maas-modular-billing-payment-intent",
        "maas-modular-billing-plan-read",
        "maas-modular-billing-usage-read",
        "maas-modular-billing-webhook",
    ]
    services_by_source = {
        _source_agent(service): service for service in trace_filter["services"]
    }
    assert services_by_source["maas-billing"]["layer"] == (
        "billing_webhook_to_commerce_bridge"
    )
    assert services_by_source["maas-billing"]["entrypoint"] == "src/api/maas_billing.py"
    assert (
        services_by_source["maas-billing"]["identity_source"]
        == "stripe_webhook_metadata"
    )
    assert services_by_source["maas-billing-invoice"]["layer"] == (
        "billing_invoice_generation"
    )
    assert (
        services_by_source["maas-billing-invoice"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-invoice"]["identity_source"]
        == "billing_invoice_request"
    )
    assert services_by_source["maas-billing-checkout"]["layer"] == (
        "billing_checkout_intent"
    )
    assert (
        services_by_source["maas-billing-checkout"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-checkout"]["identity_source"]
        == "billing_checkout_request"
    )
    assert services_by_source["maas-billing-customer-portal"]["layer"] == (
        "billing_customer_portal_intent"
    )
    assert (
        services_by_source["maas-billing-customer-portal"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-customer-portal"]["identity_source"]
        == "billing_customer_portal_request"
    )
    assert services_by_source["maas-billing-history"]["layer"] == (
        "billing_history_observed_state"
    )
    assert (
        services_by_source["maas-billing-history"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-history"]["identity_source"]
        == "billing_history_request"
    )
    assert services_by_source["maas-billing-manual-payment"]["layer"] == (
        "billing_manual_payment_mock"
    )
    assert (
        services_by_source["maas-billing-manual-payment"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-manual-payment"]["identity_source"]
        == "manual_invoice_payment_request"
    )
    assert services_by_source["maas-modular-billing-payment-intent"]["layer"] == (
        "api_modular_billing_payment_intent"
    )
    assert (
        services_by_source["maas-modular-billing-payment-intent"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-payment-intent"]["identity_source"]
        == "modular_billing_payment_request"
    )
    assert services_by_source["maas-modular-billing-estimate-read"]["layer"] == (
        "api_modular_billing_estimate_observed_state"
    )
    assert (
        services_by_source["maas-modular-billing-estimate-read"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-estimate-read"]["identity_source"]
        == "modular_billing_estimate_request"
    )
    assert services_by_source["maas-modular-billing-invoice-generation"]["layer"] == (
        "api_modular_billing_invoice_generation"
    )
    assert (
        services_by_source["maas-modular-billing-invoice-generation"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-invoice-generation"][
            "identity_source"
        ]
        == "modular_billing_invoice_request"
    )
    assert services_by_source["maas-modular-billing-plan-read"]["layer"] == (
        "api_modular_billing_plan_observed_state"
    )
    assert (
        services_by_source["maas-modular-billing-plan-read"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-plan-read"]["identity_source"]
        == "modular_billing_plan_request"
    )
    assert services_by_source["maas-modular-billing-usage-read"]["layer"] == (
        "api_modular_billing_usage_observed_state"
    )
    assert (
        services_by_source["maas-modular-billing-usage-read"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-usage-read"]["identity_source"]
        == "modular_billing_usage_request"
    )
    assert services_by_source["maas-modular-billing-webhook"]["layer"] == (
        "api_modular_billing_webhook_lifecycle"
    )
    assert (
        services_by_source["maas-modular-billing-webhook"]["entrypoint"]
        == "src/api/maas/endpoints/billing.py"
    )
    assert (
        services_by_source["maas-modular-billing-webhook"]["identity_source"]
        == "modular_billing_webhook_request"
    )
    assert services_by_source["maas-billing-subscription-checkout"]["layer"] == (
        "billing_subscription_checkout_intent"
    )
    assert (
        services_by_source["maas-billing-subscription-checkout"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-subscription-checkout"]["identity_source"]
        == "billing_subscription_checkout_request"
    )
    assert services_by_source["maas-billing-subscription-sync"]["layer"] == (
        "billing_subscription_sync"
    )
    assert (
        services_by_source["maas-billing-subscription-sync"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-subscription-sync"]["identity_source"]
        == "stripe_subscription_sync"
    )
    assert services_by_source["maas-billing-subscription-webhook"]["layer"] == (
        "billing_subscription_webhook_lifecycle"
    )
    assert (
        services_by_source["maas-billing-subscription-webhook"]["entrypoint"]
        == "src/api/maas_billing.py"
    )
    assert (
        services_by_source["maas-billing-subscription-webhook"]["identity_source"]
        == "stripe_subscription_webhook"
    )
    assert services_by_source["maas-legacy-billing"]["layer"] == (
        "billing_webhook_to_commerce_bridge"
    )
    assert (
        services_by_source["maas-legacy-billing"]["entrypoint"]
        == "src/api/maas_legacy.py"
    )
    assert (
        services_by_source["maas-legacy-billing"]["identity_source"]
        == "legacy_billing_webhook_request"
    )
    assert services_by_source["maas-legacy-billing-usage"]["layer"] == (
        "billing_usage_observed_state"
    )
    assert (
        services_by_source["maas-legacy-billing-usage"]["entrypoint"]
        == "src/api/maas_legacy.py"
    )
    assert (
        services_by_source["maas-legacy-billing-usage"]["identity_source"]
        == "legacy_billing_usage_request"
    )


def test_service_event_trace_filter_uses_source_agent_alias():
    trace_filter = service_event_trace_filter(service_name="pqc-zero-trust-executor")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["pqc-zero-trust-healer"]
    assert trace_filter["services"][0]["service_name"] == "pqc-zero-trust-executor"
    assert trace_filter["services"][0]["source_agent"] == "pqc-zero-trust-healer"


def test_service_event_trace_filter_includes_yggdrasil_client():
    trace_filter = service_event_trace_filter(service_name="yggdrasil-client")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["yggdrasil-client"]
    assert trace_filter["services"][0]["layer"] == "network_yggdrasil_observed_state"
    assert (
        trace_filter["services"][0]["entrypoint"] == "src/network/yggdrasil_client.py"
    )


def test_service_event_trace_filter_includes_mptcp_status_read():
    trace_filter = service_event_trace_filter(service_name="mptcp-manager-status-read")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["mptcp-manager-status-read"]
    assert trace_filter["services"][0]["layer"] == "network_mptcp_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/network/mptcp_manager.py"
    assert (
        trace_filter["services"][0]["identity_source"]
        == "local_mptcp_kernel_status_read"
    )


def test_service_event_trace_filter_includes_proxy_orchestrator():
    trace_filter = service_event_trace_filter(service_name="proxy-orchestrator")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["proxy-orchestrator"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_proxy_orchestrator_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/proxy_orchestrator.py"
    )


def test_service_event_trace_filter_includes_proxy_metrics_collector():
    trace_filter = service_event_trace_filter(service_name="proxy-metrics-collector")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["proxy-metrics-collector"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_proxy_metrics_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/proxy_metrics_collector.py"
    )


def test_service_event_trace_filter_includes_proxy_control_plane():
    trace_filter = service_event_trace_filter(service_name="proxy-control-plane")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["proxy-control-plane"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_proxy_control_plane_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/proxy_control_plane.py"
    )


def test_service_event_trace_filter_includes_geo_proxy_shard_manager():
    trace_filter = service_event_trace_filter(
        service_name="geo-proxy-shard-manager"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["geo-proxy-shard-manager"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_geo_proxy_sharding_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/geo_proxy_sharding.py"
    )


def test_service_event_trace_filter_includes_proxy_selection_algorithm():
    trace_filter = service_event_trace_filter(
        service_name="proxy-selection-algorithm"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["proxy-selection-algorithm"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_proxy_selection_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/proxy_selection_algorithm.py"
    )


def test_service_event_trace_filter_includes_reputation_scoring_system():
    trace_filter = service_event_trace_filter(
        service_name="reputation-scoring-system"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["reputation-scoring-system"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_reputation_scoring_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/reputation_scoring.py"
    )


def test_service_event_trace_filter_includes_residential_proxy_manager():
    trace_filter = service_event_trace_filter(
        service_name="residential-proxy-manager"
    )

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["residential-proxy-manager"]
    assert (
        trace_filter["services"][0]["layer"]
        == "network_residential_proxy_manager_observed_state"
    )
    assert (
        trace_filter["services"][0]["entrypoint"]
        == "src/network/residential_proxy_manager.py"
    )


def test_service_event_trace_filter_includes_real_network_adapter():
    trace_filter = service_event_trace_filter(service_name="real-network-adapter")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["real-network-adapter"]
    assert trace_filter["services"][0]["layer"] == "mesh_real_network_observed_state"
    assert (
        trace_filter["services"][0]["entrypoint"] == "src/mesh/real_network_adapter.py"
    )


def test_service_event_trace_filter_includes_mesh_network_manager():
    trace_filter = service_event_trace_filter(service_name="mesh-network-manager")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["mesh-network-manager"]
    assert trace_filter["services"][0]["layer"] == "mesh_network_manager_observed_state"
    assert trace_filter["services"][0]["entrypoint"] == "src/mesh/network_manager.py"


def test_service_event_trace_filter_includes_mesh_action_enforcer():
    trace_filter = service_event_trace_filter(service_name="mesh-action-enforcer")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["mesh-action-enforcer"]
    assert trace_filter["services"][0]["layer"] == (
        "mesh_action_enforcer_control_action"
    )
    assert trace_filter["services"][0]["entrypoint"] == "src/mesh/action_enforcer.py"


def test_service_event_trace_filter_includes_mesh_yggdrasil_optimizer():
    trace_filter = service_event_trace_filter(service_name="mesh-yggdrasil-optimizer")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["mesh-yggdrasil-optimizer"]
    assert trace_filter["services"][0]["layer"] == (
        "mesh_yggdrasil_optimizer_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == (
        "src/mesh/yggdrasil_optimizer.py"
    )


def test_service_event_trace_filter_includes_mesh_telemetry_collector():
    trace_filter = service_event_trace_filter(service_name="mesh-telemetry-collector")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["mesh-telemetry-collector"]
    assert trace_filter["services"][0]["layer"] == (
        "mesh_telemetry_collector_observed_state"
    )
    assert trace_filter["services"][0]["entrypoint"] == (
        "src/mesh/telemetry_collector.py"
    )


def test_service_event_trace_filter_includes_core_mapek_loop():
    trace_filter = service_event_trace_filter(service_name="core-mapek-loop")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["core-mapek-loop"]
    assert trace_filter["services"][0]["layer"] == "core_mapek_control_spine"
    assert trace_filter["services"][0]["entrypoint"] == "src/core/mape_k_loop.py"


def test_service_event_trace_filter_includes_self_healing_mapek():
    trace_filter = service_event_trace_filter(service_name="self-healing-mapek")

    assert trace_filter["status"] == "ok"
    assert trace_filter["source_agents"] == ["self-healing-mapek"]
    assert trace_filter["services"][0]["layer"] == "self_healing_mapek_control_spine"
    assert trace_filter["services"][0]["entrypoint"] == (
        "src/self_healing/mape_k/manager.py"
    )


def test_service_event_trace_summarizes_self_healing_safe_actuator_metadata(
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "self-healing-mapek",
        {
            "component": "self_healing.mape_k",
            "operation": "execute",
            "service_name": "self-healing-mapek",
            "layer": "self_healing_mapek_control_spine",
            "safe_actuator": True,
            "success": True,
            "safe_actuator_evidence_metadata": {
                "schema": "x0tta6bl4.safe_actuator.evidence_metadata.v1",
                "claim_gate": {
                    "schema": (
                        "x0tta6bl4.self_healing_mapek."
                        "safe_actuator_claim_gate.v1"
                    ),
                    "surface": "self_healing.mapek.execute",
                    "local_control_action_claim_allowed": True,
                    "safe_actuator_result_successful": True,
                    "safe_actuator_result_simulated": False,
                    "dataplane_confirmed": True,
                    "post_action_dataplane_revalidated": True,
                    "restored_dataplane_claim_allowed": True,
                    "traffic_delivery_claim_allowed": False,
                    "customer_traffic_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "blockers": [],
                    "claim_boundary": "bounded self-healing evidence only",
                    "redacted": True,
                },
                "evidence": {
                    "event_ids": ["evt-secret-self-heal"],
                    "events_total": 1,
                    "source_agents": ["recovery-action-executor"],
                    "redacted": True,
                },
                "event_ids": ["evt-secret-self-heal"],
                "source_agents": ["recovery-action-executor"],
                "claim_boundary": "bounded self-healing evidence only",
                "redacted": True,
            },
            "claim_boundary": "Self-healing local control evidence only.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="self-healing-mapek",
        limit=10,
    )
    summary = payload["events"][0]["evidence_summary"]
    metadata = summary["safe_actuator_evidence_metadata"]
    profile = summary["cross_plane_evidence_profile"]
    summary_text = str(summary)

    assert metadata["present"] is True
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["evidence"]["event_ids_count"] == 1
    assert metadata["evidence"]["source_agents_count"] == 1
    assert metadata["claim_gate"]["local_control_action_claim_allowed"] is True
    assert metadata["claim_gate"]["restored_dataplane_claim_allowed"] is True
    assert metadata["claim_gate"]["traffic_delivery_claim_allowed"] is False
    assert metadata["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert metadata["claim_gate"]["production_readiness_claim_allowed"] is False
    assert profile["dataplane_confirmed"] is True
    assert profile["safe_actuator_evidence_gate_required"] is True
    assert profile["safe_actuator_evidence_gate_allowed"] is True
    assert profile["production_ready_candidate"] is False
    assert "evt-secret-self-heal" not in summary_text


def test_service_event_trace_blocks_self_healing_dataplane_without_safe_gate(
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "self-healing-mapek",
        {
            "component": "self_healing.mape_k",
            "operation": "execute",
            "service_name": "self-healing-mapek",
            "layer": "self_healing_mapek_control_spine",
            "safe_actuator": True,
            "success": True,
            "safe_actuator_evidence_metadata": {
                "schema": "x0tta6bl4.safe_actuator.evidence_metadata.v1",
                "claim_gate": {
                    "schema": (
                        "x0tta6bl4.self_healing_mapek."
                        "safe_actuator_claim_gate.v1"
                    ),
                    "surface": "self_healing.mapek.execute",
                    "local_control_action_claim_allowed": True,
                    "dataplane_confirmed": True,
                    "post_action_dataplane_revalidated": False,
                    "restored_dataplane_claim_allowed": False,
                    "traffic_delivery_claim_allowed": False,
                    "customer_traffic_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "blockers": ["bounded_dataplane_probe_not_confirmed"],
                    "claim_boundary": "bounded self-healing evidence only",
                    "redacted": True,
                },
                "evidence": {
                    "event_ids": ["evt-secret-self-heal"],
                    "events_total": 1,
                    "source_agents": ["recovery-action-executor"],
                    "redacted": True,
                },
                "redacted": True,
            },
            "claim_boundary": "Self-healing local control evidence only.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="self-healing-mapek",
        limit=10,
    )
    profile = payload["events"][0]["evidence_summary"][
        "cross_plane_evidence_profile"
    ]

    assert profile["raw_dataplane_confirmed"] is True
    assert profile["dataplane_confirmed"] is False
    assert profile["safe_actuator_evidence_gate_required"] is True
    assert profile["safe_actuator_evidence_gate_allowed"] is False
    assert "safe_actuator_evidence_claim_gate_not_allowed" in profile[
        "dataplane_claim_blockers"
    ]
    assert "bounded_dataplane_probe_not_confirmed" in profile[
        "dataplane_claim_blockers"
    ]


def test_service_event_history_and_replay_use_registry_filters(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    consensus = bus.publish(
        EventType.PIPELINE_STAGE_START,
        "swarm-pbft",
        {"stage": "consensus"},
        target_agents={"agent-b"},
    )
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "pqc-rotator",
        {"stage": "rotation"},
        target_agents={"agent-b"},
    )
    bus.publish(
        EventType.SYSTEM_ALERT,
        "unregistered-service",
        {"stage": "noise"},
        target_agents={"agent-b"},
    )

    history = get_service_event_history(
        bus,
        service_name="swarm-pbft",
        limit=10,
    )
    assert [event.event_id for event in history] == [consensus.event_id]

    replay = get_service_event_replay(
        bus,
        "agent-b",
        layer="swarm_consensus_to_control_plane",
    )
    assert [event.event_id for event in replay] == [consensus.event_id]


def test_service_event_history_uses_source_agent_alias(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "pqc-zero-trust-healer",
        {"stage": "action_completed"},
    )

    history = get_service_event_history(
        bus,
        service_name="pqc-zero-trust-executor",
        limit=10,
    )

    assert [item.event_id for item in history] == [event.event_id]


def test_service_event_trace_history_redacts_identity_values(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_START,
        "swarm-pbft",
        {
            "spiffe_id": "spiffe://secret/workload",
            "did": "did:mesh:secret",
            "wallet_address": "0xffffffffffffffffffffffffffffffffffffffff",
            "reward_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "escrow_id": "escrow-secret",
            "listing_id": "listing-secret",
            "mesh_id": "mesh-secret",
            "identity": {
                "spiffe_id": "spiffe://secret/nested",
                "api_token": "secret-value-that-must-not-leak",
                "node_id": "node-1",
                "actor_id": "actor-secret",
                "renter_id": "renter-secret",
                "reward_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="swarm-pbft",
        limit=10,
    )
    text = str(payload)

    assert payload["events_total"] == 1
    assert payload["events"][0]["data"]["spiffe_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["spiffe_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["api_token"] == "[redacted]"
    assert payload["events"][0]["data"]["reward_address"] == "[redacted]"
    assert payload["events"][0]["data"]["escrow_id"] == "[redacted]"
    assert payload["events"][0]["data"]["listing_id"] == "[redacted]"
    assert payload["events"][0]["data"]["mesh_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["node_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["actor_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["renter_id"] == "[redacted]"
    assert payload["events"][0]["data"]["identity"]["reward_address"] == "[redacted]"
    assert "spiffe://secret" not in text
    assert "did:mesh:secret" not in text
    assert "secret-value-that-must-not-leak" not in text
    assert "0xffff" not in text
    assert "0xbbbb" not in text
    assert "0xaaaa" not in text
    assert "node-1" not in text
    assert "escrow-secret" not in text
    assert "listing-secret" not in text
    assert "mesh-secret" not in text
    assert "actor-secret" not in text
    assert "renter-secret" not in text


def test_service_event_trace_history_summarizes_reward_claim_gate(tmp_path):
    bus = EventBus(project_root=str(tmp_path))

    event_id = publish_reward_settlement_event(
        transition="recorded",
        source_agent="share-to-earn",
        node_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        node_id="node-reward-secret",
        spiffe_id="spiffe://secret/reward",
        did="did:mesh:secret-reward",
        wallet_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        packets=250,
        amount="0.0250",
        status="local_accounting_only",
        submitted_transaction=False,
        simulated=True,
        settlement_recorded=False,
        local_accounting_recorded=True,
        upstream_event_ids=["evt-mesh-secret"],
        upstream_source_agents=["mesh-vpn-bridge"],
        upstream_claim_gate={
            "schema": "x0tta6bl4.integration_spine.claim_gate.v1",
            "surface": "integration_spine.reward_context",
            "status": "reward_context",
            "local_actuator_execution_claim_allowed": True,
            "external_settlement_finality_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "blocked_claim_ids": ["settlement_finality", "dataplane_delivery"],
            "raw_payload": "must-not-copy",
        },
        upstream_cross_plane_claim_gate={
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": "integration_spine.reward_context",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": ["settlement_finality", "dataplane_delivery"],
            "blockers": ["integration_spine_local_contract_only"],
            "raw_payload": "must-not-copy",
        },
        event_bus=bus,
    )

    payload = service_event_trace_history(
        bus,
        service_name="share-to-earn",
        limit=10,
    )
    event = payload["events"][0]
    summary = event["evidence_summary"]
    profile = summary["cross_plane_evidence_profile"]
    economy_finality = summary["economy_finality_summary"]
    reward_gate = summary["reward_claim_gate"]
    text = str(payload)
    summary_text = str(summary)

    assert event["event_id"] == event_id
    assert profile["primary_status"] == "local_only"
    assert profile["economy_evidence_present"] is True
    assert profile["dataplane_confirmed"] is False
    assert profile["settlement_confirmed"] is False
    assert profile["production_ready_candidate"] is False
    assert "economy_plane" in profile["planes_observed"]
    assert reward_gate == {
        "present": True,
        "decision": "local_reward_accounting_only",
        "local_reward_accounting_claim_allowed": True,
        "pending_token_submission_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "token_settlement_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_upstream_dataplane_evidence_for_traffic_claim": True,
        "requires_chain_finality_evidence_for_settlement_claim": True,
        "simulated": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    assert economy_finality["present"] is True
    assert economy_finality["local_or_pending_only"] is True
    assert summary["upstream_evidence"]["upstream_claim_boundary_present"] is True
    assert summary["upstream_evidence"]["claim_gate_summary"]["surface"] == (
        "integration_spine.reward_context"
    )
    assert (
        summary["upstream_evidence"]["claim_gate_summary"][
            "external_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert summary["upstream_evidence"]["cross_plane_claim_gate_summary"]["allowed"] is False
    assert economy_finality["upstream_claim_boundary_present"] is True
    assert economy_finality["upstream_claim_gate"] == {
        "present": True,
        "surface": "integration_spine.reward_context",
        "local_actuator_execution_claim_allowed": True,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "payloads_redacted": True,
    }
    assert economy_finality["upstream_cross_plane_claim_gate"] == {
        "present": True,
        "surface": "integration_spine.reward_context",
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "payloads_redacted": True,
    }
    assert economy_finality["high_risk_claim_gate"]["present"] is True
    assert (
        economy_finality["high_risk_claim_gate"][
            "local_or_pending_economy_claim_allowed"
        ]
        is True
    )
    assert (
        economy_finality["high_risk_claim_gate"][
            "token_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert "external_settlement_finality_missing" in (
        economy_finality["high_risk_claim_gate"]["blockers"]
    )
    assert economy_finality["reward_claim_gate"] == {
        "present": True,
        "decision": "local_reward_accounting_only",
        "local_reward_accounting_claim_allowed": True,
        "pending_token_submission_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "token_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }
    assert event["data"]["node_id"] == "[redacted]"
    assert event["data"]["reward_address"] == "[redacted]"
    assert event["data"]["identity"]["wallet_address"] == "[redacted]"
    assert "node-reward-secret" not in text
    assert "evt-mesh-secret" not in summary_text
    assert "must-not-copy" not in summary_text
    assert "0xbbbb" not in text


def test_service_event_trace_history_summarizes_marketplace_request_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    listing_id = "listing-secret"
    idempotency_key = "idem-secret"

    publish_marketplace_escrow_event(
        transition="held",
        source_agent="maas-marketplace",
        escrow_id="escrow-secret",
        listing_id=listing_id,
        renter_id="renter-secret",
        actor_id="renter-secret",
        currency="X0T",
        status="held",
        node_id="node-secret",
        mesh_id="mesh-secret",
        spiffe_id="spiffe://secret/workload",
        did="did:mesh:secret",
        wallet_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        upstream_event_ids=["evt-lock-secret"],
        upstream_source_agents=["token-bridge"],
        request_evidence={
            "action": "rent_node",
            "route": "POST /rent/{listing_id}",
            "actor_role": "user",
            "request_scope_hash": "scope-hash",
            "idempotency_key_present": True,
            "idempotency_key_hash": "idem-hash",
            "idempotency_key": idempotency_key,
            "db_write_ready": True,
            "listing_status": "available",
            "currency": "X0T",
            "hours": 2,
            "renter_matches_listing": False,
            "admin_override": False,
            "service_identity_present": {
                "spiffe_id": True,
                "did": True,
                "wallet_address": True,
            },
            "listing_id": listing_id,
        },
        settlement_evidence={
            "decision_basis": "uptime_tracker_cached_window",
            "source_quality": "telemetry_eventbus_linked_uptime_tracker",
            "settlement_action": "release",
            "duration_ms": 12.25,
            "dataplane_confirmed": False,
            "threshold_met": True,
            "uptime_percent": 1.0,
            "uptime_threshold": 0.999,
            "measurement_window_hours": 24,
            "bridge_evidence": {
                "attempted": True,
                "status": "released",
                "source_agent": "token-bridge",
                "payloads_redacted": True,
            },
            "db_write_evidence": {
                "storage_backend": "sqlalchemy",
                "attempted": True,
                "committed": True,
                "payloads_redacted": True,
            },
            "output_summary": {
                "escrow_status_after": "released",
                "listing_status_after": "rented",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            "claim_gate": {
                "decision": "local_escrow_lifecycle_only",
                "local_escrow_lifecycle_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_dataplane_evidence_for_delivery_claim": True,
                "requires_external_finality_evidence_for_settlement_claim": True,
                "bridge_status": "released",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            "telemetry_evidence": {
                "event_ids": ["evt-telemetry-secret"],
                "source_agents": ["maas-telemetry"],
            },
        },
        event_bus=bus,
    )

    payload = service_event_trace_history(
        bus,
        service_name="maas-marketplace",
        limit=10,
    )
    event = payload["events"][0]
    summary = event["evidence_summary"]
    text = str(payload)
    summary_text = str(summary)

    assert payload["events_total"] == 1
    assert summary["available"] is True
    profile = summary["cross_plane_evidence_profile"]
    assert profile["primary_status"] == "local_only"
    assert profile["planes_observed"] == [
        "trust_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert profile["local_only"] is True
    assert profile["dataplane_confirmed"] is False
    assert profile["trust_metadata_present"] is True
    assert profile["trust_confirmed"] is False
    assert profile["settlement_confirmed"] is False
    assert profile["economy_evidence_present"] is True
    assert profile["production_ready_candidate"] is False
    economy_finality = summary["economy_finality_summary"]
    assert economy_finality["present"] is True
    assert economy_finality["local_or_pending_only"] is True
    assert economy_finality["submitted_transaction_only"] is False
    assert economy_finality["payment_provider_settlement_confirmed"] is False
    assert economy_finality["bank_settlement_confirmed"] is False
    assert economy_finality["token_settlement_finality_confirmed"] is False
    assert economy_finality["settlement_confirmed"] is False
    assert economy_finality["dataplane_confirmed"] is False
    assert economy_finality["production_ready_candidate"] is False
    assert economy_finality["settlement_action"] == "release"
    assert economy_finality["source_quality"] == (
        "telemetry_eventbus_linked_uptime_tracker"
    )
    assert economy_finality["telemetry_linked"] is True
    assert economy_finality["claim_gate"] == {
        "present": True,
        "decision": "local_escrow_lifecycle_only",
        "local_escrow_lifecycle_claim_allowed": True,
        "traffic_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }
    assert (
        economy_finality["high_risk_claim_gate"][
            "dataplane_delivery_claim_allowed"
        ]
        is False
    )
    assert (
        economy_finality["high_risk_claim_gate"][
            "external_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert "external_settlement_finality_missing" in (
        economy_finality["high_risk_claim_gate"]["blockers"]
    )
    assert economy_finality["upstream_event_ids_count"] == 1
    assert summary["request_evidence"]["present"] is True
    assert summary["request_evidence"]["action"] == "rent_node"
    assert summary["request_evidence"]["route"] == "POST /rent/{listing_id}"
    assert summary["request_evidence"]["actor_role"] == "user"
    assert summary["request_evidence"]["request_scope_hash_present"] is True
    assert summary["request_evidence"]["idempotency_key_present"] is True
    assert summary["request_evidence"]["idempotency_key_hash_present"] is True
    assert summary["request_evidence"]["db_write_ready"] is True
    assert summary["request_evidence"]["service_identity_present"] == {
        "spiffe_id": True,
        "did": True,
        "wallet_address": True,
    }
    assert summary["upstream_evidence"]["present"] is True
    assert summary["upstream_evidence"]["source_agents"] == ["token-bridge"]
    assert summary["upstream_evidence"]["event_ids_count"] == 1
    assert summary["settlement_evidence"]["present"] is True
    assert summary["settlement_evidence"]["settlement_action"] == "release"
    assert summary["settlement_evidence"]["duration_ms"] == 12.25
    assert summary["settlement_evidence"]["telemetry_evidence"]["event_ids_count"] == 1
    assert summary["settlement_evidence"]["bridge_evidence"] == {
        "present": True,
        "attempted": True,
        "status": "released",
        "source_agent": "token-bridge",
        "payloads_redacted": True,
    }
    assert summary["settlement_evidence"]["db_write_evidence"] == {
        "present": True,
        "storage_backend": "sqlalchemy",
        "attempted": True,
        "committed": True,
        "payloads_redacted": True,
    }
    assert summary["settlement_evidence"]["output_summary"] == {
        "present": True,
        "escrow_status_after": "released",
        "listing_status_after": "rented",
        "billing_stage": None,
        "invoice_status_after": None,
        "plan_after": None,
        "subscription_status": None,
        "checkout_url_present": None,
        "portal_url_present": None,
        "stripe_session_present": None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    assert summary["settlement_evidence"]["claim_gate"] == {
        "present": True,
        "decision": "local_escrow_lifecycle_only",
        "local_escrow_lifecycle_claim_allowed": True,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_dataplane_evidence_for_delivery_claim": True,
        "requires_external_finality_evidence_for_settlement_claim": True,
        "bridge_status": "released",
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    assert summary["identity_evidence"]["present"] is True
    assert "listing_id_hash" in summary["identity_evidence"]["hash_fields"]
    assert event["data"]["request_evidence"]["idempotency_key"].startswith("sha256:")
    assert event["data"]["listing_id_hash"]
    assert "evt-lock-secret" not in summary_text
    assert "evt-telemetry-secret" not in summary_text
    for raw_value in (
        listing_id,
        idempotency_key,
        "escrow-secret",
        "renter-secret",
        "node-secret",
        "mesh-secret",
        "spiffe://secret",
        "did:mesh:secret",
        "0xaaaaaaaa",
    ):
        assert raw_value not in text


def test_service_event_trace_history_summarizes_runtime_claim_metadata(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "yggdrasil-client",
        {
            "component": "network.yggdrasil_client",
            "operation": "yggdrasilctl.getPeers",
            "service_name": "yggdrasil-client",
            "layer": "network_yggdrasil_observed_state",
            "status": "observed_state_read",
            "success": True,
            "duration_ms": 12.25,
            "returncode": 0,
            "command": "yggdrasilctl getPeers --secret raw-command-value",
            "downstream_evidence": {
                "event_ids": ["evt-downstream-secret"],
                "claim_boundaries": [
                    "Downstream local-only mesh observation; not remote proof."
                ],
                "claim_boundaries_total": 1,
                "payloads_redacted": True,
            },
            "claim_boundary": (
                "Read-only local yggdrasilctl observation; not dataplane proof."
            ),
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="yggdrasil-client",
        limit=10,
    )
    summary = payload["events"][0]["evidence_summary"]
    runtime = summary["runtime_evidence"]
    summary_text = str(summary)

    assert summary["available"] is True
    assert runtime["present"] is True
    profile = summary["cross_plane_evidence_profile"]
    assert profile["primary_status"] == "local_only"
    assert profile["planes_observed"] == ["data_plane", "evidence_plane"]
    assert profile["local_only"] is True
    assert profile["dataplane_confirmed"] is False
    assert profile["trust_confirmed"] is False
    assert profile["settlement_confirmed"] is False
    assert profile["production_ready_candidate"] is False
    assert runtime["text_fields"] == {
        "component": "network.yggdrasil_client",
        "operation": "yggdrasilctl.getPeers",
        "service_name": "yggdrasil-client",
        "layer": "network_yggdrasil_observed_state",
        "status": "observed_state_read",
    }
    assert runtime["bool_fields"] == {"success": True}
    assert runtime["numeric_fields"] == {
        "duration_ms": 12.25,
        "returncode": 0.0,
    }
    assert runtime["evidence_blocks_present"] == ["downstream_evidence"]
    assert runtime["claim_boundary_present"] is True
    assert runtime["claim_boundaries_present"] is True
    assert summary["claim_boundary"].startswith("Read-only local yggdrasilctl")
    claim_boundaries = summary["claim_boundary_summary"]
    assert claim_boundaries["present"] is True
    assert claim_boundaries["claim_boundaries"] == [
        "Downstream local-only mesh observation; not remote proof.",
        "Read-only local yggdrasilctl observation; not dataplane proof.",
    ]
    assert claim_boundaries["claim_boundaries_total"] == 2
    assert claim_boundaries["claim_boundaries_truncated"] is False
    assert "raw-command-value" not in summary_text
    assert "evt-downstream-secret" not in summary_text


def test_service_event_trace_history_bounds_claim_boundary_summary(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-action-enforcer",
        {
            "component": "mesh.action_enforcer",
            "operation": "enforce_recommendations",
            "service_name": "mesh-action-enforcer",
            "layer": "mesh_action_enforcer_control_action",
            "status": "success",
            "safe_actuator": True,
            "downstream_evidence": {
                "event_ids": ["probe-event-secret"],
                "claim_boundaries": [
                    f"bounded downstream claim boundary {index}"
                    for index in range(10)
                ],
                "claim_boundaries_total": 10,
                "redacted": True,
            },
            "post_action_dataplane_revalidation": {
                "evidence": {
                    "claim_boundary": "Bounded dataplane probe evidence only.",
                    "redacted": True,
                },
                "claim_gate": {
                    "claim_boundary": "Restored-dataplane gate metadata only.",
                    "redacted": True,
                },
                "redacted": True,
            },
            "claim_boundary": "Mesh action enforcer local control evidence only.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="mesh-action-enforcer",
        limit=10,
    )
    summary = payload["events"][0]["evidence_summary"]
    claim_boundaries = summary["claim_boundary_summary"]
    summary_text = str(summary)

    assert claim_boundaries["present"] is True
    assert len(claim_boundaries["claim_boundaries"]) == 8
    assert claim_boundaries["claim_boundaries_total"] == 13
    assert claim_boundaries["claim_boundaries_limit"] == 8
    assert claim_boundaries["claim_boundaries_truncated"] is True
    assert "Mesh action enforcer local control evidence only." in claim_boundaries[
        "claim_boundaries"
    ]
    assert summary["cross_plane_evidence_profile"]["claim_boundary_present"] is True
    assert "probe-event-secret" not in summary_text


def test_service_event_trace_profile_blocks_post_action_dataplane_without_claim_gate(
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-action-enforcer",
        {
            "component": "mesh.action_enforcer",
            "operation": "restart_yggdrasil",
            "service_name": "mesh-action-enforcer",
            "layer": "mesh_action_enforcer_control_action",
            "safe_actuator": True,
            "dataplane_confirmed": True,
            "post_action_dataplane_revalidation": {
                "post_action_dataplane_revalidated": True,
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": False,
                "probe_attempted": True,
                "claim_gate": {
                    "restored_dataplane_claim_allowed": False,
                    "blockers": ["bounded_dataplane_probe_not_confirmed"],
                    "observed_evidence": {
                        "probe_attempted": True,
                        "dataplane_confirmed": False,
                    },
                    "claim_boundary": "Restored-dataplane gate metadata only.",
                    "redacted": True,
                },
                "evidence": {
                    "event_ids": ["probe-event-secret"],
                    "event_ids_count": 1,
                    "events_total": 1,
                    "source_agents": ["real-network-adapter"],
                    "redacted": True,
                },
                "claim_boundary": "Bounded dataplane probe evidence only.",
                "redacted": True,
            },
            "claim_boundary": "Local control action; restored dataplane is gated.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="mesh-action-enforcer",
        limit=10,
    )

    summary = payload["events"][0]["evidence_summary"]
    profile = summary["cross_plane_evidence_profile"]
    post_action = summary["post_action_dataplane_revalidation"]

    assert post_action["present"] is True
    assert post_action["claim_gate"]["restored_dataplane_claim_allowed"] is False
    assert profile["raw_dataplane_confirmed"] is True
    assert profile["dataplane_confirmed"] is False
    assert profile["dataplane_claim_gate_required"] is True
    assert profile["dataplane_claim_gate_allowed"] is False
    assert "post_action_dataplane_claim_gate_not_allowed" in profile[
        "dataplane_claim_blockers"
    ]
    assert "bounded_dataplane_probe_not_confirmed" in profile[
        "dataplane_claim_blockers"
    ]
    assert summary["economy_finality_summary"]["dataplane_confirmed"] is False


def test_service_event_trace_profile_allows_post_action_dataplane_with_claim_gate(
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-action-enforcer",
        {
            "component": "mesh.action_enforcer",
            "operation": "restart_yggdrasil",
            "service_name": "mesh-action-enforcer",
            "layer": "mesh_action_enforcer_control_action",
            "dataplane_confirmed": True,
            "post_action_dataplane_revalidation": {
                "post_action_dataplane_revalidated": True,
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": True,
                "probe_attempted": True,
                "claim_gate": {
                    "restored_dataplane_claim_allowed": True,
                    "blockers": [],
                    "observed_evidence": {
                        "probe_attempted": True,
                        "dataplane_confirmed": True,
                    },
                    "claim_boundary": "Restored-dataplane gate metadata only.",
                    "redacted": True,
                },
                "evidence": {
                    "event_ids": ["probe-event-secret"],
                    "event_ids_count": 1,
                    "events_total": 1,
                    "source_agents": ["real-network-adapter"],
                    "redacted": True,
                },
                "claim_boundary": "Bounded dataplane probe evidence only.",
                "redacted": True,
            },
            "claim_boundary": "Local control action; restored dataplane is gated.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="mesh-action-enforcer",
        limit=10,
    )

    profile = payload["events"][0]["evidence_summary"]["cross_plane_evidence_profile"]

    assert profile["raw_dataplane_confirmed"] is True
    assert profile["dataplane_confirmed"] is True
    assert profile["dataplane_claim_gate_required"] is True
    assert profile["dataplane_claim_gate_allowed"] is True
    assert profile["dataplane_claim_blockers"] == []


def test_service_event_trace_history_summarizes_token_bridge_runtime_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "token-bridge",
        {
            "component": "dao.token_bridge",
            "operation": "release_escrow_on_chain",
            "service_name": "token-bridge",
            "source_alias": "token-bridge",
            "layer": "dao_chain_bridge",
            "stage": "actuator_completed",
            "source_quality": "safe_actuator_submitted_transaction",
            "success": True,
            "simulated": False,
            "submitted_transaction": True,
            "safe_actuator": True,
            "safe_actuator_used": True,
            "context_values_redacted": True,
            "result_payload_redacted": True,
            "duration_ms": 15.5,
            "transaction_hash": "0xsecret-tx-hash",
            "context": {"escrow_id": "sha256:secret"},
            "result_summary": {
                "transaction_hash_hash": "hash-only",
                "raw_result_redacted": True,
            },
            "claim_boundary": "TokenBridge chain-write event only.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="token-bridge",
        limit=10,
    )
    summary = payload["events"][0]["evidence_summary"]
    runtime = summary["runtime_evidence"]
    profile = summary["cross_plane_evidence_profile"]
    economy_finality = summary["economy_finality_summary"]
    summary_text = str(summary)

    assert runtime["text_fields"]["operation"] == "release_escrow_on_chain"
    assert runtime["text_fields"]["source_quality"] == (
        "safe_actuator_submitted_transaction"
    )
    assert runtime["bool_fields"]["submitted_transaction"] is True
    assert runtime["bool_fields"]["safe_actuator"] is True
    assert runtime["bool_fields"]["safe_actuator_used"] is True
    assert runtime["bool_fields"]["context_values_redacted"] is True
    assert runtime["bool_fields"]["result_payload_redacted"] is True
    assert runtime["numeric_fields"]["duration_ms"] == 15.5
    assert runtime["claim_boundary_present"] is True
    assert profile["primary_status"] == "control_allowed"
    assert profile["planes_observed"] == [
        "control_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert profile["local_only"] is True
    assert profile["control_allowed"] is True
    assert profile["settlement_confirmed"] is False
    assert profile["production_ready_candidate"] is False
    assert economy_finality["present"] is True
    assert economy_finality["local_or_pending_only"] is True
    assert economy_finality["submitted_transaction_only"] is True
    assert economy_finality["payment_provider_settlement_confirmed"] is False
    assert economy_finality["bank_settlement_confirmed"] is False
    assert economy_finality["token_settlement_finality_confirmed"] is False
    assert economy_finality["settlement_confirmed"] is False
    assert economy_finality["dataplane_confirmed"] is False
    assert economy_finality["production_ready_candidate"] is False
    assert economy_finality["source_quality"] == "safe_actuator_submitted_transaction"
    assert "0xsecret-tx-hash" not in summary_text


def test_service_event_trace_profile_marks_candidate_only_with_explicit_proofs(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_END,
        "yggdrasil-client",
        {
            "component": "network.yggdrasil_client",
            "operation": "bounded_candidate_check",
            "service_name": "yggdrasil-client",
            "layer": "network_yggdrasil_observed_state",
            "dataplane_confirmed": True,
            "live_spire_svid_confirmed": True,
            "chain_finality_confirmed": True,
            "claim_boundary": "Candidate metadata only; still not production proof.",
        },
    )

    payload = service_event_trace_history(
        bus,
        service_name="yggdrasil-client",
        limit=10,
    )
    summary = payload["events"][0]["evidence_summary"]
    profile = summary["cross_plane_evidence_profile"]
    economy_finality = summary["economy_finality_summary"]

    assert profile["primary_status"] == "production_ready_candidate"
    assert profile["planes_observed"] == [
        "data_plane",
        "trust_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert profile["dataplane_confirmed"] is True
    assert profile["trust_confirmed"] is True
    assert profile["settlement_confirmed"] is True
    assert profile["local_only"] is False
    assert profile["production_ready_candidate"] is True
    assert economy_finality["present"] is True
    assert economy_finality["local_or_pending_only"] is False
    assert economy_finality["token_settlement_finality_confirmed"] is True
    assert economy_finality["settlement_confirmed"] is True
    assert economy_finality["dataplane_confirmed"] is True
    assert economy_finality["production_ready_candidate"] is True
    assert (
        economy_finality["high_risk_claim_gate"][
            "token_settlement_finality_claim_allowed"
        ]
        is True
    )
    assert (
        economy_finality["high_risk_claim_gate"][
            "production_readiness_claim_allowed"
        ]
        is False
    )
    assert "production_readiness_claim_gate_missing" in (
        economy_finality["high_risk_claim_gate"]["blockers"]
    )
