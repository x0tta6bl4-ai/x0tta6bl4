import asyncio
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


def _pass_cmd(_root, args, _timeout=10.0):
    return {
        "args": args,
        "available": True,
        "exit_code": 0,
        "stdout": "PASS\n",
        "stderr": "",
    }


def test_packet_capture_collector_writes_proof_gate_compatible_evidence(tmp_path, monkeypatch):
    collector = _load_script(
        "collect_ghost_pulse_packet_capture_evidence",
        "scripts/ops/collect_ghost_pulse_packet_capture_evidence.py",
    )
    proof = _load_script(
        "run_ghost_pulse_proof_gate_for_packet_capture",
        "scripts/ops/run_ghost_pulse_proof_gate.py",
    )
    monkeypatch.setattr(collector, "run_cmd", _pass_cmd)

    report = asyncio.run(
        collector.collect_report(
            root=tmp_path,
            packet_count=3,
            mode="corporate",
            seed=20260522,
        )
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.md"
    collector.write_report_outputs(tmp_path, report, output_json, output_md)
    written = json.loads(output_json.read_text(encoding="utf-8"))

    assert written["status"] == collector.STATUS_VERIFIED
    assert written["simulated"] is False
    assert written["dry_run"] is False
    assert written["template"] is False
    assert written["measurements"]["sender_pcap_packets"] == 3
    assert written["measurements"]["receiver_pcap_packets"] == 3
    assert {artifact["role"] for artifact in written["artifacts"]} == set(
        proof.EXTERNAL_REQUIREMENTS[1]["required_artifact_roles"]
    )
    for artifact in written["artifacts"]:
        artifact_path = tmp_path / artifact["path"]
        assert artifact_path.exists()
        assert artifact["sha256"] == collector.sha256_file(artifact_path)

    row = proof.validate_external_evidence(tmp_path, proof.EXTERNAL_REQUIREMENTS[1])

    assert row["status"] == "VERIFIED"
    assert row["errors"] == []


def test_packet_capture_pcap_writer_emits_nonempty_raw_ipv4_pcap(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_packet_capture_evidence_pcap",
        "scripts/ops/collect_ghost_pulse_packet_capture_evidence.py",
    )
    packet = collector.CapturedPacket(
        index=0,
        realtime_ns=1_700_000_000_123_456_000,
        monotonic_ns=123,
        src_host="127.0.0.1",
        src_port=40000,
        dst_host="127.0.0.1",
        dst_port=50000,
        payload_hex=b"abc".hex(),
    )
    pcap = tmp_path / "one.pcap"

    collector.write_pcap(pcap, [packet])

    data = pcap.read_bytes()
    assert len(data) > 24
    assert data[:4] == b"\xd4\xc3\xb2\xa1"
