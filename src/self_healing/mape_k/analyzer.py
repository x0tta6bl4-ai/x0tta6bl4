"""MAPE-K Analyzer component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MAPEKAnalyzer:
    """
    Analyzer phase with Causal Analysis, GraphSAGE and LLM support.

    Uses Causal Analysis Engine for root cause identification
    when incidents are detected. Integrates with GraphSAGE for
    enhanced root cause analysis and Kimi K2.5 for intelligent log analysis.
    """

    def __init__(self):
        self.causal_analyzer = None
        self.use_causal_analysis = False
        self.graphsage_detector = None
        self.use_graphsage = False
        self.llm_integration = None
        self.use_llm = False

    def enable_causal_analysis(self, analyzer=None):
        """
        Enable Causal Analysis for root cause identification.

        Args:
            analyzer: Optional CausalAnalysisEngine instance (created if None)
        """
        from src.ml.causal_analysis import (create_causal_analyzer_for_mapek)

        if analyzer is None:
            self.causal_analyzer = create_causal_analyzer_for_mapek()
        else:
            self.causal_analyzer = analyzer

        self.use_causal_analysis = True
        logger.info("Causal Analysis enabled for Analyzer phase")

    def enable_graphsage(self, detector=None):
        """
        Enable GraphSAGE detector for enhanced root cause analysis.

        Args:
            detector: Optional GraphSAGE detector instance (created if None)
        """
        from src.ml.graphsage_anomaly_detector import (
            create_graphsage_detector_for_mapek)

        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector

        self.use_graphsage = True
        logger.info("GraphSAGE enabled for Analyzer phase")

    def enable_llm(self, integration=None):
        """
        Enable LLM integration (Kimi K2.5) for intelligent log analysis.

        Args:
            integration: Optional KimiK25Integration instance
        """
        try:
            from src.swarm.intelligence import KimiK25Integration
            if integration is None:
                self.llm_integration = KimiK25Integration(enabled=True)
            else:
                self.llm_integration = integration
            self.use_llm = True
            logger.info("🤖 Kimi K2.5 LLM enabled for Analyzer phase")
        except ImportError:
            logger.warning("KimiK25Integration not available, LLM analysis disabled")

    async def analyze_with_llm(self, metrics: Dict, logs: Optional[str] = None) -> str:
        """
        Perform intelligent root cause analysis using LLM.
        """
        if not self.use_llm or not self.llm_integration:
            return "LLM analysis not available"

        from src.swarm.intelligence import DecisionContext, DecisionType
        
        context = DecisionContext(
            topic="Root Cause Analysis",
            decision_type=DecisionType.HEALING,
            description="Analyze system metrics and logs to identify root cause of instability.",
            data={
                "metrics": metrics,
                "logs": logs
            }
        )
        
        options = [
            "Network Link Failure (Physical/ISP level)",
            "Proxy Configuration Error (Software level)",
            "Censorship Interference (GFW/DPI detected)",
            "Byzantine Attack (Security level)",
            "Resource Exhaustion (CPU/Memory)",
            "Transport Layer Mismatch (TLS/VLESS Reality issue)"
        ]
        
        idx, reasoning = await self.llm_integration.enhance_decision(context, options)
        return f"AI-Analysis ({options[idx]}): {reasoning}"

    def analyze(
        self, metrics: Dict, node_id: str = "unknown", event_id: Optional[str] = None
    ) -> str:
        """
        Analyze metrics and identify root cause.

        Enhanced with GraphSAGE integration for better root cause identification.

        Args:
            metrics: System metrics
            node_id: Node identifier
            event_id: Optional event ID for causal analysis

        Returns:
            Issue description with root cause if available
        """
        # Try GraphSAGE + Causal Analysis first if available
        if self.use_graphsage and self.graphsage_detector:
            try:
                # Extract node features from metrics
                node_features = {
                    "rssi": metrics.get("rssi", -50.0),
                    "snr": metrics.get("snr", 20.0),
                    "loss_rate": metrics.get("packet_loss_percent", 0.0) / 100.0,
                    "link_age": metrics.get("link_age_seconds", 3600.0),
                    "latency": metrics.get("latency_ms", 10.0),
                    "throughput": metrics.get("throughput_mbps", 100.0),
                    "cpu": metrics.get("cpu_percent", 0.0) / 100.0,
                    "memory": metrics.get("memory_percent", 0.0) / 100.0,
                }

                neighbors = metrics.get("neighbor_features", [])

                # Use predict_with_causal if available
                if hasattr(self.graphsage_detector, "predict_with_causal"):
                    prediction, causal_result = (
                        self.graphsage_detector.predict_with_causal(
                            node_id=node_id,
                            node_features=node_features,
                            neighbors=neighbors,
                        )
                    )

                    if prediction.is_anomaly:
                        # Extract root cause from GraphSAGE + Causal Analysis
                        if causal_result and causal_result.root_causes:
                            root_cause = causal_result.root_causes[0]
                            root_cause_type = str(root_cause.root_cause_type)
                            if "anomaly" in root_cause_type.lower():
                                display_type = f"Anomaly: {root_cause_type}"
                            else:
                                display_type = root_cause_type
                            issue = (
                                f"{display_type} "
                                f"(GraphSAGE+Causal, confidence: {root_cause.confidence:.1%})"
                            )
                            logger.info(
                                f"GraphSAGE+Causal root cause: {root_cause.explanation}"
                            )
                            return issue
                        else:
                            # Fallback to basic issue description
                            issue = f"Anomaly detected (score: {prediction.anomaly_score:.2f})"
                            return issue
                else:
                    # Fallback to basic predict
                    prediction = self.graphsage_detector.predict(
                        node_id=node_id,
                        node_features=node_features,
                        neighbors=neighbors,
                    )

                    if prediction.is_anomaly:
                        issue = (
                            f"Anomaly detected (score: {prediction.anomaly_score:.2f})"
                        )
                        return issue
            except Exception as e:
                logger.warning(
                    f"GraphSAGE analysis failed: {e}, falling back to threshold-based"
                )

        # Basic threshold-based analysis (fallback)
        if metrics.get("cpu_percent", 0) > 90:
            issue = "High CPU"
        elif metrics.get("memory_percent", 0) > 85:
            issue = "High Memory"
        elif metrics.get("packet_loss_percent", 0) > 5:
            issue = "Network Loss"
        else:
            issue = "Healthy"

        # Use LLM Analysis if logs are present and AI enabled
        if self.use_llm and self.llm_integration and metrics.get("logs") and issue != "Healthy":
            try:
                import asyncio
                logs = metrics.get("logs")
                try:
                    asyncio.get_running_loop()
                    # Already inside an async context; can't block here, skip LLM.
                except RuntimeError:
                    issue = asyncio.run(self.analyze_with_llm(metrics, logs))
                    logger.info(f"🤖 AI-Analyzer Result: {issue}")
            except Exception as e:
                logger.warning(f"AI-Analyzer failed: {e}")

        # Use Causal Analysis if enabled and event_id provided
        if self.use_causal_analysis and self.causal_analyzer and event_id:
            try:
                from src.ml.causal_analysis import (IncidentEvent,
                                                    IncidentSeverity)

                # Create incident event
                incident = IncidentEvent(
                    event_id=event_id or f"incident_{int(time.time() * 1000)}",
                    timestamp=datetime.now(),
                    node_id=node_id,
                    service_id=metrics.get("service_id"),
                    anomaly_type=issue,
                    severity=(
                        IncidentSeverity.HIGH
                        if metrics.get("cpu_percent", 0) > 95
                        else IncidentSeverity.MEDIUM
                    ),
                    metrics=metrics,
                    detected_by="mape_k",
                    anomaly_score=0.8,
                )

                # Add to causal analyzer
                self.causal_analyzer.add_incident(incident)

                # Perform causal analysis
                result = self.causal_analyzer.analyze(incident.event_id)

                # Enhance issue description with root cause
                if result.root_causes:
                    root_cause = result.root_causes[0]
                    issue = f"{issue} (Root cause: {root_cause.root_cause_type}, confidence: {root_cause.confidence:.1%})"
                    logger.info(f"Causal analysis: {root_cause.explanation}")
            except Exception as e:
                logger.warning(f"Causal analysis failed: {e}, using basic analysis")

        return issue


