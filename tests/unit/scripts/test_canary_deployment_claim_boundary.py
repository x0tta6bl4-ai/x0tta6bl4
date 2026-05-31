import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/canary_deployment.py"
    spec = importlib.util.spec_from_file_location("canary_deployment_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_stage_percentages_is_bounded():
    module = _load_module()

    assert module.parse_stage_percentages("5,25,100") == [5.0, 25.0, 100.0]
    with pytest.raises(ValueError):
        module.parse_stage_percentages("0")
    with pytest.raises(ValueError):
        module.parse_stage_percentages("101")
    with pytest.raises(ValueError):
        module.parse_stage_percentages("")


@pytest.mark.asyncio
async def test_canary_observation_result_is_not_traffic_or_production_proof():
    module = _load_module()

    result = await module.deploy_canary(5.0, duration_minutes=0)

    assert result["percentage"] == 5.0
    assert result["passed"] is False
    assert result["traffic_shift_claim_allowed"] is False
    assert result["production_readiness_claim_allowed"] is False
    assert result["live_customer_traffic_proven"] is False
    assert result["external_dpi_bypass_confirmed"] is False
    assert result["settlement_finality_confirmed"] is False
    assert "does not prove traffic was shifted" in result["claim_boundary"]


def test_canary_source_does_not_claim_final_traffic_deployment():
    text = (ROOT / "scripts/canary_deployment.py").read_text(encoding="utf-8")

    assert "Final deployment: 100% traffic" not in text
    assert "CANARY DEPLOYMENT COMPLETE" not in text
    assert "CANARY ROLLOUT OBSERVATION" in text
    assert "production_readiness_claim_allowed" in text
    assert "traffic_shift_claim_allowed" in text
