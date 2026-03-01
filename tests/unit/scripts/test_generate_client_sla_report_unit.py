from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "generate_client_sla_report.py"
    spec = importlib.util.spec_from_file_location("generate_client_sla_report", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load generate_client_sla_report module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fetch_metrics_returns_no_data_when_no_sources():
    mod = _load_module()
    generator = mod.SLAReportGenerator(client_id="CLIENT-1")

    metrics = generator.fetch_metrics()

    assert metrics["source"] == "no-data"
    assert metrics["uptime_percent"] is None
    assert metrics["avg_mttr_sec"] is None
    assert metrics["latency_p95_ms"] is None


def test_fetch_metrics_from_json_file(tmp_path):
    mod = _load_module()
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "uptime_percent": 99.95,
                "avg_mttr_sec": 11.2,
                "threats_blocked": 123,
                "pqc_handshakes": 4567,
                "protocol_integrity": "99.99%",
                "latency_p95_ms": 44.1,
                "throughput_mbps": 512.4,
                "auto_recovery_success_rate": 98.5,
            }
        ),
        encoding="utf-8",
    )

    generator = mod.SLAReportGenerator(client_id="CLIENT-2", metrics_file=str(metrics_path))
    metrics = generator.fetch_metrics()

    assert metrics["source"] == f"json:{metrics_path}"
    assert metrics["uptime_percent"] == 99.95
    assert metrics["avg_mttr_sec"] == 11.2
    assert metrics["threats_blocked"] == 123
    assert metrics["pqc_handshakes"] == 4567
    assert metrics["protocol_integrity"] == "99.99%"
    assert metrics["latency_p95_ms"] == 44.1
    assert metrics["throughput_mbps"] == 512.4
    assert metrics["auto_recovery_success_rate"] == 98.5


def test_stable_report_hash_is_deterministic():
    mod = _load_module()
    generator = mod.SLAReportGenerator(client_id="CLIENT-3")
    metrics = {
        "uptime_percent": 99.9,
        "avg_mttr_sec": 12.0,
        "threats_blocked": 10,
        "pqc_handshakes": 20,
        "protocol_integrity": "100%",
        "latency_p95_ms": 50.0,
        "throughput_mbps": 100.0,
        "auto_recovery_success_rate": 99.0,
        "source": "json:test",
    }

    hash_1 = generator._stable_report_hash(metrics)
    hash_2 = generator._stable_report_hash(metrics)

    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_report_text_explicitly_marks_no_data():
    mod = _load_module()
    generator = mod.SLAReportGenerator(client_id="CLIENT-4")

    text = generator.generate_report_text()

    assert "Data Source: no-data" in text
    assert "Uptime: N/A (Target: 99.9%)" in text
    assert "Avg. Recovery Time (MTTR): N/A (Target: <30s)" in text
