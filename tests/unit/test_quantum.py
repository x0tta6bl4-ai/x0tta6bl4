
import unittest
import numpy as np
from src.quantum.optimizer import QuantumOptimizer

class TestQuantumOptimizer(unittest.TestCase):
    def setUp(self):
        self.optimizer = QuantumOptimizer(num_nodes=4)
        
    def test_optimization_run(self):
        # Simple square graph adjacency matrix
        # 0-1, 1-2, 2-3, 3-0
        matrix = np.array([
            [0, 1, 0, 1],
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [1, 0, 1, 0]
        ])
        
        result = self.optimizer.optimize_topology(matrix)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(bit in [0, 1] for bit in result))
        
        # Optimal solution for square is alternating 0,1,0,1 (Cut=4)
        # 0,1,0,1 -> edges (0,1)=diff, (1,2)=diff, (2,3)=diff, (3,0)=diff. All 4 edges cut.
        # Our simulated annealing should find this or close to it.
        
    def test_coherence_metrics(self):
        metrics = self.optimizer.get_coherence_metrics()
        self.assertIn("gate_fidelity", metrics)
        self.assertGreater(metrics["gate_fidelity"], 0.9)

if __name__ == '__main__':
    unittest.main()
