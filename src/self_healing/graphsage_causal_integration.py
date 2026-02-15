"""
GraphSAGE Causal Analysis Integration

Improves integration between GraphSAGE anomaly detection and Causal Analysis Engine
for complete root cause identification workflow.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Optional imports
try:
    from src.ml.graphsage_anomaly_detector import (AnomalyPrediction,
                                                   GraphSAGEAnomalyDetector)

    GRAPHSAGE_AVAILABLE = True
except ImportError:
    GRAPHSAGE_AVAILABLE = False
    GraphSAGEAnomalyDetector = None
    AnomalyPrediction = None
    logger.warning("⚠️ GraphSAGE not available")

try:
    from src.ml.causal_analysis import (CausalAnalysisEngine,
                                        CausalAnalysisResult, IncidentEvent,
                                        IncidentSeverity, RootCause)

    CAUSAL_ANALYSIS_AVAILABLE = True
except ImportError:
    CAUSAL_ANALYSIS_AVAILABLE = False
    CausalAnalysisEngine = None
    CausalAnalysisResult = None
    IncidentEvent = None
    IncidentSeverity = None
    RootCause = None
    logger.warning("⚠️ Causal Analysis not available")


class GraphSAGECausalIntegration:
    """
    Integration layer between GraphSAGE and Causal Analysis.

    Provides seamless workflow:
    1. GraphSAGE detects anomaly
    2. Causal Analysis identifies root cause
    3. Returns combined result with root cause explanation
    """

    def __init__(
        self,
        graphsage_detector: Optional[GraphSAGEAnomalyDetector] = None,
        causal_engine: Optional[CausalAnalysisEngine] = None,
    ):
        """
        Initialize integration.

        Args:
            graphsage_detector: GraphSAGE detector instance (created if None)
            causal_engine: Causal analysis engine (created if None)
        """
        if not GRAPHSAGE_AVAILABLE:
            raise ImportError(
                "GraphSAGE not available. Install torch and torch-geometric."
            )

        if not CAUSAL_ANALYSIS_AVAILABLE:
            raise ImportError("Causal Analysis not available. Install dependencies.")

        # Initialize GraphSAGE if not provided
        if graphsage_detector is None:
            self.graphsage = GraphSAGEAnomalyDetector()
        else:
            self.graphsage = graphsage_detector

        # Initialize Causal Engine if not provided
        if causal_engine is None:
            self.causal_engine = CausalAnalysisEngine(
                correlation_window_seconds=300.0, min_confidence=0.5
            )
        else:
            self.causal_engine = causal_engine

        # Ensure GraphSAGE has causal engine
        if hasattr(self.graphsage, "causal_engine"):
            if self.graphsage.causal_engine is None:
                self.graphsage.causal_engine = self.causal_engine
        else:
            # Initialize causal_engine attribute if it doesn't exist
            self.graphsage.causal_engine = self.causal_engine

        logger.info("✅ GraphSAGE-Causal Analysis integration initialized")

    def detect_with_root_cause(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        edge_index: Optional[List[Tuple[int, int]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[AnomalyPrediction, Optional[CausalAnalysisResult], Optional[RootCause]]:
        """
        Detect anomaly with GraphSAGE and identify root cause with Causal Analysis.

        Args:
            node_id: Node identifier
            node_features: Node feature dict
            neighbors: List of (neighbor_id, neighbor_features) tuples
            edge_index: Optional edge connectivity
            context: Optional context information (service_id, etc.)

        Returns:
            Tuple of:
            - AnomalyPrediction: GraphSAGE prediction result
            - CausalAnalysisResult: Full causal analysis (if anomaly detected)
            - RootCause: Primary root cause (if anomaly detected, None otherwise)
        """
        # 1. Use GraphSAGE's integrated predict_with_causal method
        prediction, causal_result = self.graphsage.predict_with_causal(
            node_id=node_id,
            node_features=node_features,
            neighbors=neighbors,
            edge_index=edge_index,
        )

        # 2. Extract primary root cause if available
        root_cause = None
        if causal_result and causal_result.root_causes:
            root_cause = causal_result.root_causes[0]  # Highest confidence

        # 3. Log integration result
        if prediction.is_anomaly:
            if root_cause:
                logger.info(
                    f"🔍 Anomaly detected on {node_id}: "
                    f"{root_cause.root_cause_type} "
                    f"(confidence: {root_cause.confidence:.1%})"
                )
            else:
                logger.warning(
                    f"⚠️ Anomaly detected on {node_id} but no root cause identified"
                )

        return prediction, causal_result, root_cause

    def get_remediation_suggestions(self, root_cause: RootCause) -> List[str]:
        """
        Get remediation suggestions based on root cause.

        Args:
            root_cause: Identified root cause

        Returns:
            List of remediation suggestions
        """
        if not root_cause:
            return []

        # Use suggestions from root cause if available
        if root_cause.remediation_suggestions:
            return root_cause.remediation_suggestions

        # Fallback to type-based suggestions
        suggestions = []

        if "CPU" in root_cause.root_cause_type:
            suggestions.extend(
                [
                    "Scale up CPU resources",
                    "Check for CPU-intensive processes",
                    "Consider load balancing",
                ]
            )
        elif "Memory" in root_cause.root_cause_type:
            suggestions.extend(
                [
                    "Check for memory leaks",
                    "Increase memory allocation",
                    "Review memory usage patterns",
                ]
            )
        elif "Network" in root_cause.root_cause_type:
            suggestions.extend(
                [
                    "Check network connectivity",
                    "Review network configuration",
                    "Verify firewall rules",
                ]
            )
        else:
            suggestions.append("Review system logs for additional context")

        return suggestions


def create_graphsage_causal_integration(
    graphsage_detector: Optional[GraphSAGEAnomalyDetector] = None,
    causal_engine: Optional[CausalAnalysisEngine] = None,
) -> GraphSAGECausalIntegration:
    """
    Factory function to create GraphSAGE-Causal integration.

    Args:
        graphsage_detector: Optional GraphSAGE detector
        causal_engine: Optional causal analysis engine

    Returns:
        GraphSAGECausalIntegration instance
    """
    return GraphSAGECausalIntegration(
        graphsage_detector=graphsage_detector, causal_engine=causal_engine
    )
