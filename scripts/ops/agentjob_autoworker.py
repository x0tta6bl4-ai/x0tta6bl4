#!/usr/bin/env python3
"""Keep an AgentJob worker online and handle paid tasks when a reply command exists."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://agent-job.ai"
DEFAULT_SECRET = Path(".tmp/non-bounty/agentjob_auto.secret.json")
DEFAULT_STATUS = Path(".tmp/non-bounty/agentjob_autoworker_status.json")
DEFAULT_INBOX = Path(".tmp/non-bounty/agentjob_inbox")
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_WITHDRAW_MIN_USDC = 1.0

SAFE_TERMS = {
    "api",
    "csv",
    "curl",
    "docs",
    "documentation",
    "json",
    "openapi",
    "python",
    "readme",
    "research",
    "script",
    "test",
    "pytest",
}

UNSAFE_TERMS = {
    "captcha",
    "fake review",
    "follow",
    "kyc",
    "like",
    "private key",
    "seed phrase",
    "spam",
    "twitter",
    "x.com",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _parse_response(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("event:") or "\ndata:" in text:
        items: list[Any] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                try:
                    items.append(json.loads(data))
                except json.JSONDecodeError:
                    items.append({"raw": data})
        return {"sse": items, "raw": text[:1000]}
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return {"raw": text[:1000]}


def _request(
    method: str,
    path: str,
    *,
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json,text/event-stream",
        "User-Agent": "x0tta6bl4-agentjob-autoworker",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "http_status": response.status,
                "ok": 200 <= response.status < 300,
                "response": _parse_response(response.read()),
            }
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "ok": False, "response": _parse_response(exc.read())}
    except (TimeoutError, urllib.error.URLError) as exc:
        return {"http_status": None, "ok": False, "response": {"error": exc.__class__.__name__}}


def _mcp(api_key: str, name: str, arguments: dict[str, Any], *, request_id: int = 1) -> dict[str, Any]:
    return _request(
        "POST",
        "/api/mcp",
        api_key=api_key,
        payload={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def _mcp_text_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        text = result["response"]["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return {}
    if not isinstance(text, str):
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return data if isinstance(data, dict) else {}


def _usdc_amount(value: Any) -> float:
    try:
        return float(str(value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def _get_profile(api_key: str) -> dict[str, Any]:
    response = _mcp(api_key, "get_my_profile", {}, request_id=20)
    return {
        "raw": response,
        "profile": _mcp_text_json(response),
    }


def _maybe_withdraw_usdc(
    api_key: str,
    *,
    target_wallet: str,
    min_usdc: float = DEFAULT_WITHDRAW_MIN_USDC,
    amount_usdc: float | None = None,
) -> dict[str, Any]:
    profile_result = _get_profile(api_key)
    profile = profile_result["profile"]
    wallet_balance = profile.get("wallet_balance") if isinstance(profile.get("wallet_balance"), dict) else {}
    available = _usdc_amount(wallet_balance.get("usdc"))
    if available < min_usdc:
        return {
            "attempted": False,
            "reason": "below_minimum",
            "available_usdc": available,
            "min_usdc": min_usdc,
            "target_wallet": target_wallet,
            "profile": {
                "agent_id": profile.get("agent_id"),
                "wallet_address": profile.get("wallet_address"),
                "revenue_usdc": (profile.get("stats") or {}).get("total_revenue_usdc"),
            },
        }

    amount = available if amount_usdc is None else min(amount_usdc, available)
    amount_text = f"{amount:.6f}".rstrip("0").rstrip(".")
    withdraw = _mcp(
        api_key,
        "withdraw_usdc",
        {"toAddress": target_wallet, "amount": amount_text},
        request_id=21,
    )
    return {
        "attempted": True,
        "available_usdc": available,
        "amount_usdc": amount_text,
        "target_wallet": target_wallet,
        "withdraw": withdraw,
        "withdraw_result": _mcp_text_json(withdraw),
    }


def _register(secret_path: Path, *, agent_name: str) -> dict[str, Any]:
    secret = _read_json(secret_path)
    if secret.get("api_key"):
        return {"status": "already_registered", "secret_path": str(secret_path)}
    response = _request(
        "POST",
        "/api/register/auto",
        payload={
            "agentName": agent_name,
            "idempotencyKey": "x0tta6bl4-6017613e-agentjob-auto-v1",
        },
    )
    data = response.get("response", {}).get("data") if isinstance(response.get("response"), dict) else None
    if response.get("ok") and isinstance(data, dict):
        _write_json(
            secret_path,
            {
                "agent_name": agent_name,
                "agent_id": data.get("agentId") or data.get("agent_id") or data.get("id"),
                "api_key": data.get("apiKey") or data.get("api_key"),
                "wallet_address": data.get("walletAddress") or data.get("wallet_address"),
                "target_payout_wallet": TARGET_WALLET,
                "raw": data,
            },
        )
    return response


def _set_paid_profile(api_key: str) -> dict[str, Any]:
    profile = {
        "name": "x0tta6bl4 Public Microtask Worker",
        "bio": "Fast API, Python, JSON, CSV and docs microtasks.",
        "description": (
            "Compact paid technical help for public links and non-sensitive snippets. "
            "I can create JSON and CSV transforms, small Python scripts, API documentation notes, "
            "OpenAPI drafts, README cleanup, curl checks, pytest notes, and source-backed research summaries. "
            "Each reply is concise and includes verification steps when practical."
        ),
        "priceSubsequent": "1.50",
        "freeDailyMax": 0,
        "dailyReplyLimit": 100,
        "maxConcurrentChats": 2,
    }
    return _mcp(api_key, "update_agent_profile", profile, request_id=10)


def _task_text(task: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "body", "prompt", "content", "text"):
        if task.get(key):
            parts.append(str(task[key]))
    messages = task.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                parts.append(str(message.get("content") or message.get("text") or ""))
    return "\n".join(parts).strip()


def _is_safe_task(task: dict[str, Any]) -> bool:
    text = _task_text(task).lower()
    if any(term in text for term in UNSAFE_TERMS):
        return False
    return any(term in text for term in SAFE_TERMS)


def _reply_from_command(command: str, task: dict[str, Any], *, timeout_seconds: float) -> str:
    completed = subprocess.run(
        command,
        input=json.dumps(task, ensure_ascii=False),
        text=True,
        shell=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"reply command failed with {completed.returncode}")
    return completed.stdout.strip()


def _fallback_ack(task: dict[str, Any]) -> str:
    text = _task_text(task)
    if len(text) > 1200:
        text = text[:1200] + "..."
    return (
        "I can work on this as a compact public-input technical task.\n\n"
        "Current received brief:\n"
        f"{text}\n\n"
        "Please provide the exact expected output format if it is not already included. "
        "For code/API/data tasks I will return the result with clear assumptions and a verification step."
    )


def _submit_response(api_key: str, task_id: str, text: str) -> dict[str, Any]:
    return _request(
        "POST",
        f"/api/agents/tasks/{task_id}/response",
        api_key=api_key,
        payload={"text": text},
    )


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    register = _register(args.secret_path, agent_name=args.agent_name)
    secret = _read_json(args.secret_path)
    api_key = str(secret.get("api_key") or "")
    if not api_key:
        return {"ok": False, "register": register, "error": "missing_api_key"}

    profile = _set_paid_profile(api_key) if args.set_profile else None
    heartbeat = _request("POST", "/api/agents/heartbeat", api_key=api_key)
    poll = _request("GET", f"/api/agents/tasks?wait={args.wait_seconds}", api_key=api_key, timeout=args.wait_seconds + 10)
    task = poll.get("response", {}).get("task") if isinstance(poll.get("response"), dict) else None
    delivery: dict[str, Any] | None = None
    task_saved_path: str | None = None

    if isinstance(task, dict):
        args.inbox_dir.mkdir(parents=True, exist_ok=True)
        task_id = str(task.get("id") or task.get("task_id") or int(time.time()))
        task_path = args.inbox_dir / f"{task_id}.json"
        _write_json(task_path, task)
        task_saved_path = str(task_path)

        if _is_safe_task(task):
            reply = ""
            if args.reply_command:
                reply = _reply_from_command(args.reply_command, task, timeout_seconds=args.reply_timeout)
            elif args.fallback_ack:
                reply = _fallback_ack(task)
            if reply:
                delivery = _submit_response(api_key, task_id, reply)
        else:
            delivery = {"ok": False, "reason": "unsafe_or_out_of_scope_task_saved_only"}

    target_wallet = args.withdraw_wallet or str(secret.get("target_payout_wallet") or TARGET_WALLET)
    withdraw = (
        _maybe_withdraw_usdc(
            api_key,
            target_wallet=target_wallet,
            min_usdc=max(0.0, args.withdraw_min_usdc),
            amount_usdc=args.withdraw_amount_usdc,
        )
        if args.auto_withdraw
        else None
    )

    return {
        "ok": True,
        "registered": bool(api_key),
        "register_status": register.get("status") or register.get("http_status"),
        "profile_updated": None if profile is None else profile.get("ok"),
        "heartbeat_ok": heartbeat.get("ok"),
        "poll_ok": poll.get("ok"),
        "task_received": isinstance(task, dict),
        "task_saved_path": task_saved_path,
        "delivery": delivery,
        "withdraw": withdraw,
        "target_payout_wallet": target_wallet,
        "platform_wallet": secret.get("wallet_address"),
        "claim_gate": {
            "funds_received_claim_allowed": bool(
                isinstance(withdraw, dict)
                and withdraw.get("attempted")
                and (withdraw.get("withdraw") or {}).get("ok")
            ),
            "reason": (
                "AgentJob withdrawal was attempted; verify target wallet on-chain."
                if isinstance(withdraw, dict) and withdraw.get("attempted")
                else "AgentJob revenue must be visible before claiming received funds."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-path", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--inbox-dir", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--agent-name", default="x0tta6bl4 Public Microtask Worker")
    parser.add_argument("--wait-seconds", type=int, default=5)
    parser.add_argument("--reply-timeout", type=float, default=120.0)
    parser.add_argument("--reply-command", default="")
    parser.add_argument("--set-profile", action="store_true")
    parser.add_argument("--fallback-ack", action="store_true")
    parser.add_argument("--auto-withdraw", action="store_true")
    parser.add_argument("--withdraw-wallet", default="")
    parser.add_argument("--withdraw-min-usdc", type=float, default=DEFAULT_WITHDRAW_MIN_USDC)
    parser.add_argument("--withdraw-amount-usdc", type=float)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=45)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    while True:
        status = run_once(args)
        _write_json(args.status_file, status)
        print(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True))
        if args.once:
            return 0 if status.get("ok") else 1
        time.sleep(max(5, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
