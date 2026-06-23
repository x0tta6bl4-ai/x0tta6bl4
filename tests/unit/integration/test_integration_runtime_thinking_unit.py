import json
from datetime import datetime

import pytest

from src.coordination.events import EventBus
from src.integration.alertmanager_client import (
    Alert,
    AlertMessageRouter,
    AlertSeverity,
    MockAlertManagerClient,
)
from src.integration.spine import (
    IntegrationSpine,
    SafeActuator,
    SpineIdentity,
    SpineRequest,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


@pytest.mark.asyncio
async def test_alertmanager_thinking_status_redacts_alert_payloads():
    router = AlertMessageRouter()
    routed = []

    async def handler(alert):
        routed.append(alert.label)

    router.register_handler("secret-alert-pattern", handler)
    client = MockAlertManagerClient(
        alertmanager_url="http://secret-alertmanager.local:9093",
        webhook_port=5001,
        webhook_path="/secret-alert-webhook",
    )
    client.subscribe(router.route_alerts)

    alert = Alert(
        label="prefix-secret-alert-pattern-secret-label",
        value=42.5,
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.now(),
        source="secret-alert-source",
        description="secret alert description",
    )

    await client.inject_alert(alert)

    assert routed == ["prefix-secret-alert-pattern-secret-label"]
    client_status = client.get_thinking_status()
    router_status = router.get_thinking_status()
    assert client_status["thinking"]["profile"]["role"] == "monitoring"
    assert router_status["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(
        client_status,
        "secret-alertmanager.local",
        "/secret-alert-webhook",
        "prefix-secret-alert-pattern-secret-label",
        "secret-alert-source",
        "secret alert description",
    )
    _assert_redacted(
        router_status,
        "secret-alert-pattern",
        "prefix-secret-alert-pattern-secret-label",
        "secret-alert-source",
        "secret alert description",
    )


def _allowing_policy():
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    engine.add_rule(
        PolicyRule(
            rule_id="secret-rule-id",
            name="secret rule name",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://mesh.x0tta6bl4.mesh/workload/*",
            allowed_resources=["secret-resource"],
            priority=500,
        )
    )
    return engine


def test_integration_spine_and_safe_actuator_thinking_status_redacts_request(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    actuator = SafeActuator(lambda _action, _context: True)
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=actuator,
        reward_manager=None,
        source_agent="secret-source-agent",
    )
    request = SpineRequest(
        request_id="secret-request-id",
        identity=SpineIdentity(
            node_id="secret-node-id",
            spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/secret-workload",
            did="did:mesh:secret-did",
            wallet_address="secret-wallet-address",
        ),
        action="secret-action",
        resource="secret-resource",
        workload_type="secret-workload",
        reward_packets=0,
        metadata={"secret-metadata-key": "secret-metadata-value"},
    )

    outcome = spine.process(request)

    assert outcome.status == "COMPLETED"
    spine_status = spine.get_thinking_status()
    actuator_status = actuator.get_thinking_status()
    assert spine_status["thinking"]["profile"]["role"] == "coordinator"
    assert actuator_status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        spine_status,
        "secret-source-agent",
        "secret-request-id",
        "secret-node-id",
        "secret-workload",
        "secret-wallet-address",
        "secret-action",
        "secret-resource",
        "secret-metadata-key",
        "secret-metadata-value",
        "secret-rule-id",
        "secret rule name",
    )
    _assert_redacted(
        actuator_status,
        "secret-action",
        "secret-node-id",
        "secret-workload",
        "secret-wallet-address",
        "secret-resource",
        "secret-metadata-key",
        "secret-metadata-value",
    )
