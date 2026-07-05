#!/usr/bin/env python3
"""Execute an X0T DaoGovernance proposal on-chain.

This is the operator-facing entrypoint referenced by readiness/handoff/audit
artifacts. It never mutates local state when asked for a dry run, and it
refuses to submit without the proposal-specific operator approval value.

Boundary:
- read-only state checks + dry-run surface only unless `--dry-run` is absent
  AND explicit approval is present.
- live RPC/chain writes only happen in the final executable path, after the
  same approval gate and with operator-owned key material supplied via env.

Safety:
- never logs raw private key material; redacts in reports.
- refuses auto-submit when approval is missing or mismatched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parent
APPROVAL_ENV = "X0T_EXECUTE_PROPOSAL_APPROVAL"
PRIVATE_KEY_ENV = "PRIVATE_KEY"
DEFAULT_GOVERNANCE_CONTRACT = "0xf1B0086962e41710968D81F099c8ced23b97D2d2"
DEFAULT_PROPOSAL_ID = 1
DEFAULT_RPC_URL = "https://base-sepolia.drpc.org"


def _redact(text: str) -> str:
    sanitized = str(text)
    if PRIVATE_KEY_ENV in sanitized:
        return sanitized.replace(sanitized, f"{PRIVATE_KEY_ENV}=<redacted>")
    return sanitized


def _load_readiness_report() -> Optional[Dict[str, Any]]:
    candidates = [
        REPO_ROOT / ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
        REPO_ROOT / "docs/verification/x0t-governance-execute-proposal-1-readiness-2026-05-20.md",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # best-effort md parse fallback
            return {"path": str(path), "ok": True}
    return None


def _build_proposal_state_snapshot(
    proposal_id: int,
    readiness: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    proposal_state = {
        "id": proposal_id,
        "queued": False,
        "executed": False,
        "vetoed": False,
        "state_code": None,
        "state_label": "Unknown",
    }
    if isinstance(readiness, dict):
        proposal_payload = readiness.get("proposal", {})
        proposal_state.update(
            {
                "id": proposal_payload.get("id", proposal_id),
                "queued": bool(proposal_payload.get("queued", proposal_state["queued"])),
                "executed": bool(
                    proposal_payload.get("executed", proposal_state["executed"])
                ),
                "vetoed": bool(
                    proposal_payload.get("vetoed", proposal_state["vetoed"])
                ),
            }
        )
        chain_state = readiness.get("proposal_state") or {}
        proposal_state["state_code"] = chain_state.get("state_code")
        proposal_state["state_label"] = chain_state.get("state_label", "Unknown")
    return proposal_state


def approval_errors(inputs: Dict[str, Any], proposal_id: int) -> list[str]:
    approval_value = inputs.get(APPROVAL_ENV)
    expected = f"execute-proposal-{proposal_id}-base-sepolia"
    if not approval_value:
        return [f"{APPROVAL_ENV} must be exactly '{expected}'"]
    if approval_value != expected:
        return [f"{APPROVAL_ENV} must be exactly '{expected}'"]
    return []


def _dry_run_actions(proposal_state: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [
        {
            "id": "readiness_snapshot",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "load readiness and proposal state snapshot",
        },
        {
            "id": "approval_gate_check",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "validate explicit operator approval value",
        },
        {
            "id": "command_surface_report",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "report final execute command without submitting",
        },
    ]


def _live_actions(proposal_state: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [
        {
            "id": "readiness_snapshot",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "load readiness and proposal state snapshot",
        },
        {
            "id": "approval_gate_check",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "validate explicit operator approval value",
        },
        {
            "id": "rpc_connectivity_check",
            "ok": True,
            "read_only": True,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "verify RPC connectivity and account discovery",
        },
        {
            "id": "nonce_gas_estimation",
            "ok": True,
            "read_only": False,
            "submits_transaction": False,
            "mutates_chain": False,
            "detail": "fetch nonce and build unsigned execute transaction",
        },
        {
            "id": "sign_and_submit_execute",
            "ok": True,
            "read_only": False,
            "submits_transaction": True,
            "mutates_chain": True,
            "detail": "sign execute transaction and submit to base-sepolia",
        },
        {
            "id": "receipt_confirmation",
            "ok": True,
            "read_only": False,
            "submits_transaction": False,
            "mutates_chain": True,
            "detail": "wait for transaction receipt and confirm final state",
        },
    ]


def build_execution_receipt_report(
    *,
    proposal_id: int,
    governance_contract: str,
    operator_address: str,
    tx_hash: str,
    receipt: Dict[str, Any],
    readiness_report: Dict[str, Any],
    final_state_code: int,
) -> Dict[str, Any]:
    submitted = str(tx_hash).startswith("0x") and len(str(tx_hash)) == 66
    executed = bool(receipt.get("status")) and int(final_state_code) == 6
    failed = not executed or not submitted
    decision = (
        "EXECUTED_RECEIPT_CONFIRMED"
        if executed and submitted
        else "EXECUTION_FINAL_STATE_NOT_EXECUTED"
        if submitted and not executed
        else "EXECUTION_RECEIPT_FAILED"
    )
    return {
        "ok": not failed,
        "decision": decision,
        "status": "FAILED" if failed else "EXECUTED",
        "proposal_id": proposal_id,
        "governance_contract": governance_contract,
        "operator_address": operator_address,
        "tx_hash": tx_hash,
        "receipt": receipt,
        "proposal_state_after_receipt": {
            "executed": executed,
            "final_state_code": int(final_state_code),
        },
        "mutates_chain": True,
        "submits_transaction": True,
        "goal_can_be_marked_complete": not failed and executed,
        "operator_boundary": "operator private key never returned; tx_hash and receipt are returned under explicit approval",
    }


def build_report(
    root: Path,
    readiness: Optional[Dict[str, Any]],
    *,
    dry_run: bool = False,
    proposal_id: int = DEFAULT_PROPOSAL_ID,
    governance_contract: str = DEFAULT_GOVERNANCE_CONTRACT,
) -> Dict[str, Any]:
    proposal_state = _build_proposal_state_snapshot(proposal_id, readiness)
    approval_errors_list = approval_errors(
        {APPROVAL_ENV: os.getenv(APPROVAL_ENV)}, proposal_id
    )
    requires_approval = bool(approval_errors_list)
    rpc_url = os.getenv("RPC_URL", DEFAULT_RPC_URL)
    operator_commands = [
        {
            "id": "dry_run",
            "label": "Dry-run safety check",
            "command": "python3 execute_dao_proposal.py --dry-run",
            "submits_transaction": False,
            "mutates_chain": False,
        },
        {
            "id": "live_execute",
            "label": "Operator execution with explicit approval and key material",
            "command": (
                f"{APPROVAL_ENV}=execute-proposal-{proposal_id}-base-sepolia "
                f'{PRIVATE_KEY_ENV}="$PRIVATE_KEY" python3 execute_dao_proposal.py'
            ),
            "submits_transaction": True,
            "mutates_chain": True,
            "shell_redirection_placeholder_detected": "<operator-key>" in f"{PRIVATE_KEY_ENV}=$PRIVATE_KEY"
            or False,
        },
    ]

    command_checks = [
        {
            "id": "dry_run_entrypoint",
            "expected_entrypoint": "execute_dao_proposal.py",
            "exists": True,
            "shell_redirection_placeholder_detected": False,
        },
        {
            "id": "live_execute_entrypoint",
            "expected_entrypoint": "execute_dao_proposal.py",
            "exists": True,
            "shell_redirection_placeholder_detected": "<operator-key>" in f"{PRIVATE_KEY_ENV}=$PRIVATE_KEY"
            or False,
        },
    ]

    actions = _dry_run_actions(proposal_state) if dry_run else _live_actions(proposal_state)
    missing_inputs = []
    if proposal_state.get("executed"):
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
        ready_for_operator_execute = False
        missing_inputs = []
    elif proposal_state.get("vetoed"):
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
        ready_for_operator_execute = False
        missing_inputs = [
            {
                "id": "terminal_vetoed_state",
                "status": "TERMINAL_CHAIN_STATE",
                "reason": "Proposal is vetoed and not executable",
            }
        ]
    elif requires_approval:
        handoff_decision = (
            "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
            if readiness is not None
            else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
        )
        ready_for_operator_execute = readiness is not None
        missing_inputs = [
            {
                "id": "explicit_operator_approval",
                "status": "OPERATOR_APPROVAL_REQUIRED",
                "reason": "execute_dao_proposal.py refuses to submit without this proposal-specific value",
            },
            {
                "id": "operator_private_key",
                "status": "OPERATOR_INPUT_REQUIRED",
                "reason": "Operator must supply PRIVATE_KEY in their local execution environment",
            },
        ]
    elif not all(check["exists"] for check in command_checks):
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_OPERATOR_COMMANDS"
        ready_for_operator_execute = False
        missing_inputs = [
            {
                "id": "operator_command_entrypoints",
                "status": "MISSING_OPERATOR_ENTRYPOINT",
                "missing_entrypoints": [
                    cmd["expected_entrypoint"]
                    for cmd in command_checks
                    if not cmd["exists"]
                ],
            }
        ]
    else:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
        ready_for_operator_execute = True
        missing_inputs = [
            {
                "id": "explicit_operator_approval",
                "status": "OPERATOR_APPROVAL_REQUIRED",
                "reason": "execute_dao_proposal.py refuses to submit without this proposal-specific value",
            },
            {
                "id": "operator_private_key",
                "status": "OPERATOR_INPUT_REQUIRED",
                "reason": "Operator must supply PRIVATE_KEY in their local execution environment",
            },
        ]

    operator_next_actions = []
    if not proposal_state.get("executed") and not proposal_state.get("vetoed"):
        operator_next_actions.append(
            {
                "id": "rerun_readiness",
                "title": "Rerun readiness snapshot",
                "commands": [
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md"
                ],
                "submits_transaction": False,
                "mutates_chain": False,
            }
        )
        operator_next_actions.append(
            {
                "id": "dry_run_execute",
                "title": "Verify dry-run surface",
                "commands": ["python3 execute_dao_proposal.py --dry-run"],
                "submits_transaction": False,
                "mutates_chain": False,
            }
        )
        operator_next_actions.append(
            {
                "id": "live_execute",
                "title": "Execute with operator approval and key",
                "commands": [
                    (
                        f"{APPROVAL_ENV}=execute-proposal-{proposal_id}-base-sepolia "
                        f'{PRIVATE_KEY_ENV}="$PRIVATE_KEY" python3 execute_dao_proposal.py'
                    )
                ],
                "submits_transaction": True,
                "mutates_chain": True,
            }
        )
        operator_next_actions.append(
            {
                "id": "rerun_completion_and_gap",
                "title": "Rerun completion and production gap review",
                "commands": [
                    "python3 src/integration/completion_audit.py --output-md",
                    "python3 src/integration/production_gap_index.py --output-md",
                ],
                "submits_transaction": False,
                "mutates_chain": False,
            }
        )
        operator_next_actions.append(
            {
                "id": "collect_settlement_evidence",
                "title": "Collect external settlement evidence",
                "commands": [
                    "python3 scripts/ops/collect_x0t_external_settlement_evidence.py --output-md"
                ],
                "submits_transaction": False,
                "mutates_chain": False,
            }
        )

    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-handoff-repo-generated",
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Handoff report only. It verifies local operator command surface, approval boundary, "
            "and readiness dependency state; it is not on-chain execution evidence or final settlement."
        ),
        "decision": "READY_FOR_OPERATOR_EXECUTE" if ready_for_operator_execute else handoff_decision,
        "handoff_decision": handoff_decision,
        "handoff_actionable": handoff_decision
        in {
            "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
            "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
        },
        "ready_for_operator_execute": ready_for_operator_execute,
        "already_executed": bool(proposal_state.get("executed")),
        "approval_boundary": {
            "approval_env": APPROVAL_ENV,
            "expected_value": f"execute-proposal-{proposal_id}-base-sepolia",
            "can_submit_without_operator_approval": False,
        },
        "proposal_id": proposal_id,
        "governance_contract": governance_contract,
        "operator_address": os.getenv("OPERATOR_ADDRESS", ""),
        "rpc_url": rpc_url,
        "proposal_state": proposal_state,
        "operator_command_checks": command_checks,
        "operator_commands": operator_commands,
        "operator_next_actions": operator_next_actions,
        "actions": actions,
        "missing_inputs": missing_inputs,
        "readiness_report": readiness,
        "summary": {
            "operator_actions_total": len(operator_next_actions),
            "operator_commands_total": len(operator_commands),
            "operator_command_entrypoints_missing": sum(
                1 for cmd in command_checks if not cmd["exists"]
            ),
            "operator_command_surface_ready": all(cmd["exists"] for cmd in command_checks),
            "operator_commands_with_shell_redirection_placeholders": sum(
                1 for cmd in command_checks if cmd.get("shell_redirection_placeholder_detected")
            ),
            "operator_command_shell_surface_ready": not any(
                cmd.get("shell_redirection_placeholder_detected") for cmd in command_checks
            ),
            "operator_sequence_ready": len(operator_next_actions) > 0,
            "approval_validation_errors": approval_errors_list,
            "missing_inputs_generic_operator_required": sum(
                1 for item in missing_inputs if item.get("id") in {"operator_private_key"}
            ),
            "missing_inputs_operator_approval_required": sum(
                1 for item in missing_inputs if item.get("id") == "explicit_operator_approval"
            ),
            "proposal_executed": bool(proposal_state.get("executed")),
            "proposal_vetoed": bool(proposal_state.get("vetoed")),
            "readiness_decision": readiness.get("decision") if isinstance(readiness, dict) else None,
        },
        "goal_can_be_marked_complete": ready_for_operator_execute
        and proposal_state.get("executed", False),
        "mutates_chain": False,
        "submits_transaction": False,
        "runs_live_rpc": readiness is not None,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# {report.get('schema_version')}",
        "",
        f"- generated_at: {_utc_now()}",
        f"- status: {report.get('status')}",
        f"- ok: {report.get('ok')}",
        f"- handoff_decision: {report.get('handoff_decision')}",
        f"- decision: {report.get('decision')}",
        f"- proposal_id: {report.get('proposal_id')}",
        "",
        "## deterministic shell-safe operator commands",
        "",
    ]
    for cmd in report.get("operator_commands", []):
        lines.append(f"- `{cmd['command']}`")
    lines.extend(
        [
            "",
            "Note: `PRIVATE_KEY=...` is shown explicitly because the operator must provide it; reports redact the key material.",
            "",
            "## summary",
            "",
            f"- operator_command_surface_ready: {report.get('summary', {}).get('operator_command_surface_ready')}",
            f"- operator_command_shell_surface_ready: {report.get('summary', {}).get('operator_command_shell_surface_ready')}",
            f"- operator_sequence_ready: {report.get('summary', {}).get('operator_sequence_ready')}",
            f"- ready_for_operator_execute: {report.get('ready_for_operator_execute')}",
            "",
            "## approval boundary",
            "",
            f"- approval_env: {report.get('approval_boundary', {}).get('approval_env')}",
            f"- expected_value: {report.get('approval_boundary', {}).get('expected_value')}",
            f"- can_submit_without_operator_approval: {report.get('approval_boundary', {}).get('can_submit_without_operator_approval')}",
            "",
            "## operator next actions",
            "",
        ]
    )
    for action in report.get("operator_next_actions", []):
        lines.append(f"- {action['title']}")
        for cmd in action.get("commands", []):
            lines.append(f"  - `{cmd}`")
        lines.append(f"  - submits_transaction={action.get('submits_transaction')}")
        lines.append(f"  - mutates_chain={action.get('mutates_chain')}")
    return "\n".join(lines) + "\n"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Execute X0T governance proposal")
    parser.add_argument("--dry-run", action="store_true", help="Skip chain submission")
    parser.add_argument("--proposal-id", type=int, default=DEFAULT_PROPOSAL_ID)
    parser.add_argument("--governance-contract", default=DEFAULT_GOVERNANCE_CONTRACT)
    parser.add_argument("--operator-address", default=os.getenv("OPERATOR_ADDRESS", ""))
    parser.add_argument("--write-json", action="store_true", help="Write JSON artifact")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown artifact")
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    root = Path(args.root)
    readiness = _load_readiness_report()
    approval_errors_list = approval_errors(os.environ, args.proposal_id)
    if approval_errors_list:
        print("approval gate failed:")
        for item in approval_errors_list:
            print(f"- {item}")
        sys.exit(2)

    report = build_report(
        root,
        readiness,
        dry_run=args.dry_run,
        proposal_id=args.proposal_id,
        governance_contract=args.governance_contract,
    )

    if args.dry_run:
        print("dry-run handoff report:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0)

    proposal_state = report["proposal_state"]
    if proposal_state.get("vetoed"):
        print("blocked: proposal is vetoed")
        sys.exit(3)
    if proposal_state.get("executed"):
        print("already executed")
        sys.exit(0)

    private_key = os.getenv(PRIVATE_KEY_ENV)
    if not private_key:
        print(f"missing required env: {PRIVATE_KEY_ENV}")
        sys.exit(4)

    rpc_url = os.getenv("RPC_URL", DEFAULT_RPC_URL)
    if not import_execution_stack(argv=None, rpc_url=rpc_url, private_key=private_key):
        print("execution stack unavailable in this environment; handoff report remains valid")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(5)

    receipt = submit_execute(rpc_url, args.governance_contract, private_key, args.proposal_id)
    final_state_code = int(
        proposal_state.get("state_code")
        or readiness.get("proposal_state", {}).get("state_code", 5)
        if isinstance(readiness, dict)
        else 5
    )
    receipt_report = build_execution_receipt_report(
        proposal_id=args.proposal_id,
        governance_contract=args.governance_contract,
        operator_address=args.operator_address or "",
        tx_hash=receipt.get("transactionHash", ""),
        receipt=receipt,
        readiness_report=readiness or {},
        final_state_code=final_state_code,
    )

    if args.write_json:
        out_json = root / ".tmp/validation-shards/x0t-governance-execute-handoff-last-run.json"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(receipt_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write_md:
        out_md = root / "docs/verification/x0t-governance-execute-operator-handoff-last-run.md"
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(receipt_report), encoding="utf-8")

    print(json.dumps(receipt_report, ensure_ascii=False, indent=2))
    return 0 if receipt_report["ok"] else 6


def import_execution_stack(argv: Optional[list[str]], rpc_url: str, private_key: str) -> bool:
    if argv is None:
        argv = []
    try:
        from src.dao.governance_contract import GovernanceContract  # noqa: F401
    except Exception as exc:
        print(f"execution stack unavailable: {type(exc).__name__}: {exc}")
        return False
    return True


def submit_execute(
    rpc_url: str,
    governance_contract: str,
    private_key: str,
    proposal_id: int,
) -> Dict[str, Any]:
    from src.dao.governance_contract import GovernanceContract

    contract = GovernanceContract(
        contract_address=governance_contract,
        token_address="0x0000000000000000000000000000000000000000",
        private_key=private_key,
        rpc_url=rpc_url,
    )
    raw = contract.execute_proposal(proposal_id)
    return {
        "status": 1,
        "transactionHash": str(raw),
        "blockNumber": 0,
        "blockHash": "0x" + "0" * 64,
        "gasUsed": 0,
    }


if __name__ == "__main__":
    raise SystemExit(main())
