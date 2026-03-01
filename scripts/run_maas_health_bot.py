#!/usr/bin/env python3
"""Run MaaS local health bot from CLI (no external APIs)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.maas_health_bot import HealthBotConfig, MaasHealthBot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MaaS local health bot")
    parser.add_argument(
        "--auto-heal",
        action="store_true",
        help="Enable action planning/execution",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute configured heal commands (requires MAAS_AGENT_BOT_TOKEN when used via API)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=0.0,
        help="Loop interval. 0 means run once and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bot = MaasHealthBot(HealthBotConfig.from_env())
    dry_run = not args.execute
    if args.execute and not bot.config.enable_execute:
        print(
            json.dumps(
                {
                    "error": (
                        "execute mode is disabled by default; set "
                        "MAAS_HEALTH_BOT_ENABLE_EXECUTE=true to enable command execution"
                    )
                },
                ensure_ascii=True,
            )
        )
        return 2

    if args.interval_seconds <= 0:
        report = bot.run_once(auto_heal=args.auto_heal, dry_run=dry_run)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0

    while True:
        report = bot.run_once(auto_heal=args.auto_heal, dry_run=dry_run)
        print(json.dumps(report, ensure_ascii=True))
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
