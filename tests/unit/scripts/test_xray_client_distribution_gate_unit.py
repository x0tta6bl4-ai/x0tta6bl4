import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = ROOT / "x0tta6bl4-xray-vps" / "scripts" / "check-client-distribution-gate.sh"
GENERATOR_SCRIPT = ROOT / "x0tta6bl4-xray-vps" / "scripts" / "generate-live-client-profiles.sh"


def test_xray_client_distribution_scripts_shell_syntax() -> None:
    for script in (GATE_SCRIPT, GENERATOR_SCRIPT):
        proc = subprocess.run(
            ["bash", "-n", str(script)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr


def test_distribution_gate_blocks_bad_reality_short_id_and_unsupported_fingerprint() -> None:
    text = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "is_valid_reality_short_id" in text
    assert "^[0-9a-fA-F]*$" in text
    assert "${#value} <= 16" in text
    assert "${#value} % 2 == 0" in text
    assert "is_supported_reality_fingerprint" in text
    assert "chrome|firefox|safari|ios|android|edge|360|qq|random|randomized" in text
    assert "profile_fp" in text
    assert "unsupported Reality fingerprint" in text


def test_generator_emits_chrome_fingerprint_and_validates_short_id() -> None:
    text = GENERATOR_SCRIPT.read_text(encoding="utf-8")

    assert 'fp: "chrome"' in text
    assert "is_valid_reality_short_id" in text
    assert "Reality shortId must be even-length hex up to 16 chars" in text


def test_distribution_gate_does_not_restart_runtime() -> None:
    text = GATE_SCRIPT.read_text(encoding="utf-8")

    forbidden_patterns = [
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+xray",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None
