#!/usr/bin/env python3
"""Collect public paid-task listings into the local scoring format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.sales.paid_task_collectors import (
    SCHEMA,
    collect_github_algora_bounty_listings,
    collect_github_paid_task_listings,
)


DEFAULT_OUTPUT_JSON = ".tmp/paid-task-listings-current.json"


def _load_fixture(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--fixture-json must contain a JSON object")
    return payload


def write_collection(collection: dict[str, Any], *, json_path: Path | None) -> dict[str, str]:
    written: dict[str, str] = {}
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(collection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--per-query", type=int, default=50)
    parser.add_argument("--source-mode", choices=["algora", "broad"], default="algora")
    parser.add_argument("--write-json", type=Path, default=Path(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--fixture-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source_mode == "broad":
        collection = collect_github_paid_task_listings(
            max_results=args.max_results,
            per_query=args.per_query,
            fixture_payload=_load_fixture(args.fixture_json),
        )
    else:
        collection = collect_github_algora_bounty_listings(
            max_results=args.max_results,
            fixture_payload=_load_fixture(args.fixture_json),
        )
    written = write_collection(collection, json_path=None if args.no_json else args.write_json)
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": collection["status"],
                "source_id": collection["source_id"],
                "github_total_count": collection["github_total_count"],
                "tasks_total": collection["tasks_total"],
                "public_network_used": collection["public_network_used"],
                "written": written,
                "funds_received_claim_allowed": collection["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
