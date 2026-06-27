#!/usr/bin/env python3
"""Build one local snapshot of the x0tta6bl4 productization state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.ops.check_commercial_mesh_platform_readiness import build_report
from scripts.ops.build_paid_task_automation_plan import build_plan as build_paid_task_plan
from scripts.ops.export_product_idea_portfolio import build_export
from scripts.ops.export_wallet_payment_intake import build_export as build_payment_export
from src.sales.economic_layer_readiness import build_economic_layer_readiness


SCHEMA = "x0tta6bl4.productization.snapshot.v1"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/productization-snapshot-current.json"
DEFAULT_OUTPUT_MD = ".tmp/validation-shards/productization-snapshot-current.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_snapshot(root: Path | str = ".", *, generated_at_utc: str | None = None) -> dict[str, Any]:
    root_path = Path(root)
    export = build_export(root_path, generated_at_utc=generated_at_utc)
    payment_export = build_payment_export(root_path, generated_at_utc=generated_at_utc)
    paid_task_plan = build_paid_task_plan(root_path, generated_at_utc=generated_at_utc)
    economic_layer = build_economic_layer_readiness(root_path)
    readiness = build_report(root_path)
    portfolio = export["portfolio"]
    pilot = export["pilot_package"]
    payment_intake = payment_export["payment_intake"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "root": str(root_path.resolve()),
        "summary": {
            "ideas_total": portfolio["ideas_total"],
            "repo_scaffold_ready": portfolio["repo_scaffold_ready"],
            "repo_scaffold_blocked": portfolio["repo_scaffold_blocked"],
            "first_pilot_status": pilot["status"],
            "payment_intake_status": payment_intake["status"],
            "paid_task_pipeline_status": paid_task_plan["pipeline"]["status"],
            "paid_task_sources_total": len(paid_task_plan["pipeline"]["sources"]),
            "economic_layer_status": economic_layer["status"],
            "economic_layer_paths_total": economic_layer["summary"]["paths_total"],
            "economic_layer_live_revenue_ready": economic_layer["summary"]["live_revenue_ready"],
            "x0t_chain_submission_code_path_present": economic_layer["summary"][
                "x0t_chain_submission_code_path_present"
            ],
            "payment_wallet": payment_intake["wallet"]["address"],
            "commercial_readiness_decision": readiness["decision"],
            "commercial_readiness_ready": readiness["ready"],
            "funds_received_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "settlement_finality_claim_allowed": False,
        },
        "product_export": export,
        "payment_export": payment_export,
        "paid_task_plan": paid_task_plan,
        "economic_layer": economic_layer,
        "commercial_readiness": readiness,
        "claim_boundary": readiness["claim_boundary"],
    }


def render_markdown(snapshot: dict[str, Any]) -> str:
    summary = snapshot["summary"]
    export = snapshot["product_export"]
    payment = snapshot["payment_export"]["payment_intake"]
    pilot = export["pilot_package"]
    return "\n".join(
        [
            "# x0tta6bl4 Productization Snapshot",
            "",
            f"Generated: {snapshot['generated_at_utc']}",
            "",
            "## Summary",
            "",
            f"- Ideas total: {summary['ideas_total']}",
            f"- Repo scaffold ready: {summary['repo_scaffold_ready']}",
            f"- Repo scaffold blocked: {summary['repo_scaffold_blocked']}",
            f"- First pilot: {pilot['offer_name']}",
            f"- First pilot status: {summary['first_pilot_status']}",
            f"- Payment intake status: {summary['payment_intake_status']}",
            f"- Paid task pipeline status: {summary['paid_task_pipeline_status']}",
            f"- Paid task sources total: {summary['paid_task_sources_total']}",
            f"- Economic layer status: {summary['economic_layer_status']}",
            f"- Economic layer paths total: {summary['economic_layer_paths_total']}",
            f"- Economic layer live revenue ready: {summary['economic_layer_live_revenue_ready']}",
            f"- X0T chain submission code path present: {summary['x0t_chain_submission_code_path_present']}",
            f"- Payment wallet: {summary['payment_wallet']}",
            f"- Commercial readiness: {summary['commercial_readiness_decision']}",
            f"- Funds received claim allowed: {summary['funds_received_claim_allowed']}",
            f"- Production readiness claim allowed: {summary['production_readiness_claim_allowed']}",
            f"- Customer traffic claim allowed: {summary['customer_traffic_claim_allowed']}",
            f"- Payment reference: {payment['payment_reference']}",
            "",
            "## Claim Boundary",
            "",
            snapshot["claim_boundary"],
            "",
        ]
    )


def write_snapshot(
    snapshot: dict[str, Any],
    *,
    json_path: Path | None,
    markdown_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(snapshot), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write-json", type=Path, default=Path(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--write-md", type=Path, default=Path(DEFAULT_OUTPUT_MD))
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-md", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = build_snapshot(args.root)
    written = write_snapshot(
        snapshot,
        json_path=None if args.no_json else args.write_json,
        markdown_path=None if args.no_md else args.write_md,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "written": written,
                "summary": snapshot["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
