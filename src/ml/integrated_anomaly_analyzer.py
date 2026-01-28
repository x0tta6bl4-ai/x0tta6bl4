# GraphSAGE + Causal Analysis Integration
# Complete pipeline for anomaly detection + root cause identification

"""
Integrated Anomaly Detection and Root Cause Analysis Pipeline

This module provides seamless integration between:
1. GraphSAGE v3 Anomaly Detector (detection layer)
2. Enhanced Causal Analysis Engine v2 (analysis layer)

Pipeline:
  Detection Phase:
    Node features → GraphSAGE v3 → Anomaly score + confidence
  
  Analysis Phase:
    Anomaly → IncidentEvent → Causal Engine → Root causes
  
  Remediation Phase:
    Root causes → Recommendations → MAPE-K Execute phase

Key Features:
- Bidirectional feedback (confidence calibration)
- Real-time incident correlation
- Service topology learning
- Temporal pattern detection
- Comprehensive incident reporting
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class DetectionAndAnalysisResult:
    """Complete detection + analysis result"""
    incident_id: str
    node_id: str
    
    # Detection results
    is_anomaly: bool
    anomaly_score: float
    anomaly_confidence: float
    anomaly_explanation: str
    detection_method: str  # "graphsage_v3", "threshold", "heartbeat"
    
    # Analysis results
    root_causes: List[Dict[str, Any]]
    primary_root_cause: Optional[Dict[str, Any]]
    causal_confidence: float
    
    # Recommendations
    immediate_actions: List[str]
    investigation_steps: List[str]
    long_term_fixes: List[str]
    
    # Metadata
    detection_timestamp: datetime
    analysis_timestamp: datetime
    total_latency_ms: float
    severity: str  # "critical", "high", "medium", "low"


class IntegratedAnomalyAnalyzer:
    """
    Integrated Anomaly Detection + Root Cause Analysis Pipeline
    
    Combines GraphSAGE v3 detection with Enhanced Causal Analysis v2
    for complete incident understanding and remediation guidance.
    """
    
    def __init__(
        self,
        graphsage_detector,  # GraphSAGEAnomalyDetectorV3 instance
        causal_analyzer  # EnhancedCausalAnalysisEngine instance
    ):
        self.detector = graphsage_detector
        self.analyzer = causal_analyzer
        
        # Result tracking
        self.completed_analyses: Dict[str, DetectionAndAnalysisResult] = {}
        self.incident_severity_history: Dict[str, str] = {}
        
        logger.info("Integrated Anomaly Analyzer initialized")
    
    def process_node_anomaly(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        service_id: Optional[str] = None,
        network_nodes_count: Optional[int] = None,
        update_baseline: bool = False
    ) -> DetectionAndAnalysisResult:
        """
        Process node features through complete detection→analysis pipeline.
        
        Args:
            node_id: Target node ID
            node_features: Node feature dict
            neighbors: Neighbor list with features
            service_id: Optional service identifier
            network_nodes_count: Total nodes in network
            update_baseline: Whether to update GraphSAGE baseline
        
        Returns:
            Complete detection and analysis result
        """
        import time
        start_time = time.time()
        
        # Phase 1: Detection
        detection_result = self.detector.predict_enhanced(
            node_id=node_id,
            node_features=node_features,
            neighbors=neighbors,
            network_nodes_count=network_nodes_count,
            update_baseline=update_baseline
        )
        
        # Phase 2: Incident creation
        if detection_result['is_anomaly']:
            incident_id = self._create_incident_id(node_id)
            
            # Create IncidentEvent
            from causal_analysis_v2_enhanced import (
                IncidentEvent, IncidentSeverity
            )
            
            severity = self._score_to_severity(detection_result['anomaly_score'])
            
            incident = IncidentEvent(
                event_id=incident_id,
                timestamp=datetime.now(),
                node_id=node_id,
                service_id=service_id,
                anomaly_type=detection_result['explanation'].split(':')[0],
                severity=severity,
                metrics={
                    'anomaly_score': detection_result['anomaly_score'],
                    'confidence': detection_result['anomaly_confidence'],
                    **{k: v for k, v in node_features.items() if not k.startswith('_')}
                },
                detected_by='graphsage_v3',
                anomaly_score=detection_result['anomaly_score'],
                description=detection_result['explanation']
            )
            
            # Add to analyzer and check for duplicate
            is_new, incident_or_dup = self.analyzer.add_incident(incident)
            
            if not is_new:
                logger.debug(f"Incident {incident_id} is duplicate of {incident_or_dup}")
                # Return cached analysis for duplicate
                if incident_or_dup in self.completed_analyses:
                    return self.completed_analyses[incident_or_dup]
            
            # Phase 3: Root cause analysis
            causal_result = self.analyzer.analyze(incident_id)
            
            # Phase 4: Generate integrated result
            result = self._create_integrated_result(
                incident_id=incident_id,
                node_id=node_id,
                detection_result=detection_result,
                causal_result=causal_result,
                start_time=start_time
            )
            
            # Store result
            self.completed_analyses[incident_id] = result
            
            # Track severity
            self.incident_severity_history[incident_id] = result.severity
            
            return result
        
        else:
            # No anomaly - return empty result
            return DetectionAndAnalysisResult(
                incident_id='',
                node_id=node_id,
                is_anomaly=False,
                anomaly_score=detection_result['anomaly_score'],
                anomaly_confidence=detection_result['anomaly_confidence'],
                anomaly_explanation="No anomaly detected",
                detection_method='graphsage_v3',
                root_causes=[],
                primary_root_cause=None,
                causal_confidence=0.0,
                immediate_actions=[],
                investigation_steps=[],
                long_term_fixes=[],
                detection_timestamp=datetime.now(),
                analysis_timestamp=datetime.now(),
                total_latency_ms=(time.time() - start_time) * 1000,
                severity='normal'
            )
    
    def _create_incident_id(self, node_id: str) -> str:
        """Create unique incident ID"""
        import hashlib
        timestamp = datetime.now().isoformat()
        key = f"{node_id}:{timestamp}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]
    
    def _score_to_severity(self, anomaly_score: float) -> Any:
        """Convert anomaly score to severity"""
        from causal_analysis_v2_enhanced import IncidentSeverity
        
        if anomaly_score > 0.8:
            return IncidentSeverity.CRITICAL
        elif anomaly_score > 0.6:
            return IncidentSeverity.HIGH
        elif anomaly_score > 0.4:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW
    
    def _create_integrated_result(
        self,
        incident_id: str,
        node_id: str,
        detection_result: Dict[str, Any],
        causal_result: Any,
        start_time: float
    ) -> DetectionAndAnalysisResult:
        """Create integrated detection + analysis result"""
        import time
        
        # Categorize recommendations
        immediate_actions = []
        investigation_steps = []
        long_term_fixes = []
        
        if causal_result.primary_root_cause:
            root_cause = causal_result.primary_root_cause
            
            # Categorize recommendations
            for rec in root_cause.remediation_suggestions:
                if any(x in rec.lower() for x in ['restart', 'restart immediately', 'emergency']):
                    immediate_actions.append(rec)
                elif any(x in rec.lower() for x in ['check', 'verify', 'investigate', 'review']):
                    investigation_steps.append(rec)
                else:
                    long_term_fixes.append(rec)
            
            # Ensure some categorization
            if not immediate_actions:
                immediate_actions = root_cause.remediation_suggestions[:1]
            if not investigation_steps:
                investigation_steps = root_cause.remediation_suggestions[1:2]
            if not long_term_fixes:
                long_term_fixes = root_cause.remediation_suggestions[2:]
        
        # Determine severity
        severity = 'critical' if detection_result['anomaly_score'] > 0.8 else \
                   'high' if detection_result['anomaly_score'] > 0.6 else \
                   'medium' if detection_result['anomaly_score'] > 0.4 else \
                   'low'
        
        # Format root causes
        root_causes_list = []
        for rc in causal_result.root_causes[:3]:
            root_causes_list.append({
                'type': rc.root_cause_type.value if hasattr(rc.root_cause_type, 'value') else str(rc.root_cause_type),
                'confidence': rc.confidence,
                'explanation': rc.explanation,
                'factors': rc.contributing_factors,
                'suggestions': rc.remediation_suggestions
            })
        
        primary_rc = None
        if causal_result.primary_root_cause:
            primary_rc = {
                'type': causal_result.primary_root_cause.root_cause_type.value if hasattr(causal_result.primary_root_cause.root_cause_type, 'value') else str(causal_result.primary_root_cause.root_cause_type),
                'confidence': causal_result.primary_root_cause.confidence,
                'explanation': causal_result.primary_root_cause.explanation,
                'factors': causal_result.primary_root_cause.contributing_factors
            }
        
        return DetectionAndAnalysisResult(
            incident_id=incident_id,
            node_id=node_id,
            is_anomaly=detection_result['is_anomaly'],
            anomaly_score=detection_result['anomaly_score'],
            anomaly_confidence=detection_result['anomaly_confidence'],
            anomaly_explanation=detection_result['explanation'],
            detection_method='graphsage_v3',
            root_causes=root_causes_list,
            primary_root_cause=primary_rc,
            causal_confidence=causal_result.confidence,
            immediate_actions=immediate_actions,
            investigation_steps=investigation_steps,
            long_term_fixes=long_term_fixes,
            detection_timestamp=datetime.now(),
            analysis_timestamp=datetime.now(),
            total_latency_ms=(time.time() - start_time) * 1000,
            severity=severity
        )
    
    def get_integrated_report(self) -> Dict[str, Any]:
        """Get comprehensive integrated analysis report"""
        if not self.completed_analyses:
            return {
                'status': 'no_analyses',
                'message': 'No analyses completed yet'
            }
        
        # Statistics
        total_incidents = len(self.completed_analyses)
        critical = sum(1 for r in self.completed_analyses.values() if r.severity == 'critical')
        high = sum(1 for r in self.completed_analyses.values() if r.severity == 'high')
        
        # Average latencies
        avg_detection_latency = sum(
            r.total_latency_ms for r in self.completed_analyses.values()
        ) / total_incidents if total_incidents else 0
        
        # Most common root causes
        root_cause_counts = {}
        for result in self.completed_analyses.values():
            for rc in result.root_causes:
                rc_type = rc['type']
                root_cause_counts[rc_type] = root_cause_counts.get(rc_type, 0) + 1
        
        # Confidence statistics
        causal_confidences = [
            r.causal_confidence for r in self.completed_analyses.values()
            if r.causal_confidence > 0
        ]
        
        return {
            'status': 'ok',
            'summary': {
                'total_incidents': total_incidents,
                'critical_severity': critical,
                'high_severity': high,
                'detection_latency_ms': avg_detection_latency
            },
            'root_cause_distribution': root_cause_counts,
            'average_causal_confidence': sum(causal_confidences) / len(causal_confidences) if causal_confidences else 0,
            'recent_incidents': [
                {
                    'incident_id': r.incident_id,
                    'node_id': r.node_id,
                    'severity': r.severity,
                    'root_cause': r.primary_root_cause['explanation'] if r.primary_root_cause else None
                }
                for r in list(self.completed_analyses.values())[-10:]
            ]
        }
    
    def export_to_json(self, incident_id: str) -> str:
        """Export incident analysis to JSON"""
        if incident_id not in self.completed_analyses:
            return json.dumps({'error': 'Incident not found'})
        
        result = self.completed_analyses[incident_id]
        
        return json.dumps({
            'incident_id': result.incident_id,
            'node_id': result.node_id,
            'severity': result.severity,
            'detection': {
                'is_anomaly': result.is_anomaly,
                'anomaly_score': result.anomaly_score,
                'confidence': result.anomaly_confidence,
                'explanation': result.anomaly_explanation,
                'method': result.detection_method
            },
            'analysis': {
                'root_causes': result.root_causes,
                'primary_root_cause': result.primary_root_cause,
                'causal_confidence': result.causal_confidence
            },
            'recommendations': {
                'immediate': result.immediate_actions,
                'investigation': result.investigation_steps,
                'long_term': result.long_term_fixes
            },
            'timing': {
                'detection_timestamp': result.detection_timestamp.isoformat(),
                'analysis_timestamp': result.analysis_timestamp.isoformat(),
                'total_latency_ms': result.total_latency_ms
            }
        }, indent=2)


# Factory function for MAPE-K integration
def create_integrated_analyzer_for_mapek(
    detector=None,
    analyzer=None
) -> IntegratedAnomalyAnalyzer:
    """
    Create integrated analyzer for MAPE-K autonomic loop.
    
    Args:
        detector: GraphSAGEAnomalyDetectorV3 instance (created if None)
        analyzer: EnhancedCausalAnalysisEngine instance (created if None)
    
    Returns:
        Configured IntegratedAnomalyAnalyzer
    """
    if detector is None:
        from graphsage_anomaly_detector_v3_enhanced import create_graphsage_v3_for_mapek
        detector = create_graphsage_v3_for_mapek()
    
    if analyzer is None:
        from causal_analysis_v2_enhanced import create_enhanced_causal_analyzer_for_mapek
        analyzer = create_enhanced_causal_analyzer_for_mapek()
    
    return IntegratedAnomalyAnalyzer(detector, analyzer)


# Example usage
if __name__ == '__main__':
    # Create integrated analyzer
    analyzer = create_integrated_analyzer_for_mapek()
    
    # Example node data
    example_node_features = {
        'rssi': -75,
        'snr': 15,
        'loss_rate': 0.02,
        'link_age_hours': 48,
        'latency': 80,
        'throughput_mbps': 45,
        'cpu_percent': 65,
        'memory_percent': 72
    }
    
    example_neighbors = [
        ('node-02', {'rssi': -70, 'snr': 20, 'loss_rate': 0.01, 'latency': 50}),
        ('node-03', {'rssi': -72, 'snr': 18, 'loss_rate': 0.015, 'latency': 65}),
    ]
    
    # Process through pipeline
    result = analyzer.process_node_anomaly(
        node_id='node-01',
        node_features=example_node_features,
        neighbors=example_neighbors,
        service_id='mesh-router',
        network_nodes_count=10
    )
    
    print(f"Incident: {result.incident_id}")
    print(f"Is Anomaly: {result.is_anomaly}")
    print(f"Severity: {result.severity}")
    if result.primary_root_cause:
        print(f"Root Cause: {result.primary_root_cause['explanation']}")
    print(f"Immediate Actions: {result.immediate_actions}")
