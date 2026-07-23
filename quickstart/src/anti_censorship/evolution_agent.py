from __future__ import annotations

import logging

from src.anti_censorship.geneva_genetic import GenevaGeneticOptimizer

logger = logging.getLogger(__name__)

class EvolutionAgent:
    """
    Standalone agent wrapping GenevaGeneticOptimizer for MAPE-K.
    Реализовано.
    """
    def __init__(self, population_size: int = 20):
        self.optimizer = GenevaGeneticOptimizer(population_size=population_size)

    def suggest_evasion(self, blocked_profile: str) -> dict:
        """Suggest an evasion strategy for a blocked profile."""
        best_dna = self.optimizer.get_best_strategy()
        actions = []
        for action in best_dna.actions:
            actions.append({"type": action.type.value, "params": action.params.copy()})
        return {
            "profile": blocked_profile,
            "strategy": actions,
            "fitness": best_dna.fitness
        }
