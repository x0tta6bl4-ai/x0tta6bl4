"""
Geneva-style Genetic Evasion for x0tta6bl4
===========================================

Automatic generation of DPI evasion strategies using genetic algorithms.
Inspired by Geneva (Genetic Evasion).

DNA consists of a sequence of packet manipulation actions:
- SPLIT: Split a packet into two segments.
- DUPLICATE: Send a duplicate packet.
- TAMPER: Change packet headers (TTL, flags, etc.)
- DROP: Drop a specific packet.
"""
from __future__ import annotations

import random
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)


_SERVICE_AGENT = "anti-censorship-geneva-optimizer"
_SERVICE_LAYER = "anti_censorship_geneva_optimizer_local_evidence"
GENEVA_OPTIMIZER_CLAIM_BOUNDARY = (
    "Local Geneva-style genetic optimizer evidence only. It records local "
    "population evolution, generation counters, fitness-result count buckets, "
    "action-type counts, best-strategy shape, duration, and service identity "
    "presence; it does not expose raw strategy parameters, random seeds, "
    "packets, payloads, target domains, fitness values, or prove DPI bypass, "
    "censorship bypass, remote reachability, packet delivery, anonymity, "
    "provider health, client installation, or production customer traffic use."
)


def _count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value == 1:
        return "single"
    if value <= 3:
        return "few"
    if value <= 10:
        return "small"
    if value <= 50:
        return "medium"
    return "large"


def _fitness_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"
    if value <= 0:
        return "zero_or_negative"
    if value < 0.25:
        return "low"
    if value < 0.75:
        return "medium"
    if value < 1.5:
        return "high"
    return "very_high"


def _action_type_counts(actions: List["Action"]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for action in actions:
        if isinstance(action, Action) and isinstance(action.type, ActionType):
            counts[action.type.value] = counts.get(action.type.value, 0) + 1
    return counts


def _population_action_type_counts(population: List["DNA"]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for dna in population:
        if not isinstance(dna, DNA):
            continue
        for action_type, count in _action_type_counts(dna.actions).items():
            counts[action_type] = counts.get(action_type, 0) + count
    return counts

class ActionType(Enum):
    SPLIT = "split"
    DUPLICATE = "duplicate"
    TAMPER = "tamper"
    DROP = "drop"

@dataclass
class Action:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"{self.type.value}({self.params})"

class DNA:
    """A sequence of actions representing an evasion strategy."""
    def __init__(self, actions: List[Action] = None):
        self.actions = actions or []
        self.fitness = 0.0

    def mutate(self):
        """Mutates the DNA by adding, removing, or changing an action."""
        if not self.actions or random.random() < 0.3:
            # Add action
            type = random.choice(list(ActionType))
            params = self._generate_random_params(type)
            self.actions.append(Action(type, params))
        elif random.random() < 0.5:
            # Change params
            idx = random.randrange(len(self.actions))
            self.actions[idx].params = self._generate_random_params(
                self.actions[idx].type
            )
        else:
            # Remove action
            if len(self.actions) > 1:
                self.actions.pop(random.randrange(len(self.actions)))

    def _generate_random_params(self, type: ActionType) -> Dict[str, Any]:
        if type == ActionType.SPLIT:
            return {
                "index": random.randint(1, 100),
                "method": random.choice(["tcp", "byte"]),
            }
        elif type == ActionType.DUPLICATE:
            return {"count": random.randint(1, 2)}
        elif type == ActionType.TAMPER:
            field = random.choice(["ttl", "tcp_flags", "window_size"])
            return {"field": field, "value": random.randint(1, 255)}
        elif type == ActionType.DROP:
            return {"probability": random.uniform(0.1, 0.5)}
        return {}

    def __repr__(self):
        return " -> ".join([str(a) for a in self.actions])

class GenevaGeneticOptimizer:
    """
    Genetic Optimizer for DPI evasion strategies.
    """
    def __init__(
        self,
        population_size: int = 20,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.population = [
            self._create_random_dna() for _ in range(population_size)
        ]
        self.generation = 0
        self.event_bus = event_bus
        self.event_project_root = event_project_root

    def _create_random_dna(self) -> DNA:
        dna = DNA()
        for _ in range(random.randint(1, 3)):
            dna.mutate()
        return dna

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize Geneva optimizer EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _strategy_metadata(self, dna: DNA) -> Dict[str, Any]:
        return {
            "action_count": len(dna.actions),
            "action_count_bucket": _count_bucket(len(dna.actions)),
            "action_type_counts": _action_type_counts(dna.actions),
            "fitness_bucket": _fitness_bucket(dna.fitness),
            "raw_strategy_redacted": True,
            "raw_action_params_redacted": True,
        }

    def _publish_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "anti_censorship.geneva_genetic",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "generation": self.generation,
            "population_size": len(self.population),
            "population_size_bucket": _count_bucket(len(self.population)),
            "service_identity": self._identity_presence(),
            "control_action": operation == "evolve",
            "observed_state": True,
            "payloads_redacted": True,
            "raw_packets_redacted": True,
            "raw_strategy_redacted": True,
            "raw_action_params_redacted": True,
            "fitness_values_redacted": True,
            "random_seed_redacted": True,
            "raw_identifiers_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": GENEVA_OPTIMIZER_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value.endswith("failed")
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish Geneva optimizer evidence: %s", exc)
            return None

    def evolve(self, fitness_results: Dict[int, float]):
        """
        Evolves the population based on fitness results.
        """
        started_at = time.monotonic()
        generation_before = self.generation
        population_size_before = len(self.population)
        fitness_result_count = (
            len(fitness_results) if hasattr(fitness_results, "__len__") else 0
        )
        try:
            # 1. Update fitness
            for i, fitness in fitness_results.items():
                if i < len(self.population):
                    self.population[i].fitness = fitness

            # 2. Sort by fitness
            self.population.sort(key=lambda x: x.fitness, reverse=True)

            best = self.population[0]
            logger.info(
                "Gen %s best fitness bucket: %s",
                self.generation,
                _fitness_bucket(best.fitness),
            )
            logger.info(
                "Best strategy action types: %s",
                _action_type_counts(best.actions),
            )

            # 3. Selection (keep top 25%)
            keep_count = max(1, len(self.population) // 4)
            new_population = self.population[:keep_count]

            # 4. Reproduction
            while len(new_population) < len(self.population):
                parent = random.choice(self.population[:keep_count])
                child = DNA(
                    [Action(a.type, a.params.copy()) for a in parent.actions]
                )
                child.mutate()
                new_population.append(child)

            self.population = new_population
            self.generation += 1
        except Exception as exc:
            self._publish_evidence(
                operation="evolve",
                status_value="evolve_failed",
                started_at=started_at,
                metadata={
                    "generation_before": generation_before,
                    "population_size_before": population_size_before,
                    "population_size_before_bucket": _count_bucket(
                        population_size_before
                    ),
                    "fitness_results_count": fitness_result_count,
                    "fitness_results_count_bucket": _count_bucket(
                        fitness_result_count
                    ),
                    "population_action_type_counts": _population_action_type_counts(
                        self.population
                    ),
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="evolve",
            status_value="evolved",
            started_at=started_at,
            metadata={
                "generation_before": generation_before,
                "generation_after": self.generation,
                "population_size_before": population_size_before,
                "population_size_before_bucket": _count_bucket(
                    population_size_before
                ),
                "fitness_results_count": fitness_result_count,
                "fitness_results_count_bucket": _count_bucket(fitness_result_count),
                "keep_count_bucket": _count_bucket(keep_count),
                "mutation_applied": len(self.population) > keep_count,
                "best_strategy": self._strategy_metadata(self.population[0]),
                "population_action_type_counts": _population_action_type_counts(
                    self.population
                ),
            },
        )

    def get_best_strategy(self) -> DNA:
        started_at = time.monotonic()
        try:
            best = self.population[0]
        except Exception as exc:
            self._publish_evidence(
                operation="get_best_strategy",
                status_value="get_best_strategy_failed",
                started_at=started_at,
                metadata={
                    "population_action_type_counts": _population_action_type_counts(
                        self.population
                    ),
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="get_best_strategy",
            status_value="selected",
            started_at=started_at,
            metadata={
                "best_strategy": self._strategy_metadata(best),
                "population_action_type_counts": _population_action_type_counts(
                    self.population
                ),
            },
        )
        return best

