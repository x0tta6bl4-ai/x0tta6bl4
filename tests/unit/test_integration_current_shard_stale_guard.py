import json
from pathlib import Path

from src.integration.current_shard_stale_guard import build_report, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_shard_stale_guard_passes_clear_current_shards(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/example-current.json",
        {
            "schema_version": "x0tta6bl4-example-v1-repo-generated",
            "summary": {
                "current_raw_files_installed": 0,
                "pipeline_raw_files_reported_installed": 0,
            },
        },
    )

    report = build_report(tmp_path)

    assert report["decision"] == "CURRENT_SHARDS_CLEAR"
    assert report["ready"] is True
    assert report["summary"]["current_shards_scanned"] == 1
    assert report["summary"]["findings_total"] == 0
    assert report["summary"]["generic_status_blocking"] == 0
    assert report["summary"]["legacy_status_map_operator_required"] == 0
    assert report["summary"]["legacy_status_map_operator_inputs_required"] == 0
    assert report["summary"]["status_observations_total"] == 0
    assert report["summary"]["generic_status_operator_required"] == 0
    assert report["mutates_files"] is False


def test_current_shard_stale_guard_blocks_source_restored_generic_status_and_legacy_counts(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/stale-current.json",
        {
            "schema_version": "x0tta6bl4-example-v1-source-restored",
            "checklist": [
                {
                    "id": "legacy-blocker",
                    "status": "BLOCKING",
                },
                {
                    "id": "operator-required",
                    "status": "OPERATOR_REQUIRED",
                },
                {
                    "id": "operator-inputs-required",
                    "status": "OPERATOR_INPUTS_REQUIRED",
                },
                {
                    "id": "blocked",
                    "status": "BLOCKED",
                },
                {
                    "id": "config",
                    "status": "CONFIG_REQUIRED",
                }
            ],
            "summary": {
                "checklist_total": 47,
                "checklist_passed": 39,
                "current_raw_files_installed": 0,
                "pipeline_raw_files_reported_installed": 30,
            },
        },
    )

    report = build_report(tmp_path)

    assert report["decision"] == "CURRENT_SHARDS_BLOCKED_ON_STALE_MARKERS"
    assert report["ready"] is False
    assert report["summary"]["source_restored_markers"] == 1
    assert report["summary"]["generic_status_blocking"] == 1
    assert report["summary"]["stale_completion_audit_count_markers"] == 1
    assert report["summary"]["raw_install_count_contradictions"] == 1
    assert report["summary"]["status_observations_total"] == 4
    assert report["summary"]["generic_status_operator_required"] == 1
    assert report["summary"]["legacy_status_operator_inputs_required"] == 1
    assert report["summary"]["legacy_status_blocked"] == 1
    assert report["summary"]["config_required_status"] == 1
    assert report["summary"]["findings_total"] == 4
    assert any(finding["kind"] == "generic_status_blocking" for finding in report["findings"])
    assert any(
        observation["kind"] == "generic_status_operator_required"
        for observation in report["status_observations"]
    )


def test_current_shard_stale_guard_observes_legacy_statuses_without_blocking(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/legacy-status-current.json",
        {
            "schema_version": "x0tta6bl4-example-v1-repo-generated",
            "items": [
                {"id": "operator-required", "status": "OPERATOR_REQUIRED"},
                {"id": "config-required", "status": "CONFIG_REQUIRED"},
            ],
        },
    )

    report = build_report(tmp_path)

    assert report["decision"] == "CURRENT_SHARDS_CLEAR"
    assert report["ready"] is True
    assert report["summary"]["findings_total"] == 0
    assert report["summary"]["status_observations_total"] == 2
    assert report["summary"]["generic_status_operator_required"] == 1
    assert report["summary"]["config_required_status"] == 1


def test_current_shard_stale_guard_blocks_legacy_status_map_keys(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/legacy-status-map-current.json",
        {
            "schema_version": "x0tta6bl4-example-v1-repo-generated",
            "evidence_key_acceptance": [
                {
                    "evidence_key": "external_settlement",
                    "statuses": {
                        "OPERATOR_REQUIRED": 1,
                        "OPERATOR_INPUTS_REQUIRED": 2,
                    },
                }
            ],
        },
    )

    report = build_report(tmp_path)

    assert report["decision"] == "CURRENT_SHARDS_BLOCKED_ON_STALE_MARKERS"
    assert report["ready"] is False
    assert report["summary"]["legacy_status_map_operator_required"] == 1
    assert report["summary"]["legacy_status_map_operator_inputs_required"] == 1
    assert report["summary"]["findings_total"] == 2
    assert {finding["kind"] for finding in report["findings"]} == {
        "legacy_status_map_operator_required",
        "legacy_status_map_operator_inputs_required",
    }


def test_current_shard_stale_guard_does_not_recount_its_own_status_observations(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/integration-spine-current-shard-stale-guard-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-current-shard-stale-guard-v1-repo-generated",
            "status_observations": [
                {
                    "kind": "generic_status_operator_required",
                    "status": "OPERATOR_REQUIRED",
                    "path": "$.legacy.status",
                }
            ],
            "actual": {"status": "CONFIG_REQUIRED"},
        },
    )

    report = build_report(tmp_path)

    assert report["ready"] is True
    assert report["summary"]["status_observations_total"] == 1
    assert report["summary"]["generic_status_operator_required"] == 0
    assert report["summary"]["config_required_status"] == 1


def test_current_shard_stale_guard_cli_require_clear_returns_two_when_blocked(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/stale-current.json",
        {"schema_version": "x0tta6bl4-example-v1-source-restored"},
    )
    output_json = tmp_path / "guard.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output_json), "--require-clear"])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["decision"] == "CURRENT_SHARDS_BLOCKED_ON_STALE_MARKERS"
