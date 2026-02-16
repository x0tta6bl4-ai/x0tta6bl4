"""
Consciousness Engine v2

Enhanced consciousness engine with multi-modal AI and XAI (Explainable AI).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Import base consciousness engine
try:
    from .consciousness import ConsciousnessEngine

    CONSCIOUSNESS_AVAILABLE = True
except ImportError:
    CONSCIOUSNESS_AVAILABLE = False
    ConsciousnessEngine = None


class ModalityType(Enum):
    """Input modality types"""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    STRUCTURED = "structured"  # JSON, tables, etc.
    GRAPH = "graph"  # Network graphs, knowledge graphs


@dataclass
class MultiModalInput:
    """Multi-modal input data"""

    modality: ModalityType
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DecisionExplanation:
    """Explanation for a decision"""

    decision_id: str
    decision: str
    reasoning: str
    confidence: float
    factors: List[Dict[str, Any]] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MultiModalProcessor:
    """
    Multi-modal AI processor.

    Provides:
    - Multi-modal input support
    - Cross-modal learning
    - Unified representation
    - Integration
    """

    def __init__(self):
        self.modality_processors: Dict[ModalityType, Any] = {}
        self.unified_representation: Optional[Dict[str, Any]] = None
        logger.info("MultiModalProcessor initialized")

    def process_input(self, input_data: MultiModalInput) -> Dict[str, Any]:
        """
        Process multi-modal input.

        Args:
            input_data: Multi-modal input

        Returns:
            Processed representation
        """
        # Process based on modality
        if input_data.modality == ModalityType.TEXT:
            return self._process_text(input_data.data)
        elif input_data.modality == ModalityType.IMAGE:
            return self._process_image(input_data.data)
        elif input_data.modality == ModalityType.AUDIO:
            return self._process_audio(input_data.data)
        elif input_data.modality == ModalityType.STRUCTURED:
            return self._process_structured(input_data.data)
        elif input_data.modality == ModalityType.GRAPH:
            return self._process_graph(input_data.data)
        else:
            logger.warning(f"Unknown modality: {input_data.modality}")
            return {}

    def _process_text(self, text: str) -> Dict[str, Any]:
        """Process text input"""
        # Extract features from text
        return {
            "type": "text",
            "length": len(text),
            "tokens": text.split(),
            "features": {
                "sentiment": "neutral",  # Would use actual sentiment analysis
                "entities": [],  # Would use NER
            },
        }

    def _process_image(self, image_data: Any) -> Dict[str, Any]:
        """Process image input"""
        # Extract features from image
        return {
            "type": "image",
            "features": {
                "objects": [],  # Would use object detection
                "scene": "unknown",  # Would use scene classification
            },
        }

    def _process_audio(self, audio_data: Any) -> Dict[str, Any]:
        """Process audio input"""
        # Extract features from audio
        return {
            "type": "audio",
            "features": {
                "duration": 0.0,
                "transcription": "",  # Would use speech-to-text
            },
        }

    def _process_structured(self, structured_data: Any) -> Dict[str, Any]:
        """Process structured input"""
        # Extract features from structured data
        return {
            "type": "structured",
            "features": {
                "keys": (
                    list(structured_data.keys())
                    if isinstance(structured_data, dict)
                    else []
                ),
                "size": (
                    len(structured_data) if hasattr(structured_data, "__len__") else 0
                ),
            },
        }

    def _process_graph(self, graph_data: Any) -> Dict[str, Any]:
        """Process graph input"""
        # Extract features from graph
        return {"type": "graph", "features": {"nodes": 0, "edges": 0, "density": 0.0}}

    def create_unified_representation(
        self, inputs: List[MultiModalInput]
    ) -> Dict[str, Any]:
        """
        Create unified representation from multiple modalities.

        Args:
            inputs: List of multi-modal inputs

        Returns:
            Unified representation
        """
        processed = [self.process_input(inp) for inp in inputs]

        unified = {
            "modalities": [p.get("type") for p in processed],
            "combined_features": {},
            "cross_modal_relations": [],
        }

        # Combine features across modalities
        for proc in processed:
            if "features" in proc:
                unified["combined_features"].update(proc["features"])

        self.unified_representation = unified
        return unified


class XAIEngine:
    """
    Explainable AI (XAI) engine.

    Provides:
    - Model interpretability
    - Decision explanations
    - Feature importance
    - Visualization
    """

    def __init__(self):
        self.explanations: Dict[str, DecisionExplanation] = {}
        logger.info("XAIEngine initialized")

    def explain_decision(
        self,
        decision: str,
        model_output: Dict[str, Any],
        input_features: Dict[str, Any],
        confidence: float,
    ) -> DecisionExplanation:
        """
        Generate explanation for a decision.

        Args:
            decision: Decision made
            model_output: Model output
            input_features: Input features
            confidence: Decision confidence

        Returns:
            DecisionExplanation
        """
        decision_id = f"decision-{int(datetime.utcnow().timestamp())}"

        # Extract reasoning
        reasoning = self._extract_reasoning(model_output, input_features)

        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(
            input_features, model_output
        )

        # Identify key factors
        factors = self._identify_factors(input_features, model_output)

        # Generate alternatives
        alternatives = self._generate_alternatives(decision, input_features)

        explanation = DecisionExplanation(
            decision_id=decision_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            factors=factors,
            feature_importance=feature_importance,
            alternatives=alternatives,
        )

        self.explanations[decision_id] = explanation
        logger.info(f"Generated explanation for decision: {decision}")

        return explanation

    def _extract_reasoning(
        self, model_output: Dict[str, Any], input_features: Dict[str, Any]
    ) -> str:
        """Extract reasoning from model output"""
        # Generate human-readable reasoning
        reasoning_parts = []

        if "anomaly_score" in model_output:
            score = model_output["anomaly_score"]
            reasoning_parts.append(f"Anomaly score: {score:.2f}")

        if "prediction" in model_output:
            prediction = model_output["prediction"]
            reasoning_parts.append(f"Prediction: {prediction}")

        # Add feature-based reasoning
        top_features = sorted(
            input_features.items(),
            key=lambda x: abs(x[1]) if isinstance(x[1], (int, float)) else 0,
            reverse=True,
        )[:3]

        if top_features:
            reasoning_parts.append(
                f"Key features: {', '.join([f'{k}={v}' for k, v in top_features])}"
            )

        return (
            ". ".join(reasoning_parts)
            if reasoning_parts
            else "Decision based on model output"
        )

    def _calculate_feature_importance(
        self, input_features: Dict[str, Any], model_output: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate feature importance"""
        importance = {}

        # Simple heuristic: features with larger values contribute more
        for feature, value in input_features.items():
            if isinstance(value, (int, float)):
                importance[feature] = abs(value) / (1.0 + abs(value))  # Normalize
            else:
                importance[feature] = 0.5  # Default for non-numeric

        # Normalize to sum to 1.0
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}

        return importance

    def _identify_factors(
        self, input_features: Dict[str, Any], model_output: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify key factors in decision"""
        factors = []

        # Top contributing features
        sorted_features = sorted(
            input_features.items(),
            key=lambda x: abs(x[1]) if isinstance(x[1], (int, float)) else 0,
            reverse=True,
        )[:5]

        for feature, value in sorted_features:
            if isinstance(value, (int, float)):
                level = (
                    "high"
                    if abs(value) > 1.0
                    else "medium" if abs(value) > 0.5 else "low"
                )
            else:
                level = "low"
            factors.append(
                {
                    "feature": feature,
                    "value": value,
                    "contribution": level,
                }
            )

        return factors

    def _generate_alternatives(
        self, decision: str, input_features: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate alternative decisions"""
        alternatives = []

        # Generate alternative scenarios
        if decision == "restart_service":
            alternatives.append(
                {
                    "decision": "scale_up",
                    "reason": "Scaling up might resolve the issue without downtime",
                }
            )
            alternatives.append(
                {
                    "decision": "switch_route",
                    "reason": "Switching route might bypass the problem",
                }
            )

        return alternatives

    def get_explanation(self, decision_id: str) -> Optional[DecisionExplanation]:
        """Get explanation by ID"""
        return self.explanations.get(decision_id)


class ConsciousnessEngineV2:
    """
    Enhanced Consciousness Engine v2.

    Provides:
    - Multi-modal AI support
    - XAI (Explainable AI)
    - Enhanced decision making
    - Integration with existing consciousness engine
    """

    def __init__(self, base_engine: Optional[ConsciousnessEngine] = None):
        """
        Initialize Consciousness Engine v2.

        Args:
            base_engine: Base consciousness engine (optional)
        """
        self.base_engine = base_engine
        self.multi_modal_processor = MultiModalProcessor()
        self.xai_engine = XAIEngine()

        logger.info("ConsciousnessEngineV2 initialized")

    def process_multi_modal(self, inputs: List[MultiModalInput]) -> Dict[str, Any]:
        """
        Process multi-modal inputs.

        Args:
            inputs: List of multi-modal inputs

        Returns:
            Processed result
        """
        unified = self.multi_modal_processor.create_unified_representation(inputs)

        # Make decision based on unified representation
        decision = self._make_decision(unified)

        # Generate explanation
        explanation = self.xai_engine.explain_decision(
            decision=decision["action"],
            model_output=decision,
            input_features=unified.get("combined_features", {}),
            confidence=decision.get("confidence", 0.5),
        )

        return {
            "decision": decision,
            "explanation": explanation,
            "unified_representation": unified,
        }

    # Weighted scoring matrix: action → {feature: (threshold, weight)}
    # Each feature contributes score = weight * sigmoid(value / threshold)
    # for proportional signals, or weight * (1 - value/threshold) for inverse.
    ACTION_SCORES: Dict[str, Dict[str, Tuple[float, float]]] = {
        "restart_service": {
            "anomaly_score": (0.7, 0.35),
            "error_rate": (0.5, 0.25),
            "packet_loss": (0.3, 0.15),
            "latency": (500.0, 0.15),
            "cpu_usage": (0.95, 0.10),
        },
        "scale_up": {
            "traffic_rate": (1000.0, 0.30),
            "cpu_usage": (0.80, 0.25),
            "memory_usage": (0.85, 0.25),
            "latency": (200.0, 0.10),
            "queue_depth": (100.0, 0.10),
        },
        "rotate_keys": {
            "anomaly_score": (0.5, 0.30),
            "key_age_hours": (24.0, 0.40),
            "auth_failures": (10.0, 0.30),
        },
        "switch_route": {
            "packet_loss": (0.2, 0.35),
            "latency": (300.0, 0.30),
            "rssi": (-75.0, 0.20),  # inverse: lower RSSI → higher score
            "link_flap_count": (3.0, 0.15),
        },
        "isolate_node": {
            "anomaly_score": (0.9, 0.40),
            "auth_failures": (20.0, 0.30),
            "error_rate": (0.8, 0.30),
        },
    }

    # Minimum score to recommend an action (below this → "monitor")
    ACTION_THRESHOLD = 0.3

    def _make_decision(self, unified_representation: Dict[str, Any]) -> Dict[str, Any]:
        """Make decision using weighted multi-objective scoring.

        Evaluates every candidate action against all observed features,
        producing a normalized score in [0, 1]. The highest-scoring action
        above ACTION_THRESHOLD wins. If nothing breaches the threshold,
        the decision is "monitor".
        """
        features = unified_representation.get("combined_features", {})
        scored = self._score_actions(features)

        if not scored or scored[0][1] < self.ACTION_THRESHOLD:
            return {
                "action": "monitor",
                "confidence": max(0.3, 1.0 - (scored[0][1] if scored else 0.0)),
                "reasoning": "All signals within normal range",
                "scores": {a: round(s, 3) for a, s in scored},
            }

        best_action, best_score = scored[0]
        # Confidence proportional to score and separation from runner-up
        runner_up = scored[1][1] if len(scored) > 1 else 0.0
        separation = best_score - runner_up
        confidence = min(0.99, 0.5 + best_score * 0.3 + separation * 0.2)

        # Build human-readable reasoning
        reasoning_parts = self._explain_score(best_action, features)

        return {
            "action": best_action,
            "confidence": round(confidence, 3),
            "reasoning": "; ".join(reasoning_parts),
            "scores": {a: round(s, 3) for a, s in scored},
        }

    def _score_actions(self, features: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Score every candidate action against observed features."""
        results = []
        for action, criteria in self.ACTION_SCORES.items():
            score = 0.0
            for feature, (threshold, weight) in criteria.items():
                value = features.get(feature)
                if value is None:
                    continue
                if not isinstance(value, (int, float)):
                    continue
                # Sigmoid-like activation: 0 when value << threshold, ~1 when value >> threshold
                # For negative thresholds (e.g. RSSI=-75), dividing two negatives
                # naturally gives ratio>1 when the signal is worse than threshold.
                ratio = value / threshold if threshold != 0 else 0.0
                activation = 1.0 / (1.0 + 2.718 ** (-4.0 * (ratio - 1.0)))
                score += weight * activation
            results.append((action, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _explain_score(self, action: str, features: Dict[str, Any]) -> List[str]:
        """Build per-feature reasoning for the winning action."""
        parts = []
        criteria = self.ACTION_SCORES.get(action, {})
        for feature, (threshold, weight) in criteria.items():
            value = features.get(feature)
            if value is None or not isinstance(value, (int, float)):
                continue
            if threshold < 0:
                triggered = value <= threshold * 0.7  # 70% of |threshold| into negative
            else:
                triggered = value >= threshold * 0.7  # 70% of threshold
            if triggered:
                parts.append(
                    f"{feature}={value} (threshold={threshold}, weight={weight})"
                )
        if not parts:
            parts.append(f"Composite score triggered {action}")
        return parts

    def explain_decision(self, decision_id: str) -> Optional[DecisionExplanation]:
        """Get explanation for a decision"""
        return self.xai_engine.get_explanation(decision_id)


def create_consciousness_v2(
    base_engine: Optional[ConsciousnessEngine] = None,
) -> ConsciousnessEngineV2:
    """
    Factory function to create Consciousness Engine v2.

    Args:
        base_engine: Base consciousness engine (optional)

    Returns:
        ConsciousnessEngineV2 instance
    """
    return ConsciousnessEngineV2(base_engine=base_engine)
