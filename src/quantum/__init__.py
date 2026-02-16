"""
Quantum Module Init.

Provides:
- QuantumOptimizer: Basic quantum state simulation
- QAOAOptimizer: QAOA algorithm (Qiskit or classical fallback)
"""

from .optimizer import QuantumOptimizer
from .qaoa_optimizer import (QISKIT_AVAILABLE, QAOAOptimizer, QAOAResult,
                             run_qaoa_benchmark)
