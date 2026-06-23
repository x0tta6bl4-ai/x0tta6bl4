#!/usr/bin/env python3
"""Generate a valid session_end payload JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tool_audit_helper import build_tool_audit


def parse_verification_entry(raw: str) -> dict[str, Any]:
    parts = raw.split("::")
    if len(parts) < 2:
        raise ValueError("verification entry must be command::exit_code[::status]")
    command = parts[0].strip()
    exit_code = int(parts[1].strip())
    status = parts[2].strip() if len(parts) > 2 and parts[2].strip() else ("passed" if exit_code == 0 else "failed")
    return {"command": command, "exit_code": exit_code, "status": status}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a valid session_end payload")
    parser.add_argument("--result", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--verified-here", type=int, default=0)
    parser.add_argument("--file-changed", action="append", default=[])
    parser.add_argument("--verification-entry", action="append", default=[])
    parser.add_argument("--verification-note", default="")
    parser.add_argument("--tool-audit-json", default="")
    parser.add_argument("--source-of-truth", default="")
    parser.add_argument("--memory-considered", action="store_true")
    parser.add_argument("--memory-used", action="append", default=[])
    parser.add_argument("--memory-skipped-reason", default="")
    parser.add_argument("--mcp-considered", action="store_true")
    parser.add_argument("--mcp-used", action="store_true")
    parser.add_argument("--skills-considered", action="store_true")
    parser.add_argument("--skills-used", action="append", default=[])
    parser.add_argument("--skills-skipped-reason", default="")
    parser.add_argument("--subagents-considered", action="store_true")
    parser.add_argument("--subagents-used", action="append", default=[])
    parser.add_argument("--subagents-skipped-reason", default="")
    parser.add_argument("--manual-path-used", action="store_true")
    parser.add_argument("--manual-path-reason", default="")
    parser.add_argument("--next-for-claude", default="")
    parser.add_argument("--next-for-gemini", default="")
    parser.add_argument("--next-for-codex", default="")
    parser.add_argument("--output-file", default="")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    args = parser.parse_args()

    if args.tool_audit_json:
        tool_audit = json.loads(args.tool_audit_json)
    else:
        if not args.source_of_truth:
            parser.error("either --tool-audit-json or --source-of-truth must be provided")
        tool_audit = build_tool_audit(args)
    verification = [parse_verification_entry(item) for item in args.verification_entry]
    passed = sum(1 for item in verification if item["exit_code"] == 0)
    failed = len(verification) - passed

    payload: dict[str, Any] = {
        "verified_here": args.verified_here,
        "files_changed": args.file_changed,
        "verification_summary": {"total": len(verification), "passed": passed, "failed": failed},
        "verification": verification,
        "tool_audit": tool_audit,
    }
    if args.result:
        payload["result"] = args.result
    if args.summary:
        payload["summary"] = args.summary
    if args.verification_note:
        payload["verification_note"] = args.verification_note
    if args.next_for_claude:
        payload["next_for_claude"] = args.next_for_claude
    if args.next_for_gemini:
        payload["next_for_gemini"] = args.next_for_gemini
    if args.next_for_codex:
        payload["next_for_codex"] = args.next_for_codex

    raw = json.dumps(payload, ensure_ascii=True)
    if args.output_file:
        Path(args.output_file).write_text(raw, encoding="utf-8")
        print(args.output_file)
        return 0
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
