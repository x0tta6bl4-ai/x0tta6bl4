#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "systemd" / "ghost-access-client-compatibility-summary.service"
TIMER = ROOT / "systemd" / "ghost-access-client-compatibility-summary.timer"


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


def test_client_compatibility_systemd_templates_exist() -> None:
    assert SERVICE.exists()
    assert TIMER.exists()


def test_service_runs_only_summary_publisher() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "build_client_compatibility_runtime_summary.py" in text
    assert "/opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py" in text
    assert "--matrix /var/lib/ghost-access/client-compatibility/matrix.json" in text
    assert "--json-out /var/lib/ghost-access/client-compatibility/latest.json" in text
    assert "--markdown-out /var/lib/ghost-access/client-compatibility/latest.md" in text
    assert "ConditionPathExists=/var/lib/ghost-access/client-compatibility/matrix.json" in text
    assert "ReadWritePaths=/var/lib/ghost-access/client-compatibility" in text
    assert "ReadOnlyPaths=/opt/x0tta6bl4-mesh/scripts" in text


def test_service_has_no_vpn_mutation_or_restart_commands() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    forbidden_tokens = [
        "systemctl restart",
        "systemctl reload",
        "x-ui",
        "nginx",
        "telegram-bot-simple",
        "ghost-access-nl-xhttp",
        "ghost-access-nl-https-ws",
        "rollback_ghost_fallbacks",
        "sync_ghost_https_ws_clients",
        "sync_v2rayn_subscription_fallbacks",
    ]

    for token in forbidden_tokens:
        assert token not in text


def test_service_is_hardened_and_localhost_free() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "Type=oneshot" in text
    assert "NoNewPrivileges=true" in text
    assert "PrivateTmp=true" in text
    assert "ProtectSystem=strict" in text
    assert "CapabilityBoundingSet=" in text
    assert "RestrictAddressFamilies=AF_UNIX" in text


def test_timer_references_service_and_has_no_network_or_secret_values() -> None:
    text = TIMER.read_text(encoding="utf-8")

    assert "Unit=ghost-access-client-compatibility-summary.service" in text
    assert "OnBootSec=2min" in text
    assert "OnUnitActiveSec=2min" in text
    assert "Persistent=true" in text
    assert "http://" not in text
    assert "https://" not in text


def test_templates_do_not_embed_secret_patterns() -> None:
    rendered = SERVICE.read_text(encoding="utf-8") + "\n" + TIMER.read_text(encoding="utf-8")

    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(rendered)
