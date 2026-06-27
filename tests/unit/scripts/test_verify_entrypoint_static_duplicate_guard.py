import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/ops/check_verify_entrypoint_duplicates.py"
    spec = importlib.util.spec_from_file_location("check_verify_entrypoint_duplicates", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_entrypoint_duplicate_guard_accepts_current_script():
    guard = _load_module()

    report = guard.build_report(ROOT / "scripts/verify-v1.1.sh")

    assert report["ok"] is True
    assert report["schema_version"] == "x0tta6bl4-verify-entrypoint-static-guard-v2"
    assert report["summary"]["duplicate_smoke_invocations"] == 0
    assert report["summary"]["duplicate_pytest_entries"] == 0
    assert report["summary"]["duplicate_function_definitions"] == 0
    assert report["summary"]["required_missing_total"] == 0


def test_code_wiring_smoke_validates_output_json_not_stdout():
    script = (ROOT / "scripts/verify-v1.1.sh").read_text(encoding="utf-8")
    start = script.index("run_code_wiring_current_smoke_check()")
    end = script.index("\n}\n\nrun_production_gap_index_current_smoke_check", start)
    block = script[start:end]

    assert '--output-json "${tmp}"' in block
    assert ">/dev/null 2>&1" in block
    assert '>"${tmp}" 2>/dev/null' not in block


def test_verify_entrypoint_covers_ghost_pulse_artifact_chain_surface():
    guard = _load_module()
    report = guard.build_report(ROOT / "scripts/verify-v1.1.sh")

    assert report["missing_required_smoke_definitions"] == []
    assert report["missing_required_smoke_invocations"] == []
    assert report["missing_required_pytest_entries"] == []
    assert report["required_smoke_invocations"] == [
        "run_ghost_pulse_artifact_chain_current_smoke_check",
    ]
    assert report["required_pytest_entries"] == [
        "tests/unit/scripts/test_run_ghost_pulse_verification_suite.py",
        "tests/unit/scripts/test_verify_ghost_pulse_artifact_chain.py",
        "tests/unit/scripts/test_verify_ghost_pulse_rng_replay.py",
        "tests/unit/scripts/test_verify_ghost_pulse_verification_suite.py",
        "tests/unit/network/test_pulse_transport_replay_unit.py",
    ]


def test_verify_entrypoint_required_coverage_rejects_missing_smoke_and_pytest(tmp_path):
    guard = _load_module()
    script = tmp_path / "verify.sh"
    script.write_text(
        "\n".join(
            [
                "run_other_smoke_check() {",
                "  true",
                "}",
                "run_other_smoke_check",
                "python3 -m pytest \\",
                "  tests/unit/test_example.py \\",
                "  --no-cov",
            ]
        ),
        encoding="utf-8",
    )

    report = guard.build_report(
        script,
        required_smoke_invocations=("run_required_smoke_check",),
        required_pytest_entries=("tests/unit/required_test.py",),
    )

    assert report["ok"] is False
    assert report["summary"]["required_missing_total"] == 3
    assert report["missing_required_smoke_definitions"] == [
        {"name": "run_required_smoke_check"},
    ]
    assert report["missing_required_smoke_invocations"] == [
        {"name": "run_required_smoke_check"},
    ]
    assert report["missing_required_pytest_entries"] == [
        {"name": "tests/unit/required_test.py"},
    ]


def test_verify_entrypoint_duplicate_guard_rejects_duplicate_smoke_invocations(tmp_path):
    guard = _load_module()
    script = tmp_path / "verify.sh"
    script.write_text(
        "\n".join(
            [
                "run_alpha_smoke_check() {",
                "  true",
                "}",
                "run_alpha_smoke_check",
                "run_alpha_smoke_check",
            ]
        ),
        encoding="utf-8",
    )

    report = guard.build_report(
        script,
        required_smoke_invocations=(),
        required_pytest_entries=(),
    )

    assert report["ok"] is False
    assert report["summary"]["duplicate_smoke_invocations"] == 1
    assert report["duplicate_smoke_invocations"][0]["name"] == "run_alpha_smoke_check"


def test_verify_entrypoint_duplicate_guard_rejects_duplicate_pytest_entries(tmp_path):
    guard = _load_module()
    script = tmp_path / "verify.sh"
    script.write_text(
        "\n".join(
            [
                "python3 -m pytest \\",
                "  tests/unit/test_example.py \\",
                "  tests/unit/test_example.py \\",
                "  --no-cov",
            ]
        ),
        encoding="utf-8",
    )

    report = guard.build_report(
        script,
        required_smoke_invocations=(),
        required_pytest_entries=(),
    )

    assert report["ok"] is False
    assert report["summary"]["duplicate_pytest_entries"] == 1
    assert report["duplicate_pytest_entries"][0]["name"] == "tests/unit/test_example.py"


def test_verify_entrypoint_duplicate_guard_rejects_duplicate_function_definitions(tmp_path):
    guard = _load_module()
    script = tmp_path / "verify.sh"
    script.write_text(
        "\n".join(
            [
                "run_alpha_smoke_check() {",
                "  true",
                "}",
                "run_alpha_smoke_check() {",
                "  false",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    report = guard.build_report(
        script,
        required_smoke_invocations=(),
        required_pytest_entries=(),
    )

    assert report["ok"] is False
    assert report["summary"]["duplicate_function_definitions"] == 1
    assert report["duplicate_function_definitions"][0]["name"] == "run_alpha_smoke_check"
