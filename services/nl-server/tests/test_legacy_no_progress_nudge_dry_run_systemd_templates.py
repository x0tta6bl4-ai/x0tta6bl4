from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "systemd" / "ghost-access-legacy-no-progress-nudge-dry-run.service"
TIMER = ROOT / "systemd" / "ghost-access-legacy-no-progress-nudge-dry-run.timer"

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
    re.compile(r"\bhttps?://", re.IGNORECASE),
    re.compile(r"@[A-Za-z0-9_]{4,}"),
]


def test_legacy_no_progress_nudge_dry_run_templates_exist() -> None:
    assert SERVICE.exists()
    assert TIMER.exists()


def test_dry_run_service_writes_only_aggregate_report() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "Type=oneshot" in text
    assert "send_legacy_no_progress_nudge.py" in text
    assert "/opt/ghost-access-bot/shared/scripts/send_legacy_no_progress_nudge.py" in text
    assert "--write --json" in text
    assert "--json-out /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json" in text
    assert "--apply" not in text
    assert "--bot-token" not in text
    assert "TELEGRAM_BOT_TOKEN" not in text


def test_dry_run_service_has_no_restart_or_mutation_commands() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    forbidden_tokens = [
        "systemctl restart",
        "systemctl reload",
        " x-ui",
        "xray_runtime_user_manager",
        "sync_ghost_https_ws_clients",
        "sync_v2rayn_subscription_fallbacks",
        "rollback_ghost_fallbacks",
        "--confirm",
    ]

    for token in forbidden_tokens:
        assert token not in text


def test_dry_run_service_is_hardened_without_network_access() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "NoNewPrivileges=true" in text
    assert "PrivateTmp=true" in text
    assert "ProtectSystem=strict" in text
    assert "ReadOnlyPaths=/opt/ghost-access-bot/shared" in text
    assert "ReadWritePaths=/var/lib/ghost-access/legacy-migration" in text
    assert "RestrictAddressFamilies=AF_UNIX" in text
    assert "CapabilityBoundingSet=" in text


def test_dry_run_timer_references_service_and_has_no_secrets() -> None:
    text = TIMER.read_text(encoding="utf-8")

    assert "Unit=ghost-access-legacy-no-progress-nudge-dry-run.service" in text
    assert "OnBootSec=7min" in text
    assert "OnUnitActiveSec=15min" in text
    assert "Persistent=true" in text


def test_dry_run_templates_do_not_embed_secret_patterns() -> None:
    rendered = SERVICE.read_text(encoding="utf-8") + "\n" + TIMER.read_text(encoding="utf-8")

    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(rendered)
