from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_validate_production_readiness_delegates_to_real_readiness_gate():
    text = (ROOT / "scripts/validate_production_readiness.sh").read_text(
        encoding="utf-8"
    )

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "Production readiness validation PASSED" not in text
    assert "Local checks are not production deployment proof." in text
    assert "production deployment is not allowed yet" in text
    assert "((ERRORS++))" not in text
    assert "((WARNINGS++))" not in text
