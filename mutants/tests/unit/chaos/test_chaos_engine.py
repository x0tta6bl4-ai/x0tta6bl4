"""
Tests for Chaos Engine.

Tests chaos injection, scenario execution, and recovery verification.
"""
import pytest
from unittest.mock import Mock, patch
import asyncio

try:
    from src.chaos.chaos_engine import ChaosEngine, ChaosScenario
    CHAOS_ENGINE_AVAILABLE = True
except ImportError:
    CHAOS_ENGINE_AVAILABLE = False
    ChaosEngine = None
    ChaosScenario = None


@pytest.mark.skipif(not CHAOS_ENGINE_AVAILABLE, reason="Chaos engine not available")
class TestChaosEngine:
    """Tests for ChaosEngine"""
    
    def test_chaos_engine_initialization(self):
        """Test chaos engine initialization"""
        engine = ChaosEngine()
        
        assert engine is not None
        assert hasattr(engine, 'run_scenario')
    
    @pytest.mark.asyncio
    async def test_scenario_execution(self):
        """Test chaos scenario execution"""
        engine = ChaosEngine()
        
        # Create mock scenario
        scenario = Mock(spec=ChaosScenario)
        scenario.name = "test_scenario"
        scenario.inject_chaos = Mock(return_value=None)
        scenario.verify_recovery = Mock(return_value=True)
        
        # Run scenario
        result = await engine.run_scenario(scenario)
        
        assert result is not None
        scenario.inject_chaos.assert_called_once()
        scenario.verify_recovery.assert_called_once()
    
    def test_scenario_registration(self):
        """Test scenario registration"""
        engine = ChaosEngine()
        
        scenario = Mock(spec=ChaosScenario)
        scenario.name = "test"
        
        engine.register_scenario(scenario)
        assert scenario.name in [s.name for s in engine.scenarios]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

