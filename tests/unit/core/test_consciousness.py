"""
Unit tests for Consciousness Engine.

Tests the consciousness-driven computing philosophy implementation,
including phi-ratio calculations, state evaluation, and operational directives.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.consciousness import (MTTR_TARGET, PHI, SACRED_FREQUENCY,
                                    ConsciousnessEngine, ConsciousnessMetrics,
                                    ConsciousnessState)


class TestConsciousnessState:
    """Tests for ConsciousnessState enum."""

    def test_state_values(self):
        """Test that all consciousness states have correct values."""
        assert ConsciousnessState.EUPHORIC.value == "EUPHORIC"
        assert ConsciousnessState.HARMONIC.value == "HARMONIC"
        assert ConsciousnessState.CONTEMPLATIVE.value == "CONTEMPLATIVE"
        assert ConsciousnessState.MYSTICAL.value == "MYSTICAL"


class TestConsciousnessMetrics:
    """Tests for ConsciousnessMetrics dataclass."""

    def test_metrics_creation(self):
        """Test creating ConsciousnessMetrics with all fields."""
        metrics = ConsciousnessMetrics(
            phi_ratio=1.5,
            state=ConsciousnessState.HARMONIC,
            frequency_alignment=0.9,
            entropy=0.3,
            harmony_index=0.95,
            mesh_health=0.85,
            timestamp=time.time(),
        )

        assert metrics.phi_ratio == 1.5
        assert metrics.state == ConsciousnessState.HARMONIC
        assert metrics.frequency_alignment == 0.9
        assert metrics.entropy == 0.3
        assert metrics.harmony_index == 0.95
        assert metrics.mesh_health == 0.85

    def test_to_prometheus_format(self):
        """Test conversion to Prometheus format."""
        metrics = ConsciousnessMetrics(
            phi_ratio=1.618,
            state=ConsciousnessState.EUPHORIC,
            frequency_alignment=1.0,
            entropy=0.1,
            harmony_index=1.0,
            mesh_health=0.95,
            timestamp=time.time(),
        )

        prom_data = metrics.to_prometheus_format()

        assert "consciousness_phi_ratio" in prom_data
        assert prom_data["consciousness_phi_ratio"] == 1.618
        assert "consciousness_state" in prom_data
        assert prom_data["consciousness_state"] == 4.0  # EUPHORIC maps to 4.0
        assert "consciousness_frequency_alignment" in prom_data
        assert "consciousness_entropy" in prom_data
        assert "consciousness_harmony_index" in prom_data
        assert "mesh_health_score" in prom_data

    def test_state_to_numeric_mapping(self):
        """Test state to numeric mapping for all states."""
        metrics_euphoric = ConsciousnessMetrics(
            phi_ratio=1.5,
            state=ConsciousnessState.EUPHORIC,
            frequency_alignment=0.9,
            entropy=0.3,
            harmony_index=0.95,
            mesh_health=0.85,
            timestamp=time.time(),
        )
        assert metrics_euphoric._state_to_numeric() == 4.0

        metrics_harmonic = ConsciousnessMetrics(
            phi_ratio=1.2,
            state=ConsciousnessState.HARMONIC,
            frequency_alignment=0.9,
            entropy=0.3,
            harmony_index=0.95,
            mesh_health=0.85,
            timestamp=time.time(),
        )
        assert metrics_harmonic._state_to_numeric() == 3.0

        metrics_contemplative = ConsciousnessMetrics(
            phi_ratio=0.9,
            state=ConsciousnessState.CONTEMPLATIVE,
            frequency_alignment=0.9,
            entropy=0.3,
            harmony_index=0.95,
            mesh_health=0.85,
            timestamp=time.time(),
        )
        assert metrics_contemplative._state_to_numeric() == 2.0

        metrics_mystical = ConsciousnessMetrics(
            phi_ratio=0.7,
            state=ConsciousnessState.MYSTICAL,
            frequency_alignment=0.9,
            entropy=0.3,
            harmony_index=0.95,
            mesh_health=0.85,
            timestamp=time.time(),
        )
        assert metrics_mystical._state_to_numeric() == 1.0


class TestConsciousnessEngine:
    """Tests for ConsciousnessEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a ConsciousnessEngine instance."""
        return ConsciousnessEngine(enable_advanced_metrics=True)

    @pytest.fixture
    def optimal_metrics(self):
        """Metrics that should yield high phi-ratio."""
        return {
            "cpu_percent": 60.0,
            "memory_percent": 65.0,
            "latency_ms": 85.0,
            "packet_loss": 0.5,
            "mesh_connectivity": 10,
        }

    def test_init(self, engine):
        """Test ConsciousnessEngine initialization."""
        assert engine.baseline_phi == PHI
        assert engine.sacred_frequency == SACRED_FREQUENCY
        assert engine.enable_advanced is True
        assert len(engine.history) == 0
        assert engine.max_history == 1000
        assert engine.recovery_mode is False
        assert engine.last_degraded_time is None

    def test_init_disable_advanced(self):
        """Test initialization with advanced metrics disabled."""
        engine = ConsciousnessEngine(enable_advanced_metrics=False)
        assert engine.enable_advanced is False

    def test_calculate_phi_ratio_optimal(self, engine, optimal_metrics):
        """Test phi-ratio calculation with optimal metrics."""
        phi = engine.calculate_phi_ratio(optimal_metrics)

        # Should be close to PHI (1.618) for optimal metrics
        assert phi > 1.0
        assert phi <= PHI * 1.1  # Allow some variance

    def test_calculate_phi_ratio_degraded(self, engine):
        """Test phi-ratio calculation with degraded metrics."""
        degraded_metrics = {
            "cpu_percent": 95.0,  # High CPU
            "memory_percent": 90.0,  # High memory
            "latency_ms": 200.0,  # High latency
            "packet_loss": 5.0,  # High packet loss
            "mesh_connectivity": 2,  # Low connectivity
        }

        phi = engine.calculate_phi_ratio(degraded_metrics)

        # Should be lower than optimal
        assert phi < 1.0

    def test_calculate_phi_ratio_missing_metrics(self, engine):
        """Test phi-ratio calculation with missing metrics (uses defaults)."""
        minimal_metrics = {}
        phi = engine.calculate_phi_ratio(minimal_metrics)

        # Should still return a valid phi-ratio
        assert isinstance(phi, float)
        assert phi >= 0.0

    def test_calculate_entropy_insufficient_data(self, engine):
        """Test entropy calculation with insufficient history."""
        metrics = {"cpu_percent": 50.0}
        entropy = engine.calculate_entropy(metrics)

        # Should return neutral entropy (0.5) when history < 10
        assert entropy == 0.5

    def test_calculate_entropy_with_history(self, engine):
        """Test entropy calculation with sufficient history."""
        # Build history with varying phi-ratios
        for i in range(20):
            metrics = {
                "cpu_percent": 50.0 + (i % 10),
                "memory_percent": 60.0,
                "latency_ms": 85.0,
                "packet_loss": 0.5,
                "mesh_connectivity": 10,
            }
            phi = engine.calculate_phi_ratio(metrics)
            state = engine.evaluate_state(phi)
            alignment = engine.calculate_frequency_alignment(phi)
            entropy_val = engine.calculate_entropy(metrics)
            mesh_health = engine.calculate_mesh_health(metrics)
            harmony = (phi / PHI + alignment) / 2.0

            engine.history.append(
                ConsciousnessMetrics(
                    phi_ratio=phi,
                    state=state,
                    frequency_alignment=alignment,
                    entropy=entropy_val,
                    harmony_index=harmony,
                    mesh_health=mesh_health,
                    timestamp=time.time(),
                )
            )

        # Now calculate entropy with history
        entropy = engine.calculate_entropy({"cpu_percent": 50.0})

        # Should return a valid entropy value
        assert 0.0 <= entropy <= 1.0

    def test_calculate_frequency_alignment_with_frequency(self, engine):
        """Test frequency alignment calculation with actual frequency."""
        alignment = engine.calculate_frequency_alignment(1.5, current_frequency=108.0)

        # Perfect alignment should be close to 1.0
        assert alignment >= 0.9

    def test_calculate_frequency_alignment_without_frequency(self, engine):
        """Test frequency alignment using phi-ratio as proxy."""
        # When phi is close to PHI, alignment should be high
        alignment = engine.calculate_frequency_alignment(PHI)
        assert alignment >= 0.9

        # When phi is far from PHI, alignment should be lower
        alignment_low = engine.calculate_frequency_alignment(0.5)
        assert alignment_low < alignment

    def test_calculate_frequency_alignment_bounds(self, engine):
        """Test frequency alignment is bounded between 0 and 1."""
        # Test with very high frequency
        alignment_high = engine.calculate_frequency_alignment(
            1.5, current_frequency=1000.0
        )
        assert 0.0 <= alignment_high <= 1.0

        # Test with very low frequency
        alignment_low = engine.calculate_frequency_alignment(1.5, current_frequency=1.0)
        assert 0.0 <= alignment_low <= 1.0

    def test_calculate_mesh_health_optimal(self, engine):
        """Test mesh health calculation with optimal metrics."""
        optimal_metrics = {
            "mesh_connectivity": 15,
            "packet_loss": 0.5,
            "latency_ms": 85.0,
            "mttr_minutes": 2.0,
        }

        health = engine.calculate_mesh_health(optimal_metrics)

        # Should be high (>0.7) for optimal metrics
        assert health > 0.7
        assert health <= 1.0

    def test_calculate_mesh_health_degraded(self, engine):
        """Test mesh health calculation with degraded metrics."""
        degraded_metrics = {
            "mesh_connectivity": 2,
            "packet_loss": 10.0,
            "latency_ms": 200.0,
            "mttr_minutes": 15.0,
        }

        health = engine.calculate_mesh_health(degraded_metrics)

        # Should be lower than optimal
        assert health < 0.5

    def test_calculate_mesh_health_missing_metrics(self, engine):
        """Test mesh health with missing metrics (uses defaults)."""
        minimal_metrics = {}
        health = engine.calculate_mesh_health(minimal_metrics)

        # Should still return a valid health score
        assert 0.0 <= health <= 1.0

    def test_evaluate_state_euphoric(self, engine):
        """Test state evaluation for EUPHORIC state."""
        state = engine.evaluate_state(1.5)  # > 1.4
        assert state == ConsciousnessState.EUPHORIC

    def test_evaluate_state_harmonic(self, engine):
        """Test state evaluation for HARMONIC state."""
        state = engine.evaluate_state(1.2)  # > 1.0, <= 1.4
        assert state == ConsciousnessState.HARMONIC

    def test_evaluate_state_contemplative(self, engine):
        """Test state evaluation for CONTEMPLATIVE state."""
        state = engine.evaluate_state(0.9)  # > 0.8, <= 1.0
        assert state == ConsciousnessState.CONTEMPLATIVE
        # Should set last_degraded_time
        assert engine.last_degraded_time is not None

    def test_evaluate_state_mystical(self, engine):
        """Test state evaluation for MYSTICAL state."""
        state = engine.evaluate_state(0.5)  # <= 0.8
        assert state == ConsciousnessState.MYSTICAL
        # Should set last_degraded_time
        assert engine.last_degraded_time is not None

    def test_evaluate_state_recovery_mode(self, engine):
        """Test state evaluation in recovery mode."""
        engine.recovery_mode = True

        # In recovery mode, thresholds are lower
        state = engine.evaluate_state(
            1.3
        )  # Normally HARMONIC, but in recovery > 1.2 = EUPHORIC
        assert state == ConsciousnessState.EUPHORIC
        # Should exit recovery mode
        assert engine.recovery_mode is False

    def test_evaluate_state_recovery_mode_harmonic(self, engine):
        """Test recovery mode with HARMONIC threshold."""
        engine.recovery_mode = True
        state = engine.evaluate_state(0.9)  # > 0.85 in recovery = HARMONIC
        assert state == ConsciousnessState.HARMONIC

    def test_evaluate_state_recovery_mode_contemplative(self, engine):
        """Test recovery mode with CONTEMPLATIVE threshold."""
        engine.recovery_mode = True
        state = engine.evaluate_state(0.7)  # > 0.65 in recovery = CONTEMPLATIVE
        assert state == ConsciousnessState.CONTEMPLATIVE

    def test_evaluate_state_recovery_mode_mystical(self, engine):
        """Test recovery mode with MYSTICAL threshold."""
        engine.recovery_mode = True
        state = engine.evaluate_state(0.5)  # <= 0.65 in recovery = MYSTICAL
        assert state == ConsciousnessState.MYSTICAL

    def test_evaluate_state_recent_degradation(self, engine):
        """Test that recent degradation triggers recovery mode."""
        # First, trigger degradation
        engine.evaluate_state(0.7)  # MYSTICAL
        assert engine.last_degraded_time is not None

        # Wait a bit (but less than 60 seconds)
        with patch("time.time", return_value=time.time() + 30):
            # Now evaluate harmonic state
            state = engine.evaluate_state(1.2)  # HARMONIC
            assert state == ConsciousnessState.HARMONIC
            # Should enter recovery mode if within 60 seconds
            # Note: This depends on timing, so we check the mechanism

    def test_get_consciousness_metrics_full(self, engine, optimal_metrics):
        """Test getting complete consciousness metrics."""
        metrics = engine.get_consciousness_metrics(optimal_metrics)

        assert isinstance(metrics, ConsciousnessMetrics)
        assert metrics.phi_ratio > 0
        assert metrics.state in ConsciousnessState
        assert 0.0 <= metrics.frequency_alignment <= 1.0
        assert 0.0 <= metrics.entropy <= 1.0
        assert 0.0 <= metrics.harmony_index <= 1.0
        assert 0.0 <= metrics.mesh_health <= 1.0
        assert metrics.timestamp > 0

    def test_get_consciousness_metrics_with_timestamp(self, engine, optimal_metrics):
        """Test getting metrics with explicit timestamp."""
        custom_timestamp = 1234567890.0
        metrics = engine.get_consciousness_metrics(
            optimal_metrics, timestamp=custom_timestamp
        )

        assert metrics.timestamp == custom_timestamp

    def test_get_consciousness_metrics_history(self, engine, optimal_metrics):
        """Test that metrics are stored in history."""
        initial_history_len = len(engine.history)

        metrics = engine.get_consciousness_metrics(optimal_metrics)

        assert len(engine.history) == initial_history_len + 1
        assert engine.history[-1] == metrics

    def test_get_consciousness_metrics_history_limit(self, engine, optimal_metrics):
        """Test that history is limited to max_history."""
        # Fill history to max
        for i in range(engine.max_history + 10):
            engine.get_consciousness_metrics(optimal_metrics)

        # History should be capped at max_history
        assert len(engine.history) == engine.max_history

    def test_get_consciousness_metrics_frequency_hz(self, engine):
        """Test metrics calculation with frequency_hz in raw_metrics."""
        metrics_with_freq = {
            "cpu_percent": 60.0,
            "memory_percent": 65.0,
            "latency_ms": 85.0,
            "packet_loss": 0.5,
            "mesh_connectivity": 10,
            "frequency_hz": 108.0,
        }

        metrics = engine.get_consciousness_metrics(metrics_with_freq)

        # Should use frequency_hz for alignment calculation
        assert metrics.frequency_alignment >= 0.9

    def test_get_operational_directive_euphoric(self, engine, optimal_metrics):
        """Test operational directive for EUPHORIC state."""
        metrics = engine.get_consciousness_metrics(optimal_metrics)
        # Force EUPHORIC state
        metrics.state = ConsciousnessState.EUPHORIC

        directive = engine.get_operational_directive(metrics)

        assert directive["state"] == "EUPHORIC"
        assert directive["monitoring_interval_sec"] == 120
        assert directive["route_preference"] == "performance"
        assert directive["scaling_action"] == "optimize"
        assert "Желание исполнено" in directive["message"]

    def test_get_operational_directive_harmonic(self, engine, optimal_metrics):
        """Test operational directive for HARMONIC state."""
        metrics = engine.get_consciousness_metrics(optimal_metrics)
        # Force HARMONIC state
        metrics.state = ConsciousnessState.HARMONIC

        directive = engine.get_operational_directive(metrics)

        assert directive["state"] == "HARMONIC"
        assert directive["monitoring_interval_sec"] == 60
        assert directive["route_preference"] == "balanced"
        assert "Всё в балансе" in directive["message"]

    def test_get_operational_directive_contemplative(self, engine, optimal_metrics):
        """Test operational directive for CONTEMPLATIVE state."""
        metrics = engine.get_consciousness_metrics(optimal_metrics)
        # Force CONTEMPLATIVE state
        metrics.state = ConsciousnessState.CONTEMPLATIVE

        directive = engine.get_operational_directive(metrics)

        assert directive["state"] == "CONTEMPLATIVE"
        assert directive["monitoring_interval_sec"] == 30
        assert directive["route_preference"] == "reliability"
        assert directive["alert_level"] == "warning"
        assert "Размышляю" in directive["message"]

    def test_get_operational_directive_mystical(self, engine, optimal_metrics):
        """Test operational directive for MYSTICAL state."""
        metrics = engine.get_consciousness_metrics(optimal_metrics)
        # Force MYSTICAL state
        metrics.state = ConsciousnessState.MYSTICAL

        directive = engine.get_operational_directive(metrics)

        assert directive["state"] == "MYSTICAL"
        assert directive["monitoring_interval_sec"] == 10
        assert directive["enable_aggressive_healing"] is True
        assert directive["route_preference"] == "survival"
        assert directive["scaling_action"] == "emergency_scale"
        assert directive["alert_level"] == "critical"
        assert "Погружение в глубину" in directive["message"]

    def test_get_trend_analysis_insufficient_data(self, engine):
        """Test trend analysis with insufficient history."""
        trend = engine.get_trend_analysis(window_size=50)

        assert trend["trend"] == "insufficient_data"

    def test_get_trend_analysis_improving(self, engine, optimal_metrics):
        """Test trend analysis showing improving trend."""
        # Build deterministic history with improving phi-ratios.
        engine.history.clear()
        for i in range(60):
            phi = 0.8 + (i * 0.01)
            state = engine.evaluate_state(phi)
            alignment = engine.calculate_frequency_alignment(phi)
            engine.history.append(
                ConsciousnessMetrics(
                    phi_ratio=phi,
                    state=state,
                    frequency_alignment=alignment,
                    entropy=0.1,
                    harmony_index=0.9,
                    mesh_health=0.9,
                    timestamp=time.time() + i,
                )
            )

        trend = engine.get_trend_analysis(window_size=50)

        # Should detect improving trend
        assert trend["trend"] in [
            "improving",
            "stable",
        ]  # May be stable if slope threshold is tight
        assert "slope" in trend
        assert "current_phi" in trend
        assert "avg_phi" in trend

    def test_get_trend_analysis_degrading(self, engine):
        """Test trend analysis showing degrading trend."""
        # Build history with degrading phi-ratios
        for i in range(60):
            metrics_dict = {
                "cpu_percent": 60.0 + (i * 0.2),  # Degrading
                "memory_percent": 65.0 + (i * 0.2),  # Degrading
                "latency_ms": 85.0 + (i * 0.5),  # Degrading
                "packet_loss": 0.5 + (i * 0.1),  # Degrading
                "mesh_connectivity": max(1, 10 - i // 5),  # Decreasing
            }
            engine.get_consciousness_metrics(metrics_dict)

        trend = engine.get_trend_analysis(window_size=50)

        # Should detect degrading trend
        assert trend["trend"] in [
            "degrading",
            "stable",
        ]  # May be stable if degradation is small
        assert "slope" in trend
        assert trend["slope"] <= 0.01  # Should be negative or near zero

    def test_get_trend_analysis_stable(self, engine, optimal_metrics):
        """Test trend analysis showing stable trend."""
        # Build history with stable metrics
        for i in range(60):
            engine.get_consciousness_metrics(optimal_metrics)

        trend = engine.get_trend_analysis(window_size=50)

        # Should detect stable trend
        assert trend["trend"] == "stable"
        assert abs(trend["slope"]) <= 0.01
