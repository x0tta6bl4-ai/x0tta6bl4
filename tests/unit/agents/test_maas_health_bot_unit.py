"""Unit tests for src.agents.maas_health_bot."""

from __future__ import annotations

from src.agents.maas_health_bot import HealthBotConfig, MaasHealthBot


def _base_config(tmp_path) -> HealthBotConfig:
    return HealthBotConfig(
        socks_host="127.0.0.1",
        socks_port=65535,
        socks_probe_timeout_seconds=0.1,
        enable_socks_probe=False,
        proxy_log_path=str(tmp_path / "proxy.log"),
        log_tail_lines=100,
        max_delay_ms=100,
        max_abort_events=1,
        health_urls=[],
        health_timeout_seconds=0.2,
        allow_external_urls=False,
        enable_execute=False,
        action_cooldown_seconds=0,
        restart_xray_cmd="",
        reroute_cmd="",
        restart_control_plane_cmd="",
        history_size=20,
    )


def test_run_once_healthy_when_no_fail_signals(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("2026.02.26 08:08:45 The delay: 81 ms\n", encoding="utf-8")

    cfg = _base_config(tmp_path)
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=False, dry_run=True)

    assert report["status"] == "healthy"
    assert report["external_ai_providers_used"] is False
    assert any(sig["name"] == "proxy_delay_ms" for sig in report["signals"])


def test_run_once_degraded_when_abort_events_exceed_threshold(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text(
        "\n".join(
            [
                "connection upload closed",
                "connection upload closed",
                "The delay: 81 ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cfg = _base_config(tmp_path)
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=False, dry_run=True)

    assert report["status"] == "degraded"
    abort_signal = next(sig for sig in report["signals"] if sig["name"] == "proxy_abort_events")
    assert abort_signal["status"] == "fail"


def test_run_once_plans_actions_in_dry_run_mode(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text(
        "\n".join(
            [
                "connection upload closed",
                "connection upload closed",
                "The delay: 300 ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cfg = HealthBotConfig(
        **{
            **_base_config(tmp_path).__dict__,
            "restart_xray_cmd": "/bin/echo restart-xray",
            "reroute_cmd": "/bin/echo reroute",
            "enable_execute": True,
        }
    )
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=True, dry_run=True)

    assert report["status"] == "degraded"
    assert len(report["executed_actions"]) >= 1
    assert all(action["attempted"] is False for action in report["executed_actions"])
    assert any("dry-run" in action["detail"] for action in report["executed_actions"])


def test_run_once_executes_commands_when_not_dry_run(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("connection upload closed\nconnection upload closed\n", encoding="utf-8")

    cfg = HealthBotConfig(
        **{
            **_base_config(tmp_path).__dict__,
            "restart_xray_cmd": "/bin/echo restart-xray",
            "enable_execute": True,
        }
    )
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=True, dry_run=False)

    assert len(report["executed_actions"]) >= 1
    assert any(action["attempted"] is True for action in report["executed_actions"])
    assert any(action["success"] is True for action in report["executed_actions"])


def test_run_once_does_not_execute_when_execute_disabled(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("connection upload closed\nconnection upload closed\n", encoding="utf-8")

    cfg = HealthBotConfig(
        **{
            **_base_config(tmp_path).__dict__,
            "restart_xray_cmd": "/bin/echo restart-xray",
            "enable_execute": False,
        }
    )
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=True, dry_run=False)

    assert len(report["executed_actions"]) >= 1
    assert all(action["attempted"] is False for action in report["executed_actions"])
    assert any("execute disabled by config" in action["detail"] for action in report["executed_actions"])


def test_run_once_respects_action_cooldown(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("connection upload closed\nconnection upload closed\n", encoding="utf-8")

    cfg = HealthBotConfig(
        **{
            **_base_config(tmp_path).__dict__,
            "restart_xray_cmd": "/bin/echo restart-xray",
            "enable_execute": True,
            "action_cooldown_seconds": 60,
        }
    )
    bot = MaasHealthBot(cfg)
    first = bot.run_once(auto_heal=True, dry_run=False)
    second = bot.run_once(auto_heal=True, dry_run=False)

    assert any(action["attempted"] is True for action in first["executed_actions"])
    assert any(action["attempted"] is False for action in second["executed_actions"])
    assert any("cooldown active" in action["detail"] for action in second["executed_actions"])


def test_external_health_url_is_skipped_in_local_only_mode(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("The delay: 80 ms\n", encoding="utf-8")

    cfg = HealthBotConfig(
        **{
            **_base_config(tmp_path).__dict__,
            "health_urls": ["https://example.com/health"],
            "allow_external_urls": False,
        }
    )
    bot = MaasHealthBot(cfg)
    report = bot.run_once(auto_heal=False, dry_run=True)

    signal = next(sig for sig in report["signals"] if sig["name"] == "health_url:https://example.com/health")
    assert signal["status"] == "skip"


def test_history_returns_latest_first(tmp_path):
    log_path = tmp_path / "proxy.log"
    log_path.write_text("The delay: 50 ms\n", encoding="utf-8")

    cfg = _base_config(tmp_path)
    bot = MaasHealthBot(cfg)

    first = bot.run_once(auto_heal=False, dry_run=True)
    second = bot.run_once(auto_heal=False, dry_run=True)
    history = bot.history(limit=2)

    assert len(history) == 2
    assert history[0]["timestamp"] == second["timestamp"]
    assert history[1]["timestamp"] == first["timestamp"]
