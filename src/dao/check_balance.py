"""
CLI tool to check X0T balance and earnings.
"""

import argparse
import json
import logging
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

logging.basicConfig(level=logging.ERROR)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATS_FILE = PROJECT_ROOT / "node_stats.json"
STATS_FILE_ENV = "X0T_VPN_STATS_FILE"
X0T_USD_PRICE_ENV = "X0T_USD_PRICE"


def _decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def load_balance_snapshot(stats_file: Path) -> dict:
    """Load balance and earnings from the bridge runtime stats file."""
    if not stats_file.exists():
        raise FileNotFoundError(f"balance stats file not found: {stats_file}")

    try:
        with stats_file.open(encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"balance stats file is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("balance stats file must contain a JSON object")

    return {
        "node_id": str(payload.get("node_id", "unknown")),
        "balance": _decimal(payload.get("balance", "0"), "balance"),
        "earnings_today": _decimal(
            payload.get("earnings_today", "0"), "earnings_today"
        ),
        "packets": int(payload.get("packets", 0) or 0),
        "bytes": int(payload.get("bytes", 0) or 0),
        "uptime_seconds": _decimal(payload.get("uptime", "0"), "uptime"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check X0T balance")
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed earnings"
    )
    parser.add_argument(
        "--stats-file",
        type=Path,
        default=Path(os.environ.get(STATS_FILE_ENV, DEFAULT_STATS_FILE)),
        help=f"node stats JSON path; can also be set with {STATS_FILE_ENV}",
    )
    args = parser.parse_args(argv)

    try:
        snapshot = load_balance_snapshot(args.stats_file)
        x0t_usd_price = _decimal(
            os.environ.get(X0T_USD_PRICE_ENV, "0.1"), X0T_USD_PRICE_ENV
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return 2

    balance = snapshot["balance"]
    earnings_today = snapshot["earnings_today"]
    packets = snapshot["packets"]
    bytes_relayed = snapshot["bytes"]
    uptime_seconds = snapshot["uptime_seconds"]

    if args.detailed:
        print(f"🧩 Node: {snapshot['node_id']}")
        print(f"💰 Баланс: {balance:,.4f} X0T")
        print(f"📊 Пакетов: {packets}")
        print(f"📦 Байт: {bytes_relayed}")
        print(f"⏱️ Uptime: {uptime_seconds:,.0f}s")
        print(f"💵 Заработок сегодня: {earnings_today:,.4f} X0T")
        print(
            f"💵 Месячная проекция: {earnings_today * 30:,.2f} X0T (${earnings_today * 30 * x0t_usd_price:,.2f} @ ${x0t_usd_price})"
        )
    else:
        print(f"   Баланс: {balance:,.1f} X0T")

    return 0


if __name__ == "__main__":
    sys.exit(main())
