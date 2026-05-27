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


def _pass_cmd(_root, args, _timeout=20.0):
    return {
        "args": args,
        "available": True,
        "exit_code": 0,
        "stdout": "PASS\n",
        "stderr": "",
    }


def test_baseline_comparison_collector_writes_proof_gate_compatible_evidence(tmp_path, monkeypatch):
    collector = _load_script(
        "collect_ghost_pulse_baseline_comparison_evidence",
        "scripts/ops/collect_ghost_pulse_baseline_comparison_evidence.py",
    )
    proof = _load_script(
        "run_ghost_pulse_proof_gate_for_baseline_comparison",
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
    output_json = tmp_path / "docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.md"
    collector.write_report_outputs(tmp_path, report, output_json, output_md)
    written = json.loads(output_json.read_text(encoding="utf-8"))

    assert written["status"] == collector.STATUS_VERIFIED
    assert written["measurements"]["sample_count"] > 0
    assert written["measurements"]["comparison_passed"] is True
    assert len(written["measurements"]["baseline_digest"]) == 64
    assert len(written["measurements"]["pulse_digest"]) == 64
    assert {artifact["role"] for artifact in written["artifacts"]} == set(
        proof.EXTERNAL_REQUIREMENTS[2]["required_artifact_roles"]
    )
    for artifact in written["artifacts"]:
        artifact_path = tmp_path / artifact["path"]
        assert artifact_path.exists()
        assert artifact["sha256"] == collector.sha256_file(artifact_path)

    row = proof.validate_external_evidence(tmp_path, proof.EXTERNAL_REQUIREMENTS[2])

    assert row["status"] == "VERIFIED"
    assert row["errors"] == []


def test_baseline_comparable_sample_count_uses_shared_gap_count():
    collector = _load_script(
        "collect_ghost_pulse_baseline_comparison_evidence_count",
        "scripts/ops/collect_ghost_pulse_baseline_comparison_evidence.py",
    )

    assert (
        collector.comparable_sample_count(
            {"event_summary": {"inter_packet_gap_ms": {"count": 4}}},
            {"event_summary": {"inter_packet_gap_ms": {"count": 2}}},
        )
        == 2
    )
