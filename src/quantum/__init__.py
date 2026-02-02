"""
Quantum Module Init.

Provides:
- QuantumOptimizer: Basic quantum state simulation
- QAOAOptimizer: QAOA algorithm (Qiskit or classical fallback)
"""
from .optimizer import QuantumOptimizer
from .qaoa_optimizer import QAOAOptimizer, QAOAResult, run_qaoa_benchmark, QISKIT_AVAILABLE
