import json
from pathlib import Path

from src.integration.rollout_provenance import RolloutImageDigestGate, main


DIGEST_A = "x0tta6bl4/mesh-node@sha256:" + "a" * 64
DIGEST_B = "x0tta6bl4/mesh-operator@sha256:" + "b" * 64


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_command_entrypoints(root: Path) -> None:
    for relative in [
        "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py",
        "scripts/ops/verify_live_rollout_evidence_gate.py",
        "src/integration/rollout_provenance.py",
        "src/integration/current_evidence_rollup.py",
    ]:
        _write_text(root / relative, "")


def _raw(images, *, all_pinned=True, provenance_ready=True):
    return {
        "status": "VERIFIED HERE",
        "evidence_status": "VERIFIED HERE",
        "all_deploy_refs_digest_pinned": all_pinned,
        "runtime_image_provenance_ready": provenance_ready,
        "runtime_images": images,
    }


def _provenance(total=2, pinned=2, *, verified=True, retained=True, ready=True):
    return {
        "status": "VERIFIED HERE",
        "summary": {
            "all_deploy_images_have_verified_provenance": verified,
            "deploy_images_digest_pinned": pinned,
            "deploy_images_total": total,
            "runtime_image_digest_pinning_ready": ready,
            "runtime_image_provenance_artifacts_retained_here": retained,
        },
    }


def test_rollout_gate_blocks_tag_based_images(tmp_path):
    raw = tmp_path / "image-digests.json"
    provenance = tmp_path / "provenance.json"
    _write_json(raw, _raw(["x0tta6bl4/mesh-node:3.4.0"], all_pinned=False, provenance_ready=False))
    _write_json(provenance, _provenance(total=1, pinned=0, verified=False, retained=False, ready=False))

    report = RolloutImageDigestGate.load(raw, provenance).report()

    assert report["decision"] == "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"
    assert report["operator_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert report["ready_for_completion_rerun"] is False
    assert report["summary"]["can_close_image_digests_blocker"] is False
    assert report["summary"]["raw_deploy_images_digest_pinned"] == 0
    assert report["summary"]["missing_inputs_total"] == 1
    assert report["summary"]["operator_actions_total"] == 5
    assert report["summary"]["operator_command_entrypoints_missing"] == 0
    assert report["summary"]["operator_command_surface_ready"] is True
    assert report["missing_inputs"][0]["id"] == "live_rollout_image_digest_provenance"
    assert any(
        "scaffold_live_rollout_image_provenance_evidence.py" in command
        for command in report["missing_inputs"][0]["commands"]
    )
    assert {item["action_id"] for item in report["operator_command_checks"]} == {
        "render_template_pack",
        "verify_live_rollout_evidence_gate",
        "rerun_rollout_provenance",
        "rerun_current_evidence_rollup",
    }
    assert any("runtime_images must be digest-pinned" in error for error in report["blocking_preflight_errors"])


def test_rollout_gate_accepts_digest_pinned_images_with_retained_provenance(tmp_path):
    raw = tmp_path / "image-digests.json"
    provenance = tmp_path / "provenance.json"
    _write_json(raw, _raw([DIGEST_A, DIGEST_B]))
    _write_json(provenance, _provenance())

    report = RolloutImageDigestGate.load(raw, provenance).report()

    assert report["decision"] == "READY_TO_CLOSE"
    assert report["operator_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
    assert report["ready_for_completion_rerun"] is True
    assert report["summary"]["can_close_image_digests_blocker"] is True
    assert report["summary"]["raw_deploy_images_digest_pinned"] == 2
    assert report["summary"]["missing_inputs_total"] == 0
    assert report["operator_next_actions"] == []
    assert report["operator_command_checks"] == []
    assert report["missing_inputs"] == []
    assert report["blocking_preflight_errors"] == []


def test_rollout_cli_writes_fail_closed_report(tmp_path):
    _write_command_entrypoints(tmp_path)
    output_md = tmp_path / "rollout.md"
    exit_code = main(["--root", str(tmp_path), "--output-md", str(output_md), "--write-md", "--require-ready"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["decision"] == "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"
    assert report["summary"]["can_close_image_digests_blocker"] is False
    assert report["summary"]["operator_command_surface_ready"] is True
    assert "Live Rollout Image Digest Provenance Gate" in output_md.read_text(encoding="utf-8")
    assert "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR" in output_md.read_text(encoding="utf-8")
