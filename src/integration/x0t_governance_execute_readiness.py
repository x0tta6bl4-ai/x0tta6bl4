"""Read-only X0T governance proposal execute-readiness evidence.

This module checks whether a queued Base governance proposal is ready to be
executed. It never submits `execute(...)`; it only reads proposal state,
latest block time, and writes local evidence artifacts when requested.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_RPC_URL = "https://base-sepolia.drpc.org"
DEFAULT_GOVERNANCE_CONTRACT = "0xf1B0086962e41710968D81F099c8ced23b97D2d2"
DEFAULT_PROPOSAL_ID = 1
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/x0t-governance-execute-proposal-1-readiness-2026-05-20.md"

STATE_LABELS = ["Unknown", "Active", "Defeated", "Succeeded", "Queued", "Ready", "Executed", "Vetoed"]
VALID_DECISIONS = {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
    "VETOED_NOT_EXECUTABLE",
    "NOT_READY_STATE_NOT_EXECUTABLE",
}

ABI = [
    {
        "inputs": [{"name": "proposalId", "type": "uint256"}],
        "name": "getProposal",
        "outputs": [
            {
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "proposer", "type": "address"},
                    {"name": "ipfsCid", "type": "string"},
                    {"name": "configHash", "type": "bytes32"},
                    {"name": "actionType", "type": "bytes32"},
                    {"name": "pqSignatureHash", "type": "bytes32"},
                    {"name": "kind", "type": "uint8"},
                    {"name": "targetNode", "type": "address"},
                    {"name": "startTime", "type": "uint256"},
                    {"name": "endTime", "type": "uint256"},
                    {"name": "earliestExecutionTime", "type": "uint256"},
                    {"name": "forPower", "type": "uint256"},
                    {"name": "againstPower", "type": "uint256"},
                    {"name": "abstainPower", "type": "uint256"},
                    {"name": "queued", "type": "bool"},
                    {"name": "executed", "type": "bool"},
                    {"name": "vetoed", "type": "bool"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "proposalId", "type": "uint256"}],
        "name": "state",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_from_unix(value: int) -> str:
    return datetime.fromtimestamp(int(value), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _state_label(state_code: int) -> str:
    return STATE_LABELS[state_code] if 0 <= state_code < len(STATE_LABELS) else f"UnknownState({state_code})"


def _proposal_dict(proposal: Any) -> Dict[str, Any]:
    if isinstance(proposal, dict):
        return dict(proposal)
    return {
        "id": proposal[0],
        "proposer": proposal[1],
        "ipfsCid": proposal[2],
        "configHash": proposal[3],
        "actionType": proposal[4],
        "pqSignatureHash": proposal[5],
        "kind": proposal[6],
        "targetNode": proposal[7],
        "startTime": proposal[8],
        "endTime": proposal[9],
        "earliestExecutionTime": proposal[10],
        "forPower": proposal[11],
        "againstPower": proposal[12],
        "abstainPower": proposal[13],
        "queued": proposal[14],
        "executed": proposal[15],
        "vetoed": proposal[16],
    }


def _decision(state_code: int, proposal: Dict[str, Any], latest_block_timestamp: int) -> Tuple[str, bool]:
    state_label = _state_label(state_code)
    earliest_execution = int(proposal.get("earliestExecutionTime") or 0)
    executed = bool(proposal.get("executed"))
    vetoed = bool(proposal.get("vetoed"))
    queued = bool(proposal.get("queued"))

    if executed or state_label == "Executed":
        return "ALREADY_EXECUTED", False
    if vetoed or state_label == "Vetoed":
        return "VETOED_NOT_EXECUTABLE", False
    if state_label == "Ready" and latest_block_timestamp >= earliest_execution:
        return "READY_TO_EXECUTE", True
    if state_label == "Queued" and queued and latest_block_timestamp < earliest_execution:
        return "NOT_READY_TIMELOCK_ACTIVE", False
    if state_label == "Queued" and queued:
        return "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED", False
    return "NOT_READY_STATE_NOT_EXECUTABLE", False


def build_readiness_report(
    *,
    proposal: Any,
    state_code: int,
    latest_block: int,
    latest_block_timestamp: int,
    governance_contract: str = DEFAULT_GOVERNANCE_CONTRACT,
    proposal_id: int = DEFAULT_PROPOSAL_ID,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    data = _proposal_dict(proposal)
    state_label = _state_label(int(state_code))
    earliest_execution = int(data.get("earliestExecutionTime") or 0)
    remaining = max(0, earliest_execution - int(latest_block_timestamp))
    decision, execute_ready = _decision(int(state_code), data, int(latest_block_timestamp))

    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-readiness-v2",
        "generated_at": generated_at or utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only execute readiness check for Base Sepolia proposal. It verifies current "
            "proposal state and timelock timing, but does not submit execute(...), does not "
            "mutate chain/runtime state, and does not satisfy the external_settlement receipt gate."
        ),
        "chain": {"name": "base-sepolia", "chain_id": 84532},
        "governance_contract": governance_contract,
        "proposal_id": int(proposal_id),
        "proposal": {
            "id": int(data.get("id") or proposal_id),
            "proposer": str(data.get("proposer") or ""),
            "ipfs_cid": str(data.get("ipfsCid") or ""),
            "for_power": int(data.get("forPower") or 0),
            "against_power": int(data.get("againstPower") or 0),
            "abstain_power": int(data.get("abstainPower") or 0),
        },
        "proposal_state": {
            "state_code": int(state_code),
            "state_label": state_label,
            "queued": bool(data.get("queued")),
            "executed": bool(data.get("executed")),
            "vetoed": bool(data.get("vetoed")),
        },
        "timelock": {
            "earliest_execution_time_unix": earliest_execution,
            "earliest_execution_time_utc": _utc_from_unix(earliest_execution),
            "checked_at_utc": _utc_from_unix(int(latest_block_timestamp)),
            "latest_block": int(latest_block),
            "latest_block_timestamp_unix": int(latest_block_timestamp),
            "latest_block_timestamp_utc": _utc_from_unix(int(latest_block_timestamp)),
            "seconds_until_earliest_execution_by_block_time": remaining,
        },
        "decision": decision,
        "summary": {
            "execute_ready_now": execute_ready,
            "proposal_queued": bool(data.get("queued")),
            "proposal_executed": bool(data.get("executed")),
            "proposal_vetoed": bool(data.get("vetoed")),
            "next_executable_after_utc": _utc_from_unix(earliest_execution),
            "safe_to_retry_readiness_check": not bool(data.get("executed")),
        },
        "source_commands": [
            "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md",
            "python3 check_dao_proposal.py",
            "python3 final_dao_check.py",
            'PRIVATE_KEY="$PRIVATE_KEY" python3 execute_dao_proposal.py # only after explicit operator approval when state is Ready',
        ],
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "submits_transaction": False,
        "runs_live_rpc": True,
        "not_verified_yet": [
            "execute(1) with explicit operator approval after proposal state becomes Ready",
            "execution transaction receipt and final Executed proposal state",
        ],
    }


def fetch_readiness_report(
    rpc_url: str,
    governance_contract: str = DEFAULT_GOVERNANCE_CONTRACT,
    proposal_id: int = DEFAULT_PROPOSAL_ID,
) -> Dict[str, Any]:
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("failed to connect to Base Sepolia RPC")

    contract = w3.eth.contract(address=Web3.to_checksum_address(governance_contract), abi=ABI)
    proposal = contract.functions.getProposal(proposal_id).call()
    state_code = contract.functions.state(proposal_id).call()
    block = w3.eth.get_block("latest")
    return build_readiness_report(
        proposal=proposal,
        state_code=state_code,
        latest_block=int(block["number"]),
        latest_block_timestamp=int(block["timestamp"]),
        governance_contract=governance_contract,
        proposal_id=proposal_id,
    )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def validate_readiness_report(report: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    state = report.get("proposal_state", {})
    summary = report.get("summary", {})
    timelock = report.get("timelock", {})
    decision = report.get("decision")

    if report.get("schema_version") != "x0tta6bl4-x0t-governance-execute-readiness-v2":
        errors.append("schema_version must be x0tta6bl4-x0t-governance-execute-readiness-v2")
    if report.get("status") != "VERIFIED HERE":
        errors.append("status must be VERIFIED HERE")
    if report.get("ok") is not True:
        errors.append("ok must be true")
    if report.get("goal_can_be_marked_complete") is not False:
        errors.append("goal_can_be_marked_complete must be false")
    if report.get("mutates_chain") is not False:
        errors.append("mutates_chain must be false")
    if report.get("submits_transaction") is not False:
        errors.append("submits_transaction must be false")
    if report.get("runs_live_rpc") is not True:
        errors.append("runs_live_rpc must be true for generated readiness evidence")
    if report.get("chain", {}).get("chain_id") != 84532:
        errors.append("chain.chain_id must be Base Sepolia 84532")
    if decision not in VALID_DECISIONS:
        errors.append("decision must be a known execute-readiness decision")

    state_code = state.get("state_code")
    if not isinstance(state_code, int):
        errors.append("proposal_state.state_code must be an integer")
    elif state.get("state_label") != _state_label(state_code):
        errors.append("proposal_state.state_label must match state_code")

    earliest = timelock.get("earliest_execution_time_unix")
    latest_ts = timelock.get("latest_block_timestamp_unix")
    remaining = timelock.get("seconds_until_earliest_execution_by_block_time")
    if not all(isinstance(value, int) for value in (earliest, latest_ts, remaining)):
        errors.append("timelock unix/remaining fields must be integers")
    elif remaining != max(0, earliest - latest_ts):
        errors.append("seconds_until_earliest_execution_by_block_time must match timelock delta")

    execute_ready = summary.get("execute_ready_now")
    if decision == "READY_TO_EXECUTE" and execute_ready is not True:
        errors.append("READY_TO_EXECUTE requires summary.execute_ready_now=true")
    if decision != "READY_TO_EXECUTE" and execute_ready is not False:
        errors.append("non-ready decisions require summary.execute_ready_now=false")
    if state.get("executed") is True and summary.get("safe_to_retry_readiness_check") is not False:
        errors.append("executed proposals must not be safe_to_retry_readiness_check")

    commands = report.get("source_commands", [])
    if not isinstance(commands, list) or not any("check_x0t_governance_execute_readiness.py" in str(command) for command in commands):
        errors.append("source_commands must include the read-only readiness generator")
    if not any("explicit operator approval" in str(command) for command in commands):
        errors.append("source_commands must preserve the explicit operator approval boundary")

    return errors


def build_validation_report(report: Dict[str, Any], artifact_path: str) -> Dict[str, Any]:
    errors = validate_readiness_report(report)
    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-readiness-validation-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": not errors,
        "claim_boundary": (
            "Offline validation of an existing X0T governance execute-readiness artifact. "
            "It does not call RPC, submit transactions, mutate chain/runtime state, or mark the goal complete."
        ),
        "artifact_path": artifact_path,
        "decision": "VALID_EXECUTE_READINESS_ARTIFACT" if not errors else "INVALID_EXECUTE_READINESS_ARTIFACT",
        "goal_can_be_marked_complete": False,
        "runs_live_rpc": False,
        "mutates_chain": False,
        "submits_transaction": False,
        "errors": errors,
        "summary": {
            "valid": not errors,
            "errors_total": len(errors),
            "source_decision": report.get("decision"),
            "execute_ready_now": report.get("summary", {}).get("execute_ready_now"),
            "state_label": report.get("proposal_state", {}).get("state_label"),
            "state_code": report.get("proposal_state", {}).get("state_code"),
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    ready = bool(report["summary"]["execute_ready_now"])
    status = "READY - WAITING FOR EXPLICIT EXECUTE APPROVAL" if ready else "NOT READY - TIMELOCK/STATE ACTIVE"
    state = report["proposal_state"]
    timelock = report["timelock"]
    return f"""# X0T Governance Execute Readiness

Status: {status}

This is the read-only readiness check for executing proposal `{report["proposal_id"]}` on Base
Sepolia. It does not submit `execute(1)`.

## Current State

- Chain: Base Sepolia (`84532`)
- Governance contract: `{report["governance_contract"]}`
- Proposal id: `{report["proposal_id"]}`
- State: `{state["state_label"]} ({state["state_code"]})`
- Executed: `{str(state["executed"]).lower()}`
- Vetoed: `{str(state["vetoed"]).lower()}`
- Earliest execution: `{timelock["earliest_execution_time_utc"]}`
- Latest checked block: `{timelock["latest_block"]}`
- Latest block timestamp: `{timelock["latest_block_timestamp_utc"]}`
- Checked at: `{timelock["checked_at_utc"]}`
- Remaining by block time: `{timelock["seconds_until_earliest_execution_by_block_time"]}` seconds
- Decision: `{report["decision"]}`

The local calendar date can differ from chain readiness. The contract readiness
is governed by Base Sepolia block time and proposal `state(...)`.

## Next Command

Rerun this read-only generator first:

```bash
python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md
```

If the state is `Ready (5)`, execute only with explicit operator approval and
the operator key supplied from the environment:

```bash
X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-{report["proposal_id"]}-base-sepolia PRIVATE_KEY="$PRIVATE_KEY" python3 execute_dao_proposal.py
```

The machine-readable readiness shard is:

- `{DEFAULT_OUTPUT_JSON}`
"""


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _rpc_url(value: Optional[str]) -> str:
    return value or os.environ.get("BASE_SEPOLIA_RPC_URL") or os.environ.get("X0T_BASE_RPC_URL") or DEFAULT_RPC_URL


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate read-only X0T governance execute-readiness evidence")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--rpc-url")
    parser.add_argument("--governance-contract", default=DEFAULT_GOVERNANCE_CONTRACT)
    parser.add_argument("--proposal-id", type=int, default=DEFAULT_PROPOSAL_ID)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--write-json", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate-json", help="validate an existing readiness JSON artifact without RPC")
    parser.add_argument("--output-validation-json")
    parser.add_argument("--require-valid", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.validate_json:
        artifact_path = _resolve(root, args.validate_json)
        report = json.loads(artifact_path.read_text(encoding="utf-8"))
        validation = build_validation_report(report, str(Path(args.validate_json)))
        if args.output_validation_json:
            write_json(_resolve(root, args.output_validation_json), validation)
        print(json.dumps(validation, ensure_ascii=True, sort_keys=True))
        if args.require_valid and not validation["ok"]:
            return 2
        return 0

    report = fetch_readiness_report(_rpc_url(args.rpc_url), args.governance_contract, args.proposal_id)

    if args.write_json:
        write_json(_resolve(root, args.output_json), report)
    if args.write_md:
        md_path = _resolve(root, args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "decision": report["decision"],
                "execute_ready_now": report["summary"]["execute_ready_now"],
                "state": report["proposal_state"],
                "timelock": report["timelock"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and not report["summary"]["execute_ready_now"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
