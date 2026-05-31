import json
from pathlib import Path

import src.integration.external_settlement as external_settlement
from src.integration.external_settlement import (
    build_capture_preflight_report,
    build_blocker_report,
    capture_evidence_from_rpc,
    main,
    validate_evidence_file,
    verify_live_rpc,
)


TX_HASH = "0x" + "a" * 64
BLOCK_HASH = "0x" + "b" * 64
FROM_ADDRESS = "0x" + "1" * 40
TO_ADDRESS = "0x" + "2" * 40


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
            "cast send 0x2222222222222222222222222222222222222222 settle --rpc-url $BASE_SEPOLIA_RPC_URL",
            f"cast receipt {TX_HASH} --rpc-url $BASE_SEPOLIA_RPC_URL",
        ],
        "explorer_url": f"https://sepolia.basescan.org/tx/{TX_HASH}",
        "template_only": False,
    }
    payload["packet_hash"] = external_settlement._packet_hash(payload)
    return payload


def _rpc_result(method: str, params: list):
    if method == "eth_chainId":
        return hex(84532)
    if method == "eth_getTransactionReceipt":
        return {
            "transactionHash": TX_HASH,
            "blockHash": BLOCK_HASH,
            "blockNumber": hex(123456),
            "status": "0x1",
            "from": FROM_ADDRESS,
            "to": TO_ADDRESS,
        }
    if method == "eth_getTransactionByHash":
        return {
            "hash": TX_HASH,
            "blockNumber": hex(123456),
            "from": FROM_ADDRESS,
            "to": TO_ADDRESS,
        }
    raise AssertionError(f"unexpected RPC method {method}")


def test_validate_evidence_rejects_missing_and_template_files(tmp_path):
    missing = validate_evidence_file(tmp_path / "missing.json")
    assert missing.found is False
    assert missing.valid is False

    template = tmp_path / "settlement-submit.json"
    _write_json(
        template,
        {
            "status": "TEMPLATE_ONLY",
            "settlement_submitted": False,
            "destination_chain": "<chain>",
            "settlement_id": "<settlement>",
            "token_symbol": "X0T",
            "transaction_hash": "0x1234",
            "template_only": True,
        },
    )

    result = validate_evidence_file(template)

    assert result.found is True
    assert result.valid is False
    assert "status/evidence_status must be VERIFIED HERE" in result.errors
    assert "template_only must not be true" in result.errors


def test_validate_evidence_accepts_real_shaped_receipt(tmp_path):
    evidence_path = tmp_path / "settlement-submit.json"
    _write_json(evidence_path, _valid_receipt())

    result = validate_evidence_file(evidence_path)

    assert result.valid is True
    assert result.transaction_hash == TX_HASH
    assert result.destination_chain == "base-sepolia"
    assert result.expected_chain_id == 84532


def test_validate_evidence_rejects_packet_hash_mismatch(tmp_path):
    evidence_path = tmp_path / "settlement-submit.json"
    payload = _valid_receipt()
    payload["packet_hash"] = "c" * 64
    _write_json(evidence_path, payload)

    result = validate_evidence_file(evidence_path)

    assert result.valid is False
    assert "packet_hash must match the canonical receipt payload" in result.errors


def test_validate_evidence_rejects_wrong_explorer_host(tmp_path):
    evidence_path = tmp_path / "settlement-submit.json"
    payload = _valid_receipt()
    payload["explorer_url"] = f"https://basescan.org/tx/{TX_HASH}"
    payload["packet_hash"] = external_settlement._packet_hash(payload)
    _write_json(evidence_path, payload)

    result = validate_evidence_file(evidence_path)

    assert result.valid is False
    assert "explorer_url host must match destination_chain" in result.errors


def test_validate_evidence_requires_source_command_transaction_hash(tmp_path):
    evidence_path = tmp_path / "settlement-submit.json"
    payload = _valid_receipt()
    payload["source_commands"] = [
        "cast send 0x2222222222222222222222222222222222222222 settle --rpc-url $BASE_SEPOLIA_RPC_URL",
        "cast receipt latest --rpc-url $BASE_SEPOLIA_RPC_URL",
    ]
    payload["packet_hash"] = external_settlement._packet_hash(payload)
    _write_json(evidence_path, payload)

    result = validate_evidence_file(evidence_path)

    assert result.valid is False
    assert "source_commands must include the exact transaction hash" in result.errors


def test_live_rpc_gate_stays_blocked_without_rpc_url(tmp_path):
    evidence_path = tmp_path / "settlement-submit.json"
    _write_json(evidence_path, _valid_receipt())
    evidence = validate_evidence_file(evidence_path)

    rpc_report = verify_live_rpc(evidence, None)
    blocker = build_blocker_report(evidence.report(), rpc_report)

    assert rpc_report["summary"]["retained_evidence_ready"] is True
    assert rpc_report["summary"]["rpc_url_available"] is False
    assert rpc_report["rpc_endpoint"] is None
    assert rpc_report["rpc_endpoint_present"] is False
    assert rpc_report["rpc_endpoint_redacted"] is True
    assert rpc_report["summary"]["x0t_external_settlement_live_rpc_ready"] is False
    assert blocker["decision"] == "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT"
    assert blocker["summary"]["evidence_file_valid"] is True
    assert blocker["summary"]["live_rpc_ready"] is False


def test_capture_evidence_from_rpc_builds_valid_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(external_settlement, "_rpc_call", lambda rpc_url, method, params: _rpc_result(method, params))

    captured, errors = capture_evidence_from_rpc(
        TX_HASH,
        "base-sepolia",
        "settlement-2026-05-20-001",
        "https://rpc.example",
        ".tmp/external-settlement-evidence/settlement-submit.json",
    )

    assert errors == []
    assert captured is not None
    assert captured["status"] == "VERIFIED HERE"
    assert captured["transaction_hash"] == TX_HASH
    assert captured["packet_hash"]
    evidence_path = tmp_path / "settlement-submit.json"
    _write_json(evidence_path, captured)
    assert validate_evidence_file(evidence_path).valid is True


def test_capture_evidence_from_rpc_rejects_chain_mismatch(monkeypatch):
    monkeypatch.setattr(external_settlement, "_rpc_call", lambda rpc_url, method, params: _rpc_result(method, params))

    captured, errors = capture_evidence_from_rpc(
        TX_HASH,
        "base-mainnet",
        "settlement-2026-05-20-001",
        "https://rpc.example",
    )

    assert captured is None
    assert any("observed chain id" in error for error in errors)


def test_capture_preflight_validates_inputs_without_rpc(monkeypatch):
    monkeypatch.setattr(
        external_settlement,
        "_rpc_call",
        lambda rpc_url, method, params: (_ for _ in ()).throw(AssertionError("RPC must not be called")),
    )

    report = build_capture_preflight_report(
        TX_HASH,
        "base-sepolia",
        "settlement-2026-05-20-001",
        "https://base-sepolia-rpc.invalid",
    )

    assert report["decision"] == "CAPTURE_INPUTS_READY"
    assert report["summary"]["capture_inputs_ready"] is True
    assert report["input_status"]["expected_chain_id"] == 84532
    assert report["runs_live_rpc"] is False
    assert report["materializes_evidence"] is False


def test_capture_preflight_rejects_missing_inputs_without_rpc(monkeypatch):
    monkeypatch.setattr(
        external_settlement,
        "_rpc_call",
        lambda rpc_url, method, params: (_ for _ in ()).throw(AssertionError("RPC must not be called")),
    )

    report = build_capture_preflight_report(
        "0x1234",
        "base-sepolia",
        "<settlement>",
        "",
    )

    assert report["decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert report["summary"]["capture_inputs_ready"] is False
    assert report["summary"]["errors_total"] == 3
    assert "rpc_url is required for live receipt capture" in report["errors"]


def test_cli_preflight_writes_report_and_returns_two_when_inputs_missing(tmp_path):
    output = tmp_path / "preflight.json"
    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--preflight-capture-inputs",
            "--transaction-hash",
            "0x1234",
            "--settlement-id",
            "<settlement>",
            "--output-preflight-json",
            str(output),
            "--require-preflight-ready",
        ]
    )

    assert exit_code == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert payload["summary"]["capture_inputs_ready"] is False
    assert payload["runs_live_rpc"] is False


def test_cli_capture_writes_evidence_and_gate_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(external_settlement, "_rpc_call", lambda rpc_url, method, params: _rpc_result(method, params))

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--capture-from-rpc",
            "--transaction-hash",
            TX_HASH,
            "--destination-chain",
            "base-sepolia",
            "--settlement-id",
            "settlement-2026-05-20-001",
            "--rpc-url",
            "https://rpc.example",
            "--write-evidence",
            "--require-ready",
        ]
    )

    assert exit_code == 0
    evidence_path = tmp_path / ".tmp/external-settlement-evidence/settlement-submit.json"
    assert validate_evidence_file(evidence_path).valid is True
    blocker = json.loads(
        (tmp_path / ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert blocker["decision"] == "READY_TO_PROMOTE"
    assert blocker["summary"]["x0t_external_settlement_ready"] is True
    rpc_report = json.loads(
        (tmp_path / ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert rpc_report["rpc_endpoint"] is None
    assert rpc_report["rpc_endpoint_present"] is True
    assert rpc_report["rpc_endpoint_scheme"] == "https"
    assert rpc_report["rpc_endpoint_hash"]
    assert rpc_report["rpc_endpoint_redacted"] is True
    assert "https://rpc.example" not in json.dumps(rpc_report)


def test_cli_writes_fail_closed_current_artifacts_when_receipt_is_missing(tmp_path):
    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--require-ready",
        ]
    )

    assert exit_code == 2
    blocker = json.loads(
        (tmp_path / ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert blocker["decision"] == "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT"
    assert blocker["summary"]["expected_evidence_file_exists"] is False
    assert blocker["summary"]["x0t_external_settlement_ready"] is False
