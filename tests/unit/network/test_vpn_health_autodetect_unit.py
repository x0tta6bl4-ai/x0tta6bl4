"""Unit tests for VPN health auto-detection safeguards."""

from __future__ import annotations

import builtins
import subprocess
import types

import pytest

from src.network import self_healing_daemon, vpn_watchdog


def test_healing_cooldowns_default_to_thirty_minutes():
    assert vpn_watchdog.HEAL_COOLDOWN_SEC == 1800
    assert self_healing_daemon._HEAL_COOLDOWN == 1800


def test_hard_heal_is_disabled_by_default():
    assert vpn_watchdog.ENABLE_HARD_HEAL is False


def test_vpn_watchdog_default_port_matches_current_local_profile():
    assert vpn_watchdog.VPN_PORT == 443


def test_vpn_watchdog_provider_guard_blocks_heal(monkeypatch):
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_DISABLED", False)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_REQUIRE_FRESH", False)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_MAX_AGE_SECONDS", 3600)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_SCRIPT", "/tmp/provider-guard")
    monkeypatch.setattr(vpn_watchdog.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(
        vpn_watchdog.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=10,
            stdout="BLOCK: provider_outage\n",
            stderr="",
        ),
    )

    allowed, reason = vpn_watchdog.provider_guard_allows_heal()

    assert allowed is False
    assert "provider_outage" in reason


def test_vpn_watchdog_provider_guard_adds_require_fresh(monkeypatch):
    captured: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ALLOW: ok\n", stderr="")

    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_DISABLED", False)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_REQUIRE_FRESH", True)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_MAX_AGE_SECONDS", 120)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_SCRIPT", "/tmp/provider-guard")
    monkeypatch.setattr(vpn_watchdog.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(vpn_watchdog.subprocess, "run", fake_run)

    allowed, reason = vpn_watchdog.provider_guard_allows_heal()

    assert allowed is True
    assert "--require-fresh" in captured[0]
    assert captured[0][captured[0].index("--max-age-seconds") + 1] == "120"
    assert "ALLOW" in reason


def test_vpn_watchdog_provider_guard_blocks_missing_guard_when_fresh_required(monkeypatch):
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_DISABLED", False)
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_SCRIPT", "/tmp/missing-provider-guard")
    monkeypatch.setattr(vpn_watchdog.os.path, "exists", lambda _path: False)

    allowed, reason = vpn_watchdog.provider_guard_allows_heal(require_fresh=True)

    assert allowed is False
    assert "fresh snapshot required" in reason


def test_vpn_watchdog_provider_guard_disable_does_not_bypass_fresh_requirement(monkeypatch):
    monkeypatch.setattr(vpn_watchdog, "PROVIDER_GUARD_DISABLED", True)

    allowed, reason = vpn_watchdog.provider_guard_allows_heal(require_fresh=True)

    assert allowed is False
    assert "fresh snapshot required" in reason


def test_self_healing_provider_guard_blocks_missing_guard_when_fresh_required(monkeypatch):
    monkeypatch.setattr(self_healing_daemon, "PROVIDER_GUARD_DISABLED", False)
    monkeypatch.setattr(self_healing_daemon, "PROVIDER_GUARD_REQUIRE_FRESH", True)
    monkeypatch.setattr(self_healing_daemon, "PROVIDER_GUARD_SCRIPT", "/tmp/missing-provider-guard")
    monkeypatch.setattr(self_healing_daemon.os.path, "exists", lambda _path: False)

    allowed, reason = self_healing_daemon.provider_guard_allows_heal()

    assert allowed is False
    assert "fresh snapshot required" in reason


def test_self_healing_guard_disable_does_not_bypass_fresh_requirement(monkeypatch):
    monkeypatch.setattr(self_healing_daemon, "PROVIDER_GUARD_DISABLED", True)
    monkeypatch.setattr(self_healing_daemon, "PROVIDER_GUARD_REQUIRE_FRESH", True)

    allowed, reason = self_healing_daemon.provider_guard_allows_heal()

    assert allowed is False
    assert "fresh snapshot required" in reason


def test_vpn_watchdog_restart_xray_requires_hard_heal_flag(monkeypatch):
    monkeypatch.setattr(vpn_watchdog, "ENABLE_HARD_HEAL", False)
    monkeypatch.setattr(vpn_watchdog, "get_xray_pid", lambda: 12345)
    monkeypatch.setattr(
        vpn_watchdog.os,
        "kill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SIGTERM should not run")),
    )

    assert vpn_watchdog.VPNHealer().restart_xray() is False


def test_vpn_watchdog_restart_xray_requires_fresh_provider_guard(monkeypatch):
    seen_require_fresh: list[bool | None] = []

    def fake_provider_guard(*, require_fresh=None):
        seen_require_fresh.append(require_fresh)
        return False, "BLOCK: snapshot_missing"

    monkeypatch.setattr(vpn_watchdog, "ENABLE_HARD_HEAL", True)
    monkeypatch.setattr(vpn_watchdog, "provider_guard_allows_heal", fake_provider_guard)
    monkeypatch.setattr(vpn_watchdog, "get_xray_pid", lambda: 12345)
    monkeypatch.setattr(
        vpn_watchdog.os,
        "kill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SIGTERM should not run")),
    )

    assert vpn_watchdog.VPNHealer().restart_xray() is False
    assert seen_require_fresh == [True]


def test_vpn_watchdog_restart_xray_can_sigterm_when_all_hard_heal_gates_pass(monkeypatch):
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(vpn_watchdog, "ENABLE_HARD_HEAL", True)
    monkeypatch.setattr(vpn_watchdog, "provider_guard_allows_heal", lambda *, require_fresh=None: (True, "ALLOW"))
    monkeypatch.setattr(vpn_watchdog, "get_xray_pid", lambda: 12345)
    monkeypatch.setattr(vpn_watchdog.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(vpn_watchdog.os, "kill", lambda pid, sig: killed.append((pid, sig)))

    assert vpn_watchdog.VPNHealer().restart_xray() is True
    assert killed == [(12345, vpn_watchdog.signal.SIGTERM)]


def test_self_healing_daemon_provider_guard_blocks_trigger(monkeypatch):
    monkeypatch.setattr(self_healing_daemon, "ENABLE_HEAL", True)
    monkeypatch.setattr(self_healing_daemon, "_healing_attempts_count", 0)
    monkeypatch.setattr(self_healing_daemon, "_last_heal_time", -9999.0)
    monkeypatch.setattr(
        self_healing_daemon,
        "provider_guard_allows_heal",
        lambda: (False, "BLOCK: provider_outage"),
    )
    monkeypatch.setattr(
        self_healing_daemon.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run should not run")),
    )

    self_healing_daemon.trigger_healing("test provider block")

    assert self_healing_daemon._healing_attempts_count == 0


def _reset_self_healing_counters(monkeypatch):
    monkeypatch.setattr(self_healing_daemon, "_consecutive_failures", 0)
    monkeypatch.setattr(self_healing_daemon, "_consecutive_latency_failures", 0)
    monkeypatch.setattr(self_healing_daemon, "_consecutive_proxy_failures", 0)
    monkeypatch.setattr(self_healing_daemon, "_consecutive_fin_wait2_failures", 0)


def test_self_healing_daemon_detects_active_socks_port(monkeypatch):
    monkeypatch.setattr(self_healing_daemon, "SOCKS_HOST", "127.0.0.1")
    monkeypatch.setattr(self_healing_daemon, "SOCKS_PORT", 10808)
    monkeypatch.setattr(self_healing_daemon, "SOCKS_PORT_CANDIDATES", (10808, 10918))
    monkeypatch.setattr(
        self_healing_daemon,
        "_socks_handshake",
        lambda host, port, timeout=1.0: port == 10918,
    )

    assert self_healing_daemon.check_proxy_health() is True
    assert self_healing_daemon.SOCKS_PORT == 10918


def test_self_healing_daemon_skips_reality_rotation_by_default(monkeypatch):
    import_attempted = False

    def fake_import(name, *args, **kwargs):
        nonlocal import_attempted
        if name == "vpn_config_generator":
            import_attempted = True
            raise AssertionError("rotation import should be gated")
        return real_import(name, *args, **kwargs)

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(self_healing_daemon, "ENABLE_HEAL", True)
    monkeypatch.setattr(self_healing_daemon, "ENABLE_REALITY_ROTATION", False)
    monkeypatch.setattr(self_healing_daemon, "_healing_attempts_count", 3)
    monkeypatch.setattr(self_healing_daemon, "_last_heal_time", -9999.0)
    monkeypatch.setattr(self_healing_daemon.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        self_healing_daemon.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    self_healing_daemon.trigger_healing("test rotation guard")

    assert import_attempted is False


def test_self_healing_daemon_trigger_healing_disabled_by_default(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(self_healing_daemon, "ENABLE_HEAL", False)
    monkeypatch.setattr(self_healing_daemon, "_healing_attempts_count", 0)
    monkeypatch.setattr(self_healing_daemon, "_last_heal_time", -9999.0)
    monkeypatch.setattr(
        self_healing_daemon.subprocess,
        "run",
        lambda cmd, **_kwargs: commands.append(cmd),
    )
    monkeypatch.setattr(
        self_healing_daemon.os,
        "kill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("os.kill should not run")),
    )

    self_healing_daemon.trigger_healing("single proxy blip")

    assert commands == []
    assert self_healing_daemon._healing_attempts_count == 0


def test_self_healing_daemon_defers_proxy_heal_until_failure_streak(monkeypatch):
    _reset_self_healing_counters(monkeypatch)
    healed: list[str] = []

    monkeypatch.setattr(self_healing_daemon, "PROXY_HEAL_FAILURES", 3)
    monkeypatch.setattr(self_healing_daemon, "ping_target", lambda *_args, **_kwargs: 25.0)
    monkeypatch.setattr(self_healing_daemon, "check_proxy_health", lambda: False)
    monkeypatch.setattr(self_healing_daemon, "get_fin_wait2_count", lambda: 0)
    monkeypatch.setattr(self_healing_daemon, "trigger_healing", lambda reason: healed.append(reason))

    self_healing_daemon.check_once()
    self_healing_daemon.check_once()
    assert healed == []

    self_healing_daemon.check_once()

    assert healed == ["SOCKS5 proxy health check failed for 3 checks"]


def test_self_healing_daemon_resets_latency_streak_after_success(monkeypatch):
    _reset_self_healing_counters(monkeypatch)
    healed: list[str] = []
    latencies = iter([250.0, 25.0, 250.0, 250.0])

    monkeypatch.setattr(self_healing_daemon, "MAX_LATENCY_MS", 150.0)
    monkeypatch.setattr(self_healing_daemon, "LATENCY_HEAL_FAILURES", 3)
    monkeypatch.setattr(self_healing_daemon, "ping_target", lambda *_args, **_kwargs: next(latencies))
    monkeypatch.setattr(self_healing_daemon, "check_proxy_health", lambda: True)
    monkeypatch.setattr(self_healing_daemon, "get_fin_wait2_count", lambda: 0)
    monkeypatch.setattr(self_healing_daemon, "trigger_healing", lambda reason: healed.append(reason))

    self_healing_daemon.check_once()
    self_healing_daemon.check_once()
    self_healing_daemon.check_once()
    self_healing_daemon.check_once()

    assert healed == []
    assert self_healing_daemon._consecutive_latency_failures == 2


def test_self_healing_daemon_defers_packet_loss_heal_until_failure_streak(monkeypatch):
    _reset_self_healing_counters(monkeypatch)
    healed: list[str] = []

    monkeypatch.setattr(self_healing_daemon, "PACKET_LOSS_HEAL_FAILURES", 3)
    monkeypatch.setattr(self_healing_daemon, "ping_target", lambda *_args, **_kwargs: float("inf"))
    monkeypatch.setattr(self_healing_daemon, "check_proxy_health", lambda: True)
    monkeypatch.setattr(self_healing_daemon, "get_fin_wait2_count", lambda: 0)
    monkeypatch.setattr(self_healing_daemon, "trigger_healing", lambda reason: healed.append(reason))

    self_healing_daemon.check_once()
    self_healing_daemon.check_once()
    assert healed == []

    self_healing_daemon.check_once()

    assert healed == ["Sustained packet loss for 3 checks"]


def test_self_healing_daemon_defers_fin_wait2_heal_until_failure_streak(monkeypatch):
    _reset_self_healing_counters(monkeypatch)
    healed: list[str] = []

    monkeypatch.setattr(self_healing_daemon, "FIN_WAIT2_HEAL_FAILURES", 2)
    monkeypatch.setattr(self_healing_daemon, "ping_target", lambda *_args, **_kwargs: 25.0)
    monkeypatch.setattr(self_healing_daemon, "check_proxy_health", lambda: True)
    monkeypatch.setattr(self_healing_daemon, "get_fin_wait2_count", lambda: 50)
    monkeypatch.setattr(self_healing_daemon, "trigger_healing", lambda reason: healed.append(reason))

    self_healing_daemon.check_once()
    assert healed == []

    self_healing_daemon.check_once()

    assert healed == ["FIN-WAIT-2 spike: 50 connections for 2 checks"]


def test_vpn_watchdog_detects_active_socks_port(monkeypatch):
    monkeypatch.setattr(vpn_watchdog, "SOCKS_HOST", "127.0.0.1")
    monkeypatch.setattr(vpn_watchdog, "SOCKS_PORT", 10808)
    monkeypatch.setattr(vpn_watchdog, "SOCKS_PORT_CANDIDATES", (10808, 10918))
    monkeypatch.setattr(
        vpn_watchdog,
        "_socks_handshake",
        lambda host, port, timeout=1.0: port == 10918,
    )
    monkeypatch.setattr(vpn_watchdog, "_curl_proxy_health", lambda port: (True, 42.0))

    assert vpn_watchdog.discover_socks_port() == 10918
    assert vpn_watchdog.check_proxy_health() == (True, 42.0)
    assert vpn_watchdog.SOCKS_PORT == 10918


def test_vpn_watchdog_curl_proxy_health_parses_204(monkeypatch):
    monkeypatch.setattr(
        vpn_watchdog.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="0.123 204",
            stderr="",
        ),
    )

    assert vpn_watchdog._curl_proxy_health(10918) == (True, pytest.approx(123.0))


def test_vpn_watchdog_defers_proxy_heal_until_failure_streak(monkeypatch):
    healed: list[str] = []

    class FakeHealer:
        def heal(self, reason):
            healed.append(reason)

        def force_close_stale(self):
            raise AssertionError("preemptive cleanup should not run")

    monkeypatch.setattr(vpn_watchdog, "ENABLE_HEAL", True)
    monkeypatch.setattr(vpn_watchdog, "PROXY_HEAL_FAILURES", 3)
    monkeypatch.setattr(vpn_watchdog, "check_connection_states", lambda: {
        "ESTAB": 1,
        "FIN-WAIT-2": 0,
        "CLOSE-WAIT": 0,
        "LAST-ACK": 0,
    })
    monkeypatch.setattr(vpn_watchdog, "check_proxy_health", lambda: (False, 0.0))
    monkeypatch.setattr(vpn_watchdog._metrics, "check_count", 0)

    watchdog = vpn_watchdog.VPNWatchdog()
    watchdog.healer = FakeHealer()

    watchdog._check_cycle()
    watchdog._check_cycle()
    assert healed == []

    watchdog._check_cycle()

    assert healed == ["Proxy health check failed 3 consecutive times"]
    assert vpn_watchdog._metrics.proxy_failure_streak == 3


def test_vpn_watchdog_resets_proxy_failure_streak_after_success(monkeypatch):
    proxy_results = iter([(False, 0.0), (True, 25.0), (False, 0.0), (False, 0.0)])
    healed: list[str] = []

    class FakeHealer:
        def heal(self, reason):
            healed.append(reason)

        def force_close_stale(self):
            raise AssertionError("preemptive cleanup should not run")

    monkeypatch.setattr(vpn_watchdog, "ENABLE_HEAL", True)
    monkeypatch.setattr(vpn_watchdog, "PROXY_HEAL_FAILURES", 3)
    monkeypatch.setattr(vpn_watchdog, "check_connection_states", lambda: {
        "ESTAB": 1,
        "FIN-WAIT-2": 0,
        "CLOSE-WAIT": 0,
        "LAST-ACK": 0,
    })
    monkeypatch.setattr(vpn_watchdog, "check_proxy_health", lambda: next(proxy_results))
    monkeypatch.setattr(vpn_watchdog._metrics, "check_count", 0)

    watchdog = vpn_watchdog.VPNWatchdog()
    watchdog.healer = FakeHealer()

    watchdog._check_cycle()
    watchdog._check_cycle()
    watchdog._check_cycle()
    watchdog._check_cycle()

    assert healed == []
    assert vpn_watchdog._metrics.proxy_failure_streak == 2


def test_vpn_watchdog_does_not_heal_when_metrics_mode(monkeypatch):
    called = False

    class FakeHealer:
        def heal(self, reason: str):
            nonlocal called
            called = True

        def force_close_stale(self):
            nonlocal called
            called = True

    monkeypatch.setattr(vpn_watchdog, "ENABLE_HEAL", False)
    monkeypatch.setattr(
        vpn_watchdog,
        "check_connection_states",
        lambda: {"ESTAB": 1, "FIN-WAIT-2": 99, "CLOSE-WAIT": 0, "LAST-ACK": 0},
    )
    monkeypatch.setattr(vpn_watchdog, "check_proxy_health", lambda: (True, 10.0))

    watchdog = vpn_watchdog.VPNWatchdog()
    watchdog.healer = FakeHealer()
    watchdog._check_cycle()

    assert called is False
