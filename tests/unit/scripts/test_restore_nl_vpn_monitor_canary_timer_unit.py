import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "ops" / "restore_nl_vpn_monitor_canary_timer.sh"
PHRASE = "APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER"


def test_restore_nl_vpn_monitor_script_shell_syntax() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_restore_nl_vpn_monitor_defaults_to_dry_run_without_ssh_write() -> None:
    env = os.environ.copy()
    env.pop("RESTORE_NL_VPN_MONITOR_CONFIRM", None)
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run", "--host", "nl"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "DRY_RUN=1" in proc.stdout
    assert PHRASE in proc.stdout
    assert "systemctl enable --now ghost-access-vpn-monitor.timer" in proc.stdout


def test_restore_nl_vpn_monitor_apply_requires_exact_phrase() -> None:
    env = os.environ.copy()
    env.pop("RESTORE_NL_VPN_MONITOR_CONFIRM", None)
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--apply", "--host", "nl"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 2
    assert PHRASE in proc.stderr


def test_restore_nl_vpn_monitor_has_narrow_write_scope() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ghost-access-vpn-monitor.timer" in text
    assert "ghost-access-vpn-monitor.service" in text
    assert "x0tta6bl4-runtime-state.service" in text

    forbidden_patterns = [
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
        r"ufw\s+",
        r"iptables\s+",
        r"nft\s+",
        r"x-ui\s+restart",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None
