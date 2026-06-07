#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_SOURCE = ROOT / "redacted" / "ghost-access" / "telegram_bot_simple.redacted.py"


def test_admin_anti_block_command_and_callback_are_wired() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")

    assert 'builder.button(text="Anti-block", callback_data="admin:anti_block")' in text
    assert '@router.message(Command("anti_block"))' in text
    assert 'elif callback.data == "admin:anti_block":' in text
    assert 'render_admin_anti_block_text()' in text


def test_admin_anti_block_uses_operator_status_api_only() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")

    assert 'PROFILE_STATUS_API_URL' in text
    assert 'load_profile_status_api("/transport-usage")' in text
    assert 'load_profile_status_api("/client-compatibility")' in text
    assert 'http://127.0.0.1:9472' in text


def test_admin_anti_block_includes_rollback_dry_run_without_apply() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")
    start = text.index("def load_rollback_dry_run")
    end = text.index("def render_admin_anti_block_text")
    rollback_text = text[start:end]

    assert "ROLLBACK_GHOST_FALLBACKS_SCRIPT" in text
    assert "render_rollback_dry_run_block()" in text
    assert "rollback_ghost_fallbacks.py" in text
    assert '"--json"' in rollback_text
    assert '"--apply"' not in rollback_text
    assert "no rollback was applied" in text


def test_admin_anti_block_output_is_aggregate_only() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")
    start = text.index("def render_admin_anti_block_text")
    end = text.index("def render_admin_runtime_text")
    function_text = text[start:end]

    assert "dataplane_events" in function_text
    assert "nginx_requests" in function_text
    assert "unique_clients" in function_text
    assert "client_hashes_sample" not in function_text
    assert "raw_ip" not in function_text
    assert "raw_email" not in function_text
    assert "raw_target_host" not in function_text
    assert "vless://" not in function_text


def test_admin_anti_block_surfaces_client_evidence_gap_without_raw_rows() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")
    start = text.index("def render_client_compatibility_block")
    end = text.index("def render_admin_anti_block_text")
    function_text = text[start:end]

    assert 'load_profile_status_api("/client-compatibility")' in function_text
    assert "Client evidence:" in function_text
    assert "desktop v2rayN" in function_text
    assert "Android Happ/Hiddify" in function_text
    assert "mobile network" in function_text
    assert "work/restricted Wi-Fi" in function_text
    assert "missing_requirements" in function_text
    assert "passing_real_client_checks" in function_text
    assert "real_client_checks" in function_text
    assert "raw user IDs" in function_text
    assert "real_client_checks[" not in function_text
    assert "symptom" not in function_text
    assert "vless://" not in function_text
    assert "/sub/" not in function_text


def test_subscription_handler_does_not_emit_fake_vless_error_profiles() -> None:
    text = BOT_SOURCE.read_text(encoding="utf-8")
    start = text.index("async def handle_subscription_request")
    end = text.index("async def handle_android_stealth_bundle_request")
    function_text = text[start:end]

    assert "_build_stub_profiles" not in function_text
    assert "status=403" in function_text
    assert "status=404" in function_text
    assert "status=409" in function_text
    assert "status=429" in function_text
