#!/usr/bin/env python3
"""Validate retained external X0T settlement evidence without RPC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.external_settlement import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_EVIDENCE_REPORT,
    validate_evidence_file,
    write_json,
)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate retained X0T settlement evidence JSON")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--output-json", default=DEFAULT_EVIDENCE_REPORT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    evidence_input = Path(args.evidence)
    evidence_path = evidence_input if evidence_input.is_absolute() else root / evidence_input
    report = validate_evidence_file(evidence_path, str(evidence_input)).report()
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["x0t_external_settlement_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["summary"]["x0t_external_settlement_ready"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
