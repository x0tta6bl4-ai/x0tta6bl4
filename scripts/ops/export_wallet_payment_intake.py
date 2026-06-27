#!/usr/bin/env python3
"""Export the wallet payment intake package for the first x0tta6bl4 paid pilot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sales.wallet_payment_intake import build_wallet_payment_intake


SCHEMA = "x0tta6bl4.wallet_payment_intake.export.v1"
DEFAULT_OUTPUT_MD = "docs/commercial/PAYMENT_INTAKE.md"
DEFAULT_OUTPUT_JSON = "docs/commercial/payment_intake.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_export(root: Path | str = ".", *, generated_at_utc: str | None = None) -> dict[str, Any]:
    root_path = Path(root)
    intake = build_wallet_payment_intake(root_path)
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "root": str(root_path.resolve()),
        "payment_intake": intake,
        "claim_boundary": intake["claim_gate"]["claim_boundary"],
    }


def render_markdown(export: dict[str, Any]) -> str:
    intake = export["payment_intake"]
    wallet = intake["wallet"]
    claim_gate = intake["claim_gate"]
    lines = [
        "# x0tta6bl4 Payment Intake",
        "",
        f"Generated: {export['generated_at_utc']}",
        "",
        "## Payment Target",
        "",
        f"- Offer: {intake['offer_name']}",
        f"- Status: {intake['status']}",
        f"- Wallet: {wallet['address']}",
        f"- Wallet kind: {wallet['address_kind']}",
        f"- Payment reference: {intake['payment_reference']}",
        f"- Wallet URI: {wallet['wallet_uri']}",
        f"- Network policy: {wallet['network_policy']}",
        "",
        "## Pricing Ladder",
        "",
    ]
    for item in intake["pricing_ladder"]:
        lines.append(
            f"- {item['label']}: USD {item['amount_usd']} - {item['purpose']}"
        )
    lines.extend(
        [
            "",
            "## Buyer Steps",
            "",
            *[f"- {step}" for step in intake["buyer_steps"]],
            "",
            "## Operator Steps",
            "",
            *[f"- {step}" for step in intake["operator_steps"]],
            "",
            "## Claim Boundary",
            "",
            claim_gate["claim_boundary"],
            "",
            f"- Payment intake claim allowed: {claim_gate['payment_intake_claim_allowed']}",
            f"- Funds received claim allowed: {claim_gate['funds_received_claim_allowed']}",
            f"- Settlement finality claim allowed: {claim_gate['settlement_finality_claim_allowed']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_export(
    export: dict[str, Any],
    *,
    markdown_path: Path | None,
    json_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(export), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write-md", type=Path, default=Path(DEFAULT_OUTPUT_MD))
    parser.add_argument("--write-json", type=Path, default=Path(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--no-md", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export = build_export(args.root)
    written = write_export(
        export,
        markdown_path=None if args.no_md else args.write_md,
        json_path=None if args.no_json else args.write_json,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "written": written,
                "status": export["payment_intake"]["status"],
                "wallet": export["payment_intake"]["wallet"]["masked"],
                "funds_received_claim_allowed": export["payment_intake"]["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
