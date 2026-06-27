import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_parl_mapek_integration_import() -> None:
    import src.core.parl_mapek_integration as module

    assert module is not None


@pytest.mark.asyncio
async def test_parl_mapek_executor_records_thinking_context() -> None:
    from src.core.parl_mapek_integration import MAPEKContext, PARLMAPEKExecutor

    executor = PARLMAPEKExecutor()
    executor._initialized = True

    result = await executor.execute_cycle(
        MAPEKContext(cycle_id="cycle-thinking", mesh_nodes=[])
    )
    metrics = executor.get_metrics()

    assert result["success"] is True
    assert metrics["thinking"]["profile"]["role"] == "healing"
    assert metrics["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "parl_mapek_monitor_phase"
    )
