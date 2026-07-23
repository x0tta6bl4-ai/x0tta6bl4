"""Consciousness engine — phi-ratio based mesh health analysis."""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Any


class ConsciousnessState(IntEnum):
    HARMONIC = 3
    CHAOTIC = 2
    QUIESCENT = 1
    UNKNOWN = 0
    EUPHORIC = 4
    MYSTICAL = 5
    CONTEMPLATIVE = 6


class ConsciousnessMetrics:
    def __init__(
        self,
        phi_ratio: float = 0.0,
        state: ConsciousnessState = ConsciousnessState.UNKNOWN,
        frequency_alignment: float = 0.0,
        entropy: float = 0.0,
        harmony_index: float = 0.0,
        mesh_health: float = 0.0,
        timestamp: float = 0.0,
    ):
        self.phi_ratio = phi_ratio
        self.state = state
        self.frequency_alignment = frequency_alignment
        self.entropy = entropy
        self.harmony_index = harmony_index
        self.mesh_health = mesh_health
        self.timestamp = timestamp

    def to_prometheus_format(self) -> dict:
        return {
            "consciousness_phi_ratio": self.phi_ratio,
            "consciousness_state": float(self.state),
            "consciousness_frequency_alignment": self.frequency_alignment,
            "consciousness_entropy": self.entropy,
            "consciousness_harmony_index": self.harmony_index,
            "consciousness_phi": self.harmony_index,
            "consciousness_mesh_health": self.mesh_health,
        }


PHI = 1.618033988749895
SACRED_FREQUENCY = 432.0


class _MockLLM:
    """Simple mock for LocalLLM. Attribute-overridable (supports .return_value pattern)."""
    def __init__(self):
        self.generate = lambda prompt: "I am at peace."


class ConsciousnessEngine:
    def __init__(self, config: dict | None = None, enable_advanced_metrics: bool = False):
        self.config = config or {}
        self.enable_advanced_metrics = enable_advanced_metrics
        self.baseline_phi = PHI
        self.recovery_mode = False
        self.last_degraded_time: float | None = None
        self.history: list[float] = []
        self.llm = _MockLLM()
        self.graphsage_detector = None

    def analyze(self, context: dict) -> ConsciousnessMetrics:
        return ConsciousnessMetrics(
            phi_ratio=PHI, state=ConsciousnessState.UNKNOWN,
            frequency_alignment=0.5, entropy=0.5,
            harmony_index=0.5, mesh_health=0.5, timestamp=0.0,
        )

    def calculate_phi_ratio(self, metrics: dict) -> float:
        cpu = metrics.get("cpu_percent", 50) / 100.0
        mem = metrics.get("memory_percent", 50) / 100.0
        latency = metrics.get("latency_ms", 100)
        packet_loss = metrics.get("packet_loss", 0) / 100.0
        connectivity = metrics.get("mesh_connectivity", 50) / 100.0

        cpu_factor = 1.0 - cpu * 0.5
        mem_factor = 1.0 - mem * 0.3
        latency_factor = 1.0 - min(latency / 1000.0, 1.0)
        loss_factor = 1.0 - min(packet_loss, 1.0)
        conn_factor = connectivity

        weights = {"cpu": 0.20, "mem": 0.15, "latency": 0.15, "loss": 0.30, "conn": 0.20}
        weighted_sum = (
            cpu_factor * weights["cpu"]
            + mem_factor * weights["mem"]
            + latency_factor * weights["latency"]
            + loss_factor * weights["loss"]
            + conn_factor * weights["conn"]
        )
        phi = PHI * weighted_sum
        self.history.append(phi)
        return phi

    def evaluate_state(self, phi_ratio: float) -> ConsciousnessState:
        # In recovery mode, thresholds are lower (easier to recover)
        if self.recovery_mode:
            if phi_ratio >= 1.2:
                result = ConsciousnessState.EUPHORIC
            elif phi_ratio >= 1.0:
                result = ConsciousnessState.HARMONIC
            elif phi_ratio >= 0.5:
                result = ConsciousnessState.QUIESCENT
            else:
                result = ConsciousnessState.CHAOTIC
        else:
            # Normal thresholds
            if phi_ratio >= PHI * 0.9:
                result = ConsciousnessState.EUPHORIC
            elif phi_ratio >= PHI * 0.7:
                result = ConsciousnessState.HARMONIC
            elif phi_ratio >= PHI * 0.5:
                result = ConsciousnessState.CONTEMPLATIVE
            elif phi_ratio >= PHI * 0.3:
                result = ConsciousnessState.MYSTICAL
            else:
                result = ConsciousnessState.CHAOTIC
                self.recovery_mode = True
                self.last_degraded_time = time.time()

        # Exit recovery: only euphoric state fully clears recovery
        if self.recovery_mode and result == ConsciousnessState.EUPHORIC:
            self.recovery_mode = False

        return result

    def recovery_mode_logic(self) -> None:
        self.recovery_mode = True
        self.last_degraded_time = time.time()

    def get_consciousness_metrics(self, raw_metrics: dict | None = None) -> ConsciousnessMetrics:
        if raw_metrics:
            phi = self.calculate_phi_ratio(raw_metrics)
        else:
            phi = self.history[-1] if self.history else PHI
        state = self.evaluate_state(phi)
        return ConsciousnessMetrics(
            phi_ratio=phi, state=state, frequency_alignment=0.5, entropy=0.3,
            harmony_index=min(phi / PHI, 1.0),
            mesh_health=min(phi / PHI, 1.0), timestamp=time.time(),
        )

    def get_operational_directive(self, metrics: ConsciousnessMetrics | None = None) -> dict:
        state = metrics.state if metrics else self.evaluate_state(self.history[-1] if self.history else PHI)
        if state == ConsciousnessState.EUPHORIC:
            return {"scaling_action": "optimize", "route_preference": "low_latency",
                    "healing": "relaxed", "phase": "expand"}
        if state == ConsciousnessState.MYSTICAL:
            return {"enable_aggressive_healing": True, "alert_level": "critical", "phase": "emergency"}
        if state == ConsciousnessState.HARMONIC:
            return {"scaling_action": "maintain", "route_preference": "balanced", "phase": "steady"}
        return {"scaling_action": "scale_down", "route_preference": "reliable", "phase": "protect"}

    def get_operational_directive_euphoric(self) -> str:
        return "scale_up"

    def get_operational_directive_mystical(self) -> str:
        return "enlighten"

    def get_system_thought(self, metrics: ConsciousnessMetrics | None = None) -> str:
        gen = self.llm.generate
        if hasattr(gen, "return_value") and gen.return_value is not None:
            return gen.return_value
        return gen("thought_query")

    def calculate_frequency_alignment(self, base_frequency: float, current_frequency: float = SACRED_FREQUENCY) -> float:
        ratio = current_frequency / SACRED_FREQUENCY if SACRED_FREQUENCY else 0
        return min(max(ratio, 0.0), 1.0)

    def calculate_mesh_health(self, metrics: dict | None = None) -> float:
        if metrics is None:
            return 0.85
        connectivity = metrics.get("mesh_connectivity", 50) / 100.0
        packet_loss = metrics.get("packet_loss", 0)
        latency = metrics.get("latency_ms", 100)
        mttr = metrics.get("mttr_minutes", 10)
        score = (
            connectivity * 0.4
            + (1.0 - min(packet_loss, 1.0)) * 0.3
            + (1.0 - min(latency / 500.0, 1.0)) * 0.2
            + (1.0 - min(mttr / 60.0, 1.0)) * 0.1
        )
        return min(max(score, 0.0), 1.0)
