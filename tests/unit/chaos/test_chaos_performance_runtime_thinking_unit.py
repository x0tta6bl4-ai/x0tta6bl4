import asyncio
import json
from datetime import datetime

import pytest

from src.chaos.advanced_scenarios import AdvancedChaosController
from src.chaos.controller import ChaosController, ChaosExperiment, ExperimentType
from src.optimization.performance_tuner import PerformanceTuner


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert raw_value not in text


@pytest.mark.asyncio
async def test_chaos_controller_thinking_status_redacts_targets_and_parameters():
    controller = ChaosController()
    experiment = ChaosExperiment(
        experiment_type=ExperimentType.NODE_FAILURE,
        duration=0,
        target_nodes=["secret-node"],
        parameters={"secret-param": "secret-value"},
        start_time=datetime.now(),
    )

    await controller._collect_recovery_metrics(experiment)
    status = controller.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    _assert_redacted(status, "secret-node", "secret-param", "secret-value")


@pytest.mark.asyncio
async def test_advanced_chaos_controller_thinking_status_redacts_targets_and_behavior():
    controller = AdvancedChaosController()
    await controller.run_byzantine_behavior(
        ["secret-node-a", "secret-node-b"],
        behavior_type="secret-behavior",
        duration=0,
    )

    status = controller.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    _assert_redacted(status, "secret-node-a", "secret-node-b", "secret-behavior")


def test_performance_tuner_thinking_status_redacts_function_and_operation_names():
    tuner = PerformanceTuner()

    @tuner.profile_function("secret-operation")
    def _profiled():
        return "ok"

    assert _profiled() == "ok"
    status = tuner.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "quality"
    _assert_redacted(status, "secret-operation")

    tuner.bottleneck_detector.record_baseline("secret-slow-op", 10.0)
    tuner.bottleneck_detector.record_current("secret-slow-op", 40.0)
    tuner.analyze_performance()
    status = tuner.get_thinking_status()
    _assert_redacted(status, "secret-operation", "secret-slow-op")
