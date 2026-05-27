import importlib.util
import json
from pathlib import Path

import src.integration.external_settlement as external_settlement
from src.integration.evidence_source_candidates import COLLECTOR_BY_KEY
from src.integration.rollout_provenance import RolloutImageDigestGate


ROOT = Path(__file__).resolve().parents[2]
TX_HASH = "0x" + "a" * 64
BLOCK_HASH = "0x" + "b" * 64
FROM_ADDRESS = "0x" + "1" * 40
TO_ADDRESS = "0x" + "2" * 40


def _load_script(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _valid_receipt() -> dict:
    payload = {
        "status": "VERIFIED HERE",
        "settlement_submitted": True,
        "destination_chain": "base-sepolia",
        "settlement_id": "settlement-2026-05-20-001",
        "token_symbol": "X0T",
        "transaction_receipt_status": "success",
        "block_number": 123456,
        "block_hash": BLOCK_HASH,
        "from_address": FROM_ADDRESS,
        "to_address": TO_ADDRESS,
        "transaction_hash": TX_HASH,
        "source_commands": [
            f"cast send 0x2222222222222222222222222222222222222222 settle {TX_HASH} --rpc-url $BASE_SEPOLIA_RPC_URL",
            f"cast receipt {TX_HASH} --rpc-url $BASE_SEPOLIA_RPC_URL",
        ],
        "explorer_url": f"https://sepolia.basescan.org/tx/{TX_HASH}",
        "template_only": False,
    }
    payload["packet_hash"] = external_settlement._packet_hash(payload)
    return payload


def _write_raw_bundle_fixture(root: Path, *, ready: bool) -> None:
    collectors = sorted(set(COLLECTOR_BY_KEY.values()))
    _write_json(
        root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                        }
                    ],
                }
                for collector_id in collectors
            ]
        },
    )
    _write_json(
        root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "summary": {"by_collector": {} if ready else {collector_id: 1 for collector_id in collectors}},
        },
    )
    for collector_id in collectors:
        payload = {
            "evidence_status": "VERIFIED HERE",
            "collector_id": collector_id,
            "raw_id": f"{collector_id}/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "production-operator-2026-05-20",
            "source_commands": [f"kubectl --context prod get {collector_id} -o json"],
            "production_ready": ready,
            "production_promotion_blockers": [] if ready else ["local runtime capture"],
        }
        if not ready:
            payload["claim_boundary"] = "local contract-validation bundle, not production evidence"
        _write_json(
            root / f".tmp/production-raw-evidence-operator-bundle/{collector_id}/operator-manifest.json",
            payload,
        )


def test_import_raw_evidence_bundle_wrapper_fails_closed_on_local_bundle(tmp_path):
    wrapper = _load_script(
        "import_production_raw_evidence_bundle",
        "scripts/ops/import_production_raw_evidence_bundle.py",
    )
    _write_raw_bundle_fixture(tmp_path, ready=False)
    output = tmp_path / "raw-import.json"

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--output-json",
        str(output),
        "--require-ready",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["raw_evidence_bundle_import_decision"] == "BLOCKED"
    assert report["summary"]["collectors_ready"] == 0
    assert report["installs_raw_evidence"] is False
    assert report["mutates_vpn_runtime"] is False


def test_import_raw_evidence_bundle_wrapper_accepts_ready_bundle(tmp_path):
    wrapper = _load_script(
        "import_production_raw_evidence_bundle_ready",
        "scripts/ops/import_production_raw_evidence_bundle.py",
    )
    _write_raw_bundle_fixture(tmp_path, ready=True)
    output = tmp_path / "raw-import.json"

    exit_code = wrapper.main(["--root", str(tmp_path), "--output-json", str(output), "--require-ready"])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["raw_evidence_bundle_import_decision"] == "READY_TO_INSTALL"
    assert report["summary"]["collectors_ready"] == len(COLLECTOR_BY_KEY)
    assert report["summary"]["ready_to_install"] is True


def test_external_settlement_evidence_wrapper_writes_non_live_gate(tmp_path):
    wrapper = _load_script(
        "verify_x0t_external_settlement_evidence",
        "scripts/ops/verify_x0t_external_settlement_evidence.py",
    )
    evidence = tmp_path / "settlement-submit.json"
    output = tmp_path / "evidence-report.json"
    _write_json(evidence, _valid_receipt())

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--evidence",
        str(evidence),
        "--output-json",
        str(output),
        "--require-ready",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["x0t_external_settlement_decision"] == "READY"
    assert report["summary"]["x0t_external_settlement_ready"] is True
    assert report["runs_live_rpc"] is False


def test_external_settlement_live_rpc_wrapper_requires_rpc_url(tmp_path):
    wrapper = _load_script(
        "verify_x0t_external_settlement_live_rpc",
        "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
    )
    evidence = tmp_path / "settlement-submit.json"
    output_rpc = tmp_path / "rpc-report.json"
    output_blocker = tmp_path / "blocker-report.json"
    _write_json(evidence, _valid_receipt())

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--evidence",
        str(evidence),
        "--output-rpc-json",
        str(output_rpc),
        "--output-blocker-json",
        str(output_blocker),
        "--require-ready",
    ])

    rpc_report = json.loads(output_rpc.read_text(encoding="utf-8"))
    blocker = json.loads(output_blocker.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert rpc_report["summary"]["retained_evidence_ready"] is True
    assert rpc_report["summary"]["rpc_url_available"] is False
    assert blocker["decision"] == "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT"


def test_external_settlement_collector_wrapper_fails_closed_without_rpc(tmp_path):
    wrapper = _load_script(
        "collect_x0t_external_settlement_evidence",
        "scripts/ops/collect_x0t_external_settlement_evidence.py",
    )
    evidence = tmp_path / "settlement-submit.json"

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--evidence",
        str(evidence),
        "--transaction-hash",
        TX_HASH,
        "--destination-chain",
        "base-sepolia",
        "--settlement-id",
        "settlement-2026-05-20-001",
        "--write-evidence",
        "--output",
        "text",
        "--require-ready",
    ])

    assert exit_code == 2
    assert evidence.exists() is False


def test_raw_evidence_collect_wrapper_accepts_raw_root_manifest_flag(tmp_path):
    from src.integration.operator_bundle_gate import main as operator_bundle_gate_main

    _write_raw_bundle_fixture(tmp_path, ready=False)
    output = tmp_path / "paid-client-collector.json"

    exit_code = operator_bundle_gate_main([
        "--root",
        str(tmp_path),
        "--evidence-key",
        "paid_client_path",
        "--raw-root",
        ".tmp/paid-client-serviceability-raw-evidence",
        "--output-json",
        str(output),
        "--require-ready",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert report["decision"] == "BLOCKED"
    assert report["goal_can_be_marked_complete"] is False


def test_external_settlement_scaffold_writes_templates_not_evidence(tmp_path):
    wrapper = _load_script(
        "scaffold_x0t_external_settlement_evidence",
        "scripts/ops/scaffold_x0t_external_settlement_evidence.py",
    )
    output = tmp_path / "scaffold-report.json"
    expected_evidence = "external-settlement-evidence/settlement-submit.json"

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--template-dir",
        "template-pack",
        "--expected-evidence",
        expected_evidence,
        "--output-json",
        str(output),
        "--write-template-files",
        "--force",
        "--require-written",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    template = tmp_path / "template-pack/settlement-submit.template.json"
    retained_evidence = tmp_path / expected_evidence
    template_payload = json.loads(template.read_text(encoding="utf-8"))
    template_gate = external_settlement.validate_evidence_file(template)

    assert exit_code == 0
    assert report["scaffold_decision"] == "TEMPLATE_ONLY_NOT_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["materializes_evidence"] is False
    assert report["runs_live_rpc"] is False
    assert report["submits_transaction"] is False
    assert report["mutates_vpn_runtime"] is False
    assert report["summary"]["template_files_written"] == 3
    assert report["summary"]["templates_marked_not_evidence"] is True
    assert report["summary"]["expected_evidence_file_exists"] is False
    assert retained_evidence.exists() is False
    assert template_payload["status"] == "TEMPLATE_ONLY"
    assert template_payload["_not_evidence"] is True
    assert template_payload["template_only"] is True
    assert template_gate.valid is False


def test_production_raw_evidence_template_pack_writes_templates_not_evidence(tmp_path):
    wrapper = _load_script(
        "generate_production_raw_evidence_template_pack",
        "scripts/ops/generate_production_raw_evidence_template_pack.py",
    )
    passport = tmp_path / "passport.json"
    output = tmp_path / "scaffold-report.json"
    _write_json(
        passport,
        {
            "required_evidence_files": [
                {
                    "kind": "raw_evidence",
                    "evidence_key": "live_spire_mtls",
                    "raw_id": "zero-trust-pqc/operator-manifest.json",
                    "operator_return_path": "operator-bundle/zero-trust-pqc/operator-manifest.json",
                    "retained_destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
                    "required_statuses": ["VERIFIED HERE"],
                    "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
                    "required_hash_binding_fields": ["evidence_root", "evidence_files[].sha256"],
                    "semantic_json_pointers": ["/environment"],
                    "production_evidence_requirements": ["operator-manifest environment must be production"],
                    "validation_commands": ["python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready"],
                },
                {
                    "kind": "raw_evidence",
                    "evidence_key": "live_spire_mtls",
                    "raw_id": "zero-trust-pqc/mtls-fail-closed.json",
                    "operator_return_path": "operator-bundle/zero-trust-pqc/mtls-fail-closed.json",
                    "retained_destination_path": ".tmp/zero-trust-pqc-raw-evidence/mtls-fail-closed.json",
                },
                {
                    "kind": "external_settlement",
                    "evidence_key": "external_settlement",
                    "operator_return_path": "external-settlement-evidence/settlement-submit.json",
                },
            ]
        },
    )

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--passport",
        str(passport),
        "--template-dir",
        "template-pack",
        "--operator-bundle-root",
        "operator-bundle",
        "--output-json",
        str(output),
        "--write-template-files",
        "--force",
        "--require-written",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    template = tmp_path / "template-pack/zero-trust-pqc/operator-manifest.json"
    operator_bundle_file = tmp_path / "operator-bundle/zero-trust-pqc/operator-manifest.json"
    template_payload = json.loads(template.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["scaffold_decision"] == "TEMPLATE_ONLY_NOT_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["materializes_evidence"] is False
    assert report["installs_raw_evidence"] is False
    assert report["runs_collectors"] is False
    assert report["runs_live_cluster"] is False
    assert report["mutates_vpn_runtime"] is False
    assert report["summary"]["raw_template_files_total"] == 2
    assert report["summary"]["template_files_total"] == 4
    assert report["summary"]["template_files_written"] == 4
    assert report["summary"]["templates_marked_not_evidence"] is True
    assert report["summary"]["expected_operator_bundle_files_total"] == 2
    assert report["summary"]["expected_operator_bundle_files_existing"] == 0
    assert operator_bundle_file.exists() is False
    assert template_payload["status"] == "TEMPLATE_ONLY"
    assert template_payload["evidence_status"] == "TEMPLATE_ONLY"
    assert template_payload["_not_evidence"] is True
    assert template_payload["template_only"] is True
    assert template_payload["collector_id"] == "zero-trust-pqc"
    assert template_payload["raw_id"] == "zero-trust-pqc/operator-manifest.json"
    assert template_payload["operator_return_path"] == "operator-bundle/zero-trust-pqc/operator-manifest.json"
    assert template_payload["production_ready"] is False
    assert template_payload["production_evidence_requirements"] == [
        "operator-manifest environment must be production"
    ]


def test_import_raw_evidence_bundle_rejects_generated_templates(tmp_path):
    generator = _load_script(
        "generate_production_raw_evidence_template_pack_for_import_rejection",
        "scripts/ops/generate_production_raw_evidence_template_pack.py",
    )
    importer = _load_script(
        "import_production_raw_evidence_bundle_template_rejection",
        "scripts/ops/import_production_raw_evidence_bundle.py",
    )
    collectors = sorted(set(COLLECTOR_BY_KEY.values()))
    raw_items = [
        {
            "kind": "raw_evidence",
            "evidence_key": evidence_key,
            "raw_id": f"{collector_id}/operator-manifest.json",
            "operator_return_path": f"operator-bundle/{collector_id}/operator-manifest.json",
            "retained_destination_path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
            "required_statuses": ["VERIFIED HERE"],
            "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
        }
        for evidence_key, collector_id in COLLECTOR_BY_KEY.items()
    ]
    _write_json(
        tmp_path / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                        }
                    ],
                }
                for collector_id in collectors
            ]
        },
    )
    _write_json(
        tmp_path / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {"status": "VERIFIED HERE", "summary": {"by_collector": {}}},
    )
    passport = tmp_path / "passport.json"
    _write_json(passport, {"required_evidence_files": raw_items})

    generated = tmp_path / "generated.json"
    assert generator.main([
        "--root",
        str(tmp_path),
        "--passport",
        str(passport),
        "--template-dir",
        "operator-bundle",
        "--operator-bundle-root",
        "operator-bundle",
        "--output-json",
        str(generated),
        "--write-template-files",
        "--force",
        "--require-written",
    ]) == 0

    output = tmp_path / "raw-import.json"
    exit_code = importer.main([
        "--root",
        str(tmp_path),
        "--bundle-root",
        "operator-bundle",
        "--output-json",
        str(output),
        "--require-ready",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    blocking_text = json.dumps(report["evidence_key_reports"])
    assert exit_code == 2
    assert report["raw_evidence_bundle_import_decision"] == "BLOCKED"
    assert report["summary"]["source_files_found"] == len(COLLECTOR_BY_KEY)
    assert report["summary"]["collectors_ready"] == 0
    assert report["summary"]["ready_to_install"] is False
    assert report["installs_raw_evidence"] is False
    assert "template/mock/placeholder markers must be absent" in blocking_text
    assert "production_ready must be true for source-candidate promotion" in blocking_text


def test_live_rollout_image_provenance_scaffold_writes_templates_not_evidence(tmp_path):
    wrapper = _load_script(
        "scaffold_live_rollout_image_provenance_evidence",
        "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py",
    )
    output = tmp_path / "scaffold-report.json"
    expected_evidence = "production-raw-evidence-operator-bundle/live-rollout/image-digests.json"

    exit_code = wrapper.main([
        "--root",
        str(tmp_path),
        "--template-dir",
        "template-pack",
        "--expected-evidence",
        expected_evidence,
        "--output-json",
        str(output),
        "--write-template-files",
        "--force",
        "--require-written",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    image_template = tmp_path / "template-pack/image-digests.template.json"
    provenance_template = tmp_path / "template-pack/deploy-image-provenance-gate.template.json"
    retained_evidence = tmp_path / expected_evidence
    template_payload = json.loads(image_template.read_text(encoding="utf-8"))
    template_gate = RolloutImageDigestGate.load(image_template, provenance_template).report()

    assert exit_code == 0
    assert report["scaffold_decision"] == "TEMPLATE_ONLY_NOT_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["materializes_evidence"] is False
    assert report["contacts_registry"] is False
    assert report["contacts_cluster"] is False
    assert report["runs_cosign"] is False
    assert report["mutates_vpn_runtime"] is False
    assert report["summary"]["template_files_written"] == 4
    assert report["summary"]["templates_marked_not_evidence"] is True
    assert report["summary"]["expected_evidence_file_exists"] is False
    assert report["summary"]["template_validation_rejects_as_rollout_evidence"] is True
    assert retained_evidence.exists() is False
    assert template_payload["status"] == "TEMPLATE_ONLY"
    assert template_payload["_not_evidence"] is True
    assert template_payload["template_only"] is True
    assert template_gate["summary"]["can_close_image_digests_blocker"] is False
