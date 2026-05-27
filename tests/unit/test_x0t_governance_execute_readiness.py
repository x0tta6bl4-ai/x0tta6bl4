from src.integration.x0t_governance_execute_readiness import (
    build_validation_report,
    build_readiness_report,
    render_markdown,
)


def _proposal(**overrides):
    proposal = {
        "id": 1,
        "proposer": "0x870B8b23F431c140FDf5c7b96987306a327AFF96",
        "ipfsCid": "ipfs://x0t-sota-event-lifecycle-harmless-testnet-config",
        "earliestExecutionTime": 1779338722,
        "forPower": 10_000_000_000,
        "againstPower": 0,
        "abstainPower": 0,
        "queued": True,
        "executed": False,
        "vetoed": False,
    }
    proposal.update(overrides)
    return proposal


def test_queued_proposal_before_timelock_is_not_ready():
    report = build_readiness_report(
        proposal=_proposal(),
        state_code=4,
        latest_block=41773612,
        latest_block_timestamp=1779315512,
        generated_at="2026-05-20T22:18:32Z",
    )

    assert report["decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert report["summary"]["execute_ready_now"] is False
    assert report["proposal_state"]["state_label"] == "Queued"
    assert report["timelock"]["seconds_until_earliest_execution_by_block_time"] == 23210
    assert report["mutates_chain"] is False
    assert report["submits_transaction"] is False
    assert report["goal_can_be_marked_complete"] is False


def test_ready_proposal_after_timelock_is_readiness_only():
    report = build_readiness_report(
        proposal=_proposal(),
        state_code=5,
        latest_block=41800000,
        latest_block_timestamp=1779338723,
        generated_at="2026-05-21T04:45:23Z",
    )

    assert report["decision"] == "READY_TO_EXECUTE"
    assert report["summary"]["execute_ready_now"] is True
    assert report["timelock"]["seconds_until_earliest_execution_by_block_time"] == 0
    assert report["mutates_chain"] is False
    assert report["submits_transaction"] is False


def test_executed_proposal_does_not_request_another_execute():
    report = build_readiness_report(
        proposal=_proposal(executed=True),
        state_code=6,
        latest_block=41800010,
        latest_block_timestamp=1779338800,
        generated_at="2026-05-21T04:46:40Z",
    )

    assert report["decision"] == "ALREADY_EXECUTED"
    assert report["summary"]["execute_ready_now"] is False
    assert report["summary"]["safe_to_retry_readiness_check"] is False


def test_markdown_keeps_operator_approval_boundary():
    report = build_readiness_report(
        proposal=_proposal(),
        state_code=5,
        latest_block=41800000,
        latest_block_timestamp=1779338723,
        generated_at="2026-05-21T04:45:23Z",
    )

    markdown = render_markdown(report)

    assert "It does not submit `execute(1)`." in markdown
    assert "explicit operator approval" in markdown
    assert "X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia" in markdown
    assert 'PRIVATE_KEY="$PRIVATE_KEY" python3 execute_dao_proposal.py' in markdown
    assert "PRIVATE_KEY=..." not in markdown


def test_validation_accepts_read_only_ready_artifact():
    report = build_readiness_report(
        proposal=_proposal(),
        state_code=5,
        latest_block=41800000,
        latest_block_timestamp=1779338723,
        generated_at="2026-05-21T04:45:23Z",
    )

    validation = build_validation_report(report, ".tmp/readiness.json")

    assert validation["ok"] is True
    assert validation["decision"] == "VALID_EXECUTE_READINESS_ARTIFACT"
    assert validation["runs_live_rpc"] is False
    assert validation["mutates_chain"] is False
    assert validation["submits_transaction"] is False
    assert validation["goal_can_be_marked_complete"] is False


def test_validation_rejects_mutating_or_goal_complete_artifact():
    report = build_readiness_report(
        proposal=_proposal(),
        state_code=5,
        latest_block=41800000,
        latest_block_timestamp=1779338723,
        generated_at="2026-05-21T04:45:23Z",
    )
    report["mutates_chain"] = True
    report["submits_transaction"] = True
    report["goal_can_be_marked_complete"] = True

    validation = build_validation_report(report, ".tmp/readiness.json")

    assert validation["ok"] is False
    assert validation["decision"] == "INVALID_EXECUTE_READINESS_ARTIFACT"
    assert "mutates_chain must be false" in validation["errors"]
    assert "submits_transaction must be false" in validation["errors"]
    assert "goal_can_be_marked_complete must be false" in validation["errors"]
