from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gemini_rules_require_real_readiness_gate_before_production_claims():
    rules = (ROOT / "GEMINI.md").read_text(encoding="utf-8")

    assert "scripts/ops/check_real_readiness.py" in rules
    assert "REAL_READINESS_READY" in rules
    assert "REAL_READINESS_BLOCKED" in rules
    assert "external-dpi-proof-missing" in rules
    assert "production readiness proof" in rules
    assert "Do not describe it as production-ready" in rules


def test_gemini_rules_block_worktree_and_private_input_mistakes():
    rules = (ROOT / "GEMINI.md").read_text(encoding="utf-8")

    assert "Do not suggest committing the entire dirty worktree" in rules
    assert "Do not stage unrelated files" in rules
    assert "Do not delete or move broad directory trees" in rules
    assert "Never ask the user to paste private target URLs" in rules
    assert "run_external_dpi_intake_local.py --write-ready" in rules


def test_gemini_rules_preserve_logging_contract():
    rules = (ROOT / "GEMINI.md").read_text(encoding="utf-8")

    assert "setup_logging(name=...)" in rules
    assert "must return the named" in rules
    assert "Do not silently replace it with the root logger" in rules
