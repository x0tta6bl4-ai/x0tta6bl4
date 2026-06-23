#!/usr/bin/env python3
"""Build non-bounty income map and first machine artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.non_bounty_income import SCHEMA, build_non_bounty_income_map


DEFAULT_JSON = Path("docs/commercial/non_bounty_income_map.json")
DEFAULT_MD = Path("docs/commercial/NON_BOUNTY_INCOME_MAP.md")
DEFAULT_ARTIFACT_DIR = Path(".tmp/non-bounty")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4 Non-Bounty Income Map",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "## Status",
        "",
        f"- Schema: {payload['schema']}",
        f"- Status: {payload['status']}",
        f"- Funds received claim allowed: {payload['claim_gate']['funds_received_claim_allowed']}",
        "",
        "## Thinking",
        "",
    ]
    thinking = payload["thinking_contract"]
    for key in ("first_principles", "reverse_planning", "scamper", "mapek"):
        lines.append(f"- {key}: {thinking[key]}")
    lines.extend(["", "## Ranked Routes", ""])
    for item in payload["ranked"]:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Decision: {item['decision']}",
                f"- Score: {item['score']}",
                f"- Channel: {item['channel']}",
                f"- Revenue model: {item['revenue_model']}",
                f"- First artifact: {item['first_artifact']}",
                f"- Next machine step: {item['next_machine_step']}",
                f"- Gates: {', '.join(item['gates'])}",
                f"- Risks: {', '.join(item['risks'])}",
                f"- Sources: {', '.join(item['source_urls'])}",
                "",
            ]
        )
    lines.extend(["## Claim Boundary", "", payload["claim_boundary"], ""])
    return "\n".join(lines)


def _first_artifact_payload(item: dict[str, Any]) -> dict[str, Any]:
    oid = item["opportunity_id"]
    base = {
        "schema": f"x0tta6bl4.non_bounty.{oid}.v1",
        "opportunity_id": oid,
        "title": item["title"],
        "created_at_utc": _utc_now(),
        "claim_gate": {
            "ready_for_external_submission": False,
            "funds_received_claim_allowed": False,
            "requires_human_account_or_payout_gate": True,
        },
    }
    if oid == "agentpact_offer_pack":
        base["offer"] = {
            "title": "Structured data extraction and repo triage agent",
            "category": "data",
            "tags": ["data-extraction", "github", "triage", "json", "reports"],
            "basePrice": 5,
            "slaDays": 1,
            "descriptionMd": (
                "I turn public pages, GitHub issues, and small repositories into structured JSON, "
                "risk summaries, and short action reports. I reject tasks that require secrets, "
                "private prompts, CAPTCHA bypass, spam, or account manipulation."
            ),
        }
    elif oid == "sporeagent_task_runner":
        base["worker_profile"] = {
            "skills": ["web-scraping", "pytest", "fastapi", "translation-review", "structured-json"],
            "min_task_usd": 20,
            "reject_rules": [
                "No private secrets",
                "No prompt exfiltration",
                "No fake engagement",
                "No CAPTCHA bypass",
            ],
        }
    elif oid == "apify_actor_factory":
        base["actor_backlog"] = [
            {
                "actor_name": "github-paid-task-clean-target-scanner",
                "input": {"query": "GitHub bounty search query", "maxResults": 200},
                "output": {"cleanTargets": [], "rejectReasons": []},
                "paid_event": "clean_target_found",
            },
            {
                "actor_name": "public-page-to-json-extractor",
                "input": {"url": "public page", "schemaHint": "optional"},
                "output": {"records": [], "warnings": []},
                "paid_event": "records_extracted",
            },
        ]
    elif oid == "x402_paid_micro_api":
        base["service_catalog"] = [
            {
                "route": "/v1/github/bounty-filter",
                "price_usdc": "0.02",
                "result": "Ranked task list with prompt-leak, claim, and competition filters.",
            },
            {
                "route": "/v1/page/extract-json",
                "price_usdc": "0.01",
                "result": "Structured JSON from a public page.",
            },
        ]
    else:
        base["draft"] = {"next_machine_step": item["next_machine_step"]}
    return base


def _write_first_artifacts(income_map: dict[str, Any], artifact_dir: Path) -> list[str]:
    written: list[str] = []
    for item in income_map["selected_first"]:
        payload = _first_artifact_payload(item)
        path = artifact_dir / f"{item['opportunity_id']}.json"
        _write_json(path, payload)
        written.append(str(path))
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--write-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    income_map = build_non_bounty_income_map(args.root)
    payload = {
        **income_map,
        "schema": SCHEMA,
        "generated_at_utc": _utc_now(),
        "root": str(args.root.resolve()),
    }
    _write_json(args.write_json, payload)
    args.write_md.parent.mkdir(parents=True, exist_ok=True)
    args.write_md.write_text(_render_markdown(payload), encoding="utf-8")
    artifacts = _write_first_artifacts(payload, args.artifact_dir)
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": payload["status"],
                "selected_first": [item["opportunity_id"] for item in payload["selected_first"]],
                "written": {
                    "json": str(args.write_json),
                    "markdown": str(args.write_md),
                    "artifacts": artifacts,
                },
                "funds_received_claim_allowed": payload["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
