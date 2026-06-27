import pytest

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.services.pqc_rotator_service import PQCRotatorService


class FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode

    async def wait(self):
        return self.returncode


def _allow_policy():
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-pqc-rotator",
            name="Allow PQC rotator",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/pqc-rotator",
            allowed_resources=["services:pqc_rotator:rotate_identity"],
            priority=1000,
        )
    )
    return policy


def _service(tmp_path, **kwargs):
    return PQCRotatorService(
        identity_file=tmp_path / "pqc_identity.txt",
        temp_identity_file=tmp_path / "pqc_identity.new",
        signer_cmd=("python3", "pqc_signer.py", "--api-token", "secret-token"),
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/pqc-rotator",
        did="did:mesh:pqc:rotator",
        wallet_address="0xrotator",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_pqc_rotator_success_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    calls = []

    async def process_factory(*cmd, stdout=None, stderr=None):
        calls.append(cmd)
        stdout.write(b"Private Key (hex): 00\n")
        stdout.flush()
        return FakeProcess(0)

    reports = []
    service = _service(
        tmp_path,
        process_factory=process_factory,
        report_generator=lambda: reports.append("generated"),
        policy_engine=_allow_policy(),
        require_policy=True,
    )

    result = await service.rotate_once()

    assert result["success"] is True
    assert service.identity_file.read_text() == "Private Key (hex): 00\n"
    assert calls == [("python3", "pqc_signer.py", "--api-token", "secret-token")]
    assert reports == ["generated"]

    events = service.event_bus.get_event_history(source_agent="pqc-rotator", limit=10)
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "pqc-rotator"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/pqc-rotator"
    assert payload["did"] == "did:mesh:pqc:rotator"
    assert payload["wallet_address"] == "0xrotator"
    assert payload["resource"] == "services:pqc_rotator:rotate_identity"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-pqc-rotator"]
    assert payload["safe_actuator"] is True
    assert payload["context"]["signer_command"] == "python3"
    assert payload["context"]["signer_args_count"] == 3
    assert "secret-token" not in str(payload["context"])
    assert payload["claim_boundary"]


@pytest.mark.asyncio
async def test_pqc_rotator_policy_denied_blocks_signer_process(tmp_path):
    calls = []

    async def process_factory(*cmd, stdout=None, stderr=None):
        calls.append(cmd)
        return FakeProcess(0)

    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    service = _service(
        tmp_path,
        process_factory=process_factory,
        report_generator=lambda: None,
        policy_engine=policy,
        require_policy=True,
    )

    result = await service.rotate_once()

    assert result["success"] is False
    assert "No rules matched" in result["error"]
    assert calls == []
    assert not service.identity_file.exists()
    blocked = service.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="pqc-rotator",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


@pytest.mark.asyncio
async def test_pqc_rotator_policy_engine_requires_spiffe_identity(tmp_path):
    service = _service(
        tmp_path,
        process_factory=lambda *args, **kwargs: FakeProcess(0),
        report_generator=lambda: None,
        policy_engine=_allow_policy(),
    )
    service.identity["spiffe_id"] = ""

    result = await service.rotate_once()

    assert result["success"] is False
    assert "SPIFFE identity is required" in result["error"]
    assert not service.identity_file.exists()
    blocked = service.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="pqc-rotator",
    )
    assert blocked[-1].data["policy_allowed"] is None


@pytest.mark.asyncio
async def test_pqc_rotator_simulated_safe_actuator_fails_closed(tmp_path):
    class SimulatedActuator:
        async def execute(self, _action_type, _context):
            return SafeActuatorResult(True, "dry run", simulated=True)

    service = _service(
        tmp_path,
        safe_actuator=SimulatedActuator(),
        report_generator=lambda: None,
    )

    result = await service.rotate_once()

    assert result["success"] is False
    assert result["simulated"] is True
    assert not service.identity_file.exists()
    failed = service.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="pqc-rotator",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"


@pytest.mark.asyncio
async def test_pqc_rotator_signer_failure_fails_closed(tmp_path):
    async def process_factory(*cmd, stdout=None, stderr=None):
        stdout.write(b"partial")
        stdout.flush()
        return FakeProcess(2)

    service = _service(
        tmp_path,
        process_factory=process_factory,
        report_generator=lambda: None,
    )

    result = await service.rotate_once()

    assert result["success"] is False
    assert "exited with code 2" in result["error"]
    assert not service.identity_file.exists()
    assert not service.temp_identity_file.exists()
    failed = service.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="pqc-rotator",
    )
    assert failed[-1].data["stage"] == "actuator_failed"
