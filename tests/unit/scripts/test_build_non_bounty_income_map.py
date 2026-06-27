from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/build_non_bounty_income_map.py"


def test_build_non_bounty_income_map_writes_outputs(tmp_path: Path) -> None:
    output_json = tmp_path / "map.json"
    output_md = tmp_path / "map.md"
    artifact_dir = tmp_path / "artifacts"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--write-json",
            str(output_json),
            "--write-md",
            str(output_md),
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert stdout["status"] == "map_ready"
    assert stdout["funds_received_claim_allowed"] is False
    assert payload["selected_first"]
    assert "x0tta6bl4 Non-Bounty Income Map" in markdown
    assert stdout["written"]["artifacts"]
    for artifact in stdout["written"]["artifacts"]:
        assert Path(artifact).exists()
