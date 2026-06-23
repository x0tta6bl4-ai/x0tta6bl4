"""
Analyze phase for MAPE-K Self-Healing.
"""
import logging
import asyncio
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from src.core.agent_thinking import AgentThinkingCoach
from src.core.mape_k.interfaces import AnalyzerInterface


def _safe_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

class MAPEKAnalyzer(AnalyzerInterface):
    """
    Analyzer phase with Causal Analysis, GraphSAGE and LLM support.
    """

    def __init__(self):
        self.causal_analyzer = None
        self.use_causal_analysis = False
        self.graphsage_detector = None
        self.use_graphsage = False
        self.llm_integration = None
        self.use_llm = False
        self.thinking_coach = AgentThinkingCoach(
            agent_id="self-healing-mapek-analyzer",
            role="analysis",
            capabilities=("mape_k", "causal_analysis", "zero-trust"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "causal_enabled": self.use_causal_analysis,
            "graphsage_enabled": self.use_graphsage,
            "llm_enabled": self.use_llm,
            "constraints": {
                "redact_node_ids": True,
                "redact_raw_metrics": True,
                "redact_logs": True,
                "analysis_is_not_recovery_proof": True,
            },
            "safety_boundary": (
                "MAPE-K analysis produces local diagnosis only; it does not prove "
                "recovery action execution, dataplane delivery, or production readiness."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose analyzer thinking state without raw metrics or logs."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def enable_causal_analysis(self, analyzer=None):
        """Enable Causal Analysis for root cause identification."""
        from src.ml.causal_analysis import create_causal_analyzer_for_mapek
        if analyzer is None:
            self.causal_analyzer = create_causal_analyzer_for_mapek()
        else:
            self.causal_analyzer = analyzer
        self.use_causal_analysis = True
        self._record_thinking(
            "mapek_analyzer_enable_causal",
            "enable causal analysis for local root-cause diagnostics",
        )
        logger.info("Causal Analysis enabled for Analyzer phase")

    def enable_graphsage(self, detector=None):
        """Enable GraphSAGE detector for enhanced root cause analysis."""
        from src.ml.graphsage_anomaly_detector import create_graphsage_detector_for_mapek
        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector
        self.use_graphsage = True
        self._record_thinking(
            "mapek_analyzer_enable_graphsage",
            "enable GraphSAGE for local anomaly diagnostics",
        )
        logger.info("GraphSAGE enabled for Analyzer phase")

    def enable_llm(self, integration=None):
        """Enable LLM integration (Kimi K2.5) for intelligent log analysis."""
        try:
            from src.swarm.intelligence import KimiK25Integration
            if integration is None:
                self.llm_integration = KimiK25Integration(enabled=True)
            else:
                self.llm_integration = integration
            self.use_llm = True
            self._record_thinking(
                "mapek_analyzer_enable_llm",
                "enable LLM-assisted local log analysis with redaction boundary",
            )
            logger.info("🤖 Kimi K2.5 LLM enabled for Analyzer phase")
        except ImportError:
            self._record_thinking(
                "mapek_analyzer_enable_llm",
                "record unavailable LLM integration",
                {"status": "unavailable"},
            )
            logger.warning("KimiK25Integration not available, LLM analysis disabled")

    async def analyze_with_llm(self, metrics: Dict, logs: Optional[str] = None) -> str:
        """Perform intelligent root cause analysis using LLM."""
        if not self.use_llm or not self.llm_integration:
            self._record_thinking(
                "mapek_analyzer_llm_analysis",
                "skip LLM analysis when integration is unavailable",
                {"logs_present": bool(logs), "metric_keys": sorted(str(key) for key in metrics)},
            )
            return "LLM analysis not available"

        self._record_thinking(
            "mapek_analyzer_llm_analysis",
            "run LLM-assisted analysis without storing raw logs",
            {
                "logs_present": bool(logs),
                "logs_hash": _safe_hash(logs),
                "metric_keys": sorted(str(key) for key in metrics),
            },
        )
        from src.swarm.intelligence import DecisionContext, DecisionType
        context = DecisionContext(
            topic="Root Cause Analysis",
            decision_type=DecisionType.HEALING,
            description="Analyze system metrics and logs to identify root cause of instability.",
            data={"metrics": metrics, "logs": logs},
        )
        options = [
            "Network Link Failure (Physical/ISP level)",
            "Proxy Configuration Error (Software level)",
            "Censorship Interference (GFW/DPI detected)",
            "Byzantine Attack (Security level)",
            "Resource Exhaustion (CPU/Memory)",
            "Transport Layer Mismatch (TLS/VLESS Reality issue)",
        ]
        idx, reasoning = await self.llm_integration.enhance_decision(context, options)
        return f"AI-Analysis ({options[idx]}): {reasoning}"

    def analyze(self, metrics: Dict, node_id: str = "unknown", event_id: Optional[str] = None) -> str:
        """Analyze metrics and identify root cause."""
        self._record_thinking(
            "mapek_analyzer_analyze",
            "analyze local MAPE-K metrics without raw metric payloads",
            {
                "node_id_hash": _safe_hash(node_id),
                "event_id_hash": _safe_hash(event_id),
                "metric_keys": sorted(str(key) for key in metrics),
            },
        )
        if self.use_graphsage and self.graphsage_detector:
            try:
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

                prediction = None
                if hasattr(self.graphsage_detector, "predict_with_causal"):
                    prediction, causal_result = self.graphsage_detector.predict_with_causal(
                        node_id=node_id, node_features=node_features, neighbors=neighbors
                    )
                    if prediction.is_anomaly:
                        if causal_result and causal_result.root_causes:
                            root_cause = causal_result.root_causes[0]
                            root_cause_type = str(root_cause.root_cause_type)
                            display_type = f"Anomaly: {root_cause_type}" if "anomaly" in root_cause_type.lower() else root_cause_type
                            return f"{display_type} (GraphSAGE+Causal, confidence: {root_cause.confidence:.1%})"
                        else:
                            return f"Anomaly detected (score: {prediction.anomaly_score:.2f})"
                elif hasattr(self.graphsage_detector, "predict"):
                    prediction = self.graphsage_detector.predict(node_id=node_id, node_features=node_features, neighbors=neighbors)
                    if prediction.is_anomaly:
                        return f"Anomaly detected (score: {prediction.anomaly_score:.2f})"
            except Exception as e:
                logger.warning(f"GraphSAGE analysis failed: {e}")

        # Fallback
        if metrics.get("cpu_percent", 0) > 90: issue = "High CPU"
        elif metrics.get("memory_percent", 0) > 85: issue = "High Memory"
        elif metrics.get("packet_loss_percent", 0) > 5: issue = "Network Loss"
        else: issue = "Healthy"

        if self.use_llm and self.llm_integration and metrics.get("logs") and issue != "Healthy":
            try:
                import asyncio
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    issue = asyncio.run(self.analyze_with_llm(metrics, metrics.get("logs")))
            except Exception as e:
                logger.warning(f"AI-Analyzer failed: {e}")

        if self.use_causal_analysis and self.causal_analyzer and event_id:
            try:
                from src.ml.causal_analysis import IncidentEvent, IncidentSeverity
                incident = IncidentEvent(
                    event_id=event_id, timestamp=datetime.now(), node_id=node_id,
                    service_id=metrics.get("service_id"), anomaly_type=issue,
                    severity=IncidentSeverity.HIGH if metrics.get("cpu_percent", 0) > 95 else IncidentSeverity.MEDIUM,
                    metrics=metrics, detected_by="mape_k", anomaly_score=0.8
                )
                self.causal_analyzer.add_incident(incident)
                result = self.causal_analyzer.analyze(incident.event_id)
                if result.root_causes:
                    root_cause = result.root_causes[0]
                    issue = f"{issue} (Root cause: {root_cause.root_cause_type}, confidence: {root_cause.confidence:.1%})"
            except Exception: pass
        self._record_thinking(
            "mapek_analyzer_analyze",
            "record local MAPE-K analysis result class",
            {
                "node_id_hash": _safe_hash(node_id),
                "event_id_hash": _safe_hash(event_id),
                "issue_hash": _safe_hash(issue),
                "issue_redacted": True,
            },
        )
        return issue
