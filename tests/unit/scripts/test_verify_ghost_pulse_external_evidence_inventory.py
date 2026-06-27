import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _current_proof() -> dict:
    return json.loads((ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json").read_text(encoding="utf-8"))


def _write_fixture_proof(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _fixture_inventory_report(inventory) -> dict:
    return {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_inventory.v1",
        "status": "PASS",
        "inventory_status": inventory.STATUS_COMPLETE_WITH_GAPS,
        "proof": "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
        "rows": [
            {
                "claim_id": "packet_capture",
                "title": "Sender and receiver packet captures",
                "json": "docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json",
                "json_exists": True,
                "markdown": "docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.md",
                "markdown_exists": True,
                "proof_status": "VERIFIED",
                "validation_status": "VERIFIED",
                "proof_errors": [],
                "validation_errors": [],
                "sha256": "a" * 64,
                "failures": [],
            },
            {
                "claim_id": "kernel_attach",
                "title": "XDP attach and map-counter evidence",
                "json": "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json",
                "json_exists": True,
                "markdown": "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md",
                "markdown_exists": True,
                "proof_status": "INVALID",
                "validation_status": "INVALID",
                "proof_errors": ["status must be VERIFIED"],
                "validation_errors": ["status must be VERIFIED"],
                "sha256": "b" * 64,
                "failures": [],
            },
        ],
        "failures": [],
        "verified": ["packet_capture"],
        "invalid": ["kernel_attach"],
        "missing": [],
        "gap_audit": {
            "path": "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json",
            "status": "PASS",
            "replacement_required": ["kernel_attach"],
            "expected_replacement_required": ["kernel_attach"],
            "covered_replacement_required": ["kernel_attach"],
            "missing_replacement_rows": [],
            "contract_mismatches": [],
            "failures": [],
        },
        "claim_boundary": {
            "note": "External evidence inventory only; this report does not promote proof-gate claims.",
            "proof_claim_boundary": {
                "kernel_attach_verified": False,
                "production_ready": False,
                "stealth_verified": False,
                "whitelist_verified": False,
            },
        },
    }


def test_external_inventory_accepts_current_incomplete_inventory():
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_current",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )

    report = inventory.build_report(
        root=ROOT,
        proof_path=ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
    )

    assert report["status"] == "PASS"
    assert report["inventory_status"] == inventory.STATUS_COMPLETE_WITH_GAPS
    assert report["missing"] == []
    assert report["verified"] == ["kernel_attach", "packet_capture", "baseline_timing_comparison"]
    assert set(report["invalid"]) == {
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    }
    assert report["gap_audit"]["status"] == "PASS"
    assert report["gap_audit"]["replacement_required"] == [
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]
    assert report["gap_audit"]["covered_replacement_required"] == [
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]


def test_external_inventory_writes_and_verifies_saved_report(tmp_path, monkeypatch):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_saved",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    report = _fixture_inventory_report(inventory)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md"

    paths = inventory.write_report_outputs(tmp_path, report, output_json, output_md)
    expected = inventory.stable_subset(report)

    def fake_build_report(
        root,
        proof_path,
        *,
        gap_audit_path,
        check_proof_consistency=True,
        check_gap_audit_consistency=True,
    ):
        assert root == tmp_path
        assert proof_path == tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
        assert gap_audit_path == tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
        assert check_proof_consistency is True
        assert check_gap_audit_consistency is True
        return expected

    monkeypatch.setattr(inventory, "build_report", fake_build_report)

    assert inventory.verify_saved_report(paths["latest_json"], tmp_path) == []
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert saved["bundle"].startswith("docs/verification/ghost-pulse-external-evidence-inventory-")
    assert saved["artifacts"]["inventory_latest_json"] == (
        "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    )
    assert saved["artifacts"]["inventory_latest_md"] == (
        "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md"
    )
    assert paths["latest_json"].read_bytes() == paths["bundle_json"].read_bytes()
    assert paths["latest_md"].read_bytes() == paths["bundle_md"].read_bytes()
    assert paths["latest_md"].read_text(encoding="utf-8") == inventory.render_markdown(saved)


def test_external_inventory_saved_report_rejects_stale_stable_fields(tmp_path, monkeypatch):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_stale_saved",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    report = _fixture_inventory_report(inventory)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md"
    paths = inventory.write_report_outputs(tmp_path, report, output_json, output_md)
    expected = inventory.stable_subset(report)
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    saved["verified"] = []
    stale_json = json.dumps(saved, indent=2, sort_keys=True)
    paths["latest_json"].write_text(stale_json, encoding="utf-8")
    paths["bundle_json"].write_text(stale_json, encoding="utf-8")

    def fake_build_report(
        _root,
        _proof_path,
        *,
        gap_audit_path,
        check_proof_consistency=True,
        check_gap_audit_consistency=True,
    ):
        assert gap_audit_path == tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
        assert check_proof_consistency is True
        assert check_gap_audit_consistency is True
        return expected

    monkeypatch.setattr(inventory, "build_report", fake_build_report)

    failures = inventory.verify_saved_report(paths["latest_json"], tmp_path)

    assert "external evidence inventory stable fields do not match current proof/gap state" in failures


def test_external_inventory_saved_report_can_skip_recursive_consistency_checks(tmp_path, monkeypatch):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_skip_recursive_checks",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    report = _fixture_inventory_report(inventory)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md"
    paths = inventory.write_report_outputs(tmp_path, report, output_json, output_md)
    expected = inventory.stable_subset(report)

    def fake_build_report(
        _root,
        _proof_path,
        *,
        gap_audit_path,
        check_proof_consistency=True,
        check_gap_audit_consistency=True,
    ):
        assert gap_audit_path == tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
        assert check_proof_consistency is False
        assert check_gap_audit_consistency is False
        return expected

    monkeypatch.setattr(inventory, "build_report", fake_build_report)

    assert inventory.verify_saved_report(
        paths["latest_json"],
        tmp_path,
        check_proof_consistency=False,
        check_gap_audit_consistency=False,
    ) == []


def test_external_inventory_rejects_stale_proof_row_status(tmp_path):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_stale",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    payload = _current_proof()
    for row in payload["proof_rows"]:
        if row["claim_id"] == "packet_capture":
            row["status"] = "INVALID"
            row["errors"] = ["stale fixture"]
            break
    proof_path = _write_fixture_proof(tmp_path, payload)

    report = inventory.build_report(
        root=ROOT,
        proof_path=proof_path,
        check_proof_consistency=False,
    )

    assert report["status"] == "FAIL"
    assert "packet_capture: proof row status does not match current evidence validation" in report["failures"]
    assert "packet_capture: proof row errors do not match current evidence validation" in report["failures"]


def test_external_inventory_rejects_missing_markdown(tmp_path):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_missing_md",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    source_proof = ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    payload = _current_proof()
    verify_root = tmp_path / "docs/verification"
    verify_root.mkdir(parents=True)
    proof_path = verify_root / "GHOST_PULSE_PROOF_GATE_LATEST.json"
    proof_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    for row in payload["proof_rows"]:
        evidence = row.get("evidence")
        if isinstance(evidence, str) and evidence.startswith("docs/verification/GHOST_PULSE_"):
            source = ROOT / evidence
            destination = tmp_path / evidence
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            source_md = source.with_suffix(".md")
            if source_md.exists() and "PACKET_CAPTURE" not in source.name:
                destination.with_suffix(".md").write_bytes(source_md.read_bytes())

    report = inventory.build_report(
        root=tmp_path,
        proof_path=proof_path,
        check_proof_consistency=False,
        check_gap_audit_consistency=False,
    )

    assert report["status"] == "FAIL"
    assert "packet_capture: required external evidence markdown is missing" in report["failures"]
    assert source_proof.exists()


def test_external_inventory_rejects_stale_gap_audit_replacement_list(tmp_path):
    inventory = _load_script(
        "verify_ghost_pulse_external_evidence_inventory_stale_gap",
        "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    )
    gap_audit_path = tmp_path / "gap-audit.json"
    payload = json.loads(
        (ROOT / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json").read_text(
            encoding="utf-8"
        )
    )
    payload["replacement_required"] = []
    gap_audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report = inventory.build_report(
        root=ROOT,
        proof_path=ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
        gap_audit_path=gap_audit_path,
        check_proof_consistency=False,
    )

    assert report["status"] == "FAIL"
    assert "gap audit replacement_required does not match external inventory gaps" in report["failures"]
