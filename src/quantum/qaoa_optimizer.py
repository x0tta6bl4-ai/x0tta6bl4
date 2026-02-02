"""
QAOA (Quantum Approximate Optimization Algorithm) Implementation.

Provides real Qiskit QAOA when available, with fallback to classical simulation.
Used for network topology optimization and routing problems.

QAOA is particularly suited for:
- Max-Cut problems (network partitioning)
- Graph coloring
- Combinatorial optimization

References:
- Farhi et al., "A Quantum Approximate Optimization Algorithm" (2014)
- NIST Post-Quantum Standardization
"""
import logging
import math
import time
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Try to import Qiskit
try:
    from qiskit import QuantumCircuit
    from qiskit.circuit import Parameter
    from qiskit_algorithms import QAOA
    from qiskit_algorithms.optimizers import COBYLA, SPSA
    from qiskit.primitives import Sampler
    from qiskit_optimization import QuadraticProgram
    from qiskit_optimization.algorithms import MinimumEigenOptimizer
    QISKIT_AVAILABLE = True
    logger.info("Qiskit QAOA available - using real quantum simulation")
except ImportError:
    QISKIT_AVAILABLE = False
    logger.warning("Qiskit not available - using classical QAOA simulation")


@dataclass
class QAOAResult:
    """Result from QAOA optimization."""
    configuration: List[int]
    cost: float
    execution_time: float
    num_iterations: int
    method: str  # 'qiskit' or 'classical'
    convergence_history: List[float]


class QAOAOptimizer:
    """
    Quantum Approximate Optimization Algorithm implementation.

    Uses Qiskit when available, falls back to classical simulation otherwise.
    Optimized for Max-Cut problems common in network topology optimization.
    """

    def __init__(
        self,
        num_qubits: int,
        p_depth: int = 1,
        optimizer: str = "COBYLA",
        max_iterations: int = 100
    ):
        """
        Initialize QAOA optimizer.

        Args:
            num_qubits: Number of qubits (nodes in graph)
            p_depth: QAOA circuit depth (higher = better but slower)
            optimizer: Classical optimizer ('COBYLA', 'SPSA')
            max_iterations: Maximum optimization iterations
        """
        self.num_qubits = num_qubits
        self.p_depth = p_depth
        self.optimizer_name = optimizer
        self.max_iterations = max_iterations
        self.use_qiskit = QISKIT_AVAILABLE

        if self.use_qiskit:
            self._init_qiskit()
        else:
            self._init_classical()

        logger.info(
            f"QAOAOptimizer initialized: {num_qubits} qubits, p={p_depth}, "
            f"method={'qiskit' if self.use_qiskit else 'classical'}"
        )

    def _init_qiskit(self):
        """Initialize Qiskit components."""
        if self.optimizer_name == "COBYLA":
            self.optimizer = COBYLA(maxiter=self.max_iterations)
        else:
            self.optimizer = SPSA(maxiter=self.max_iterations)
        self.sampler = Sampler()

    def _init_classical(self):
        """Initialize classical simulation."""
        self.temperature = 10.0
        self.cooling_rate = 0.95

    def optimize_maxcut(
        self,
        adjacency_matrix: np.ndarray,
        weights: Optional[np.ndarray] = None
    ) -> QAOAResult:
        """
        Solve Max-Cut problem using QAOA.

        Max-Cut: Partition graph nodes into two sets to maximize
        the total weight of edges between the sets.

        Args:
            adjacency_matrix: Graph adjacency matrix (n x n)
            weights: Optional edge weights (default: use adjacency values)

        Returns:
            QAOAResult with optimal configuration
        """
        start_time = time.time()

        if weights is None:
            weights = adjacency_matrix

        if self.use_qiskit:
            result = self._qiskit_maxcut(adjacency_matrix, weights)
        else:
            result = self._classical_maxcut(adjacency_matrix, weights)

        result.execution_time = time.time() - start_time
        return result

    def _qiskit_maxcut(
        self,
        adjacency: np.ndarray,
        weights: np.ndarray
    ) -> QAOAResult:
        """Solve Max-Cut using Qiskit QAOA."""
        convergence = []

        # Build QUBO (Quadratic Unconstrained Binary Optimization)
        qp = QuadraticProgram()

        # Add binary variables for each node
        for i in range(self.num_qubits):
            qp.binary_var(f"x{i}")

        # Build Max-Cut objective: maximize sum of w_ij * (x_i XOR x_j)
        # XOR can be written as: x_i + x_j - 2*x_i*x_j
        linear = {}
        quadratic = {}

        for i in range(self.num_qubits):
            for j in range(i + 1, self.num_qubits):
                w = weights[i, j]
                if w != 0:
                    # Coefficient for x_i
                    linear[f"x{i}"] = linear.get(f"x{i}", 0) + w
                    # Coefficient for x_j
                    linear[f"x{j}"] = linear.get(f"x{j}", 0) + w
                    # Coefficient for x_i * x_j
                    quadratic[(f"x{i}", f"x{j}")] = -2 * w

        qp.maximize(linear=linear, quadratic=quadratic)

        # Create QAOA instance
        qaoa = QAOA(
            sampler=self.sampler,
            optimizer=self.optimizer,
            reps=self.p_depth
        )

        # Solve
        algorithm = MinimumEigenOptimizer(qaoa)
        result = algorithm.solve(qp)

        # Extract configuration
        config = [int(result.x[i]) for i in range(self.num_qubits)]
        cost = self._calculate_cut(config, weights)

        return QAOAResult(
            configuration=config,
            cost=cost,
            execution_time=0,  # Will be set by caller
            num_iterations=self.max_iterations,
            method="qiskit",
            convergence_history=convergence
        )

    def _classical_maxcut(
        self,
        adjacency: np.ndarray,
        weights: np.ndarray
    ) -> QAOAResult:
        """Solve Max-Cut using classical simulated annealing."""
        convergence = []

        # Random initial configuration
        current = [np.random.randint(0, 2) for _ in range(self.num_qubits)]
        current_cost = self._calculate_cut(current, weights)
        convergence.append(current_cost)

        best = current[:]
        best_cost = current_cost

        temp = self.temperature

        for iteration in range(self.max_iterations):
            # Propose neighbor (flip one qubit)
            neighbor = current[:]
            flip_idx = np.random.randint(0, self.num_qubits)
            neighbor[flip_idx] = 1 - neighbor[flip_idx]

            neighbor_cost = self._calculate_cut(neighbor, weights)

            # Metropolis acceptance
            delta = neighbor_cost - current_cost
            if delta > 0 or np.random.random() < math.exp(delta / max(temp, 0.01)):
                current = neighbor
                current_cost = neighbor_cost

                if current_cost > best_cost:
                    best = current[:]
                    best_cost = current_cost

            convergence.append(best_cost)
            temp *= self.cooling_rate

        return QAOAResult(
            configuration=best,
            cost=best_cost,
            execution_time=0,
            num_iterations=self.max_iterations,
            method="classical",
            convergence_history=convergence
        )

    def _calculate_cut(self, config: List[int], weights: np.ndarray) -> float:
        """Calculate cut value for a configuration."""
        cut = 0.0
        for i in range(self.num_qubits):
            for j in range(i + 1, self.num_qubits):
                if config[i] != config[j]:
                    cut += weights[i, j]
        return cut

    def benchmark(
        self,
        adjacency_matrix: np.ndarray,
        num_trials: int = 10
    ) -> Dict[str, Any]:
        """
        Benchmark QAOA performance.

        Args:
            adjacency_matrix: Test graph
            num_trials: Number of trials for statistics

        Returns:
            Benchmark results with statistics
        """
        results = []

        for _ in range(num_trials):
            result = self.optimize_maxcut(adjacency_matrix)
            results.append({
                "cost": result.cost,
                "time": result.execution_time,
                "method": result.method
            })

        costs = [r["cost"] for r in results]
        times = [r["time"] for r in results]

        return {
            "method": results[0]["method"],
            "num_qubits": self.num_qubits,
            "p_depth": self.p_depth,
            "trials": num_trials,
            "cost_mean": np.mean(costs),
            "cost_std": np.std(costs),
            "cost_max": np.max(costs),
            "time_mean": np.mean(times),
            "time_std": np.std(times),
            "optimal_found_ratio": sum(1 for c in costs if c == max(costs)) / num_trials
        }

    @staticmethod
    def is_qiskit_available() -> bool:
        """Check if Qiskit is available."""
        return QISKIT_AVAILABLE


def run_qaoa_benchmark(num_nodes: int = 10, p_depth: int = 1) -> Dict[str, Any]:
    """
    Run QAOA benchmark for network optimization.

    Args:
        num_nodes: Number of nodes in test graph
        p_depth: QAOA circuit depth

    Returns:
        Benchmark results
    """
    # Generate random weighted graph
    np.random.seed(42)
    adjacency = np.random.rand(num_nodes, num_nodes)
    adjacency = (adjacency + adjacency.T) / 2  # Make symmetric
    np.fill_diagonal(adjacency, 0)

    optimizer = QAOAOptimizer(num_nodes, p_depth=p_depth)
    results = optimizer.benchmark(adjacency, num_trials=10)

    logger.info(f"QAOA Benchmark ({num_nodes} nodes, p={p_depth}):")
    logger.info(f"  Method: {results['method']}")
    logger.info(f"  Cost: {results['cost_mean']:.2f} ± {results['cost_std']:.2f}")
    logger.info(f"  Time: {results['time_mean']*1000:.1f}ms ± {results['time_std']*1000:.1f}ms")
    logger.info(f"  Optimal ratio: {results['optimal_found_ratio']:.1%}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_qaoa_benchmark(10, p_depth=2)
