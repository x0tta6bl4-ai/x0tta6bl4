#!/usr/bin/env python3
"""Capture retained X0T settlement evidence from read-only Base RPC."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.external_settlement import DEFAULT_EVIDENCE_PATH, main as external_settlement_main


def _rpc_url(value: Optional[str]) -> str:
    return (
        value
        or os.environ.get("X0T_BASE_RPC_URL")
        or os.environ.get("BASE_SEPOLIA_RPC_URL")
        or os.environ.get("BASE_MAINNET_RPC_URL")
        or ""
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Capture retained X0T settlement evidence from read-only RPC")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--transaction-hash", default="")
    parser.add_argument("--destination-chain", default="base-sepolia")
    parser.add_argument("--settlement-id", default="")
    parser.add_argument("--rpc-url")
    parser.add_argument("--collected-by", default="codex-external-settlement-rpc-collector")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--output-preflight-json", default=".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json")
    parser.add_argument("--output-evidence-json", default=".tmp/validation-shards/x0t-external-settlement-evidence-current.json")
    parser.add_argument("--output-rpc-json", default=".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json")
    parser.add_argument("--output-blocker-json", default=".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    forwarded = [
        "--root",
        args.root,
        "--evidence",
        args.evidence,
        "--transaction-hash",
        args.transaction_hash,
        "--destination-chain",
        args.destination_chain,
        "--settlement-id",
        args.settlement_id,
        "--rpc-url",
        _rpc_url(args.rpc_url),
        "--collected-by",
        args.collected_by,
        "--output-preflight-json",
        args.output_preflight_json,
        "--output-evidence-json",
        args.output_evidence_json,
        "--output-rpc-json",
        args.output_rpc_json,
        "--output-blocker-json",
        args.output_blocker_json,
    ]
    if args.preflight_only:
        forwarded.extend(["--preflight-capture-inputs", "--require-preflight-ready"])
    else:
        forwarded.append("--capture-from-rpc")
    if args.write_evidence:
        forwarded.append("--write-evidence")
    if args.require_ready:
        forwarded.append("--require-ready")
    return external_settlement_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
