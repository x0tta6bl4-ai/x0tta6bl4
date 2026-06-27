import importlib.util
from pathlib import Path

from src.integration.x0t_governance_execute_readiness import build_readiness_report


ROOT = Path(__file__).resolve().parents[2]


def _load_script():
    path = ROOT / "execute_dao_proposal.py"
    spec = importlib.util.spec_from_file_location("execute_dao_proposal", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _ready_report():
    return build_readiness_report(
        proposal=_proposal(),
        state_code=5,
        latest_block=41800000,
        latest_block_timestamp=1779338723,
        generated_at="2026-05-21T04:45:23Z",
    )


def test_approval_requires_proposal_specific_value():
    script = _load_script()

    assert script.approval_errors({}, 1) == [
        "X0T_EXECUTE_PROPOSAL_APPROVAL must be exactly 'execute-proposal-1-base-sepolia'"
    ]
    assert script.approval_errors({"X0T_EXECUTE_PROPOSAL_APPROVAL": "execute-proposal-1-base-sepolia"}, 1) == []


def test_success_receipt_report_keeps_goal_boundary():
    script = _load_script()
    receipt = {
        "status": 1,
        "blockNumber": 41801000,
        "blockHash": "0x" + "a" * 64,
        "gasUsed": 123456,
    }

    report = script.build_execution_receipt_report(
        proposal_id=1,
        governance_contract="0xf1B0086962e41710968D81F099c8ced23b97D2d2",
        operator_address="0x870B8b23F431c140FDf5c7b96987306a327AFF96",
        tx_hash="0x" + "b" * 64,
        receipt=receipt,
        readiness_report=_ready_report(),
        final_state_code=6,
    )

    assert report["ok"] is True
    assert report["decision"] == "EXECUTED_RECEIPT_CONFIRMED"
    assert report["receipt"]["status"] == 1
    assert report["proposal_state_after_receipt"]["executed"] is True
    assert report["mutates_chain"] is True
    assert report["submits_transaction"] is True
    assert report["goal_can_be_marked_complete"] is False


def test_failed_receipt_report_is_not_ok():
    script = _load_script()
    receipt = {
        "status": 0,
        "blockNumber": 41801000,
        "blockHash": "0x" + "a" * 64,
        "gasUsed": 123456,
    }

    report = script.build_execution_receipt_report(
        proposal_id=1,
        governance_contract="0xf1B0086962e41710968D81F099c8ced23b97D2d2",
        operator_address="0x870B8b23F431c140FDf5c7b96987306a327AFF96",
        tx_hash="0x" + "b" * 64,
        receipt=receipt,
        readiness_report=_ready_report(),
        final_state_code=5,
    )

    assert report["ok"] is False
    assert report["decision"] == "EXECUTION_RECEIPT_FAILED"
    assert report["status"] == "FAILED"
    assert report["goal_can_be_marked_complete"] is False


def test_successful_receipt_without_final_executed_state_is_not_ok():
    script = _load_script()
    receipt = {
        "status": 1,
        "blockNumber": 41801000,
        "blockHash": "0x" + "a" * 64,
        "gasUsed": 123456,
    }

    report = script.build_execution_receipt_report(
        proposal_id=1,
        governance_contract="0xf1B0086962e41710968D81F099c8ced23b97D2d2",
        operator_address="0x870B8b23F431c140FDf5c7b96987306a327AFF96",
        tx_hash="0x" + "b" * 64,
        receipt=receipt,
        readiness_report=_ready_report(),
        final_state_code=5,
    )

    assert report["ok"] is False
    assert report["decision"] == "EXECUTION_FINAL_STATE_NOT_EXECUTED"
    assert report["status"] == "FAILED"
    assert report["receipt"]["status"] == 1
    assert report["receipt"]["final_state_executed"] is False
    assert report["proposal_state_after_receipt"]["executed"] is False
    assert report["goal_can_be_marked_complete"] is False
