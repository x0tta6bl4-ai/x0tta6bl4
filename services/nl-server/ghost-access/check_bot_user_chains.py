#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_target() -> Path:
    candidates = [
        Path.cwd() / "telegram_bot_simple.py",
        Path("/opt/ghost-access-bot/current/telegram_bot_simple.py"),
        Path("/opt/ghost-access-bot/telegram_bot_simple.py"),
        Path("/mnt/projects/telegram_bot_simple.py"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    fail("telegram_bot_simple.py not found in cwd, /opt/ghost-access-bot, or /mnt/projects")
    raise SystemExit(1)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(label)
    ok(label)


def require_regex(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, re.S):
        fail(label)
    ok(label)


def main() -> int:
    target = resolve_target()
    text = target.read_text(encoding="utf-8")
    ok(f"target resolved: {target}")

    commands = sorted(set(re.findall(r'BotCommand\(command="([^"]+)"', text)))
    handlers = set(re.findall(r'@router\.message\(Command\("([^"]+)"\)\)', text))
    missing_commands = [cmd for cmd in commands if cmd not in handlers]
    if missing_commands:
        fail(f"missing command handlers: {', '.join(missing_commands)}")
    ok(f"all BotCommand entries have handlers ({len(commands)})")

    literal_callbacks = sorted(set(re.findall(r'callback_data="([^"]+)"', text)))
    handler_eq = set(re.findall(r'elif callback\.data == "([^"]+)"', text)) | set(
        re.findall(r'if callback\.data == "([^"]+)"', text)
    )
    handler_prefixes = set(re.findall(r'callback\.data\.startswith\("([^"]+)"\)', text))
    uncovered = []
    for callback in literal_callbacks:
        covered = callback in handler_eq or any(callback.startswith(prefix) for prefix in handler_prefixes)
        if not covered:
            uncovered.append(callback)
    if uncovered:
        fail(f"uncovered literal callbacks: {', '.join(uncovered)}")
    ok(f"all literal callbacks covered ({len(literal_callbacks)})")

    require(text, 'async def cmd_start(', "/start handler present")
    require(text, 'async def cmd_trial(', "/trial handler present")
    require(text, 'async def cmd_buy(', "/buy handler present")
    require(text, 'async def cmd_devices(', "/devices handler present")
    require(text, 'async def cmd_payments(', "/payments handler present")
    require(text, 'async def cmd_deleteme(', "/deleteme handler present")
    require(text, 'async def cmd_config(', "/config handler present")

    require_regex(text, r'(if|elif) callback\.data == "trial":', "trial callback present")
    require_regex(text, r'(if|elif) callback\.data == "config":', "config callback present")
    require_regex(text, r'(if|elif) callback\.data == "upgrade":', "upgrade callback present")
    require_regex(text, r'(if|elif) callback\.data == "buy:resume_latest":', "buy:resume_latest callback present")
    require_regex(text, r'(if|elif) callback\.data == "payments":', "payments callback present")
    require_regex(text, r'(if|elif) callback\.data == "confirm_delete_account":', "delete-account callback present")

    require_regex(
        text,
        r'if callback\.data == "trial":.*?if not check_xray_port_alive\(\):',
        "trial callback checks xray health",
    )
    require_regex(
        text,
        r'elif callback\.data == "config":.*?elif not check_xray_port_alive\(\):',
        "config callback checks xray health",
    )
    require_regex(
        text,
        r'async def cmd_trial\(.*?if not check_xray_port_alive\(\):',
        "/trial command checks xray health",
    )
    require_regex(
        text,
        r'async def cmd_config\(.*?if not check_xray_port_alive\(\):',
        "/config command checks xray health",
    )

    require(text, 'elif callback.data.startswith("buy:yoomoney:"):', "buy:yoomoney callback present")
    if 'callback_data=f"buy:{get_active_payment_provider()}:' in text:
        fail("provider-dynamic buy callback still present in upgrade/build flow")
    ok("YooMoney callback flow uses explicit handlers")

    require(text, 'def build_device_type_menu(user_id: int)', "family device type menu present")
    require(text, 'def build_device_added_menu(device_id: int)', "post-create device menu present")
    require(text, 'def build_device_connect_menu(device_id: int)', "device OS selection menu present")
    require(text, 'def render_device_platform_text(device: dict, platform: str)', "device platform helper present")
    require(text, 'elif callback.data.startswith("device:share:"):', "device share callback present")
    require(text, 'elif callback.data.startswith("device:rename:"):', "device rename callback present")
    require(text, 'elif callback.data.startswith("device:make_primary:"):', "make-primary callback present")
    require(text, 'elif callback.data.startswith("device:replace:"):', "replace-device callback present")
    require(text, 'elif callback.data.startswith("device:remove:"):', "remove-device callback present")

    require(text, 'render_subscription_text(user)', "subscription text renderer used")
    require(text, 'send_subscription_bundle(callback.message, user)', "subscription bundle sent from callbacks")
    require(text, 'summary = delete_user_account(user_id)', "delete_user_account invoked in callback")

    print("PASS: core user-chain checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
