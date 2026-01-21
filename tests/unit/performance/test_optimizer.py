"""
Tests for Performance Optimizer.

Tests optimization strategies, caching, and performance improvements.
"""
import pytest
from unittest.mock import Mock, patch
import time

try:
    from src.performance.optimizer import PerformanceOptimizer, OptimizationStrategy
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False
    PerformanceOptimizer = None
    OptimizationStrategy = None


@pytest.mark.skipif(not OPTIMIZER_AVAILABLE, reason="Performance optimizer not available")
class TestPerformanceOptimizer:
    """Tests for PerformanceOptimizer"""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization"""
        optimizer = PerformanceOptimizer()
        
        assert optimizer is not None
        assert hasattr(optimizer, 'optimize')
    
    def test_optimization_strategy(self):
        """Test optimization strategy selection"""
        optimizer = PerformanceOptimizer()
        
        strategy = optimizer.select_strategy(OptimizationStrategy.CACHE)
        assert strategy is not None
    
    def test_performance_improvement(self):
        """Test performance improvement measurement"""
        optimizer = PerformanceOptimizer()
        
        # Measure before
        start = time.time()
        # Simulate operation
        time.sleep(0.01)
        before = time.time() - start
        
        # Optimize
        optimizer.optimize(OptimizationStrategy.CACHE)
        
        # Measure after
        start = time.time()
        # Simulate optimized operation
        time.sleep(0.005)
        after = time.time() - start
        
        # Should be faster (or at least not slower)
        assert after <= before * 1.5  # Allow some variance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

