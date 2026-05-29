import json
from pathlib import Path

from src.integration.operator_bundle_secret_scan import build_report, main


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_secret_scan_accepts_clean_return_packet(tmp_path):
    packet = tmp_path / "return-packet.json"
    _write_text(packet, json.dumps({"status": "VERIFIED HERE", "next_commands": ["echo safe"]}))

    report = build_report(tmp_path, packet)

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["content_scan_decision"] == "OPERATOR_BUNDLE_CONTENT_SCAN_CLEAR"
    assert report["summary"]["content_scan_findings"] == 0
    assert report["ready_for_stage"] is True
    assert report["mutates_files"] is False


def test_secret_scan_blocks_obvious_private_key(tmp_path):
    packet = tmp_path / "return-packet.json"
    _write_text(packet, json.dumps({"payload": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----"}))

    report = build_report(tmp_path, packet)

    assert report["content_scan_decision"] == "OPERATOR_BUNDLE_CONTENT_SCAN_BLOCKED"
    assert report["summary"]["content_scan_findings"] == 1
    assert report["ready_for_stage"] is False


def test_secret_scan_cli_require_clear_returns_two_when_blocked(tmp_path):
    packet = tmp_path / "return-packet.json"
    _write_text(packet, json.dumps({"payload": "aws_secret_key=abcdefghijklmnopqrstuvwxyz"}))
    output_json = tmp_path / "scan.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--return-packet-json",
        str(packet),
        "--output-json",
        str(output_json),
        "--require-clear",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["summary"]["content_scan_findings"] == 1
