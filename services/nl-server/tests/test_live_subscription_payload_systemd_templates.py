#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "systemd" / "ghost-access-live-subscription-payload-check.service"
TIMER = ROOT / "systemd" / "ghost-access-live-subscription-payload-check.timer"

FORBIDDEN_PATTERNS = [
    re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
]


def test_live_subscription_payload_systemd_templates_exist() -> None:
    assert SERVICE.exists()
    assert TIMER.exists()


def test_service_runs_only_readonly_payload_check() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "Type=oneshot" in text
    assert "check_live_subscription_payload.py --limit 50" in text
    assert "--expired-limit 50" in text
    assert "--json-out /var/lib/ghost-access/subscription-payload/latest.json" in text
    assert re.search(r"(?<!-)--json(?!-)", text) is None
    assert "/opt/ghost-access-bot/shared/scripts/check_live_subscription_payload.py" in text
    assert "ConditionPathExists=/opt/ghost-access-bot/shared/x0tta6bl4.db" in text
    assert "ReadOnlyPaths=/opt/ghost-access-bot/shared" in text
    assert "ReadWritePaths=/var/lib/ghost-access" in text


def test_service_has_no_vpn_mutation_or_restart_commands() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    forbidden_tokens = [
        "systemctl restart",
        "systemctl reload",
        "sqlite3",
        "xray_runtime_user_manager",
        "run_vpn_delivery_canary",
        "rollback_ghost_fallbacks",
        "sync_ghost_https_ws_clients",
        "sync_v2rayn_subscription_fallbacks",
    ]

    for token in forbidden_tokens:
        assert token not in text


def test_service_is_hardened_but_allows_subscription_http_fetch() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "NoNewPrivileges=true" in text
    assert "PrivateTmp=true" in text
    assert "ProtectSystem=strict" in text
    assert "CapabilityBoundingSet=" in text
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in text


def test_timer_references_service_and_has_no_secret_values() -> None:
    text = TIMER.read_text(encoding="utf-8")

    assert "Unit=ghost-access-live-subscription-payload-check.service" in text
    assert "OnBootSec=3min" in text
    assert "OnUnitActiveSec=5min" in text
    assert "Persistent=true" in text
    assert "http://" not in text
    assert "https://" not in text


def test_templates_do_not_embed_secret_patterns() -> None:
    rendered = SERVICE.read_text(encoding="utf-8") + "\n" + TIMER.read_text(encoding="utf-8")

    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(rendered)
