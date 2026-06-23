from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_dataplane_delivery_private_target_operator_run.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_dataplane_delivery_private_target_operator_run",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeServer:
    def close(self) -> None:
        return None


class _FakeThread:
    def join(self, timeout: float | None = None) -> None:
        return None


def _fake_retained_operator_report(**overrides):
    report = {
        "decision": "DATAPLANE_OPERATOR_EVIDENCE_RETAINED",
        "ok": True,
        "summary": {
            "operator_run_evidence_retained": True,
            "eventbus_evidence_recognized_by_proof_gate": True,
            "opens_socket": True,
            "writes_eventbus": True,
            "writes_validation_artifacts": True,
            "raw_targets_redacted": True,
            "customer_traffic_claimed": False,
            "traffic_delivery_claimed": False,
            "production_readiness_claimed": False,
        },
        "collector": {"raw_target_redacted": True},
        "proof_gate": {
            "artifact_valid": True,
            "selected_event": {
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "redacted": True,
            },
        },
    }
    report.update(overrides)
    return report


def test_private_target_operator_run_requires_explicit_authorization(tmp_path: Path):
    module = load_module()

    report = module.build_report(
        tmp_path,
        target_host="10.0.0.5",
        host_candidates=["10.0.0.5"],
    )

    assert report["decision"] == module.DECISION_BLOCKED
    assert report["ok"] is False
    assert "allow_private_target_probe_required" in report["blockers"]
    assert report["summary"]["operator_run_attempted"] is False
    assert report["target"]["private_non_loopback"] is True
    assert "10.0.0.5" not in json.dumps(report)


def test_private_target_operator_run_rejects_loopback_or_public_target(tmp_path: Path):
    module = load_module()

    loopback = module.build_report(
        tmp_path,
        target_host="127.0.0.1",
        allow_private_target_probe=True,
        host_candidates=["127.0.0.1"],
    )
    public = module.build_report(
        tmp_path,
        target_host="8.8.8.8",
        allow_private_target_probe=True,
        host_candidates=["8.8.8.8"],
    )

    assert "private_non_loopback_target_required" in loopback["blockers"]
    assert "private_non_loopback_target_required" in public["blockers"]
    assert loopback["summary"]["server_started"] is False
    assert public["summary"]["server_started"] is False
    assert "127.0.0.1" not in json.dumps(loopback)
    assert "8.8.8.8" not in json.dumps(public)


def test_private_target_operator_run_retains_redacted_operator_evidence(
    tmp_path: Path,
):
    module = load_module()
    calls = {}

    def server_factory(host: str):
        calls["server_host"] = host
        return _FakeServer(), _FakeThread(), 19443

    def operator_runner(root: Path, **kwargs):
        calls["operator_kwargs"] = kwargs
        return _fake_retained_operator_report()

    report = module.build_report(
        tmp_path,
        target_host="10.0.0.5",
        allow_private_target_probe=True,
        host_candidates=["10.0.0.5"],
        server_factory=server_factory,
        operator_runner=operator_runner,
    )

    assert report["decision"] == module.DECISION_RETAINED
    assert report["ok"] is True
    assert report["summary"]["server_started"] is True
    assert report["summary"]["operator_run_attempted"] is True
    assert report["summary"]["operator_run_evidence_retained"] is True
    assert report["summary"]["eventbus_evidence_recognized_by_proof_gate"] is True
    assert report["summary"]["customer_traffic_claimed"] is False
    assert report["summary"]["traffic_delivery_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["operator_evidence"]["raw_targets_redacted"] is True
    assert calls["server_host"] == "10.0.0.5"
    assert calls["operator_kwargs"]["target_host"] == "10.0.0.5"
    assert calls["operator_kwargs"]["target_port"] == "19443"
    assert "10.0.0.5" not in json.dumps(report)


def test_private_target_operator_run_fails_if_operator_report_leaks_target(
    tmp_path: Path,
):
    module = load_module()

    def operator_runner(root: Path, **kwargs):
        return _fake_retained_operator_report(debug_target="10.0.0.5")

    report = module.build_report(
        tmp_path,
        target_host="10.0.0.5",
        allow_private_target_probe=True,
        host_candidates=["10.0.0.5"],
        server_factory=lambda host: (_FakeServer(), _FakeThread(), 19443),
        operator_runner=operator_runner,
    )

    assert report["decision"] == module.DECISION_GAPS
    assert report["ok"] is False
    assert "raw_target_leaked" in report["blockers"]


def test_private_target_operator_run_cli_blocks_without_authorization(
    tmp_path: Path,
):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--target-host",
            "10.0.0.5",
            "--require-retained",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "DATAPLANE_PRIVATE_TARGET_OPERATOR_RUN_BLOCKED"
    assert "allow_private_target_probe_required" in payload["blockers"]
