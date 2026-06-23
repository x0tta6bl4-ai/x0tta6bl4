from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/release_gate.sh"


def test_release_gate_delegates_production_claim_to_real_readiness_gate():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "Code is ready for production." not in text
