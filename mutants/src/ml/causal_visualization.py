"""
Causal Analysis Visualization

Generates dashboard data and visualizations for causal analysis results.
Supports multiple output formats: JSON API, Grafana dashboard, HTML demo.

Target: Sales-ready visualization for email wave 3-4 demo.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from .causal_analysis import CausalAnalysisEngine, CausalAnalysisResult, IncidentEvent, IncidentSeverity

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """Timeline event for visualization"""
    timestamp: str
    event_id: str
    event_type: str  # "anomaly", "correlation", "root_cause", "remediation"
    title: str
    description: str
    node_id: str
    service_id: Optional[str]
    severity: str
    confidence: Optional[float] = None


@dataclass
class DependencyNode:
    """Node in dependency graph"""
    id: str
    label: str
    node_type: str  # "service", "node", "incident"
    status: str  # "healthy", "degraded", "failed", "root_cause"
    metrics: Dict[str, float] = None


@dataclass
class DependencyEdge:
    """Edge in dependency graph"""
    source: str
    target: str
    relationship: str  # "depends_on", "causes", "correlates"
    confidence: float
    evidence: List[str] = None


@dataclass
class DashboardData:
    """Complete dashboard data structure"""
    incident_id: str
    timeline: List[TimelineEvent]
    dependency_graph: Dict[str, Any]  # {nodes: [...], edges: [...]}
    root_causes: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    remediation: Dict[str, Any]
    analysis_metadata: Dict[str, Any]


class CausalAnalysisVisualizer:
    """
    Visualizer for Causal Analysis results.
    
    Generates dashboard data, Grafana dashboards, and demo scenarios.
    
    Example:
        >>> visualizer = CausalAnalysisVisualizer(engine)
        >>> dashboard_data = visualizer.generate_dashboard_data(incident_id)
        >>> html = visualizer.generate_html_dashboard(dashboard_data)
    """
    
    def __init__(self, causal_engine: CausalAnalysisEngine):
        """
        Initialize visualizer.
        
        Args:
            causal_engine: CausalAnalysisEngine instance
        """
        self.engine = causal_engine
        logger.info("Causal Analysis Visualizer initialized")
    
    def generate_dashboard_data(self, incident_id: str) -> DashboardData:
        """
        Generate complete dashboard data for an incident.
        
        Args:
            incident_id: Incident ID to visualize
        
        Returns:
            DashboardData with all visualization components
        """
        # Perform analysis if not already done
        if incident_id not in [r.incident_id for r in self.engine.analysis_history]:
            result = self.engine.analyze(incident_id)
        else:
            result = next(r for r in self.engine.analysis_history if r.incident_id == incident_id)
        
        # Generate timeline
        timeline = self._generate_timeline(result)
        
        # Generate dependency graph
        dependency_graph = self._generate_dependency_graph(result)
        
        # Format root causes
        root_causes = [self._format_root_cause(rc) for rc in result.root_causes]
        
        # Generate metrics panel
        metrics = self._generate_metrics_panel(result)
        
        # Generate remediation panel
        remediation = self._generate_remediation_panel(result)
        
        # Analysis metadata
        metadata = {
            "analysis_time_ms": result.analysis_time_ms,
            "overall_confidence": result.confidence,
            "total_events": len(result.causal_graph.nodes()),
            "root_causes_count": len(result.root_causes),
            "timestamp": datetime.now().isoformat()
        }
        
        return DashboardData(
            incident_id=incident_id,
            timeline=timeline,
            dependency_graph=dependency_graph,
            root_causes=root_causes,
            metrics=metrics,
            remediation=remediation,
            analysis_metadata=metadata
        )
    
    def _generate_timeline(self, result: CausalAnalysisResult) -> List[TimelineEvent]:
        """Generate timeline events from causal analysis."""
        timeline = []
        
        # Get all events in causal chain
        event_ids = result.event_chain if result.event_chain else list(result.causal_graph.nodes())
        
        for event_id in event_ids:
            if event_id not in self.engine.incidents:
                continue
            
            incident = self.engine.incidents[event_id]
            
            # Determine event type
            if event_id == result.incident_id:
                event_type = "anomaly"
                title = f"Anomaly Detected: {incident.anomaly_type}"
                description = f"Detected by {incident.detected_by} with {incident.anomaly_score:.1%} confidence"
            elif event_id in [rc.event_id for rc in result.root_causes]:
                event_type = "root_cause"
                root_cause = next(rc for rc in result.root_causes if rc.event_id == event_id)
                title = f"Root Cause: {root_cause.root_cause_type}"
                description = f"{root_cause.explanation} (Confidence: {root_cause.confidence:.1%})"
            else:
                event_type = "correlation"
                title = f"Correlated Event: {incident.anomaly_type}"
                description = f"Correlated with main incident on node {incident.node_id}"
            
            timeline.append(TimelineEvent(
                timestamp=incident.timestamp.isoformat(),
                event_id=event_id,
                event_type=event_type,
                title=title,
                description=description,
                node_id=incident.node_id,
                service_id=incident.service_id,
                severity=incident.severity.value,
                confidence=incident.anomaly_score if event_type == "anomaly" else None
            ))
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x.timestamp)
        
        return timeline
    
    def _generate_dependency_graph(self, result: CausalAnalysisResult) -> Dict[str, Any]:
        """Generate dependency graph data structure."""
        nodes = []
        edges = []
        
        # Add nodes
        for event_id in result.causal_graph.nodes():
            if event_id not in self.engine.incidents:
                continue
            
            incident = self.engine.incidents[event_id]
            
            # Determine node status
            if event_id == result.incident_id:
                status = "failed"
            elif event_id in [rc.event_id for rc in result.root_causes]:
                status = "root_cause"
            else:
                status = "degraded"
            
            node = DependencyNode(
                id=event_id,
                label=f"{incident.anomaly_type} ({incident.node_id})",
                node_type="incident",
                status=status,
                metrics=incident.metrics
            )
            nodes.append(asdict(node))
        
        # Add edges
        for source, target, data in result.causal_graph.edges(data=True):
            edge = DependencyEdge(
                source=source,
                target=target,
                relationship=data.get('relationship_type', 'correlates'),
                confidence=data.get('confidence', 0.5),
                evidence=data.get('evidence', [])
            )
            edges.append(asdict(edge))
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def _format_root_cause(self, root_cause) -> Dict[str, Any]:
        """Format root cause for display."""
        return {
            "event_id": root_cause.event_id,
            "node_id": root_cause.node_id,
            "service_id": root_cause.service_id,
            "root_cause_type": root_cause.root_cause_type,
            "confidence": root_cause.confidence,
            "explanation": root_cause.explanation,
            "contributing_factors": root_cause.contributing_factors,
            "remediation_suggestions": root_cause.remediation_suggestions
        }
    
    def _generate_metrics_panel(self, result: CausalAnalysisResult) -> Dict[str, Any]:
        """Generate metrics panel data."""
        # Get metrics from all events in chain
        all_metrics = {}
        
        for event_id in result.event_chain:
            if event_id in self.engine.incidents:
                incident = self.engine.incidents[event_id]
                for key, value in incident.metrics.items():
                    if key not in all_metrics:
                        all_metrics[key] = []
                    all_metrics[key].append({
                        "timestamp": incident.timestamp.isoformat(),
                        "value": value,
                        "event_id": event_id
                    })
        
        # Calculate before/after if remediation applied
        before_after = {}
        if len(result.event_chain) >= 2:
            first_event = self.engine.incidents[result.event_chain[0]]
            last_event = self.engine.incidents[result.event_chain[-1]]
            
            for key in set(first_event.metrics.keys()) & set(last_event.metrics.keys()):
                before_after[key] = {
                    "before": first_event.metrics[key],
                    "after": last_event.metrics[key],
                    "improvement": ((first_event.metrics[key] - last_event.metrics[key]) / first_event.metrics[key] * 100) if first_event.metrics[key] > 0 else 0
                }
        
        return {
            "time_series": all_metrics,
            "before_after": before_after,
            "summary": {
                "total_events": len(result.event_chain),
                "affected_nodes": len(set(self.engine.incidents[eid].node_id for eid in result.event_chain if eid in self.engine.incidents)),
                "affected_services": len(set(self.engine.incidents[eid].service_id for eid in result.event_chain if eid in self.engine.incidents and self.engine.incidents[eid].service_id))
            }
        }
    
    def _generate_remediation_panel(self, result: CausalAnalysisResult) -> Dict[str, Any]:
        """Generate remediation panel data."""
        if not result.root_causes:
            return {
                "recommendations": [],
                "estimated_recovery_time": "Unknown",
                "priority": "low"
            }
        
        # Aggregate remediation suggestions from all root causes
        all_suggestions = []
        for rc in result.root_causes:
            all_suggestions.extend(rc.remediation_suggestions)
        
        # Deduplicate
        unique_suggestions = list(dict.fromkeys(all_suggestions))
        
        # Estimate recovery time (simplified)
        estimated_time = "5-10 minutes" if len(result.root_causes) == 1 else "10-20 minutes"
        
        # Priority based on confidence
        top_confidence = result.root_causes[0].confidence
        if top_confidence > 0.9:
            priority = "critical"
        elif top_confidence > 0.7:
            priority = "high"
        else:
            priority = "medium"
        
        return {
            "recommendations": unique_suggestions,
            "estimated_recovery_time": estimated_time,
            "priority": priority,
            "root_causes_count": len(result.root_causes),
            "top_confidence": top_confidence
        }
    
    def generate_json_api_response(self, incident_id: str) -> Dict[str, Any]:
        """
        Generate JSON API response for dashboard.
        
        Returns:
            JSON-serializable dict
        """
        dashboard_data = self.generate_dashboard_data(incident_id)
        return asdict(dashboard_data)
    
    def generate_demo_incident(self) -> str:
        """
        Generate synthetic incident for demo purposes.
        
        Returns:
            Incident ID of generated demo incident
        """
        from datetime import datetime, timedelta
        
        base_time = datetime.now() - timedelta(minutes=10)
        
        # Create root cause incident (memory leak)
        root_incident = IncidentEvent(
            event_id="demo-root-001",
            timestamp=base_time,
            node_id="node-cache-01",
            service_id="cache-service",
            anomaly_type="Memory Leak",
            severity=IncidentSeverity.HIGH,
            metrics={
                "memory_percent": 95.0,
                "cpu_percent": 45.0,
                "response_time_ms": 1200.0
            },
            detected_by="graphsage",
            anomaly_score=0.95
        )
        
        # Create correlated incident (API slowdown)
        correlated_incident = IncidentEvent(
            event_id="demo-correlated-001",
            timestamp=base_time + timedelta(seconds=30),
            node_id="node-api-01",
            service_id="api-service",
            anomaly_type="High Latency",
            severity=IncidentSeverity.MEDIUM,
            metrics={
                "latency_ms": 850.0,
                "error_rate_percent": 15.0,
                "requests_per_second": 500.0
            },
            detected_by="mape_k",
            anomaly_score=0.75
        )
        
        # Create main incident (service failure)
        main_incident = IncidentEvent(
            event_id="demo-main-001",
            timestamp=base_time + timedelta(minutes=2),
            node_id="node-api-01",
            service_id="api-service",
            anomaly_type="Service Failure",
            severity=IncidentSeverity.CRITICAL,
            metrics={
                "error_rate_percent": 50.0,
                "latency_ms": 2500.0,
                "requests_per_second": 100.0,
                "availability_percent": 50.0
            },
            detected_by="graphsage",
            anomaly_score=0.98
        )
        
        # Add incidents to engine
        self.engine.add_incident(root_incident)
        self.engine.add_incident(correlated_incident)
        self.engine.add_incident(main_incident)
        
        # Set service dependencies for demo
        self.engine.service_dependencies = {
            "api-service": ["cache-service", "database-service"],
            "cache-service": ["database-service"]
        }
        
        logger.info(f"Demo incident created: {main_incident.event_id}")
        return main_incident.event_id
    
    def export_to_grafana_dashboard(self, incident_id: str) -> Dict[str, Any]:
        """
        Export as Grafana dashboard JSON.
        
        Returns:
            Grafana dashboard JSON structure
        """
        dashboard_data = self.generate_dashboard_data(incident_id)
        
        # Create Grafana dashboard structure
        grafana_dashboard = {
            "dashboard": {
                "title": f"Causal Analysis: {incident_id}",
                "tags": ["causal-analysis", "incident", "root-cause"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "Timeline",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "causal_analysis_timeline_events",
                                "legendFormat": "{{event_type}}"
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "title": "Dependency Graph",
                        "type": "nodeGraph",
                        "targets": [
                            {
                                "expr": "causal_analysis_dependency_graph"
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "title": "Root Causes",
                        "type": "table",
                        "targets": [
                            {
                                "expr": "causal_analysis_root_causes"
                            }
                        ]
                    }
                ]
            }
        }
        
        return grafana_dashboard

