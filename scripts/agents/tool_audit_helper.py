#!/usr/bin/env python3
"""Emit a valid tool_audit object for session_end payloads."""

from __future__ import annotations

import argparse
import json


def build_tool_audit(args: argparse.Namespace) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_of_truth_checked": True,
        "source_of_truth": args.source_of_truth,
        "memory_considered": args.memory_considered,
        "memory_tools_used": args.memory_used,
        "mcp_considered": args.mcp_considered,
        "mcp_used": args.mcp_used,
        "skills_considered": args.skills_considered,
        "skills_used": args.skills_used,
        "subagents_considered": args.subagents_considered,
        "subagents_used": args.subagents_used,
        "manual_path_used": args.manual_path_used,
        "manual_path_reason": args.manual_path_reason,
    }
    if args.memory_skipped_reason:
        payload["memory_skipped_reason"] = args.memory_skipped_reason
    if args.skills_skipped_reason:
        payload["skills_skipped_reason"] = args.skills_skipped_reason
    if args.subagents_skipped_reason:
        payload["subagents_skipped_reason"] = args.subagents_skipped_reason
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a valid tool_audit object")
    parser.add_argument("--source-of-truth", required=True)
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
    parser.add_argument("--json", action="store_true", help="Emit JSON object (default)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = build_tool_audit(args)
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
