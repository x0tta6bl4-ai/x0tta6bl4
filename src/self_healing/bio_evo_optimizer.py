"""
Bio-evolutionary Optimizer for Self-Healing Mesh
================================================

Optimizes MAPE-K parameters and GraphSAGE weights using Genetic Algorithms (GA)
to minimize MTTR (Mean Time To Recovery) in 10k+ node environments.
"""

import random
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bio-evo")

@dataclass
class MapeKParameters:
    """Hyperparameters for the MAPE-K self-healing loop."""
    monitor_interval: float # seconds
    anomaly_threshold: float # 0.0 to 1.0
    causal_confidence_min: float
    recovery_parallelism: int
    reinforcement_rate: float

@dataclass
class Individual:
    """A single set of parameters (DNA) in the population."""
    params: MapeKParameters
    fitness: float = 0.0 # MTTR (lower is better)
    generation: int = 0

class BioEvoOptimizer:
    """
    Genetic Algorithm optimizer for self-healing efficiency.
    """
    def __init__(self, population_size: int = 20):
        self.population_size = population_size
        self.population = [self._generate_random_individual() for _ in range(population_size)]
        self.generation = 0
        self.best_mttr = float('inf')

    def _generate_random_individual(self) -> Individual:
        params = MapeKParameters(
            monitor_interval=random.uniform(1.0, 30.0),
            anomaly_threshold=random.uniform(0.5, 0.95),
            causal_confidence_min=random.uniform(0.6, 0.9),
            recovery_parallelism=random.randint(1, 10),
            reinforcement_rate=random.uniform(0.01, 0.2)
        )
        return Individual(params=params)

    def evaluate_fitness(self, individual: Individual, simulation_results: Dict[str, Any]) -> float:
        """
        Calculates fitness based on MTTR and False Positive Rate.
        Goal: Minimize MTTR while keeping FPR < 5%.
        """
        mttr = simulation_results.get("mttr", 60.0)
        fpr = simulation_results.get("fpr", 0.1)
        
        # Penalty for high FPR
        penalty = 0.0
        if fpr > 0.05:
            penalty = (fpr - 0.05) * 1000.0
            
        fitness = mttr + penalty
        individual.fitness = fitness
        return fitness

    def evolve(self):
        """Perform one generation of evolution."""
        # 1. Sort by fitness (lower is better)
        self.population.sort(key=lambda x: x.fitness)
        
        if self.population[0].fitness < self.best_mttr:
            self.best_mttr = self.population[0].fitness
            logger.info(f"New best MTTR: {self.best_mttr:.2f}s in Gen {self.generation}")

        # 2. Selection (Elitism: keep top 20%)
        new_population = self.population[:max(1, self.population_size // 5)]

        # 3. Crossover & Mutation
        while len(new_population) < self.population_size:
            parent1 = random.choice(self.population[:10])
            parent2 = random.choice(self.population[:10])
            
            child_params = self._crossover(parent1.params, parent2.params)
            child = Individual(params=child_params, generation=self.generation + 1)
            self._mutate(child)
            
            new_population.append(child)

        self.population = new_population
        self.generation += 1

    def _crossover(self, p1: MapeKParameters, p2: MapeKParameters) -> MapeKParameters:
        """Uniform crossover of parameters."""
        return MapeKParameters(
            monitor_interval=random.choice([p1.monitor_interval, p2.monitor_interval]),
            anomaly_threshold=random.choice([p1.anomaly_threshold, p2.anomaly_threshold]),
            causal_confidence_min=random.choice([p1.causal_confidence_min, p2.causal_confidence_min]),
            recovery_parallelism=random.choice([p1.recovery_parallelism, p2.recovery_parallelism]),
            reinforcement_rate=random.choice([p1.reinforcement_rate, p2.reinforcement_rate])
        )

    def _mutate(self, individual: Individual):
        """Small random adjustments to parameters with bounds checking."""
        if random.random() < 0.1:
            # Keep monitor_interval in reasonable range [1.0, 60.0] seconds
            individual.params.monitor_interval = max(
                1.0, min(60.0, individual.params.monitor_interval * random.uniform(0.8, 1.2))
            )
        if random.random() < 0.1:
            individual.params.anomaly_threshold = max(0.5, min(0.99, individual.params.anomaly_threshold + random.uniform(-0.05, 0.05)))
        if random.random() < 0.1:
            individual.params.recovery_parallelism = max(1, min(20, individual.params.recovery_parallelism + random.randint(-1, 1)))

    def get_best_params(self) -> MapeKParameters:
        return self.population[0].params
