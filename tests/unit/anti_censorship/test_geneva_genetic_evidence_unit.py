from src.anti_censorship.geneva_genetic import (
    Action,
    ActionType,
    DNA,
    GenevaGeneticOptimizer,
)
from src.coordination.events import EventBus, EventType


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="anti-censorship-geneva-optimizer",
            limit=20,
        )
    ]


def test_evolve_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    optimizer = GenevaGeneticOptimizer(population_size=0, event_bus=bus)
    optimizer.population = [
        DNA(
            [
                Action(ActionType.SPLIT, {"marker": "SECRET-GENEVA-PARAM"}),
                Action(ActionType.TAMPER, {"field": "SECRET-TTL-FIELD"}),
            ]
        ),
        DNA([Action(ActionType.DROP, {"marker": "SECRET-DROP-PARAM"})]),
    ]

    optimizer.evolve({0: 1.0, 1: 0.1})
    payload = _payloads(bus)[0]
    text = repr(payload)

    assert payload["component"] == "anti_censorship.geneva_genetic"
    assert payload["operation"] == "evolve"
    assert payload["status"] == "evolved"
    assert payload["service_name"] == "anti-censorship-geneva-optimizer"
    assert payload["layer"] == "anti_censorship_geneva_optimizer_local_evidence"
    assert payload["generation_before"] == 0
    assert payload["generation_after"] == 1
    assert payload["fitness_results_count"] == 2
    assert payload["best_strategy"]["action_type_counts"] == {
        "split": 1,
        "tamper": 1,
    }
    assert payload["best_strategy"]["raw_action_params_redacted"] is True
    assert payload["fitness_values_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert payload["raw_packets_redacted"] is True
    assert payload["raw_strategy_redacted"] is True
    assert payload["random_seed_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["external_dpi_tested"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "SECRET-GENEVA-PARAM" not in text
    assert "SECRET-TTL-FIELD" not in text
    assert "SECRET-DROP-PARAM" not in text


def test_get_best_strategy_publishes_shape_without_raw_params(tmp_path):
    bus = EventBus(str(tmp_path))
    optimizer = GenevaGeneticOptimizer(population_size=0, event_bus=bus)
    best = DNA([Action(ActionType.DUPLICATE, {"secret": "SECRET-DUPE-PARAM"})])
    best.fitness = 0.9
    optimizer.population = [best]

    selected = optimizer.get_best_strategy()
    payload = _payloads(bus)[0]

    assert selected is best
    assert payload["operation"] == "get_best_strategy"
    assert payload["status"] == "selected"
    assert payload["control_action"] is False
    assert payload["observed_state"] is True
    assert payload["best_strategy"]["action_count"] == 1
    assert payload["best_strategy"]["action_type_counts"] == {"duplicate": 1}
    assert payload["best_strategy"]["fitness_bucket"] == "high"
    assert "SECRET-DUPE-PARAM" not in repr(payload)


def test_evolve_failure_publishes_failed_event_without_strategy_params(tmp_path):
    bus = EventBus(str(tmp_path))
    optimizer = GenevaGeneticOptimizer(population_size=0, event_bus=bus)

    try:
        optimizer.evolve({})
        assert False, "Expected IndexError for empty population"
    except IndexError:
        pass

    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="anti-censorship-geneva-optimizer",
        limit=10,
    )

    assert len(failed_events) == 1
    payload = failed_events[0].data
    assert payload["operation"] == "evolve"
    assert payload["status"] == "evolve_failed"
    assert payload["error"]["type"] == "IndexError"
    assert payload["population_size_before"] == 0
    assert payload["fitness_values_redacted"] is True
    assert payload["raw_action_params_redacted"] is True
    assert payload["dpi_bypass_confirmed"] is False
