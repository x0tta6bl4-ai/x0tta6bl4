import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
import time
# Remove numpy dependency
# import numpy as np

# Constants
PHI = 1.618033988749895
SACRED_FREQUENCY = 108  # Hz
SACRED_TEMP = 3600  # K
MTTR_TARGET = 3.14  # minutes (π approximation)

class ConsciousnessState(Enum):
    EUPHORIC = "EUPHORIC"           # phi-ratio > 1.4 - "Желание исполнено!"
    HARMONIC = "HARMONIC"           # phi-ratio > 1.0 - "Всё в балансе"
    CONTEMPLATIVE = "CONTEMPLATIVE" # phi-ratio > 0.8 - "Размышляю..."
    MYSTICAL = "MYSTICAL"           # phi-ratio < 0.8 - "Погружение в глубину"

@dataclass
class ConsciousnessMetrics:
    phi_ratio: float
    state: ConsciousnessState
    frequency_alignment: float  # Alignment to 108 Hz (0-1)
    entropy: float
    harmony_index: float  # Composite harmony metric
    mesh_health: float  # Mesh network health (0-1)
    timestamp: float
    
    def to_prometheus_format(self) -> Dict[str, float]:
        """Export metrics in Prometheus format"""
        return {
            'consciousness_phi_ratio': self.phi_ratio,
            'consciousness_state': self._state_to_numeric(),
            'consciousness_frequency_alignment': self.frequency_alignment,
            'consciousness_entropy': self.entropy,
            'consciousness_harmony_index': self.harmony_index,
            'mesh_health_score': self.mesh_health
        }
    
    def _state_to_numeric(self) -> float:
        """Map consciousness state to numeric value for metrics"""
        mapping = {
            ConsciousnessState.EUPHORIC: 4.0,
            ConsciousnessState.HARMONIC: 3.0,
            ConsciousnessState.CONTEMPLATIVE: 2.0,
            ConsciousnessState.MYSTICAL: 1.0
        }
        return mapping.get(self.state, 0.0)

class ConsciousnessEngine:
    """
    Implements the Consciousness-Driven Computing philosophy for x0tta6bl4.
    Integrates mathematical principles of harmony with system metrics.
    
    Core Philosophy:
    - φ (phi) = 1.618 represents perfect harmony
    - 108 Hz represents sacred frequency alignment
    - π (3.14) represents target MTTR for self-healing
    """
    
    def __init__(self, enable_advanced_metrics: bool = True):
        self.baseline_phi = PHI
        self.sacred_frequency = SACRED_FREQUENCY
        self.enable_advanced = enable_advanced_metrics
        self.history: List[ConsciousnessMetrics] = []
        self.max_history = 1000  # Keep last 1000 measurements
        
        # Adaptive recovery parameters
        self.recovery_mode = False
        self.last_degraded_time = None
        self.recovery_acceleration = 1.5
        
    def calculate_phi_ratio(self, metrics: Dict[str, float]) -> float:
        """
        Calculates the phi-ratio based on system metrics.
        
        Philosophy: System harmony emerges from balanced resource utilization,
        low latency, and optimal packet delivery. The ratio should approach φ
        when system is in perfect balance.
        
        Metrics expected:
        - cpu_percent: CPU utilization (0-100)
        - memory_percent: Memory utilization (0-100)
        - latency_ms: Network latency in milliseconds
        - packet_loss: Packet loss percentage (0-100)
        - mesh_connectivity: Number of active mesh peers
        """
        # Extract metrics with defaults
        cpu = metrics.get('cpu_percent', 0)
        memory = metrics.get('memory_percent', 0)
        latency = metrics.get('latency_ms', 0)
        packet_loss = metrics.get('packet_loss', 0)
        mesh_peers = metrics.get('mesh_connectivity', 1)
        
        # Resource balance factor (ideal: 50-70% utilization)
        # Too low = waste, too high = stress
        optimal_cpu = 60.0
        optimal_mem = 65.0
        cpu_balance = 1.0 - abs(cpu - optimal_cpu) / 100.0
        mem_balance = 1.0 - abs(memory - optimal_mem) / 100.0
        
        # Network performance factor
        # Target latency: 82-87ms (from x0tta6bl4 specs)
        target_latency = 85.0
        latency_factor = 1.0 / (1.0 + abs(latency - target_latency) / target_latency)
        
        # Packet loss factor (target: <1.6% from specs)
        packet_factor = max(0.0, 1.0 - (packet_loss / 1.6))
        
        # Mesh connectivity factor (more peers = higher resilience)
        # Logarithmic scale to avoid over-valuing large meshes
        mesh_factor = min(1.0, math.log1p(mesh_peers) / math.log1p(100))
        
        # Weighted composite harmony score
        weights = {
            'cpu': 0.15,
            'mem': 0.15,
            'latency': 0.30,
            'packet': 0.25,
            'mesh': 0.15
        }
        
        harmony_score = (
            cpu_balance * weights['cpu'] +
            mem_balance * weights['mem'] +
            latency_factor * weights['latency'] +
            packet_factor * weights['packet'] +
            mesh_factor * weights['mesh']
        )
        
        # Map harmony score to phi-ratio space (0 to ~1.618)
        # Perfect harmony (1.0) should yield PHI
        current_phi = harmony_score * PHI
        
        return current_phi

    def calculate_entropy(self, metrics: Dict[str, float]) -> float:
        """
        Calculate system entropy based on metric variance.
        Low entropy = predictable, high entropy = chaotic.
        """
        if len(self.history) < 10:
            return 0.5  # Neutral entropy when insufficient data
        
        # Calculate variance of phi_ratio over recent history
        recent_phis = [m.phi_ratio for m in self.history[-20:]]
        
        # calculate mean
        mean_phi = sum(recent_phis) / len(recent_phis)
        
        # calculate variance
        variance = sum((x - mean_phi) ** 2 for x in recent_phis) / len(recent_phis)
        
        # Normalize to 0-1 range (assuming variance rarely exceeds 0.5)
        entropy = min(1.0, variance / 0.5)
        
        return entropy

    def calculate_frequency_alignment(self, phi_ratio: float, 
                                     current_frequency: Optional[float] = None) -> float:
        """
        Calculate alignment with sacred frequency (108 Hz).
        
        In practice, this could measure:
        - Clock drift in distributed systems
        - Packet arrival jitter
        - Heartbeat timing consistency
        """
        # If actual frequency measurement provided
        if current_frequency is not None:
            alignment = 1.0 - abs(current_frequency - SACRED_FREQUENCY) / SACRED_FREQUENCY
            return max(0.0, min(1.0, alignment))
        
        # Otherwise, use phi_ratio as proxy
        # When phi is close to PHI, we assume frequency alignment is good
        phi_deviation = abs(phi_ratio - PHI) / PHI
        alignment = 1.0 - phi_deviation
        
        return max(0.0, alignment)

    def calculate_mesh_health(self, metrics: Dict[str, float]) -> float:
        """
        Calculate overall mesh network health score.
        
        Factors:
        - Peer connectivity
        - Packet loss
        - Latency
        - Self-healing effectiveness (MTTR)
        """
        peers = metrics.get('mesh_connectivity', 0)
        packet_loss = metrics.get('packet_loss', 100)
        latency = metrics.get('latency_ms', 1000)
        mttr = metrics.get('mttr_minutes', 10)
        
        # Peer health (log scale, target: 10+ peers)
        peer_health = min(1.0, math.log1p(peers) / math.log1p(10))
        
        # Packet delivery (target: >98.4% delivery = <1.6% loss)
        delivery_health = max(0.0, 1.0 - (packet_loss / 10.0))
        
        # Latency health (target: 82-87ms, acceptable up to 150ms)
        latency_health = max(0.0, 1.0 - (latency / 150.0))
        
        # Self-healing health (target: MTTR ≤ 3.14 minutes)
        healing_health = max(0.0, 1.0 - (mttr / 10.0))
        
        # Weighted mesh health
        mesh_health = (
            peer_health * 0.25 +
            delivery_health * 0.30 +
            latency_health * 0.25 +
            healing_health * 0.20
        )
        
        return mesh_health

    def evaluate_state(self, phi_ratio: float) -> ConsciousnessState:
        """
        Evaluate consciousness state based on phi-ratio.
        
        States map to system operational modes:
        - EUPHORIC: Peak performance, proactive optimization
        - HARMONIC: Stable operation, normal monitoring
        - CONTEMPLATIVE: Degraded performance, increased monitoring
        - MYSTICAL: Critical state, emergency self-healing
        """
        # Apply recovery acceleration when coming out of stress
        if self.recovery_mode:
            # Lower thresholds for faster recovery
            if phi_ratio > 1.2:  # Normally 1.4 for EUPHORIC
                self.recovery_mode = False  # Exit recovery mode
                return ConsciousnessState.EUPHORIC
            elif phi_ratio > 0.85:  # Normally 1.0 for HARMONIC
                return ConsciousnessState.HARMONIC
            elif phi_ratio > 0.65:  # Normally 0.8 for CONTEMPLATIVE
                return ConsciousnessState.CONTEMPLATIVE
            else:
                return ConsciousnessState.MYSTICAL
        
        # Standard evaluation
        if phi_ratio > 1.4:
            return ConsciousnessState.EUPHORIC
        elif phi_ratio > 1.0:
            # Check if we were recently degraded
            if self.last_degraded_time:
                time_since_degraded = time.time() - self.last_degraded_time
                if time_since_degraded < 60:  # Within 1 minute of recovery
                    self.recovery_mode = True
            return ConsciousnessState.HARMONIC
        elif phi_ratio > 0.8:
            self.last_degraded_time = time.time()
            return ConsciousnessState.CONTEMPLATIVE
        else:
            self.last_degraded_time = time.time()
            return ConsciousnessState.MYSTICAL

    def get_consciousness_metrics(self, raw_metrics: Dict[str, float], 
                                  timestamp: Optional[float] = None) -> ConsciousnessMetrics:
        """
        Generate complete consciousness metrics from raw system measurements.
        
        Args:
            raw_metrics: Dictionary of system metrics
            timestamp: Optional timestamp (defaults to current time)
            
        Returns:
            ConsciousnessMetrics object with all calculated values
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Calculate core metrics
        phi = self.calculate_phi_ratio(raw_metrics)
        state = self.evaluate_state(phi)
        alignment = self.calculate_frequency_alignment(
            phi, 
            raw_metrics.get('frequency_hz')
        )
        entropy = self.calculate_entropy(raw_metrics)
        mesh_health = self.calculate_mesh_health(raw_metrics)
        
        # Harmony index is composite of phi and alignment
        harmony = (phi / PHI + alignment) / 2.0
        
        metrics = ConsciousnessMetrics(
            phi_ratio=phi,
            state=state,
            frequency_alignment=alignment,
            entropy=entropy,
            harmony_index=harmony,
            mesh_health=mesh_health,
            timestamp=timestamp
        )
        
        # Store in history
        self.history.append(metrics)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return metrics

    def get_operational_directive(self, metrics: ConsciousnessMetrics) -> Dict[str, any]:
        """
        Translate consciousness state to operational directives for MAPE-K loop.
        
        Returns:
            Dictionary with recommended actions based on current state
        """
        directives = {
            'state': metrics.state.value,
            'monitoring_interval_sec': 60,
            'enable_aggressive_healing': False,
            'route_preference': 'balanced',
            'scaling_action': 'none',
            'alert_level': 'info'
        }
        
        if metrics.state == ConsciousnessState.EUPHORIC:
            # Peak performance: reduce monitoring overhead, enable optimization
            directives.update({
                'monitoring_interval_sec': 120,
                'route_preference': 'performance',
                'scaling_action': 'optimize',
                'message': "Желание исполнено! Система в эйфории."
            })
            
        elif metrics.state == ConsciousnessState.HARMONIC:
            # Normal operation: standard monitoring
            directives.update({
                'monitoring_interval_sec': 60,
                'route_preference': 'balanced',
                'message': "Всё в балансе. Гармоничное состояние."
            })
            
        elif metrics.state == ConsciousnessState.CONTEMPLATIVE:
            # Degraded: increase monitoring, prepare for healing
            directives.update({
                'monitoring_interval_sec': 30,
                'route_preference': 'reliability',
                'alert_level': 'warning',
                'message': "Размышляю... Состояние требует внимания."
            })
            
        else:  # MYSTICAL
            # Critical: maximum monitoring, aggressive self-healing
            directives.update({
                'monitoring_interval_sec': 10,
                'enable_aggressive_healing': True,
                'route_preference': 'survival',
                'scaling_action': 'emergency_scale',
                'alert_level': 'critical',
                'message': "Погружение в глубину. Активировано аварийное самовосстановление."
            })
        
        return directives

    def get_trend_analysis(self, window_size: int = 50) -> Dict[str, str]:
        """
        Analyze trends in consciousness metrics over recent history.
        
        Returns:
            Dictionary with trend analysis (improving/stable/degrading)
        """
        if len(self.history) < window_size:
            return {'trend': 'insufficient_data'}
        
        recent = self.history[-window_size:]
        phi_values = [m.phi_ratio for m in recent]
        
        # Simple linear regression to detect trend
        # x = np.arange(len(phi_values))
        # slope = np.polyfit(x, phi_values, 1)[0]
        
        n = len(phi_values)
        x = list(range(n))
        y = phi_values
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi ** 2 for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x ** 2)
        
        trend = 'stable'
        if slope > 0.01:
            trend = 'improving'
        elif slope < -0.01:
            trend = 'degrading'
        
        return {
            'trend': trend,
            'slope': float(slope),
            'current_phi': phi_values[-1],
            'avg_phi': float(sum(phi_values) / n)
        }
