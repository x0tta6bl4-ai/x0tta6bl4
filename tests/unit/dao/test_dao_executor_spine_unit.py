from pathlib import Path
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.dao.executor_webhook import DAOExecutor
from src.dao.proposal_executor_webhook import ExecutorConfig, HelmRunner
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def _allow_policy(resource: str, workload_type: str, spiffe_suffix: str):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-{workload_type}",
            name=f"Allow {workload_type}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern=f"spiffe://x0tta6bl4.mesh/workload/{spiffe_suffix}",
            allowed_resources=[resource],
            priority=1000,
        )
    )
    return policy


def _executor_config(tmp_path, *, dry_run=False):
    cfg = ExecutorConfig.__new__(ExecutorConfig)
    object.__setattr__(cfg, "rpc_url", "http://localhost:8545")
    object.__setattr__(cfg, "governance_address", "0x" + "a" * 40)
    object.__setattr__(cfg, "helm_release", "mesh-op")
    object.__setattr__(cfg, "helm_chart", "charts/x0tta-mesh-operator/")
    object.__setattr__(cfg, "helm_namespace", "default")
    object.__setattr__(cfg, "helm_extra_args", [])
    object.__setattr__(cfg, "poll_interval", 1)
    object.__setattr__(cfg, "start_block_offset", 10)
    object.__setattr__(cfg, "processed_file", Path(tmp_path) / "processed.json")
    object.__setattr__(cfg, "ledger_path", Path(tmp_path) / "audit.jsonl")
    object.__setattr__(cfg, "dry_run", dry_run)
    return cfg


def _helm_runner(tmp_path, **kwargs):
    return HelmRunner(
        _executor_config(tmp_path, dry_run=kwargs.pop("dry_run", False)),
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/dao-proposal-executor",
        did="did:mesh:dao:proposal-executor",
        wallet_address="0xexecutor",
        **kwargs,
    )


def _dao_executor(tmp_path, **kwargs):
    executor = DAOExecutor.__new__(DAOExecutor)
    executor.event_bus = kwargs.pop("event_bus", EventBus(str(tmp_path)))
    executor.policy_engine = kwargs.pop("policy_engine", None)
    executor.require_policy = kwargs.pop("require_policy", False)
    executor.source_agent = "dao-executor"
    executor.event_project_root = "."
    executor.identity = {
        "node_id": "dao-executor",
        "spiffe_id": kwargs.pop(
            "spiffe_id",
            "spiffe://x0tta6bl4.mesh/workload/dao-executor",
        ),
        "did": "did:mesh:dao:executor",
        "wallet_address": "0xexecutor",
    }
    executor.safe_actuator = kwargs.pop(
        "safe_actuator",
        SafeActuator(executor._execute_release_through_actuator),
    )
    executor._last_upgrade_success = None
    return executor


def test_helm_runner_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    runner = _helm_runner(
        tmp_path,
        policy_engine=_allow_policy(
            "dao:proposal_executor:helm_upgrade",
            "dao-proposal-executor",
            "dao-proposal-executor",
        ),
        require_policy=True,
    )
    proc = MagicMock(returncode=0, stdout="upgraded", stderr="")

    with patch("subprocess.run", return_value=proc) as subprocess_run:
        result = runner.upgrade(101, extra_set={"api_token": "secret"})

    assert result.success is True
    subprocess_run.assert_called_once()
    events = runner.event_bus.get_event_history(source_agent="dao-proposal-executor")
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages
    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/dao-proposal-executor"
    assert payload["resource"] == "dao:proposal_executor:helm_upgrade"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    assert payload["context"]["extra_set"]["api_token"] == "<redacted>"
    assert payload["claim_boundary"]


def test_helm_runner_policy_denial_blocks_subprocess(tmp_path):
    runner = _helm_runner(
        tmp_path,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
        require_policy=True,
    )

    with patch("subprocess.run") as subprocess_run:
        result = runner.upgrade(102)

    assert result.success is False
    subprocess_run.assert_not_called()
    blocked = runner.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="dao-proposal-executor",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


def test_helm_runner_dry_run_is_marked_simulated_without_subprocess(tmp_path):
    runner = _helm_runner(tmp_path, dry_run=True)

    with patch("subprocess.run") as subprocess_run:
        result = runner.upgrade(103)

    assert result.success is True
    assert result.dry_run is True
    subprocess_run.assert_not_called()
    failed = runner.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="dao-proposal-executor",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["simulated"] is True


def test_dao_executor_release_script_policy_denial_blocks_popen(tmp_path):
    executor = _dao_executor(
        tmp_path,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
        require_policy=True,
    )

    with patch("src.dao.executor_webhook.subprocess.Popen") as popen:
        result = executor.trigger_upgrade(201, "HELM_UPGRADE: denied")

    assert result is False
    popen.assert_not_called()
    blocked = executor.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="dao-executor",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


def test_dao_executor_release_script_runs_through_safe_actuator(tmp_path):
    executor = _dao_executor(
        tmp_path,
        policy_engine=_allow_policy(
            "dao:executor:release_script",
            "dao-executor",
            "dao-executor",
        ),
        require_policy=True,
    )
    process = MagicMock()
    process.returncode = 0
    process.communicate.return_value = ("ok", "")

    with patch("src.dao.executor_webhook.os.path.exists", return_value=True):
        with patch("src.dao.executor_webhook.subprocess.Popen", return_value=process) as popen:
            result = executor.trigger_upgrade(202, "HELM_UPGRADE: allowed")

    assert result is True
    popen.assert_called_once()
    completed = executor.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="dao-executor",
    )
    payload = completed[-1].data
    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "dao:executor:release_script"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    assert payload["claim_boundary"]


def test_dao_executor_simulated_actuator_blocks_release_script(tmp_path):
    executor = _dao_executor(
        tmp_path,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    with patch("src.dao.executor_webhook.subprocess.Popen") as popen:
        result = executor.trigger_upgrade(203, "HELM_UPGRADE: simulated")

    assert result is False
    popen.assert_not_called()
    failed = executor.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="dao-executor",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["simulated"] is True
