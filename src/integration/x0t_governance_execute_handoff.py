"""Read-only operator handoff for X0T governance proposal execution.

This module turns the current execute-readiness shard into an actionable
operator packet. It never calls RPC and never submits ``execute(...)``.
"""

from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.x0t_governance_execute_readiness import (
    DEFAULT_GOVERNANCE_CONTRACT,
    DEFAULT_OUTPUT_JSON as DEFAULT_READINESS_JSON,
    DEFAULT_PROPOSAL_ID,
    VALID_DECISIONS,
)


DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/x0t-governance-execute-operator-handoff-2026-05-20.md"
DEFAULT_RECEIPT_JSON = ".tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json"
APPROVAL_ENV = "X0T_EXECUTE_PROPOSAL_APPROVAL"
PRIVATE_KEY_ENV_ASSIGNMENT = 'PRIVATE_KEY="$PRIVATE_KEY"'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expected_approval_value(proposal_id: int) -> str:
    return f"execute-proposal-{proposal_id}-base-sepolia"


def _read_json(path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, f"missing source artifact: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable source artifact: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"source artifact must be a JSON object: {path}"
    return data, ""


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _state(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("proposal_state", {})
    return value if isinstance(value, dict) else {}


def _timelock(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("timelock", {})
    return value if isinstance(value, dict) else {}


def _source_errors(readiness: Optional[Dict[str, Any]], read_error: str) -> List[str]:
    errors: List[str] = []
    if read_error:
        errors.append(read_error)
        return errors
    if readiness is None:
        errors.append("readiness artifact is missing or unreadable")
        return errors
    if readiness.get("schema_version") != "x0tta6bl4-x0t-governance-execute-readiness-v2":
        errors.append("readiness schema_version must be x0tta6bl4-x0t-governance-execute-readiness-v2")
    if readiness.get("status") != "VERIFIED HERE":
        errors.append("readiness status must be VERIFIED HERE")
    if readiness.get("ok") is not True:
        errors.append("readiness ok must be true")
    if readiness.get("decision") not in VALID_DECISIONS:
        errors.append("readiness decision is not a known execute-readiness decision")
    if readiness.get("mutates_chain") is not False:
        errors.append("readiness artifact must be read-only: mutates_chain=false")
    if readiness.get("submits_transaction") is not False:
        errors.append("readiness artifact must be read-only: submits_transaction=false")
    if readiness.get("goal_can_be_marked_complete") is not False:
        errors.append("readiness artifact must not close the goal")
    return errors


def _proposal_id(readiness: Optional[Dict[str, Any]]) -> int:
    try:
        return int((readiness or {}).get("proposal_id") or DEFAULT_PROPOSAL_ID)
    except (TypeError, ValueError):
        return DEFAULT_PROPOSAL_ID


def _python_command_entrypoint(command: str) -> Optional[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    while tokens and "=" in tokens[0] and tokens[0].split("=", 1)[0].isidentifier():
        tokens.pop(0)
    if len(tokens) >= 3 and tokens[0].startswith("python") and tokens[1] == "-m":
        return tokens[2].replace(".", "/") + ".py"
    if len(tokens) >= 2 and tokens[0].startswith("python") and tokens[1].endswith(".py"):
        return tokens[1]
    return None


def _shell_redirection_placeholder(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "unparseable command"
    for token in tokens:
        if token.startswith("<") or token.startswith(">") or token.endswith(">"):
            return token
    return ""


def _action_commands(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    commands: List[Dict[str, Any]] = []
    for action in actions:
        command = action.get("command")
        if isinstance(command, str) and command:
            commands.append({"action_id": action.get("id", ""), "command": command})
        action_commands = action.get("commands")
        if isinstance(action_commands, list):
            for command in action_commands:
                if isinstance(command, str) and command:
                    commands.append({"action_id": action.get("id", ""), "command": command})
    return commands


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _operator_command_checks(root: Path, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for item in _action_commands(actions):
        command = item["command"]
        entrypoint = _python_command_entrypoint(command)
        entrypoint_exists = bool(entrypoint and (root / entrypoint).is_file())
        redirection_placeholder = _shell_redirection_placeholder(command)
        ready = entrypoint_exists and not redirection_placeholder
        checks.append(
            {
                "action_id": item.get("action_id", ""),
                "command": command,
                "expected_entrypoint": entrypoint or "",
                "entrypoint_exists": entrypoint_exists,
                "shell_redirection_placeholder": redirection_placeholder,
                "shell_redirection_placeholder_detected": bool(redirection_placeholder),
                "status": "READY"
                if ready
                else "SHELL_REDIRECTION_PLACEHOLDER"
                if redirection_placeholder
                else "MISSING_LOCAL_ENTRYPOINT",
            }
        )
    return checks


def build_report(
    root: Path,
    readiness_json: Path = Path(DEFAULT_READINESS_JSON),
    *,
    readiness_display: str = DEFAULT_READINESS_JSON,
) -> Dict[str, Any]:
    readiness_path = readiness_json if readiness_json.is_absolute() else root / readiness_json
    readiness, read_error = _read_json(readiness_path)
    errors = _source_errors(readiness, read_error)
    summary = _summary(readiness)
    state = _state(readiness)
    timelock = _timelock(readiness)
    proposal_id = _proposal_id(readiness)
    approval_value = expected_approval_value(proposal_id)
    readiness_decision = str((readiness or {}).get("decision") or "")
    execute_ready = summary.get("execute_ready_now") is True
    proposal_executed = state.get("executed") is True or readiness_decision == "ALREADY_EXECUTED"
    proposal_vetoed = state.get("vetoed") is True or readiness_decision == "VETOED_NOT_EXECUTABLE"
    dry_run_command = "python3 execute_dao_proposal.py --dry-run"
    execute_command = f"{APPROVAL_ENV}={approval_value} {PRIVATE_KEY_ENV_ASSIGNMENT} python3 execute_dao_proposal.py"
    operator_next_actions = [
        {
            "id": "refresh_readiness",
            "status": "DONE" if not errors else "BLOCKING",
            "command": (
                "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                "--write-json --write-md"
            ),
            "submits_transaction": False,
        },
        {
            "id": "dry_run_execute_boundary",
            "status": "READY" if execute_ready and not errors else "AFTER_READY_STATE",
            "command": dry_run_command,
            "submits_transaction": False,
        },
        {
            "id": "execute_with_operator_approval",
            "status": "OPERATOR_APPROVAL_REQUIRED" if execute_ready and not errors else "AFTER_READY_STATE",
            "command": execute_command,
            "submits_transaction": True,
            "requires_operator_approval": True,
        },
        {
            "id": "retain_execution_receipt",
            "status": "AFTER_EXECUTE",
            "required_artifact": DEFAULT_RECEIPT_JSON,
            "acceptance_rule": (
                "receipt ok=true only when tx receipt status is 1 and final proposal state is Executed"
            ),
        },
        {
            "id": "rerun_completion_and_gap",
            "status": "AFTER_EXECUTE",
            "commands": [
                "python3 -m src.integration.completion_audit --root . --output-json .tmp/validation-shards/integration-spine-completion-audit-current.json --output-md docs/verification/integration-spine-completion-audit-2026-05-20.md",
                "python3 -m src.integration.production_gap_index --root . --output-json .tmp/validation-shards/integration-spine-production-gap-index-current.json --output-md docs/verification/integration-spine-production-gap-index-2026-05-20.md",
            ],
            "submits_transaction": False,
        },
    ]
    operator_command_checks = _operator_command_checks(root, operator_next_actions)
    missing_operator_entrypoints = [
        check["expected_entrypoint"]
        for check in operator_command_checks
        if check.get("entrypoint_exists") is not True
    ]
    operator_shell_placeholders = [
        check["shell_redirection_placeholder"]
        for check in operator_command_checks
        if check.get("shell_redirection_placeholder_detected") is True
    ]
    operator_command_surface_ready = not missing_operator_entrypoints
    operator_command_shell_surface_ready = not operator_shell_placeholders
    operator_sequence_ready = operator_command_surface_ready and operator_command_shell_surface_ready
    ready_for_operator_execute = (
        not errors
        and execute_ready
        and not proposal_executed
        and not proposal_vetoed
        and operator_sequence_ready
    )
    already_executed = not errors and proposal_executed
    handoff_actionable = not errors and bool(readiness) and operator_sequence_ready

    if not operator_sequence_ready:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_OPERATOR_COMMANDS"
    elif ready_for_operator_execute:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
    elif already_executed:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
    elif errors:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_READINESS"
    else:
        handoff_decision = "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"

    missing_inputs: List[Dict[str, Any]] = []
    if not operator_command_shell_surface_ready:
        missing_inputs.append(
            {
                "id": "operator_command_shell_placeholders",
                "status": "REPO_REQUIRED",
                "shell_redirection_placeholders": operator_shell_placeholders,
                "reason": "operator next-action commands must not use shell redirection-style placeholders",
            }
        )
    if not operator_command_surface_ready:
        missing_inputs.append(
            {
                "id": "operator_command_entrypoints",
                "status": "REPO_REQUIRED",
                "missing_entrypoints": missing_operator_entrypoints,
                "reason": "operator next-action commands reference local entrypoints that are missing",
            }
        )
    if errors:
        missing_inputs.append(
            {
                "id": "valid_readiness_artifact",
                "status": "OPERATOR_INPUT_REQUIRED",
                "command": (
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                    "--write-json --write-md"
                ),
                "reason": "current execute-readiness artifact is missing, unreadable, or invalid",
            }
        )
    elif proposal_vetoed:
        missing_inputs.append(
            {
                "id": "terminal_vetoed_state",
                "status": "TERMINAL_CHAIN_STATE",
                "command": (
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                    "--write-json --write-md"
                ),
                "reason": "proposal is vetoed and cannot become READY_TO_EXECUTE",
            }
        )
    elif readiness_decision == "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED":
        missing_inputs.append(
            {
                "id": "refresh_after_timelock_state",
                "status": "READINESS_REFRESH_REQUIRED",
                "command": (
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                    "--write-json --write-md --require-ready"
                ),
                "reason": "timelock has elapsed but the retained readiness shard still reports Queued",
            }
        )
    elif readiness_decision == "NOT_READY_STATE_NOT_EXECUTABLE":
        missing_inputs.append(
            {
                "id": "not_executable_chain_state",
                "status": "CHAIN_STATE_NOT_EXECUTABLE",
                "command": (
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                    "--write-json --write-md"
                ),
                "reason": "proposal state is not executable by the governance execute path",
            }
        )
    elif not proposal_executed and not execute_ready:
        missing_inputs.append(
            {
                "id": "ready_execute_state",
                "status": "WAIT_FOR_CHAIN_STATE",
                "command": (
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py "
                    "--write-json --write-md --require-ready"
                ),
                "reason": f"readiness decision is {readiness_decision}, not READY_TO_EXECUTE",
            }
        )
    if ready_for_operator_execute:
        missing_inputs.extend(
            [
                {
                    "id": "explicit_operator_approval",
                    "status": "OPERATOR_APPROVAL_REQUIRED",
                    "environment": {APPROVAL_ENV: approval_value},
                    "reason": "execute_dao_proposal.py refuses to submit without this proposal-specific value",
                },
                {
                    "id": "operator_private_key",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "environment": {"PRIVATE_KEY": "<operator key>"},
                    "reason": "execute transaction signing requires an operator-supplied key",
                },
            ]
        )
    missing_input_status_counts = _status_counts(missing_inputs)

    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "handoff_decision": handoff_decision,
        "decision": "READY_FOR_OPERATOR_EXECUTE" if ready_for_operator_execute else "BLOCKED_OR_ALREADY_HANDLED",
        "handoff_actionable": handoff_actionable,
        "ready_for_operator_execute": ready_for_operator_execute,
        "already_executed": already_executed,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only X0T governance execute operator handoff. It reads the current "
            "execute-readiness artifact and lists the exact dry-run, approval, and execute commands. "
            "It does not call RPC, submit execute(1), sign transactions, mutate chain/runtime state, "
            "or close /goal."
        ),
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "approval_boundary": {
            "approval_env": APPROVAL_ENV,
            "expected_value": approval_value,
            "private_key_required": True,
            "can_submit_without_operator_approval": False,
        },
        "source_artifacts": [readiness_display],
        "source_errors": errors,
        "operator_command_checks": operator_command_checks,
        "missing_inputs": missing_inputs,
        "operator_next_actions": operator_next_actions,
        "not_verified_yet": []
        if already_executed
        else [
            "operator-approved execute(1) transaction",
            "mined transaction receipt with status=1",
            "post-receipt proposal state Executed",
        ],
        "summary": {
            "readiness_decision": readiness_decision,
            "execute_ready_now": execute_ready,
            "proposal_id": proposal_id,
            "governance_contract": (readiness or {}).get("governance_contract") or DEFAULT_GOVERNANCE_CONTRACT,
            "state_code": state.get("state_code"),
            "state_label": state.get("state_label"),
            "proposal_executed": proposal_executed,
            "proposal_vetoed": proposal_vetoed,
            "next_executable_after_utc": summary.get("next_executable_after_utc"),
            "seconds_until_earliest_execution_by_block_time": timelock.get(
                "seconds_until_earliest_execution_by_block_time"
            ),
            "approval_env": APPROVAL_ENV,
            "approval_value_required": approval_value,
            "missing_inputs_total": len(missing_inputs),
            "missing_input_status_counts": missing_input_status_counts,
            "missing_inputs_operator_input_required": missing_input_status_counts.get(
                "OPERATOR_INPUT_REQUIRED",
                0,
            ),
            "missing_inputs_operator_approval_required": missing_input_status_counts.get(
                "OPERATOR_APPROVAL_REQUIRED",
                0,
            ),
            "missing_inputs_generic_operator_required": missing_input_status_counts.get(
                "OPERATOR_REQUIRED",
                0,
            ),
            "source_errors_total": len(errors),
            "operator_actions_total": len(operator_next_actions),
            "operator_commands_total": len(operator_command_checks),
            "operator_command_entrypoints_missing": len(missing_operator_entrypoints),
            "operator_command_surface_ready": operator_command_surface_ready,
            "operator_commands_with_shell_redirection_placeholders": len(operator_shell_placeholders),
            "operator_command_shell_surface_ready": operator_command_shell_surface_ready,
            "operator_sequence_ready": operator_sequence_ready,
            "safety_flags_ready": True,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# X0T Governance Execute Operator Handoff",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Handoff decision: `{report.get('handoff_decision', '')}`",
        f"Ready for operator execute: `{report.get('ready_for_operator_execute')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Claim Boundary",
        "",
        str(report.get("claim_boundary", "")),
        "",
        "## Readiness Summary",
        "",
        f"- readiness decision: `{summary.get('readiness_decision', '')}`",
        f"- execute ready now: `{summary.get('execute_ready_now')}`",
        f"- state: `{summary.get('state_label', '')} ({summary.get('state_code', '')})`",
        f"- proposal executed: `{summary.get('proposal_executed')}`",
        f"- proposal vetoed: `{summary.get('proposal_vetoed')}`",
        f"- next executable after: `{summary.get('next_executable_after_utc', '')}`",
        f"- remaining by block time: `{summary.get('seconds_until_earliest_execution_by_block_time')}`",
        "",
        "## Approval Boundary",
        "",
        f"- `{summary.get('approval_env')}` must be exactly `{summary.get('approval_value_required')}`",
        "- `PRIVATE_KEY` must be supplied by the operator only when executing",
        "- this handoff does not submit transactions",
        "",
        "## Operator Command Surface",
        "",
        f"- commands checked: `{summary.get('operator_commands_total')}`",
        f"- missing entrypoints: `{summary.get('operator_command_entrypoints_missing')}`",
        f"- shell redirection placeholders: `{summary.get('operator_commands_with_shell_redirection_placeholders')}`",
        f"- operator sequence ready: `{summary.get('operator_sequence_ready')}`",
        "",
        "## Operator Actions",
        "",
    ]
    for action in report.get("operator_next_actions", []):
        if not isinstance(action, dict):
            continue
        lines.append(f"- `{action.get('id')}`: `{action.get('status')}`")
        command = action.get("command")
        if command:
            lines.append(f"  - `{command}`")
        for command in action.get("commands", []) if isinstance(action.get("commands"), list) else []:
            lines.append(f"  - `{command}`")
        if action.get("required_artifact"):
            lines.append(f"  - required artifact: `{action.get('required_artifact')}`")
    lines.extend(["", "## Missing Inputs", ""])
    missing = report.get("missing_inputs", [])
    if isinstance(missing, list) and missing:
        for item in missing:
            if isinstance(item, dict):
                lines.append(f"- `{item.get('id')}`: `{item.get('status')}` - {item.get('reason', '')}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "X0T Governance Execute Operator Handoff",
            f"handoff_decision: {report.get('handoff_decision')}",
            f"ready_for_operator_execute: {report.get('ready_for_operator_execute')}",
            f"readiness_decision: {summary.get('readiness_decision')}",
            f"approval_env: {summary.get('approval_env')}",
            f"approval_value_required: {summary.get('approval_value_required')}",
        ]
    )


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build X0T governance execute operator handoff")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default="")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-actionable", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root, Path(args.readiness_json), readiness_display=args.readiness_json)
    write_json(_resolve(root, args.output_json), report)
    if args.write_md or args.output_md:
        write_json_path = _resolve(root, args.output_md or DEFAULT_OUTPUT_MD)
        write_json_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_path.write_text(render_markdown(report), encoding="utf-8")
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_actionable and not report["handoff_actionable"]:
        return 2
    if args.require_ready and not report["ready_for_operator_execute"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
