from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/full-cluster-test.sh"


def test_full_cluster_test_delegates_production_claim_to_real_readiness_gate():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL_READINESS_BLOCKED" in text
    assert "PRODUCTION READY" not in text
    assert "((PASS++))" not in text
    assert "((FAIL++))" not in text
