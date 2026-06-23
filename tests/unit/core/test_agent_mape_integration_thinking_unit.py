import pytest

from src.core.agent_mape_integration import AgentMAPEIntegrator


@pytest.mark.asyncio
async def test_agent_mape_integrator_records_thinking_for_manual_healing():
    integrator = AgentMAPEIntegrator()

    success = await integrator.trigger_healing(
        "recover degraded mesh route",
        {"target": "node-a"},
    )
    state = integrator.get_unified_state()

    assert success is False
    assert state["thinking"]["profile"]["role"] == "healing"
    assert state["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "manual_integrated_healing"
    )
