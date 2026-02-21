import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.network.webrtc_leak_fix as mod

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_platform_path_resolution(tmp_path):
    fix = mod.WebRTCLeakFix()
    fix.home = tmp_path

    fix.system = "Linux"
    assert fix.get_chrome_policy_path() == Path("/etc/opt/chrome/policies/managed")

    fix.system = "Darwin"
    assert fix.get_chrome_policy_path() == tmp_path / "Library/Application Support/Google/Chrome"

    fix.system = "Windows"
    assert str(fix.get_chrome_policy_path()) == "C:/Program Files (x86)/Google/Chrome/Application"

    fix.system = "Unknown"
    assert fix.get_chrome_policy_path() is None


def test_firefox_profile_resolution(tmp_path):
    fix = mod.WebRTCLeakFix()
    fix.home = tmp_path
    fix.system = "Linux"

    firefox_root = tmp_path / ".mozilla/firefox"
    firefox_root.mkdir(parents=True)
    (firefox_root / "abc.default-release").mkdir()
    (firefox_root / "profile-alt").mkdir()

    assert fix.get_firefox_profile_path() == firefox_root / "abc.default-release"

    fix.system = "Unknown"
    assert fix.get_firefox_profile_path() is None


def test_apply_chrome_fix_success_and_missing_path(tmp_path, monkeypatch):
    fix = mod.WebRTCLeakFix()

    chrome_policy_dir = tmp_path / "chrome-policies"
    monkeypatch.setattr(fix, "get_chrome_policy_path", lambda: chrome_policy_dir)

    assert fix.apply_chrome_fix() is True
    policy_file = chrome_policy_dir / "webrtc_fix.json"
    assert policy_file.exists()
    policy = json.loads(policy_file.read_text())
    assert policy["WebRtcUdpPortRange"] == ""
    assert policy["WebRtcEventLogCollectionAllowed"] is False

    monkeypatch.setattr(fix, "get_chrome_policy_path", lambda: None)
    assert fix.apply_chrome_fix() is False


def test_apply_firefox_fix_success_and_missing_profile(tmp_path, monkeypatch):
    fix = mod.WebRTCLeakFix()

    profile = tmp_path / "xyz.default-release"
    profile.mkdir(parents=True)
    (profile / "user.js").write_text('user_pref("existing.pref", true);\n')

    monkeypatch.setattr(fix, "get_firefox_profile_path", lambda: profile)
    assert fix.apply_firefox_fix() is True

    content = (profile / "user.js").read_text()
    assert "x0tta6bl4 WebRTC Leak Fix" in content
    assert 'user_pref("media.peerconnection.enabled", false);' in content
    assert 'user_pref("existing.pref", true);' in content

    monkeypatch.setattr(fix, "get_firefox_profile_path", lambda: None)
    assert fix.apply_firefox_fix() is False


def test_apply_system_wide_fix_linux_and_non_linux(monkeypatch):
    fix = mod.WebRTCLeakFix()

    fix.system = "Darwin"
    assert fix.apply_system_wide_fix() is False

    calls = {"count": 0}

    def _fake_run(*_args, **_kwargs):
        calls["count"] += 1
        return SimpleNamespace(returncode=0)

    import subprocess

    monkeypatch.setattr(subprocess, "run", _fake_run)
    fix.system = "Linux"
    assert fix.apply_system_wide_fix() is True
    assert calls["count"] == 6


def test_apply_system_wide_fix_exception_path(monkeypatch):
    fix = mod.WebRTCLeakFix()
    fix.system = "Linux"

    def _raise(*_args, **_kwargs):
        raise RuntimeError("iptables not available")

    import subprocess

    monkeypatch.setattr(subprocess, "run", _raise)
    assert fix.apply_system_wide_fix() is False


def test_apply_browser_fixes_aggregates_results(monkeypatch):
    fix = mod.WebRTCLeakFix()

    monkeypatch.setattr(fix, "apply_chrome_fix", lambda: True)
    monkeypatch.setattr(fix, "apply_firefox_fix", lambda: False)
    monkeypatch.setattr(fix, "apply_system_wide_fix", lambda: True)

    assert fix.apply_browser_fixes() == {
        "chrome": True,
        "firefox": False,
        "system_wide": True,
    }


def test_check_webrtc_status_and_iptables_error(tmp_path, monkeypatch):
    fix = mod.WebRTCLeakFix()
    fix.system = "Linux"

    chrome_dir = tmp_path / "chrome"
    chrome_dir.mkdir()
    (chrome_dir / "webrtc_fix.json").write_text("{}")

    firefox_profile = tmp_path / "default-profile"
    firefox_profile.mkdir()
    (firefox_profile / "user.js").write_text("// test")

    monkeypatch.setattr(fix, "get_chrome_policy_path", lambda: chrome_dir)
    monkeypatch.setattr(fix, "get_firefox_profile_path", lambda: firefox_profile)

    import subprocess

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(stdout="DROP udp -- 0.0.0.0/0 0.0.0.0/0 udp dpt:3478"),
    )
    status = fix.check_webrtc_status()
    assert status["chrome_policy_exists"] is True
    assert status["firefox_prefs_exists"] is True
    assert status["system_rules_active"] is True

    def _raise(*_args, **_kwargs):
        raise RuntimeError("iptables error")

    monkeypatch.setattr(subprocess, "run", _raise)
    status_err = fix.check_webrtc_status()
    assert status_err["chrome_policy_exists"] is True
    assert status_err["firefox_prefs_exists"] is True
    assert status_err["system_rules_active"] is False


def test_get_webrtc_fix_singleton():
    mod._webrtc_fix = None
    first = mod.get_webrtc_fix()
    second = mod.get_webrtc_fix()
    assert first is second
