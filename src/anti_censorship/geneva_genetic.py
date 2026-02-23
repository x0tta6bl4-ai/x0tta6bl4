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

import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

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
            self.actions[idx].params = self._generate_random_params(self.actions[idx].type)
        else:
            # Remove action
            if len(self.actions) > 1:
                self.actions.pop(random.randrange(len(self.actions)))

    def _generate_random_params(self, type: ActionType) -> Dict[str, Any]:
        if type == ActionType.SPLIT:
            return {"index": random.randint(1, 100), "method": random.choice(["tcp", "byte"])}
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
    def __init__(self, population_size: int = 20):
        self.population = [self._create_random_dna() for _ in range(population_size)]
        self.generation = 0

    def _create_random_dna(self) -> DNA:
        dna = DNA()
        for _ in range(random.randint(1, 3)):
            dna.mutate()
        return dna

    def evolve(self, fitness_results: Dict[int, float]):
        """
        Evolves the population based on fitness results.
        """
        # 1. Update fitness
        for i, fitness in fitness_results.items():
            if i < len(self.population):
                self.population[i].fitness = fitness

        # 2. Sort by fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        logger.info(f"Gen {self.generation} best fitness: {self.population[0].fitness}")
        logger.info(f"Best Strategy: {self.population[0]}")

        # 3. Selection (keep top 25%)
        keep_count = max(1, len(self.population) // 4)
        new_population = self.population[:keep_count]

        # 4. Reproduction
        while len(new_population) < len(self.population):
            parent = random.choice(self.population[:keep_count])
            child = DNA([Action(a.type, a.params.copy()) for a in parent.actions])
            child.mutate()
            new_population.append(child)

        self.population = new_population
        self.generation += 1

    def get_best_strategy(self) -> DNA:
        return self.population[0]
