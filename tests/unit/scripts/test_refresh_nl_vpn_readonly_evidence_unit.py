import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "refresh_nl_vpn_readonly_evidence.sh"


def test_refresh_nl_vpn_readonly_evidence_shell_syntax() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_refresh_nl_vpn_readonly_evidence_is_readonly_for_vpn_runtime() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden_patterns = [
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
        r"send_legacy_no_progress_nudge\.py",
        r"send_legacy_client_migration_message\.py",
        r"--apply",
        r"SEND_LEGACY_NO_PROGRESS_NUDGE",
        r"SEND_LEGACY_MIGRATION",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None

    expected_services = {
        "ghost-access-transport-usage-evidence.service",
        "ghost-access-live-subscription-payload-check.service",
        "ghost-access-legacy-migration-reply-collector.service",
        "ghost-access-legacy-migration-progress.service",
        "ghost-access-legacy-no-progress-nudge-dry-run.service",
    }
    for service in expected_services:
        assert service in text

    expected_outputs = {
        "nl-transport-usage-latest.json",
        "nl-live-subscription-payload-latest.json",
        "nl-legacy-no-progress-nudge-dry-run-latest.json",
        "nl-legacy-client-migration-progress-2026-06-05.json",
        "nl-legacy-client-migration-replies-2026-06-05.json",
    }
    for output in expected_outputs:
        assert output in text
