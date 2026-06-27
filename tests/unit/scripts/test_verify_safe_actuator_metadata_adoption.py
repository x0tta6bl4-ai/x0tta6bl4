import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_safe_actuator_metadata_adoption.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_safe_actuator_metadata_adoption", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_inventory_counts_result_metadata_adoption(tmp_path):
    module = load_module()
    source = tmp_path / "src/example.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
from src.integration.spine import SafeActuatorResult

def covered():
    return SafeActuatorResult(True, evidence_metadata={"claim_gate": {"ok": True}})

def uncovered():
    return SafeActuatorResult(False, "blocked")
""",
        encoding="utf-8",
    )

    report = module.build_report(
        tmp_path,
        scan_roots=("src",),
        high_risk_files=("src/example.py",),
    )

    assert report["schema"] == module.SCHEMA
    assert report["summary"]["safe_actuator_result_calls"] == 2
    assert report["summary"]["result_calls_with_evidence_metadata"] == 1
    assert report["summary"]["result_calls_without_evidence_metadata"] == 1
    assert report["summary"]["parse_errors"] == 0
    assert report["summary"]["parse_error_free"] is True
    assert report["summary"]["high_risk_coverage_ready"] is True
    assert report["summary"]["full_metadata_coverage_ready"] is False
    assert report["decision"] == "SAFE_ACTUATOR_METADATA_HIGH_RISK_COVERED"
    assert report["blockers"] == []
    assert report["missing_metadata_samples"][0]["function"] == "uncovered"


def test_inventory_blocks_high_risk_file_without_metadata_marker(tmp_path):
    module = load_module()
    source = tmp_path / "src/plain.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
from src.integration.spine import SafeActuatorResult

def uncovered():
    return SafeActuatorResult(False, "blocked")
""",
        encoding="utf-8",
    )

    report = module.build_report(
        tmp_path,
        scan_roots=("src",),
        high_risk_files=("src/plain.py",),
    )

    assert report["decision"] == "SAFE_ACTUATOR_METADATA_HIGH_RISK_GAPS"
    assert report["summary"]["high_risk_coverage_ready"] is False
    assert report["summary"]["full_metadata_coverage_ready"] is False
    assert report["blockers"] == ["high_risk_file_lacks_metadata_marker:src/plain.py"]


def test_inventory_treats_publish_marker_as_metadata_aware(tmp_path):
    module = load_module()
    source = tmp_path / "scripts/control.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
def publish():
    return {"safe_actuator_evidence_metadata": {"redacted": True}}
""",
        encoding="utf-8",
    )

    report = module.build_report(
        tmp_path,
        scan_roots=("scripts",),
        high_risk_files=("scripts/control.py",),
    )

    assert report["summary"]["safe_actuator_result_calls"] == 0
    assert report["summary"]["high_risk_coverage_ready"] is True
    assert report["summary"]["full_metadata_coverage_ready"] is True
    assert report["decision"] == "SAFE_ACTUATOR_METADATA_FULL_COVERAGE"
    assert report["high_risk_files"][0]["metadata_publish_marker_present"] is True


def test_inventory_blocks_full_coverage_on_parse_error(tmp_path):
    module = load_module()
    source = tmp_path / "scripts/broken.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
def broken():
    print("unterminated
""",
        encoding="utf-8",
    )

    report = module.build_report(
        tmp_path,
        scan_roots=("scripts",),
        high_risk_files=(),
    )

    assert report["summary"]["parse_errors"] == 1
    assert report["summary"]["parse_error_free"] is False
    assert report["summary"]["full_metadata_coverage_ready"] is False
    assert report["decision"] == "SAFE_ACTUATOR_METADATA_HIGH_RISK_COVERED"
    assert report["parse_errors"][0]["path"] == "scripts/broken.py"
