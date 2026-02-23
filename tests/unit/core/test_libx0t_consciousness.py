import pytest
from unittest.mock import MagicMock, patch
import time
from libx0t.core.consciousness import (
    ConsciousnessEngine,
    ConsciousnessMetrics,
    ConsciousnessState,
    PHI,
    SACRED_FREQUENCY
)

class TestConsciousnessMetrics:
    def test_to_prometheus_format(self):
        metrics = ConsciousnessMetrics(
            phi_ratio=1.618,
            state=ConsciousnessState.HARMONIC,
            frequency_alignment=0.9,
            entropy=0.1,
            harmony_index=0.95,
            mesh_health=0.8,
            timestamp=time.time()
        )
        prom_metrics = metrics.to_prometheus_format()
        assert prom_metrics["consciousness_phi_ratio"] == 1.618
        assert prom_metrics["consciousness_state"] == 3.0
        assert prom_metrics["consciousness_frequency_alignment"] == 0.9
        assert prom_metrics["consciousness_entropy"] == 0.1

class TestConsciousnessEngine:
    @pytest.fixture
    def engine(self):
        with patch("libx0t.core.consciousness.create_graphsage_detector_for_mapek") as mock_gs, \
             patch("libx0t.core.consciousness.LocalLLM") as mock_llm:
            
            mock_detector = MagicMock()
            mock_gs.return_value = mock_detector
            
            engine = ConsciousnessEngine(enable_advanced_metrics=True)
            engine.graphsage_detector = mock_detector # Explicitly set in case init calls it
            return engine

    def test_init(self, engine):
        assert engine.baseline_phi == PHI
        assert engine.recovery_mode is False
        assert len(engine.history) == 0

    def test_calculate_phi_ratio_perfect(self, engine):
        metrics = {
            "cpu_percent": 60.0,
            "memory_percent": 65.0,
            "latency_ms": 85.0,
            "packet_loss": 0.0,
            "mesh_connectivity": 100
        }
        phi = engine.calculate_phi_ratio(metrics)
        # Should be close to PHI
        assert abs(phi - PHI) < 0.2

    def test_calculate_phi_ratio_poor(self, engine):
        metrics = {
            "cpu_percent": 100.0,
            "memory_percent": 100.0,
            "latency_ms": 1000.0,
            "packet_loss": 50.0,
            "mesh_connectivity": 0
        }
        phi = engine.calculate_phi_ratio(metrics)
        assert phi < PHI * 0.5

    def test_evaluate_state(self, engine):
        assert engine.evaluate_state(1.5) == ConsciousnessState.EUPHORIC
        assert engine.evaluate_state(1.2) == ConsciousnessState.HARMONIC
        assert engine.evaluate_state(0.9) == ConsciousnessState.CONTEMPLATIVE
        assert engine.evaluate_state(0.5) == ConsciousnessState.MYSTICAL

    def test_recovery_mode_logic(self, engine):
        # Enter mystical state
        engine.evaluate_state(0.1)
        assert engine.last_degraded_time is not None
        
        # Simulate quick recovery check (within 60s)
        # We need to ensure we trigger the recovery mode logic inside evaluate_state
        # For harmonic state (phi > 1.0), it checks last_degraded_time
        
        state = engine.evaluate_state(1.1) # Harmonic range
        assert state == ConsciousnessState.HARMONIC
        assert engine.recovery_mode is True
        
        # Now in recovery mode, thresholds are lower
        # 1.25 is normally Harmonic (<1.4), but in recovery >1.2 is Euphoric
        assert engine.evaluate_state(1.25) == ConsciousnessState.EUPHORIC
        assert engine.recovery_mode is False # Should exit recovery

    def test_get_consciousness_metrics(self, engine):
        # Mock GraphSAGE prediction
        mock_prediction = MagicMock()
        mock_prediction.anomaly_score = 0.0 # Perfect health
        engine.graphsage_detector.predict.return_value = mock_prediction
        
        raw_metrics = {
            "cpu_percent": 0.6,
            "latency_ms": 50.0
        }
        
        metrics = engine.get_consciousness_metrics(raw_metrics)
        
        assert isinstance(metrics, ConsciousnessMetrics)
        # With 0 anomaly score, phi should be close to PHI
        assert metrics.phi_ratio > 1.0 
        assert len(engine.history) == 1

    def test_get_operational_directive_euphoric(self, engine):
        metrics = ConsciousnessMetrics(
            phi_ratio=2.0, state=ConsciousnessState.EUPHORIC,
            frequency_alignment=1.0, entropy=0.0, harmony_index=1.0, mesh_health=1.0, timestamp=0
        )
        directives = engine.get_operational_directive(metrics)
        assert directives["scaling_action"] == "optimize"
        assert directives["route_preference"] == "low_latency"

    def test_get_operational_directive_mystical(self, engine):
        metrics = ConsciousnessMetrics(
            phi_ratio=0.5, state=ConsciousnessState.MYSTICAL,
            frequency_alignment=0.0, entropy=1.0, harmony_index=0.0, mesh_health=0.0, timestamp=0
        )
        directives = engine.get_operational_directive(metrics)
        assert directives["enable_aggressive_healing"] is True
        assert directives["alert_level"] == "critical"

    def test_get_system_thought(self, engine):
        engine.llm.generate.return_value = "I am at peace."
        metrics = ConsciousnessMetrics(
            phi_ratio=1.618, state=ConsciousnessState.HARMONIC,
            frequency_alignment=1.0, entropy=0.0, harmony_index=1.0, mesh_health=1.0, timestamp=0
        )
        thought = engine.get_system_thought(metrics)
        assert thought == "I am at peace."

    def test_calculate_frequency_alignment(self, engine):
        # Exact match
        align = engine.calculate_frequency_alignment(PHI, current_frequency=SACRED_FREQUENCY)
        assert align == 1.0
        
        # Deviation
        align = engine.calculate_frequency_alignment(PHI, current_frequency=SACRED_FREQUENCY * 0.5)
        assert align == 0.5

    def test_calculate_mesh_health(self, engine):
        metrics = {
            "mesh_connectivity": 100,
            "packet_loss": 0.0,
            "latency_ms": 50.0,
            "mttr_minutes": 0.0
        }
        health = engine.calculate_mesh_health(metrics)
        assert health > 0.9 # Should be very high
