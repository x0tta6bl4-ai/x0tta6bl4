#!/usr/bin/env python3
"""Agent Work Receipt Gate.

Validates an AI-agent "done" receipt against the repo's existing handoff
contract plus a product-specific postcondition policy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "scripts" / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from integrity_ledger import derive_failure_signature, validate_handoff_payload  # noqa: E402


DEFAULT_ALLOWED_CHECKLIST_STATUS = {"covered", "not_covered", "blocked"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not is_nonempty_string(policy.get("product_name")):
        errors.append("policy.product_name must be a non-empty string")
    for field in ("required_source_truth", "required_commands", "required_checklist", "forbidden_claim_patterns"):
        if field in policy and not isinstance(policy[field], list):
            errors.append(f"policy.{field} must be a list")
    return errors


def command_matches(required: str, observed: str) -> bool:
    return required == observed or required in observed


def claim_text(receipt: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("result", "summary"):
        value = receipt.get(field)
        if isinstance(value, str):
            parts.append(value)
    parts.extend(as_string_list(receipt.get("claims")))
    return "\n".join(parts)


def checklist_by_requirement(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = receipt.get("checklist")
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        req = row.get("requirement")
        if is_nonempty_string(req):
            indexed[str(req).strip()] = row
    return indexed


def product_failure_signature(errors: list[str], base_signature: str) -> str:
    if base_signature:
        return base_signature
    if not errors:
        return ""
    first = errors[0]
    if "required command not covered" in first:
        return "receipt.invalid.missing_required_command"
    if "required checklist item not covered" in first:
        return "receipt.invalid.missing_required_checklist"
    if "forbidden claim pattern" in first:
        return "receipt.invalid.forbidden_claim"
    if "source_of_truth" in first:
        return "receipt.invalid.missing_source_of_truth"
    return "receipt.invalid.postcondition"


def validate_receipt(policy: dict[str, Any], receipt: dict[str, Any], agent: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    policy_errors = validate_policy(policy)
    if policy_errors:
        errors.extend(policy_errors)

    base_errors, base_warnings = validate_handoff_payload(agent, receipt)
    errors.extend(base_errors)
    warnings.extend(base_warnings)
    base_signature = derive_failure_signature(base_errors) if base_errors else ""

    if not is_nonempty_string(receipt.get("task")):
        errors.append("receipt.task must describe the requested work")
    if not any(is_nonempty_string(receipt.get(field)) for field in ("result", "summary")):
        errors.append("receipt.result or receipt.summary must describe the outcome")

    tool_audit = receipt.get("tool_audit") if isinstance(receipt.get("tool_audit"), dict) else {}
    source_of_truth = str(tool_audit.get("source_of_truth") or "")
    for required in as_string_list(policy.get("required_source_truth")):
        if required not in source_of_truth:
            errors.append(f"required source_of_truth not covered: {required}")

    if normalize_bool(policy.get("require_memory_considered"), True) and tool_audit.get("memory_considered") is not True:
        errors.append("tool_audit.memory_considered must be true")
    if normalize_bool(policy.get("require_manual_path_reason"), True) and tool_audit.get("manual_path_used"):
        if not is_nonempty_string(tool_audit.get("manual_path_reason")):
            errors.append("tool_audit.manual_path_reason must be set when manual_path_used=true")

    verification = receipt.get("verification") if isinstance(receipt.get("verification"), list) else []
    observed_commands = [
        str(entry.get("command") or "")
        for entry in verification
        if isinstance(entry, dict)
    ]
    for required in as_string_list(policy.get("required_commands")):
        if not any(command_matches(required, observed) for observed in observed_commands):
            errors.append(f"required command not covered: {required}")

    if normalize_bool(policy.get("require_all_verifications_passed"), True):
        failed_commands = [
            str(entry.get("command") or "<unknown>")
            for entry in verification
            if isinstance(entry, dict) and entry.get("exit_code") != 0
        ]
        for command in failed_commands:
            errors.append(f"verification command failed: {command}")

    checklist = checklist_by_requirement(receipt)
    if not isinstance(receipt.get("checklist"), list):
        errors.append("receipt.checklist must be a list")
    for required in as_string_list(policy.get("required_checklist")):
        row = checklist.get(required)
        if not row or row.get("status") != "covered":
            errors.append(f"required checklist item not covered: {required}")

    allowed_status = set(as_string_list(policy.get("allowed_checklist_status"))) or DEFAULT_ALLOWED_CHECKLIST_STATUS
    for requirement, row in checklist.items():
        status = row.get("status")
        if status not in allowed_status:
            errors.append(f"checklist item {requirement!r} has unsupported status: {status!r}")
        if status == "covered" and not is_nonempty_string(row.get("evidence")):
            errors.append(f"covered checklist item lacks evidence: {requirement}")

    if normalize_bool(policy.get("require_remaining_gaps"), True) and not isinstance(receipt.get("remaining_gaps"), list):
        errors.append("receipt.remaining_gaps must be a list, even when empty")

    text = claim_text(receipt)
    for pattern in as_string_list(policy.get("forbidden_claim_patterns")):
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"forbidden claim pattern present: {pattern}")

    score = max(0, 100 - len(errors) * 20 - len(warnings) * 5)
    failure_signature = product_failure_signature(errors, base_signature)
    return {
        "ok": not errors,
        "agent": agent,
        "product": policy.get("product_name", "Agent Work Receipt Gate"),
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "failure_signature": failure_signature,
        "verified_commands": observed_commands,
        "required_commands": as_string_list(policy.get("required_commands")),
        "remaining_gaps": receipt.get("remaining_gaps", []),
    }


def render_report(result: dict[str, Any], receipt: dict[str, Any]) -> str:
    status = "PASS" if result["ok"] else "FAIL"
    lines = [
        f"# Agent Work Receipt Gate Report",
        "",
        f"- Status: {status}",
        f"- Product: {result['product']}",
        f"- Agent: {result['agent']}",
        f"- Score: {result['score']}",
        f"- Task: {receipt.get('task', '')}",
        f"- Result: {receipt.get('result') or receipt.get('summary') or ''}",
        "",
        "## Errors",
    ]
    if result["errors"]:
        lines.extend(f"- {item}" for item in result["errors"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if result["warnings"]:
        lines.extend(f"- {item}" for item in result["warnings"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Verified Commands")
    if result["verified_commands"]:
        lines.extend(f"- `{item}`" for item in result["verified_commands"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Remaining Gaps")
    gaps = result.get("remaining_gaps")
    if isinstance(gaps, list) and gaps:
        lines.extend(f"- {item}" for item in gaps)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        policy = load_json(Path(args.policy))
        receipt = load_json(Path(args.receipt))
    except ValueError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=True))
        return 2
    agent = args.agent or str(receipt.get("agent") or "agent")
    result = validate_receipt(policy, receipt, agent)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(render_report(result, receipt), end="")
    return 0 if result["ok"] else 2


def cmd_report(args: argparse.Namespace) -> int:
    try:
        policy = load_json(Path(args.policy))
        receipt = load_json(Path(args.receipt))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    agent = args.agent or str(receipt.get("agent") or "agent")
    result = validate_receipt(policy, receipt, agent)
    print(render_report(result, receipt), end="")
    return 0 if result["ok"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AI-agent work receipts")
    sub = parser.add_subparsers(dest="cmd", required=True)

    validate = sub.add_parser("validate", help="Validate a receipt and emit JSON or markdown")
    validate.add_argument("--policy", required=True)
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--agent", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)

    report = sub.add_parser("report", help="Render a markdown report")
    report.add_argument("--policy", required=True)
    report.add_argument("--receipt", required=True)
    report.add_argument("--agent", default="")
    report.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
