from unittest.mock import MagicMock, mock_open, patch

import src.network.mptcp_manager as mptcp_mod
from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/mptcp-manager"


def _allow_policy(resource: str):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-{resource}",
            name=f"Allow {resource}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern=SPIFFE_ID,
            allowed_resources=[resource],
            priority=1000,
        )
    )
    return policy


def _common_kwargs(tmp_path, **overrides):
    kwargs = {
        "event_bus": EventBus(str(tmp_path)),
        "policy_engine": _allow_policy("network:mptcp:enable_mptcp"),
        "require_policy": True,
        "source_agent": "mptcp-manager",
        "node_id": "node-mptcp-1",
        "spiffe_id": SPIFFE_ID,
        "did": "did:mesh:network:mptcp",
        "wallet_address": "0xmptcp",
    }
    kwargs.update(overrides)
    return kwargs


def test_enable_mptcp_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    kwargs = _common_kwargs(tmp_path)

    with patch.object(mptcp_mod.subprocess, "run", return_value=MagicMock()) as run:
        result = mptcp_mod.MPTCPManager.enable_mptcp(True, **kwargs)

    assert result is True
    run.assert_called_once_with(["sysctl", "-w", "net.mptcp.enabled=1"], check=True)
    events = kwargs["event_bus"].get_event_history(source_agent="mptcp-manager")
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages
    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "node-mptcp-1"
    assert payload["spiffe_id"] == SPIFFE_ID
    assert payload["did"] == "did:mesh:network:mptcp"
    assert payload["wallet_address"] == "0xmptcp"
    assert payload["resource"] == "network:mptcp:enable_mptcp"
    assert payload["context"]["enabled"] is True
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["source_agents"] == ["mptcp-manager"]
    assert metadata["claim_gate"]["schema"] == (
        "x0tta6bl4.network_mptcp.safe_actuator_claim_gate.v1"
    )
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["local_mptcp_configuration_claim_allowed"] is True
    assert metadata["claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert metadata["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert metadata["claim_gate"]["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["resource"] == "network:mptcp:enable_mptcp"
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert metadata["evidence"]["action"] == "sysctl_set"
    assert metadata["evidence"]["sysctl_key_present"] is True
    assert metadata["evidence"]["outputs_redacted"] is True
    assert payload["claim_boundary"]


def test_enable_mptcp_policy_denial_blocks_subprocess(tmp_path):
    kwargs = _common_kwargs(
        tmp_path,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
    )

    with patch.object(mptcp_mod.subprocess, "run") as run:
        result = mptcp_mod.MPTCPManager.enable_mptcp(False, **kwargs)

    assert result is False
    run.assert_not_called()
    blocked = kwargs["event_bus"].get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="mptcp-manager",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False
    assert blocked[-1].data["resource"] == "network:mptcp:enable_mptcp"


def test_enable_mptcp_simulated_actuator_blocks_subprocess(tmp_path):
    kwargs = _common_kwargs(
        tmp_path,
        require_policy=False,
        policy_engine=None,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    with patch.object(mptcp_mod.subprocess, "run") as run:
        result = mptcp_mod.MPTCPManager.enable_mptcp(True, **kwargs)

    assert result is False
    run.assert_not_called()
    failed = kwargs["event_bus"].get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="mptcp-manager",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["simulated"] is True
    assert failed[-1].data["success"] is False


def test_configure_endpoints_runs_ip_mptcp_through_safe_actuator(tmp_path):
    kwargs = _common_kwargs(
        tmp_path,
        policy_engine=_allow_policy("network:mptcp:configure_endpoints"),
    )

    with patch.object(mptcp_mod.MPTCPManager, "is_mptcp_supported", return_value=True):
        with patch.object(mptcp_mod.subprocess, "run", return_value=MagicMock()) as run:
            result = mptcp_mod.MPTCPManager.configure_endpoints(
                ["eth0", "wwan0"],
                **kwargs,
            )

    assert result is True
    assert run.call_args_list[0].args == (["ip", "mptcp", "endpoint", "flush"],)
    assert run.call_args_list[0].kwargs == {"capture_output": True}
    assert run.call_args_list[1].args == (
        [
            "ip",
            "mptcp",
            "limits",
            "set",
            "subflow",
            "2",
            "add_addr_accepted",
            "2",
        ],
    )
    assert run.call_args_list[1].kwargs == {"check": True}
    completed = kwargs["event_bus"].get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mptcp-manager",
    )
    payload = completed[-1].data
    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "network:mptcp:configure_endpoints"
    assert payload["context"]["interfaces"] == ["eth0", "wwan0"]
    assert payload["context"]["subflow_limit"] == 2
    assert payload["context"]["add_addr_accepted"] == 2
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["local_endpoint_limit_claim_allowed"] is True
    assert metadata["claim_gate"]["throughput_claim_allowed"] is False
    assert metadata["claim_gate"]["remote_path_quality_claim_allowed"] is False
    assert metadata["evidence"]["resource"] == "network:mptcp:configure_endpoints"
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert metadata["evidence"]["action"] == "ip_mptcp_limits_set"
    assert metadata["evidence"]["interface_count"] == 2
    assert metadata["evidence"]["raw_interfaces_redacted"] is True


def test_configure_endpoints_unsupported_kernel_fails_closed(tmp_path):
    kwargs = _common_kwargs(
        tmp_path,
        policy_engine=_allow_policy("network:mptcp:configure_endpoints"),
    )

    with patch.object(mptcp_mod.MPTCPManager, "is_mptcp_supported", return_value=False):
        with patch.object(mptcp_mod.subprocess, "run") as run:
            result = mptcp_mod.MPTCPManager.configure_endpoints(["eth0"], **kwargs)

    assert result is False
    run.assert_not_called()
    failed = kwargs["event_bus"].get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="mptcp-manager",
    )
    assert failed[-1].data["stage"] == "actuator_failed"
    assert failed[-1].data["success"] is False
    assert failed[-1].data["simulated"] is False
    assert "not supported" in failed[-1].data["reason"]
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["local_mptcp_configuration_claim_allowed"] is False
    assert metadata["claim_gate"]["throughput_claim_allowed"] is False
    assert metadata["evidence"]["resource"] == "network:mptcp:configure_endpoints"
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert metadata["evidence"]["kernel_supported"] is False
    assert metadata["evidence"]["raw_interfaces_redacted"] is True


def test_configure_endpoints_uses_explicit_limits(tmp_path):
    kwargs = _common_kwargs(
        tmp_path,
        policy_engine=_allow_policy("network:mptcp:configure_endpoints"),
    )

    with patch.object(mptcp_mod.MPTCPManager, "is_mptcp_supported", return_value=True):
        with patch.object(mptcp_mod.subprocess, "run", return_value=MagicMock()) as run:
            result = mptcp_mod.MPTCPManager.configure_endpoints(
                ["eth0"],
                subflow_limit=8,
                add_addr_accepted=5,
                **kwargs,
            )

    assert result is True
    assert run.call_args_list[1].args == (
        [
            "ip",
            "mptcp",
            "limits",
            "set",
            "subflow",
            "8",
            "add_addr_accepted",
            "5",
        ],
    )
    completed = kwargs["event_bus"].get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mptcp-manager",
    )
    assert completed[-1].data["context"]["subflow_limit"] == 8
    assert completed[-1].data["context"]["add_addr_accepted"] == 5


def test_get_status_reads_kernel_enabled_and_mptcp_limits():
    with patch.object(mptcp_mod.MPTCPManager, "is_mptcp_supported", return_value=True):
        with patch("builtins.open", mock_open(read_data="1\n")):
            with patch.object(
                mptcp_mod.subprocess,
                "run",
                return_value=MagicMock(
                    stdout="add_addr_accepted 5 subflows 7\n",
                ),
            ) as run:
                status = mptcp_mod.MPTCPManager.get_status()

    assert status == {
        "supported": True,
        "enabled": True,
        "max_subflows": 7,
        "add_addr_accepted": 5,
    }
    run.assert_called_once_with(
        ["ip", "mptcp", "limits", "show"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def test_get_status_publishes_redacted_observed_state_evidence(tmp_path, monkeypatch):
    bus = EventBus(str(tmp_path))
    monkeypatch.setenv("MPTCP_MANAGER_SPIFFE_ID", "spiffe://private/mptcp")
    monkeypatch.setenv("MPTCP_MANAGER_DID", "did:private:mptcp")
    monkeypatch.setenv("MPTCP_MANAGER_WALLET_ADDRESS", "0xprivate")

    with patch.object(mptcp_mod.MPTCPManager, "is_mptcp_supported", return_value=True):
        with patch("builtins.open", mock_open(read_data="1\n")):
            with patch.object(
                mptcp_mod.subprocess,
                "run",
                return_value=MagicMock(
                    stdout="add_addr_accepted 5 subflows 7 private-peer-token\n",
                    stderr="private stderr detail",
                    returncode=0,
                ),
            ):
                status = mptcp_mod.MPTCPManager.get_status(
                    event_bus=bus,
                    include_evidence=True,
                )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="mptcp-manager-status-read",
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert status["supported"] is True
    assert status["enabled"] is True
    assert status["evidence"] == {
        "source_agents": ["mptcp-manager-status-read"],
        "layer": "network_mptcp_observed_state",
        "event_ids": [events[-1].event_id],
        "events_total": 1,
        "redacted": True,
    }
    assert payload["component"] == "network.mptcp_manager"
    assert payload["operation"] == "get_status"
    assert payload["resource"] == "network:mptcp:get_status"
    assert payload["read_only"] is True
    assert payload["observed_state"] is True
    assert payload["safe_actuator"] is False
    assert payload["identity"]["service_name"] == "mptcp-manager"
    assert payload["identity"]["spiffe_id_configured"] is True
    assert payload["proc"]["read_succeeded"] is True
    assert payload["proc"]["raw_value_redacted"] is True
    assert payload["limits_command"]["returncode"] == 0
    assert payload["limits_command"]["output"]["stdout_chars"] > 0
    assert payload["limits_command"]["output"]["stderr_chars"] > 0
    assert payload["limits_command"]["output"]["stdout_sha256"]
    assert payload["limits_command"]["output"]["stderr_sha256"]
    assert "private-peer-token" not in payload_text
    assert "private stderr detail" not in payload_text
    assert "spiffe://private/mptcp" not in payload_text
    assert "did:private:mptcp" not in payload_text
    assert "0xprivate" not in payload_text
