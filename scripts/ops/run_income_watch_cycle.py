#!/usr/bin/env python3
"""Run one bounded income-watch cycle across activated non-bounty channels."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(".tmp/non-bounty/income_watch_cycle_latest.json")
DEFAULT_HISTORY = Path(".tmp/non-bounty/income_watch_cycle_history.jsonl")
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
SOFT_FAILURE_REASONS = {
    "x402_directory_watch": "directory_probe_timeout_while_public_x402_ready",
    "ontario_x402_readiness": "ontario_readiness_probe_failed_while_public_x402_ready",
}
EXTERNAL_TLS_SOFT_FAILURE_REASONS = {
    "bothire_work_loop": "external_marketplace_tls_eof_while_public_x402_ready",
    "opentask_status": "external_marketplace_tls_eof_while_public_x402_ready",
    "payanagent_job_watch": "external_marketplace_tls_eof_while_public_x402_ready",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _http_json(url: str, *, timeout_seconds: float = 20.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "x0tta6bl4-income-watch-cycle"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _wallet_probe(wallet: str) -> dict[str, Any]:
    base = "https://base.blockscout.com"
    address_url = f"{base}/api/v2/addresses/{wallet}"
    token_url = f"{base}/api/v2/addresses/{wallet}/token-balances"
    try:
        address = _http_json(address_url)
        tokens = _http_json(token_url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": exc.__class__.__name__,
            "address": wallet,
            "funds_received": False,
        }
    token_balances = tokens if isinstance(tokens, list) else []
    nonzero_tokens = []
    for item in token_balances:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or item.get("balance") or "0")
        if value not in {"0", "0.0", ""}:
            token = item.get("token") if isinstance(item.get("token"), dict) else {}
            nonzero_tokens.append(
                {
                    "symbol": token.get("symbol"),
                    "address": token.get("address"),
                    "value": value,
                }
            )
    native_balance = str(address.get("coin_balance") or "0") if isinstance(address, dict) else "0"
    funds_received = native_balance != "0" or bool(nonzero_tokens)
    return {
        "ok": True,
        "address": wallet,
        "native_coin_balance": native_balance,
        "token_balances_total": len(token_balances),
        "nonzero_tokens": nonzero_tokens,
        "funds_received": funds_received,
        "address_url": address_url,
        "token_balances_url": token_url,
    }


def _run_command(name: str, argv: list[str], *, timeout_seconds: float) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f".{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "ok": False,
            "timed_out": True,
            "returncode": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": (exc.stdout or "")[-2_000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2_000:] if isinstance(exc.stderr, str) else "",
            "argv": argv,
        }
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "timed_out": timed_out,
        "returncode": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_tail": completed.stdout[-2_000:],
        "stderr_tail": completed.stderr[-2_000:],
        "argv": argv,
    }


def _commands(agentjob_wait_seconds: int) -> list[tuple[str, list[str], float]]:
    py = sys.executable
    return [
        (
            "x402_public_ready",
            [py, "scripts/ops/ensure_x402_paid_api_public.py", "--quiet"],
            35,
        ),
        (
            "x402_directory_watch",
            [
                py,
                "scripts/ops/x402_directory_watch.py",
                "--wallet",
                TARGET_WALLET,
                "--status-file",
                ".tmp/non-bounty/x402_directory_watch_latest.json",
            ],
            75,
        ),
        (
            "ontario_x402_readiness",
            [py, "scripts/ops/ontario_x402_readiness.py"],
            100,
        ),
        (
            "jaypay_402directory_submit",
            [
                py,
                "scripts/ops/jaypay_402directory_submit.py",
                "--status-file",
                ".tmp/non-bounty/jaypay_402directory_submit_status.json",
            ],
            35,
        ),
        (
            "jaypay_402directory_submit_all",
            [
                py,
                "scripts/ops/jaypay_402directory_submit_all.py",
                "--status-file",
                ".tmp/non-bounty/jaypay_402directory_submit_all_status.json",
            ],
            55,
        ),
        (
            "agentjob_paid_chat",
            [
                py,
                "scripts/ops/agentjob_autoworker.py",
                "--once",
                "--set-profile",
                "--auto-withdraw",
                "--wait-seconds",
                str(agentjob_wait_seconds),
                "--status-file",
                ".tmp/non-bounty/agentjob_autoworker_status_latest.json",
            ],
            agentjob_wait_seconds + 25,
        ),
        (
            "bothire_work_loop",
            [py, "scripts/ops/bothire_work_loop.py", "--once", "--output", ".tmp/non-bounty/bothire_work_status_latest.json"],
            35,
        ),
        (
            "opentask_status",
            [py, "scripts/ops/opentask_agent_cli.py", "--login-refresh", "--status", "--bids", "--contracts", "--notifications"],
            45,
        ),
        (
            "agentpact_wallet_targeted_offers",
            [
                py,
                "scripts/ops/agentpact_wallet_targeted_offers.py",
                "--identity",
                ".tmp/non-bounty/agentpact_wallet_identity.secret.json",
                "--status",
                ".tmp/non-bounty/agentpact_wallet_targeted_offers_status.json",
            ],
            60,
        ),
        (
            "agentpact_wallet_watch",
            [
                py,
                "scripts/ops/agentpact_wallet_watch.py",
                "--identity",
                ".tmp/non-bounty/agentpact_wallet_identity.secret.json",
                "--output",
                ".tmp/non-bounty/agentpact_wallet_watch_latest.json",
            ],
            35,
        ),
        (
            "agentpact_alerts_subscribe",
            [
                py,
                "scripts/ops/agentpact_subscribe_alerts.py",
                "--identity",
                ".tmp/non-bounty/agentpact_wallet_identity.secret.json",
                "--status",
                ".tmp/non-bounty/agentpact_alerts_subscribe_status.json",
            ],
            35,
        ),
        (
            "agentpact_webhook_register",
            [
                py,
                "scripts/ops/agentpact_register_webhook.py",
                "--identity",
                ".tmp/non-bounty/agentpact_wallet_identity.secret.json",
                "--status",
                ".tmp/non-bounty/agentpact_webhook_register_status.json",
                "--secret",
                ".tmp/non-bounty/agentpact_webhook.secret.json",
            ],
            35,
        ),
        (
            "agoragentic_seller_watch",
            [
                py,
                "scripts/ops/agoragentic_seller_watcher.py",
                "--output",
                ".tmp/non-bounty/agoragentic_seller_watch_status.json",
                "--request-timeout-seconds",
                "3",
            ],
            35,
        ),
        (
            "machina_listing_watch",
            [py, "scripts/ops/machina_listing_watcher.py"],
            35,
        ),
        (
            "payanagent_job_watch",
            [py, "scripts/ops/payanagent_job_watcher.py", "--once", "--status", ".tmp/non-bounty/payanagent_job_watcher_status_latest.json"],
            35,
        ),
        (
            "github_bounty_claim_watch",
            [py, "scripts/ops/github_bounty_claim_watch.py", "--output", ".tmp/non-bounty/github_bounty_claim_watch_status.json"],
            55,
        ),
        (
            "mergework_mrwk_claim_watch",
            [py, "scripts/ops/mergework_mrwk_claim_watch.py", "--output", ".tmp/non-bounty/mergework_mrwk_claim_watch_status.json"],
            35,
        ),
        (
            "market_matrix",
            [py, "scripts/ops/non_bounty_market_matrix.py"],
            20,
        ),
    ]


def _summarise_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    public_x402_ready = any(item.get("name") == "x402_public_ready" and item.get("ok") for item in results)
    soft_failed: list[str] = []
    hard_failed: list[str] = []
    for item in results:
        if item.get("ok"):
            continue
        name = str(item.get("name") or "")
        if name in SOFT_FAILURE_REASONS and public_x402_ready:
            item["soft_failed"] = True
            item["soft_failure_reason"] = SOFT_FAILURE_REASONS[name]
            soft_failed.append(name)
        elif name in EXTERNAL_TLS_SOFT_FAILURE_REASONS and public_x402_ready and _is_tls_eof_failure(item):
            item["soft_failed"] = True
            item["soft_failure_reason"] = EXTERNAL_TLS_SOFT_FAILURE_REASONS[name]
            soft_failed.append(name)
        else:
            hard_failed.append(name)
    return {
        "commands_ok": sum(1 for item in results if item.get("ok")),
        "commands_soft_failed": soft_failed,
        "commands_failed": hard_failed,
    }


def _is_tls_eof_failure(item: dict[str, Any]) -> bool:
    text = f"{item.get('stdout_tail') or ''}\n{item.get('stderr_tail') or ''}"
    return "UNEXPECTED_EOF_WHILE_READING" in text or "SSL_ERROR_SYSCALL" in text


def run_cycle(*, wallet: str, output: Path, agentjob_wait_seconds: int, cycle: int | None = None) -> dict[str, Any]:
    before = _wallet_probe(wallet)
    results = [
        _run_command(name, argv, timeout_seconds=timeout_seconds)
        for name, argv, timeout_seconds in _commands(agentjob_wait_seconds)
    ]
    after = _wallet_probe(wallet)
    paid_signal = after.get("funds_received") is True
    result_summary = _summarise_results(results)
    snapshot = {
        "schema": "x0tta6bl4.income_watch_cycle.v1",
        "checked_at_utc": _utc_now(),
        "cycle": cycle,
        "wallet": wallet,
        "wallet_before": before,
        "wallet_after": after,
        "commands_total": len(results),
        **result_summary,
        "paid_signal": paid_signal,
        "funds_received_claim_allowed": paid_signal,
        "results": results,
        "next_action": "verify_received_funds" if paid_signal else "keep_watchers_running",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def _append_history(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", default=TARGET_WALLET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history-jsonl", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--agentjob-wait-seconds", type=int, default=20)
    parser.add_argument("--cycles", type=int, default=1, help="0 means run forever")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle = 0
    last_snapshot: dict[str, Any] | None = None
    while args.cycles == 0 or cycle < args.cycles:
        cycle += 1
        last_snapshot = run_cycle(
            wallet=args.wallet,
            output=args.output,
            agentjob_wait_seconds=max(5, min(60, args.agentjob_wait_seconds)),
            cycle=cycle,
        )
        _append_history(args.history_jsonl, last_snapshot)
        print(
            json.dumps(
                {
                    "cycle": cycle,
                    "output": str(args.output),
                    "history_jsonl": str(args.history_jsonl),
                    "wallet": last_snapshot["wallet"],
                    "funds_received": last_snapshot["wallet_after"].get("funds_received"),
                    "commands_ok": last_snapshot["commands_ok"],
                    "commands_total": last_snapshot["commands_total"],
                    "commands_failed": last_snapshot["commands_failed"],
                    "next_action": last_snapshot["next_action"],
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        if last_snapshot["wallet_after"].get("funds_received"):
            return 0
        if args.cycles != 0 and cycle >= args.cycles:
            break
        time.sleep(max(5.0, args.interval_seconds))
    return 0 if last_snapshot and not last_snapshot["commands_failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
