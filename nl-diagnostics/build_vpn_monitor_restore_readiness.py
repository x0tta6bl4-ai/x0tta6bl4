#!/usr/bin/env python3
"""Build a local readiness packet for restoring the NL VPN monitor canary.

The report reads local files only. It does not SSH to NL and does not mutate
local or remote VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_DECISION = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_GOAL_STATUS = DIAGNOSTICS_DIR / "vpn-production-candidate-goal-2026-06-02.json"
DEFAULT_SCRIPT = ROOT / "scripts" / "ops" / "restore_nl_vpn_monitor_canary_timer.sh"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-monitor-restore-readiness-2026-06-06.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-monitor-restore-readiness-2026-06-06.md"

APPROVAL_PHRASE = "APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER"
PASS = "pass"
BLOCKED_APPROVAL = "blocked_future_approval"
MISSING = "missing"
FORBIDDEN_WRITE_PATTERNS = (
    r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
    r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
    r"\bufw\s+",
    r"\biptables\s+",
    r"\bnft\s+",
    r"\bx-ui\s+restart\b",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def flag_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def make_gate(gate_id: str, title: str, status: str, evidence: list[str], next_step: str) -> dict[str, Any]:
    return {
        "id": gate_id,
        "title": title,
        "status": status,
        "ok": status in {PASS, BLOCKED_APPROVAL},
        "evidence": evidence,
        "next_step": next_step,
    }


def decision_gate(decision: dict[str, Any]) -> dict[str, Any]:
    decision_data = decision.get("decision") if isinstance(decision.get("decision"), dict) else {}
    classification = decision.get("classification") if isinstance(decision.get("classification"), dict) else {}
    blocking = classification.get("blocking_assessment") if isinstance(classification.get("blocking_assessment"), dict) else {}
    safe_flags = all(
        [
            flag_false(decision, "mutation_allowed"),
            flag_false(decision, "nl_mutation_allowed"),
            flag_false(decision, "auto_profile_switch_allowed"),
            flag_false(decision, "spb_fallback_allowed"),
            flag_false(decision_data, "mutation_allowed"),
            flag_false(decision_data, "nl_mutation_allowed"),
            flag_false(decision_data, "auto_profile_switch_allowed"),
            flag_false(decision_data, "spb_fallback_allowed"),
        ]
    )
    ready = (
        decision_data.get("decision") == "restore_transport_canary_monitor"
        and classification.get("failure_domain") == "monitoring"
        and classification.get("recommended_action") == "restore_transport_canary_monitor"
        and blocking.get("category") == "monitoring_gap"
        and safe_flags
    )
    return make_gate(
        "DECISION-01",
        "Current decision points to canary monitor restore, not provider outage",
        PASS if ready else MISSING,
        [
            f"decision={decision_data.get('decision') or 'missing'}",
            f"failure_domain={classification.get('failure_domain') or 'missing'}",
            f"recommended_action={classification.get('recommended_action') or 'missing'}",
            f"blocking_category={blocking.get('category') or 'missing'}",
            f"safe_flags={str(safe_flags).lower()}",
        ],
        "refresh current-vpn-decision from the latest read-only snapshot",
    )


def goal_gate(goal_status: dict[str, Any]) -> dict[str, Any]:
    core = next(
        (
            row
            for row in goal_status.get("requirements") or []
            if isinstance(row, dict) and row.get("id") == "CORE-REALITY-01"
        ),
        {},
    )
    next_step = str(core.get("next_step") or "")
    ready = (
        goal_status.get("decision") == "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE"
        and core.get("status") == "missing"
        and "restore_nl_vpn_monitor_canary_timer.sh" in next_step
        and APPROVAL_PHRASE in next_step
        and goal_status.get("no_nl_or_spb_writes_performed") is True
    )
    return make_gate(
        "GOAL-01",
        "Goal status carries the exact monitor-restore next step",
        PASS if ready else MISSING,
        [
            f"goal_decision={goal_status.get('decision') or 'missing'}",
            f"core_status={core.get('status') or 'missing'}",
            f"approval_phrase_in_next_step={str(APPROVAL_PHRASE in next_step).lower()}",
            f"no_writes={str(goal_status.get('no_nl_or_spb_writes_performed') is True).lower()}",
        ],
        "rebuild vpn-production-candidate-goal after updating current decision",
    )


def script_gate(script_text: str, script_path: Path) -> dict[str, Any]:
    forbidden_hits = [
        pattern
        for pattern in FORBIDDEN_WRITE_PATTERNS
        if re.search(pattern, script_text, re.IGNORECASE)
    ]
    required_markers = {
        "default_dry_run": 'MODE="dry-run"' in script_text,
        "approval_phrase": APPROVAL_PHRASE in script_text,
        "confirm_env": "RESTORE_NL_VPN_MONITOR_CONFIRM" in script_text,
        "apply_requires_confirm": "CONFIRM_VALUE" in script_text and "!= \"$REQUIRED_CONFIRM\"" in script_text,
        "timer_enable": "systemctl enable --now ghost-access-vpn-monitor.timer" in script_text,
        "monitor_start": "systemctl start ghost-access-vpn-monitor.service" in script_text,
        "runtime_refresh": "systemctl start x0tta6bl4-runtime-state.service" in script_text,
        "rollback_hint": "disable --now ghost-access-vpn-monitor.timer" in script_text,
    }
    ready = bool(script_text) and all(required_markers.values()) and not forbidden_hits
    return make_gate(
        "SCRIPT-01",
        "Monitor restore script is approval-gated and narrowly scoped",
        PASS if ready else MISSING,
        [
            f"script_path={script_path}",
            *[f"{key}={str(value).lower()}" for key, value in required_markers.items()],
            f"forbidden_hits={','.join(forbidden_hits) if forbidden_hits else 'none'}",
        ],
        "fix restore script gating before any operator approval is accepted",
    )


def approval_gate() -> dict[str, Any]:
    return make_gate(
        "APPROVAL-01",
        "NL monitor restore remains blocked until explicit approval",
        BLOCKED_APPROVAL,
        [
            f"required_phrase={APPROVAL_PHRASE}",
            "apply_allowed_now=false",
            "nl_write_performed=false",
        ],
        "run the apply command only after the exact phrase is present",
    )


def build_payload(
    *,
    decision: dict[str, Any],
    goal_status: dict[str, Any],
    script_text: str,
    script_path: Path = DEFAULT_SCRIPT,
) -> dict[str, Any]:
    gates = [
        decision_gate(decision),
        goal_gate(goal_status),
        script_gate(script_text, script_path),
        approval_gate(),
    ]
    technical_ready = all(row["status"] == PASS for row in gates if row["id"] != "APPROVAL-01")
    approval_blocked = gates[-1]["status"] == BLOCKED_APPROVAL
    ready_for_approval = technical_ready and approval_blocked
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_vpn_monitor_restore_readiness.py",
        "generated_at": utc_now(),
        "decision": (
            "MONITOR_RESTORE_READY_FOR_APPROVAL"
            if ready_for_approval
            else "MONITOR_RESTORE_NOT_READY"
        ),
        "ready_for_approval": ready_for_approval,
        "apply_allowed_now": False,
        "approval_required": True,
        "approval_phrase": APPROVAL_PHRASE,
        "local_precheck_command": "bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --dry-run --precheck --host nl",
        "apply_command": (
            "RESTORE_NL_VPN_MONITOR_CONFIRM=APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER "
            "bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --apply --host nl"
        ),
        "rollback_command": "ssh nl 'sudo systemctl disable --now ghost-access-vpn-monitor.timer'",
        "gates": gates,
        "no_nl_or_spb_writes_performed": True,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# VPN Monitor Restore Readiness",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"decision: `{payload['decision']}`",
        f"ready_for_approval: `{str(payload['ready_for_approval']).lower()}`",
        f"apply_allowed_now: `{str(payload['apply_allowed_now']).lower()}`",
        "",
        "## Commands",
        "",
        "```text",
        f"precheck: {payload['local_precheck_command']}",
        f"apply: {payload['apply_command']}",
        f"rollback: {payload['rollback_command']}",
        "```",
        "",
        "## Gates",
        "",
        "| ID | Status | OK | Next Step |",
        "|---|---:|---:|---|",
    ]
    for gate in payload["gates"]:
        lines.append(
            f"| `{gate['id']}` | `{gate['status']}` | `{str(gate['ok']).lower()}` | {gate['next_step']} |"
        )

    lines.extend(["", "No NL or SPB writes were performed by this readiness report.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build VPN monitor restore readiness packet")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--goal-status", default=str(DEFAULT_GOAL_STATUS))
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    script_path = Path(args.script)
    payload = build_payload(
        decision=read_json(Path(args.decision)),
        goal_status=read_json(Path(args.goal_status)),
        script_text=read_text(script_path),
        script_path=script_path,
    )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ready_for_approval"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
