from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_week2_rollout_requires_real_readiness_and_local_authorization():
    text = (ROOT / "scripts/run_week2_deployment.sh").read_text(encoding="utf-8")

    assert 'PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"' not in text
    assert "scripts/ops/check_real_readiness.py" in text
    assert "X0TTA6BL4_ALLOW_LIVE_ROLLOUT=yes" in text
    assert "LIVE ROLLOUT AUTHORIZATION: BLOCKED" in text
    assert "Live rollout stage" in text
    assert "not allowed yet" in text


def test_week2_rollout_output_is_not_production_proof():
    text = (ROOT / "scripts/run_week2_deployment.sh").read_text(encoding="utf-8")

    assert "WEEK 2: PRODUCTION DEPLOYMENT" not in text
    assert "complete production deployment process" not in text.lower()
    assert "ROLLOUT ORCHESTRATOR COMPLETE" in text
    assert "does not" in text
    assert "production readiness" in text
    assert "Monitoring is observational only" in text
