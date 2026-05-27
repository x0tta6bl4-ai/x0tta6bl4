#!/usr/bin/env python3
"""Verify retained external X0T settlement evidence against read-only Base RPC."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.external_settlement import (  # noqa: E402
    DEFAULT_BLOCKER_REPORT,
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_EVIDENCE_REPORT,
    DEFAULT_RPC_REPORT,
    build_blocker_report,
    validate_evidence_file,
    verify_live_rpc,
    write_json,
)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _rpc_url(value: Optional[str]) -> Optional[str]:
    return (
        value
        or os.environ.get("X0T_BASE_RPC_URL")
        or os.environ.get("BASE_SEPOLIA_RPC_URL")
        or os.environ.get("BASE_MAINNET_RPC_URL")
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify retained X0T settlement evidence against live read-only RPC")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--rpc-url")
    parser.add_argument("--output-evidence-json", default=DEFAULT_EVIDENCE_REPORT)
    parser.add_argument("--output-rpc-json", default=DEFAULT_RPC_REPORT)
    parser.add_argument("--output-blocker-json", default=DEFAULT_BLOCKER_REPORT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    evidence_input = Path(args.evidence)
    evidence_path = evidence_input if evidence_input.is_absolute() else root / evidence_input
    evidence = validate_evidence_file(evidence_path, str(evidence_input))
    evidence_report = evidence.report()
    rpc_report = verify_live_rpc(evidence, _rpc_url(args.rpc_url))
    blocker_report = build_blocker_report(evidence_report, rpc_report)

    write_json(_resolve(root, args.output_evidence_json), evidence_report)
    write_json(_resolve(root, args.output_rpc_json), rpc_report)
    write_json(_resolve(root, args.output_blocker_json), blocker_report)
    print(json.dumps({
        "decision": blocker_report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": blocker_report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and blocker_report["summary"]["x0t_external_settlement_ready"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
