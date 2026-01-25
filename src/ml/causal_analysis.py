"""
Causal Analysis Engine for Incident Root Cause Analysis

Implements causal graph construction and root cause scoring for incidents
detected by MAPE-K and GraphSAGE v2.

Target metrics (Stage 2):
- Root cause accuracy: >90%
- Analysis latency: <100ms
- Confidence scoring: 0-100%

Differentiator: "Exact root cause identification" vs standard observability.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import networkx as nx

logger = logging.getLogger(__name__)

import numpy as np


class IncidentSeverity(Enum):
    """Incident severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IncidentEvent:
    """Represents an incident event"""
    event_id: str
    timestamp: datetime
    node_id: str
    service_id: Optional[str]
    anomaly_type: str
    severity: IncidentSeverity
    metrics: Dict[str, float]
    detected_by: str  # "graphsage", "mape_k", "threshold"
    anomaly_score: float


@dataclass
class CausalLink:
    """Represents a causal relationship between events"""
    source_event_id: str
    target_event_id: str
    confidence: float  # 0.0-1.0
    relationship_type: str  # "causes", "correlates", "precedes"
    evidence: List[str] = field(default_factory=list)


@dataclass
class RootCause:
    """Identified root cause of an incident"""
    event_id: str
    node_id: str
    service_id: Optional[str]
    root_cause_type: str
    confidence: float  # 0.0-1.0
    explanation: str
    contributing_factors: List[str] = field(default_factory=list)
    remediation_suggestions: List[str] = field(default_factory=list)


@dataclass
class CausalAnalysisResult:
    """Result of causal analysis"""
    incident_id: str
    root_causes: List[RootCause]
    causal_graph: nx.DiGraph
    analysis_time_ms: float
    confidence: float  # Overall confidence in analysis
    event_chain: List[str]  # Ordered event IDs from root to incident


class CausalAnalysisEngine:
    """
    Causal Analysis Engine for root cause identification.
    
    Analyzes incidents to identify root causes through:
    - Event correlation
    - Dependency graph traversal
    - Temporal analysis
    - Confidence scoring
    
    Example:
        >>> engine = CausalAnalysisEngine()
        >>> engine.add_incident(incident_event)
        >>> result = engine.analyze(incident_event.event_id)
        >>> print(f"Root cause: {result.root_causes[0].root_cause_type}")
    """
    
    def __init__(
        self,
        correlation_window_seconds: float = 300.0,
        min_confidence: float = 0.5
    ):
        """
        Initialize causal analysis engine.
        
        Args:
            correlation_window_seconds: Time window for event correlation
            min_confidence: Minimum confidence for root cause identification
        """
        self.correlation_window = correlation_window_seconds
        self.min_confidence = min_confidence
        
        # Incident storage
        self.incidents: Dict[str, IncidentEvent] = {}
        self.causal_graph = nx.DiGraph()
        
        # Service dependency graph (would be loaded from config/monitoring)
        self.service_dependencies: Dict[str, List[str]] = {}
        
        # Analysis history
        self.analysis_history: List[CausalAnalysisResult] = []
        
        logger.info(
            f"Causal Analysis Engine initialized: "
            f"correlation_window={correlation_window_seconds}s, "
            f"min_confidence={min_confidence}"
        )
    
    def add_incident(self, incident: IncidentEvent):
        """
        Add incident event to analysis engine.
        
        Args:
            incident: Incident event to add
        """
        self.incidents[incident.event_id] = incident
        self.causal_graph.add_node(
            incident.event_id,
            node_id=incident.node_id,
            service_id=incident.service_id,
            timestamp=incident.timestamp,
            anomaly_type=incident.anomaly_type,
            severity=incident.severity,
            metrics=incident.metrics
        )
        
        # Correlate with existing incidents
        self._correlate_incidents(incident)
        
        logger.debug(f"Added incident: {incident.event_id} ({incident.anomaly_type})")
    
    def analyze(self, incident_id: str) -> CausalAnalysisResult:
        """
        Perform causal analysis for an incident.
        
        Args:
            incident_id: ID of incident to analyze
        
        Returns:
            CausalAnalysisResult with root causes and causal chain
        """
        start_time = time.time()
        
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        
        incident = self.incidents[incident_id]
        
        logger.info(f"Analyzing incident: {incident_id} ({incident.anomaly_type})")
        
        # 1. Build causal graph for this incident
        incident_graph = self._build_incident_graph(incident_id)
        
        # 2. Identify root causes
        root_causes = self._identify_root_causes(incident_id, incident_graph)
        
        # 3. Build event chain (root → incident)
        event_chain = self._build_event_chain(incident_id, root_causes)
        
        # 4. Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(root_causes)
        
        analysis_time = (time.time() - start_time) * 1000  # ms
        
        result = CausalAnalysisResult(
            incident_id=incident_id,
            root_causes=root_causes,
            causal_graph=incident_graph,
            analysis_time_ms=analysis_time,
            confidence=overall_confidence,
            event_chain=event_chain
        )
        
        self.analysis_history.append(result)
        
        logger.info(
            f"Causal analysis complete: "
            f"{len(root_causes)} root causes, "
            f"confidence={overall_confidence:.2f}, "
            f"time={analysis_time:.2f}ms"
        )
        
        return result
    
    def _correlate_incidents(self, new_incident: IncidentEvent):
        """
        Correlate new incident with existing incidents.
        
        Creates causal links based on:
        - Temporal proximity
        - Service dependencies
        - Metric correlations
        """
        for existing_id, existing_incident in self.incidents.items():
            if existing_id == new_incident.event_id:
                continue
            
            # Temporal correlation
            time_diff = abs((new_incident.timestamp - existing_incident.timestamp).total_seconds())
            if time_diff > self.correlation_window:
                continue
            
            # Service dependency correlation
            service_correlation = self._check_service_dependency(
                existing_incident.service_id,
                new_incident.service_id
            )
            
            # Metric correlation
            metric_correlation = self._check_metric_correlation(
                existing_incident.metrics,
                new_incident.metrics
            )
            
            # Calculate overall correlation confidence
            confidence = (
                (1.0 - min(time_diff / self.correlation_window, 1.0)) * 0.3 +
                service_correlation * 0.4 +
                metric_correlation * 0.3
            )
            
            if confidence >= 0.3:  # Minimum threshold for correlation
                # Determine relationship type
                if existing_incident.timestamp < new_incident.timestamp:
                    relationship = "causes"
                elif service_correlation > 0.7:
                    relationship = "correlates"
                else:
                    relationship = "precedes"
                
                # Add causal link
                self.causal_graph.add_edge(
                    existing_id,
                    new_incident.event_id,
                    confidence=confidence,
                    relationship_type=relationship,
                    evidence=[
                        f"temporal: {time_diff:.1f}s",
                        f"service_dep: {service_correlation:.2f}",
                        f"metric_corr: {metric_correlation:.2f}"
                    ]
                )
    
    def _check_service_dependency(
        self,
        source_service: Optional[str],
        target_service: Optional[str]
    ) -> float:
        """
        Check if services have dependency relationship.
        
        Returns:
            Confidence score 0.0-1.0
        """
        if not source_service or not target_service:
            return 0.0
        
        # Direct dependency
        if target_service in self.service_dependencies.get(source_service, []):
            return 1.0
        
        # Reverse dependency (target depends on source)
        if source_service in self.service_dependencies.get(target_service, []):
            return 0.8
        
        # Transitive dependency (check 2-hop)
        for intermediate in self.service_dependencies.get(source_service, []):
            if target_service in self.service_dependencies.get(intermediate, []):
                return 0.6
        
        return 0.0
    
    def _check_metric_correlation(
        self,
        metrics1: Dict[str, float],
        metrics2: Dict[str, float]
    ) -> float:
        """
        Check metric correlation between incidents.
        
        Returns:
            Correlation score 0.0-1.0
        """
        if not metrics1 or not metrics2:
            return 0.0
        
        # Find common metrics
        common_metrics = set(metrics1.keys()) & set(metrics2.keys())
        if not common_metrics:
            return 0.0
        
        # Calculate correlation (simplified)
        correlations = []
        for metric in common_metrics:
            val1 = metrics1[metric]
            val2 = metrics2[metric]
            
            # Normalize values (assume 0-100 range for percentages)
            if metric.endswith('_percent'):
                norm1 = val1 / 100.0
                norm2 = val2 / 100.0
            else:
                # Simple normalization (would use proper scaling in production)
                norm1 = min(val1 / 100.0, 1.0)
                norm2 = min(val2 / 100.0, 1.0)
            
            # Correlation: 1 - |diff|
            correlation = 1.0 - abs(norm1 - norm2)
            correlations.append(max(0.0, correlation))
        
        return sum(correlations) / len(correlations) if correlations else 0.0
    
    def _build_incident_graph(self, incident_id: str) -> nx.DiGraph:
        """Build causal graph for specific incident."""
        # Get all nodes reachable from this incident (backwards in time)
        incident_graph = nx.DiGraph()
        
        # BFS from incident to find all related events
        visited = set()
        queue = [incident_id]
        
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            
            visited.add(current_id)
            
            # Add node
            if current_id in self.causal_graph:
                incident_graph.add_node(
                    current_id,
                    **self.causal_graph.nodes[current_id]
                )
            
            # Add incoming edges (causes)
            for predecessor in self.causal_graph.predecessors(current_id):
                if predecessor not in visited:
                    edge_data = self.causal_graph[predecessor][current_id]
                    incident_graph.add_edge(
                        predecessor,
                        current_id,
                        **edge_data
                    )
                    queue.append(predecessor)
        
        return incident_graph
    
    def _identify_root_causes(
        self,
        incident_id: str,
        incident_graph: nx.DiGraph
    ) -> List[RootCause]:
        """
        Identify root causes from causal graph.
        
        Root causes are nodes with:
        - No incoming edges (true root)
        - High confidence causal links
        - High severity
        """
        root_causes = []
        
        # Find nodes with no incoming edges (true roots)
        root_nodes = [
            node for node in incident_graph.nodes()
            if incident_graph.in_degree(node) == 0
        ]
        
        # If no true roots, find nodes with minimal incoming edges
        if not root_nodes:
            min_in_degree = min(incident_graph.in_degree(node) for node in incident_graph.nodes())
            root_nodes = [
                node for node in incident_graph.nodes()
                if incident_graph.in_degree(node) == min_in_degree
            ]
        
        for root_node_id in root_nodes:
            if root_node_id not in self.incidents:
                continue
            
            root_incident = self.incidents[root_node_id]
            
            # Calculate confidence based on path to incident
            path_confidence = self._calculate_path_confidence(root_node_id, incident_id, incident_graph)
            
            if path_confidence < self.min_confidence:
                continue
            
            # Determine root cause type
            root_cause_type = self._classify_root_cause(root_incident)
            
            # Generate explanation
            explanation = self._generate_explanation(root_incident, incident_id, incident_graph)
            
            # Get remediation suggestions
            remediation = self._get_remediation_suggestions(root_cause_type, root_incident)
            
            root_cause = RootCause(
                event_id=root_node_id,
                node_id=root_incident.node_id,
                service_id=root_incident.service_id,
                root_cause_type=root_cause_type,
                confidence=path_confidence,
                explanation=explanation,
                contributing_factors=self._get_contributing_factors(root_node_id, incident_graph),
                remediation_suggestions=remediation
            )
            
            root_causes.append(root_cause)
        
        # Sort by confidence
        root_causes.sort(key=lambda x: x.confidence, reverse=True)
        
        return root_causes
    
    def _calculate_path_confidence(
        self,
        source_id: str,
        target_id: str,
        graph: nx.DiGraph
    ) -> float:
        """Calculate confidence along causal path."""
        try:
            # Find shortest path
            path = nx.shortest_path(graph, source_id, target_id)
            
            # Multiply edge confidences
            confidence = 1.0
            for i in range(len(path) - 1):
                edge_data = graph[path[i]][path[i + 1]]
                confidence *= edge_data.get('confidence', 0.5)
            
            return confidence
        except (nx.NetworkXNoPath, KeyError):
            return 0.0
    
    def _classify_root_cause(self, incident: IncidentEvent) -> str:
        """Classify root cause type from incident."""
        metrics = incident.metrics
        
        # High CPU
        if metrics.get('cpu_percent', 0) > 90:
            return "High CPU Usage"
        
        # High Memory
        if metrics.get('memory_percent', 0) > 85:
            return "Memory Leak / High Memory Usage"
        
        # Network Issues
        if metrics.get('packet_loss_percent', 0) > 5:
            return "Network Packet Loss"
        
        if metrics.get('latency_ms', 0) > 200:
            return "Network Latency"
        
        # Service-specific
        if incident.service_id:
            return f"Service Failure: {incident.service_id}"
        
        return f"Unknown: {incident.anomaly_type}"
    
    def _generate_explanation(
        self,
        root_incident: IncidentEvent,
        target_incident_id: str,
        graph: nx.DiGraph
    ) -> str:
        """Generate human-readable explanation."""
        try:
            path = nx.shortest_path(graph, root_incident.event_id, target_incident_id)
            path_length = len(path) - 1
            
            explanation = (
                f"Root cause identified: {root_incident.anomaly_type} on node {root_incident.node_id}. "
                f"This incident propagated through {path_length} intermediate events "
                f"to cause the target incident."
            )
            
            return explanation
        except (nx.NetworkXNoPath, KeyError):
            return f"Root cause: {root_incident.anomaly_type} on node {root_incident.node_id}"
    
    def _get_contributing_factors(
        self,
        root_node_id: str,
        graph: nx.DiGraph
    ) -> List[str]:
        """Get contributing factors for root cause."""
        factors = []
        
        # Get neighbors (related events)
        neighbors = list(graph.neighbors(root_node_id))
        for neighbor_id in neighbors[:3]:  # Top 3
            if neighbor_id in self.incidents:
                neighbor = self.incidents[neighbor_id]
                factors.append(f"{neighbor.anomaly_type} on {neighbor.node_id}")
        
        return factors
    
    def _get_remediation_suggestions(
        self,
        root_cause_type: str,
        incident: IncidentEvent
    ) -> List[str]:
        """Get remediation suggestions based on root cause type."""
        suggestions = []
        
        if "CPU" in root_cause_type:
            suggestions.extend([
                "Restart service to clear CPU load",
                "Scale out service instances",
                "Check for CPU-intensive processes"
            ])
        elif "Memory" in root_cause_type:
            suggestions.extend([
                "Restart service to free memory",
                "Increase memory limits",
                "Check for memory leaks in application code"
            ])
        elif "Network" in root_cause_type:
            suggestions.extend([
                "Switch to backup network route",
                "Check network interface status",
                "Verify network connectivity to dependencies"
            ])
        else:
            suggestions.append("Investigate service logs for detailed error information")
        
        return suggestions
    
    def _build_event_chain(
        self,
        incident_id: str,
        root_causes: List[RootCause]
    ) -> List[str]:
        """Build ordered event chain from root to incident."""
        if not root_causes:
            return [incident_id]
        
        # Use highest confidence root cause
        root_cause = root_causes[0]
        
        try:
            # Find path from root to incident
            path = nx.shortest_path(
                self.causal_graph,
                root_cause.event_id,
                incident_id
            )
            return path
        except (nx.NetworkXNoPath, KeyError):
            return [root_cause.event_id, incident_id]
    
    def _calculate_overall_confidence(self, root_causes: List[RootCause]) -> float:
        """Calculate overall confidence in analysis."""
        if not root_causes:
            return 0.0
        
        # Weighted average of top 3 root causes
        top_causes = root_causes[:3]
        weights = [0.5, 0.3, 0.2]  # Decreasing weights
        
        confidence = sum(
            cause.confidence * weight
            for cause, weight in zip(top_causes, weights)
        )
        
        return min(1.0, confidence)


# Integration with MAPE-K
def create_causal_analyzer_for_mapek() -> CausalAnalysisEngine:
    """
    Create Causal Analysis Engine configured for MAPE-K integration.
    
    Returns:
        CausalAnalysisEngine instance ready for use in Analyze phase
    """
    analyzer = CausalAnalysisEngine(
        correlation_window_seconds=300.0,
        min_confidence=0.5
    )
    
    return analyzer

