"""Read-only operator handoff for the external X0T settlement blocker."""

from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_EVIDENCE_GATE = ".tmp/validation-shards/x0t-external-settlement-evidence-current.json"
DEFAULT_LIVE_RPC_GATE = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
DEFAULT_BLOCKER = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
DEFAULT_CAPTURE_PREFLIGHT = ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json"
DEFAULT_PRODUCTION_IMPORT = ".tmp/validation-shards/integration-spine-production-evidence-import-current.json"
DEFAULT_COMPLETION_GATE = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json"
DEFAULT_EVIDENCE_PATH = ".tmp/external-settlement-evidence/settlement-submit.json"
CAPTURE_PREFLIGHT_COMMAND = (
    'python3 -m src.integration.external_settlement --root . --preflight-capture-inputs '
    '--transaction-hash "$X0T_SETTLEMENT_TX_HASH" --destination-chain "$X0T_DESTINATION_CHAIN" '
    '--settlement-id "$X0T_SETTLEMENT_ID" --rpc-url "$X0T_BASE_RPC_URL" --require-preflight-ready'
)
VERIFY_EVIDENCE_COMMAND = "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready"
VERIFY_LIVE_RPC_COMMAND = (
    'python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready --rpc-url "$X0T_BASE_RPC_URL"'
)
PRODUCTION_INPUT_PIPELINE_COMMAND = (
    "python3 scripts/ops/run_integration_spine_production_input_pipeline.py --require-ready"
)
COMPLETION_GATE_COMMAND = "python3 scripts/ops/run_integration_spine_completion_gate.py --require-complete"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _bool(summary: Dict[str, Any], key: str) -> bool:
    return summary.get(key) is True


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


def _operator_input_status(ready: bool) -> str:
    return "DONE" if ready else "OPERATOR_INPUT_REQUIRED"


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _operator_command_checks(root: Path, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for action in actions:
        command = action.get("command")
        if not isinstance(command, str) or not command:
            continue
        entrypoint = _python_command_entrypoint(command)
        entrypoint_exists = bool(entrypoint and (root / entrypoint).is_file())
        redirection_placeholder = _shell_redirection_placeholder(command)
        ready = entrypoint_exists and not redirection_placeholder
        checks.append(
            {
                "action_id": action.get("id", ""),
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


def _source_reports(root: Path, paths: Dict[str, str]) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for label, rel in paths.items():
        path = root / rel
        data = _read_json(path)
        if data is None:
            reports.append(
                {
                    "label": label,
                    "path": rel,
                    "status": "MISSING",
                    "ok": False,
                    "errors": [f"missing or unreadable source artifact: {rel}"],
                }
            )
            continue
        reports.append(
            {
                "label": label,
                "path": rel,
                "schema_version": data.get("schema_version", ""),
                "status": data.get("status", ""),
                "ok": data.get("ok"),
                "decision": data.get("decision")
                or data.get("x0t_external_settlement_decision")
                or data.get("x0t_external_settlement_live_rpc_decision")
                or data.get("completion_decision")
                or "",
                "errors": [],
            }
        )
    return reports


def build_report(root: Path, paths: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    source_paths = {
        "evidence_gate": DEFAULT_EVIDENCE_GATE,
        "live_rpc_gate": DEFAULT_LIVE_RPC_GATE,
        "current_blocker": DEFAULT_BLOCKER,
        "capture_preflight": DEFAULT_CAPTURE_PREFLIGHT,
        "production_import": DEFAULT_PRODUCTION_IMPORT,
        "completion_gate": DEFAULT_COMPLETION_GATE,
    }
    if paths:
        source_paths.update(paths)
    evidence = _read_json(root / source_paths["evidence_gate"])
    live_rpc = _read_json(root / source_paths["live_rpc_gate"])
    blocker = _read_json(root / source_paths["current_blocker"])
    capture_preflight = _read_json(root / source_paths["capture_preflight"])
    production_import = _read_json(root / source_paths["production_import"])
    completion_gate = _read_json(root / source_paths["completion_gate"])
    source_reports = _source_reports(root, source_paths)
    source_errors = [
        error
        for report in source_reports
        for error in report.get("errors", [])
    ]

    evidence_summary = _summary(evidence)
    live_summary = _summary(live_rpc)
    blocker_summary = _summary(blocker)
    preflight_summary = _summary(capture_preflight)
    import_summary = _summary(production_import)
    completion_summary = _summary(completion_gate)

    capture_inputs_ready = _bool(preflight_summary, "capture_inputs_ready")
    evidence_ready = _bool(evidence_summary, "x0t_external_settlement_ready") or _bool(evidence_summary, "evidence_file_valid")
    evidence_exists = _bool(evidence_summary, "evidence_file_found") or _bool(blocker_summary, "expected_evidence_file_exists")
    live_rpc_ready = _bool(live_summary, "x0t_external_settlement_live_rpc_ready") or _bool(blocker_summary, "live_rpc_ready")
    production_import_ready = _bool(import_summary, "production_evidence_complete")
    completion_external_ready = _bool(completion_summary, "external_settlement_ready") or _bool(
        completion_summary, "external_settlement_live_rpc_ready"
    )
    blocker_ready = blocker is not None and blocker.get("decision") == "READY_TO_PROMOTE" and _bool(
        blocker_summary, "x0t_external_settlement_ready"
    )

    operator_next_actions = [
        {
            "id": "preflight_capture_inputs",
            "status": _operator_input_status(capture_inputs_ready),
            "command": CAPTURE_PREFLIGHT_COMMAND,
            "runs_live_rpc": False,
            "writes_evidence": False,
        },
        {
            "id": "capture_real_settlement_receipt",
            "status": _operator_input_status(evidence_ready),
            "description": "Place a real submitted X0T transaction receipt at .tmp/external-settlement-evidence/settlement-submit.json.",
        },
        {
            "id": "verify_retained_settlement_json",
            "status": _operator_input_status(evidence_ready),
            "command": VERIFY_EVIDENCE_COMMAND,
        },
        {
            "id": "verify_live_base_rpc",
            "status": _operator_input_status(live_rpc_ready),
            "command": VERIFY_LIVE_RPC_COMMAND,
        },
        {
            "id": "rerun_production_input_pipeline",
            "status": _operator_input_status(production_import_ready),
            "command": PRODUCTION_INPUT_PIPELINE_COMMAND,
        },
        {
            "id": "rerun_completion_gate",
            "status": _operator_input_status(completion_external_ready),
            "command": COMPLETION_GATE_COMMAND,
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
    if not capture_inputs_ready:
        missing_inputs.append(
            {
                "id": "capture_input_preflight",
                "status": "OPERATOR_INPUT_REQUIRED",
                "required_command": CAPTURE_PREFLIGHT_COMMAND,
                "reason": "operator capture inputs have not passed read-only preflight",
            }
        )
    if not evidence_ready:
        missing_inputs.append(
            {
                "id": "retained_settlement_receipt",
                "status": "OPERATOR_INPUT_REQUIRED",
                "required_artifact": DEFAULT_EVIDENCE_PATH,
                "reason": "retained settlement receipt is missing or invalid",
            }
        )
    if not live_rpc_ready:
        missing_inputs.append(
            {
                "id": "live_rpc_receipt_verification",
                "status": "OPERATOR_INPUT_REQUIRED",
                "required_command": VERIFY_LIVE_RPC_COMMAND,
                "reason": "retained receipt has not passed live Base RPC verification",
            }
        )
    if not production_import_ready:
        missing_inputs.append(
            {
                "id": "production_evidence_import",
                "status": "OPERATOR_INPUT_REQUIRED",
                "required_command": PRODUCTION_INPUT_PIPELINE_COMMAND,
                "reason": "production evidence import is not complete",
            }
        )
    if not completion_external_ready:
        missing_inputs.append(
            {
                "id": "completion_gate_external_settlement",
                "status": "OPERATOR_INPUT_REQUIRED",
                "required_command": COMPLETION_GATE_COMMAND,
                "reason": "completion gate still reports external settlement as not ready",
            }
        )

    ready = (
        not source_errors
        and capture_inputs_ready
        and evidence_ready
        and live_rpc_ready
        and production_import_ready
        and completion_external_ready
        and blocker_ready
        and operator_command_surface_ready
        and operator_command_shell_surface_ready
    )
    missing_input_status_counts = _status_counts(missing_inputs)
    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-operator-handoff-v6-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY" if ready else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
        "decision": "READY_FOR_COMPLETION_RERUN" if ready else "BLOCKED_ON_OPERATOR_EVIDENCE",
        "ready_for_completion_rerun": ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only external X0T settlement operator handoff. It binds the "
            "current capture-preflight, retained-evidence, live-RPC, production-import, and "
            "completion-gate reports to explicit operator actions. It does not create evidence, "
            "contact RPC providers, submit transactions, mutate chain/runtime state, or close /goal."
        ),
        "mutates_files": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_artifacts": list(source_paths.values()),
        "source_reports": source_reports,
        "source_errors": source_errors,
        "operator_command_checks": operator_command_checks,
        "missing_inputs": missing_inputs,
        "operator_next_actions": operator_next_actions,
        "not_verified_yet": []
        if ready
        else [
            "operator capture inputs that pass the read-only preflight",
            "submitted external X0T settlement receipt with matching live RPC report",
            "production evidence import and completion gate agree that external settlement is ready",
        ],
        "summary": {
            "evidence_path": DEFAULT_EVIDENCE_PATH,
            "capture_preflight_available": capture_preflight is not None,
            "capture_preflight_decision": (capture_preflight or {}).get("decision", ""),
            "capture_inputs_ready": capture_inputs_ready,
            "capture_preflight_errors_total": preflight_summary.get("errors_total", 0),
            "evidence_exists": evidence_exists,
            "evidence_file_ready": evidence_ready,
            "live_rpc_ready": live_rpc_ready,
            "production_import_external_settlement_ready": production_import_ready,
            "completion_gate_external_settlement_ready": completion_external_ready,
            "current_blocker_ready": blocker_ready,
            "source_errors_total": len(source_errors),
            "missing_inputs_total": len(missing_inputs),
            "missing_input_status_counts": missing_input_status_counts,
            "missing_inputs_operator_input_required": missing_input_status_counts.get(
                "OPERATOR_INPUT_REQUIRED",
                0,
            ),
            "missing_inputs_generic_operator_required": missing_input_status_counts.get(
                "OPERATOR_REQUIRED",
                0,
            ),
            "operator_actions_total": len(operator_next_actions),
            "operator_commands_total": len(operator_command_checks),
            "operator_command_entrypoints_missing": len(missing_operator_entrypoints),
            "operator_command_surface_ready": operator_command_surface_ready,
            "operator_commands_with_shell_redirection_placeholders": len(operator_shell_placeholders),
            "operator_command_shell_surface_ready": operator_command_shell_surface_ready,
            "operator_sequence_ready": operator_command_surface_ready and operator_command_shell_surface_ready,
            "safety_flags_ready": True,
            "source_alignment_ready": not source_errors,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "External X0T Settlement Operator Handoff",
            f"handoff_decision: {report.get('handoff_decision')}",
            f"ready_for_completion_rerun: {report.get('ready_for_completion_rerun')}",
            f"evidence_file_ready: {summary.get('evidence_file_ready')}",
            f"live_rpc_ready: {summary.get('live_rpc_ready')}",
            f"missing_inputs_total: {summary.get('missing_inputs_total')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build external X0T settlement operator handoff report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
    output_input = Path(args.output_json)
    write_json(output_input if output_input.is_absolute() else root / output_input, report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready_for_completion_rerun"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
