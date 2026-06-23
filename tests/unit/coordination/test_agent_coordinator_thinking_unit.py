from src.coordination.state import AgentCoordinator, AgentRole


def test_agent_coordinator_records_thinking_for_task_suggestion(tmp_path):
    (tmp_path / "src").mkdir()
    coordinator = AgentCoordinator(project_root=str(tmp_path))
    coordinator.register_agent("coder-1", AgentRole.CODER)

    suggestion = coordinator.suggest_next_task("coder-1")
    status = coordinator.get_thinking_status()

    assert suggestion["path"] == "src"
    assert status["thinking"]["profile"]["role"] == "coordinator"
    assert status["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "agent_next_task_suggestion"
    )
