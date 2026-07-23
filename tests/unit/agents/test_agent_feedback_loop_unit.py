"""Unit tests for AgentFeedbackLoop, Evals Error Heatmap, and Dual-Loop Optimization System."""

import json
from pathlib import Path
import pytest
from scripts.agents.agent_feedback_loop import AgentFeedbackLoop


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_agent_feedback.db"


def test_feedback_loop_init_and_record(temp_db: Path):
    loop = AgentFeedbackLoop(db_path=temp_db)
    loop.record_feedback(agent="agent-1", action="test", result="pass", score=1.0, error_type="NONE")
    loop.record_feedback(agent="agent-2", action="test", result="fail", score=0.0, error_type="TIMEOUT")

    perf1 = loop.get_agent_performance("agent-1")
    assert perf1["avg_accuracy"] == 1.0
    assert perf1["total_actions"] == 1

    perf2 = loop.get_agent_performance("agent-2")
    assert perf2["avg_accuracy"] == 0.0
    assert perf2["total_actions"] == 1


def test_ingest_cycle_summary(temp_db: Path):
    loop = AgentFeedbackLoop(db_path=temp_db)
    mock_summary = {
        "exit_code": 0,
        "results": [
            {"agent_id": "agent-1", "return_code": 0, "timed_out": False},
            {"agent_id": "agent-2", "return_code": 0, "timed_out": False},
            {"agent_id": "agent-3", "return_code": 1, "timed_out": False},
            {"agent_id": "agent-4", "return_code": -9, "timed_out": True},
        ]
    }
    stats = loop.ingest_cycle_summary(mock_summary)
    assert stats["ingested_agents"] == 4
    assert stats["overall_score"] == 0.5  # 2 passes out of 4 = 0.5

    heatmap = loop.generate_error_heatmap()
    assert heatmap["agent-1"]["NONE"] == 1
    assert heatmap["agent-2"]["NONE"] == 1
    assert heatmap["agent-3"]["EXECUTION_ERROR"] == 1
    assert heatmap["agent-4"]["TIMEOUT"] == 1

    ascii_render = loop.render_error_heatmap_ascii()
    assert "agent-1" in ascii_render
    assert "EXECUTION_ERROR" in ascii_render


def test_calculate_hqi(temp_db: Path):
    loop = AgentFeedbackLoop(db_path=temp_db)
    summary = {
        "results": [
            {"agent_id": "agent-1", "return_code": 0, "timed_out": False, "duration_sec": 1.5},
            {"agent_id": "agent-2", "return_code": 0, "timed_out": False, "duration_sec": 2.0},
        ]
    }
    hqi_res = loop.calculate_hqi(summary)
    assert hqi_res["pass_rate"] == 1.0
    assert hqi_res["reliability"] == 1.0
    assert hqi_res["hqi"] > 0.90


def test_loop_a_experiment_evaluation(temp_db: Path):
    loop = AgentFeedbackLoop(db_path=temp_db)
    candidate_summary = {
        "exit_code": 0,
        "results": [
            {"agent_id": "agent-1", "return_code": 0, "timed_out": False},
            {"agent_id": "agent-2", "return_code": 0, "timed_out": False},
            {"agent_id": "agent-3", "return_code": 0, "timed_out": False},
            {"agent_id": "agent-4", "return_code": 0, "timed_out": False},
        ]
    }
    res = loop.evaluate_experiment(
        experiment_name="pqc_harness_v2",
        candidate_summary=candidate_summary,
        baseline_summary=None,
    )
    assert res["candidate_score"] == 1.0
    assert res["verdict"] == "KEEP"
    assert res["score_delta"] > 0


def test_loop_b_edge_case_distillation(temp_db: Path, tmp_path: Path):
    loop = AgentFeedbackLoop(db_path=temp_db)
    res = loop.distill_edge_case(
        case_id="EDGE_PQC_TIMEOUT_01",
        task_description="ML-KEM-768 handshake timeout under 40% loss",
        failure_reason="Handshake retry threshold exceeded",
        expected_behavior="Fallback to Dilithium2 within 500ms",
        severity="critical",
    )
    assert res["case_id"] == "EDGE_PQC_TIMEOUT_01"
    assert res["total_distilled_cases"] == 1

    export_path = loop.project_root / ".tmp" / "eval_edge_cases.json"
    assert export_path.exists()
    cases = json.loads(export_path.read_text())
    assert cases[0]["case_id"] == "EDGE_PQC_TIMEOUT_01"
