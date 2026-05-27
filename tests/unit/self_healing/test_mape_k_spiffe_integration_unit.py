from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from src.coordination.events import EventBus, EventType
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.self_healing.mape_k_spiffe_integration import SPIFFEMapEKLoop


class _FakeSVID:
    def __init__(self, spiffe_id="spiffe://x0tta6bl4.mesh/workload/spiffe-mapek"):
        self.spiffe_id = spiffe_id
        self.expiry = datetime.utcnow() + timedelta(minutes=30)

    def is_expired(self):
        return False


class _FakeSPIFFEController:
    node_id = "fake-node"

    def __init__(self, *, fail_on_renew=False):
        self.fail_on_renew = fail_on_renew
        self.renew_calls = []
        self.initialize_calls = []

    def get_current_x509_svid(self, force_renew=False):
        self.renew_calls.append(force_renew)
        if self.fail_on_renew:
            raise AssertionError("policy-denied action should not renew SVID")
        return _FakeSVID()

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)
        return True


@dataclass
class _FakeEntry:
    entry_id: str
    spiffe_id: str


class _FakeServerClient:
    def __init__(self):
        self.deleted_entry_ids = []

    def delete_entry(self, entry_id):
        self.deleted_entry_ids.append(entry_id)
        return True


class _FakeRevocationController(_FakeSPIFFEController):
    def __init__(self, entries):
        super().__init__()
        self._entries = entries
        self.server_client = _FakeServerClient()

    def list_registered_workloads(self):
        return list(self._entries)


def _renew_plan():
    return {
        "phase": "PLAN",
        "priority": "high",
        "estimated_duration_seconds": 30,
        "actions": [
            {
                "action_type": "renew_svid",
                "description": "Renew SVID from SPIRE Agent",
                "parameters": {"join_token": "secret-token"},
            }
        ],
    }


def _make_loop(tmp_path, controller=None, **kwargs):
    return SPIFFEMapEKLoop(
        trust_domain="x0tta6bl4.mesh",
        spiffe_controller=controller or _FakeSPIFFEController(),
        event_bus=EventBus(str(tmp_path)),
        node_id="spiffe-node-1",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/spiffe-mapek",
        did="did:mesh:spiffe:test",
        wallet_address="0xspiffe",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_execute_publishes_events_with_identity(tmp_path):
    controller = _FakeSPIFFEController()
    loop = _make_loop(tmp_path, controller=controller)

    result = await loop.execute(_renew_plan())

    assert result["actions_executed"] == 1
    assert result["actions_failed"] == 0
    assert controller.renew_calls == [True]

    events = loop.event_bus.get_event_history(
        source_agent="spiffe-mapek-loop",
        limit=10,
    )
    stages = [event.data["stage"] for event in events]
    assert "plan_received" in stages
    assert "action_start" in stages
    assert "action_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ]
    payload = completed[-1].data
    assert payload["node_id"] == "spiffe-node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/spiffe-mapek"
    assert payload["did"] == "did:mesh:spiffe:test"
    assert payload["wallet_address"] == "0xspiffe"
    assert payload["resource"] == "self_healing:spiffe:renew_svid"
    assert payload["context"]["action"]["parameters"]["join_token"] == "<redacted>"
    assert payload["claim_boundary"]


@pytest.mark.asyncio
async def test_execute_policy_denied_blocks_action(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    loop = _make_loop(
        tmp_path,
        controller=_FakeSPIFFEController(fail_on_renew=True),
        policy_engine=policy,
        require_policy=True,
    )

    result = await loop.execute(_renew_plan())

    assert result["actions_executed"] == 0
    assert result["actions_failed"] == 1
    assert "No rules matched" in result["results"][0]["error"]

    blocked = loop.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="spiffe-mapek-loop",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["resource"] == "self_healing:spiffe:renew_svid"
    assert blocked[-1].data["policy_allowed"] is False


@pytest.mark.asyncio
async def test_execute_policy_allow_continues_to_action(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-spiffe-renew",
            name="Allow SPIFFE MAPE-K renew",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/spiffe-mapek",
            allowed_resources=["self_healing:spiffe:renew_svid"],
            priority=1000,
        )
    )
    controller = _FakeSPIFFEController()
    loop = _make_loop(
        tmp_path,
        controller=controller,
        policy_engine=policy,
        require_policy=True,
    )

    result = await loop.execute(_renew_plan())

    assert result["actions_executed"] == 1
    assert result["actions_failed"] == 0
    assert controller.renew_calls == [True]
    completed = loop.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="spiffe-mapek-loop",
    )
    assert completed[-1].data["policy_allowed"] is True
    assert completed[-1].data["matched_rules"] == ["allow-spiffe-renew"]


@pytest.mark.asyncio
async def test_revoke_identity_deletes_matching_spire_entry(tmp_path):
    target_spiffe_id = "spiffe://x0tta6bl4.mesh/workload/revoke-me"
    controller = _FakeRevocationController(
        [
            _FakeEntry("entry-1", target_spiffe_id),
            _FakeEntry("entry-2", "spiffe://x0tta6bl4.mesh/workload/keep-me"),
        ]
    )
    loop = _make_loop(tmp_path, controller=controller)

    result = await loop._revoke_identity(
        {"parameters": {"spiffe_id": target_spiffe_id}}
    )

    assert result["success"] is True
    assert result["revoked"] is True
    assert result["deleted_entry_ids"] == ["entry-1"]
    assert controller.server_client.deleted_entry_ids == ["entry-1"]


@pytest.mark.asyncio
async def test_revoke_identity_fails_closed_without_matching_entry(tmp_path):
    controller = _FakeRevocationController(
        [
            _FakeEntry(
                "entry-1",
                "spiffe://x0tta6bl4.mesh/workload/other-workload",
            )
        ]
    )
    loop = _make_loop(tmp_path, controller=controller)

    result = await loop._revoke_identity(
        {
            "parameters": {
                "spiffe_id": "spiffe://x0tta6bl4.mesh/workload/missing"
            }
        }
    )

    assert result["success"] is False
    assert result["revoked"] is False
    assert "No matching SPIRE entry" in result["error"]
    assert controller.server_client.deleted_entry_ids == []
