from __future__ import annotations

from pathlib import Path

from scripts.check_pipeline_stage_contract import (
    run_contract_checks,
    validate_ci_stage_contract,
    validate_smoke_stage_contract,
)


def test_validate_ci_stage_contract_passes_for_expected_order():
    ci_text = """
jobs:
  test:
    steps:
      - name: Lint with ruff
      - name: Test with pytest
"""
    assert validate_ci_stage_contract(ci_text) == []


def test_validate_ci_stage_contract_fails_when_lint_missing():
    ci_text = """
jobs:
  test:
    steps:
      - name: Test with pytest
"""
    errors = validate_ci_stage_contract(ci_text)
    assert any("Missing CI stages" in error for error in errors)
    assert any("lint" in error for error in errors)


def test_validate_ci_stage_contract_fails_on_wrong_order():
    ci_text = """
jobs:
  test:
    steps:
      - name: Test with pytest
      - name: Lint with ruff
"""
    errors = validate_ci_stage_contract(ci_text)
    assert any("Stage order violation" in error for error in errors)


def test_validate_smoke_stage_contract_detects_missing_step():
    smoke_text = """
jobs:
  golden-smoke-quick:
    steps:
      - name: Setup Python
"""
    errors = validate_smoke_stage_contract(smoke_text)
    assert errors == ["Missing smoke stage: Run golden smoke (quick)"]


def test_run_contract_checks_with_real_workflows():
    root = Path(__file__).resolve().parents[3]
    ci_path = root / ".github/workflows/ci.yml"
    smoke_path = root / ".github/workflows/golden-smoke-premerge.yml"
    if not ci_path.exists() or not smoke_path.exists():
        pytest.skip(
            f"Workflow contract baseline files missing: {ci_path}, {smoke_path}"
        )
    errors = run_contract_checks(ci_path, smoke_path)
    assert errors == []
