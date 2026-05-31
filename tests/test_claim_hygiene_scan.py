from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import claim_hygiene_scan as scan  # noqa: E402


def test_uncaveated_production_ready_is_active(tmp_path: Path) -> None:
    path = tmp_path / "pitch.md"
    path.write_text("Status: Production Ready\n", encoding="utf-8")

    findings = scan.scan_file(path, "active_claim_surface")

    assert len(findings) == 1
    assert findings[0].kind == "production-ready"
    assert findings[0].caveated is False


def test_inline_caveat_suppresses_high_pps_claim(tmp_path: Path) -> None:
    path = tmp_path / "readme.md"
    path.write_text(
        "This is a functional baseline, not a claim of `>1M PPS` production throughput.\n",
        encoding="utf-8",
    )

    findings = scan.scan_file(path, "active_claim_surface")

    assert len(findings) == 1
    assert findings[0].kind == "high-pps"
    assert findings[0].caveated is True


def test_file_level_truth_surface_note_suppresses_legacy_draft(tmp_path: Path) -> None:
    path = tmp_path / "legacy-pitch.md"
    path.write_text(
        "\n".join(
            [
                "> Truth-surface note: historical draft.",
                "> Superseded for current readiness claims by STATUS_REALITY.md.",
                "> Production-ready wording below is not current production deployment evidence.",
                "",
                "Status: Production Ready",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan.scan_file(path, "active_claim_surface")

    assert findings
    assert {item.caveated for item in findings} == {True}


@pytest.mark.parametrize(
    "relative_path",
    [
        "docs/05-operations/project-completion-report-v1.4.0.md",
        "docs/05-operations/project-completion-report-v1.5.md",
    ],
)
def test_historical_operations_completion_reports_are_caveated(relative_path: str) -> None:
    findings = scan.scan_file(ROOT / relative_path, "active_claim_surface")

    assert findings
    assert {item.caveated for item in findings} == {True}


def test_truth_surface_doc_is_in_authoritative_zone() -> None:
    assert "docs/team/REPO_TRUTH_SURFACE.md" in scan.ZONE_PATHS["authoritative"]
    assert (ROOT / "docs/team/REPO_TRUTH_SURFACE.md").is_file()


def test_release_docs_are_active_claim_surface() -> None:
    assert "docs/release" in scan.ZONE_PATHS["active_claim_surface"]


def test_tooling_registry_exposes_claim_hygiene_front_door() -> None:
    registry = json.loads((ROOT / ".agent-coord/tooling_registry.json").read_text(encoding="utf-8"))

    assert (
        "bash scripts/agent-coord.sh claim_hygiene_scan --zone active_claim_surface --fail-on-active"
        in registry["front_door_commands"]
    )


@pytest.mark.parametrize("zone", ["authoritative", "active_claim_surface"])
def test_current_repo_claim_surfaces_have_no_active_hits(zone: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/claim_hygiene_scan.py",
            "--zone",
            zone,
            "--fail-on-active",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_coord_claim_hygiene_front_door() -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/agent-coord.sh",
            "claim_hygiene_scan",
            "--zone",
            "active_claim_surface",
            "--fail-on-active",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_verify_entrypoint_runs_claim_hygiene_gates() -> None:
    verify_script = (ROOT / "scripts/verify-v1.1.sh").read_text(encoding="utf-8")

    assert "Truth-surface claim hygiene" in verify_script
    assert "claim_hygiene_scan --zone authoritative --fail-on-active" in verify_script
    assert "claim_hygiene_scan --zone active_claim_surface --fail-on-active" in verify_script
