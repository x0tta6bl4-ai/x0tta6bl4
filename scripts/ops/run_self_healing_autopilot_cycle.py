#!/usr/bin/env python3
"""
x0tta6bl4 24/7 Self-Healing Autopilot Cycle.
Runs continuous monitoring, health probes, and self-healing recovery triggers across nodes.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/mnt/projects").resolve()
sys.path.insert(0, str(ROOT))

from scripts.ops.vpn_health_check import check_local, check_ping, run_remote, NL_IP, MSK_IP

logger = logging.getLogger("self_healing_autopilot")

def run_single_cycle(dry_run: bool = False) -> dict:
    """Run one verification & healing cycle."""
    timestamp = datetime.now(timezone.utc).isoformat()
    status = {
        "timestamp_utc": timestamp,
        "nl_host": NL_IP,
        "msk_host": MSK_IP,
        "checks": {},
        "healing_actions": [],
        "overall_status": "HEALTHY"
    }

    # 1. Check Local PC
    local_health = check_local()
    status["checks"]["local"] = local_health

    # 2. Check NL Node (89.125.1.107)
    nl_ping = check_ping(NL_IP)
    status["checks"]["nl_ping"] = nl_ping

    if "Online" in nl_ping:
        rc, out = run_remote(NL_IP, "systemctl is-active x-ui spire-server ghost-access-bot")
        services_ok = (rc == 0 and "inactive" not in out and "failed" not in out)
        status["checks"]["nl_services"] = "OK" if services_ok else f"DEGRADED ({out})"
        
        if not services_ok and not dry_run:
            logger.warning("⚠️ NL services degraded, triggering safe recovery...")
            rec_code, rec_out = run_remote(NL_IP, "systemctl restart x-ui ghost-access-bot")
            status["healing_actions"].append({
                "target": "NL_IP",
                "action": "restart_degraded_services",
                "result_code": rec_code,
                "output": rec_out
            })
    else:
        status["overall_status"] = "UNREACHABLE_NL"
        logger.error(f"❌ NL Node ({NL_IP}) unreachable")

    # 3. Check MSK Node (84.54.47.103)
    msk_ping = check_ping(MSK_IP)
    status["checks"]["msk_ping"] = msk_ping

    if "Online" in msk_ping:
        rc, out = run_remote(MSK_IP, "systemctl is-active xray")
        status["checks"]["msk_xray"] = "OK" if (rc == 0 and "active" in out) else f"DEGRADED ({out})"
        if "active" not in out and not dry_run:
            logger.warning("⚠️ MSK xray degraded, restarting...")
            rec_code, rec_out = run_remote(MSK_IP, "systemctl restart xray")
            status["healing_actions"].append({
                "target": "MSK_IP",
                "action": "restart_xray",
                "result_code": rec_code,
                "output": rec_out
            })

    return status


def main():
    parser = argparse.ArgumentParser(description="Run Self-Healing Autopilot Cycle")
    parser.add_argument("--cycles", type=int, default=0, help="Number of cycles to run (0 = infinite)")
    parser.add_argument("--interval-seconds", type=int, default=120, help="Seconds between cycles")
    parser.add_argument("--output", type=str, default=".tmp/self_healing/autopilot_status_latest.json")
    parser.add_argument("--history-jsonl", type=str, default=".tmp/self_healing/autopilot_history.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute healing actions")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

    out_path = Path(args.output)
    hist_path = Path(args.history_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hist_path.parent.mkdir(parents=True, exist_ok=True)

    cycle_count = 0
    logger.info(f"🚀 Self-Healing Autopilot started (interval: {args.interval_seconds}s, dry_run: {args.dry_run})")

    while True:
        cycle_count += 1
        try:
            res = run_single_cycle(dry_run=args.dry_run)
            res["cycle_number"] = cycle_count

            out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
            with hist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")

            logger.info(f"✅ Cycle #{cycle_count} completed. Status: {res['overall_status']}")
        except Exception as exc:
            logger.error(f"💥 Cycle #{cycle_count} error: {exc}", exc_info=True)

        if args.cycles > 0 and cycle_count >= args.cycles:
            break

        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
