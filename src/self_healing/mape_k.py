"""
MAPE-K Self-Healing Core for x0tta6bl4
Implements Monitor, Analyze, Plan, Execute, Knowledge loop
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MAPEKMonitor:
    """
    Monitor phase with feedback loop support.

    Uses adaptive thresholds from Knowledge base to improve
    detection accuracy and reduce false positives.

    Supports GraphSAGE v2 anomaly detector for advanced detection.
    Now supports DAO-managed thresholds via ThresholdManager.
    """

    def __init__(
        self, knowledge: Optional["MAPEKKnowledge"] = None, threshold_manager=None
    ):
        self.anomaly_detectors: List[Callable[[Dict], bool]] = []
        self.knowledge = knowledge
        self.threshold_manager = threshold_manager

        # Default thresholds (can be overridden by DAO)
        self.default_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "packet_loss_percent": 5.0,
        }

        # GraphSAGE v2 detector (optional, loaded on demand)
        self.graphsage_detector = None
        self.use_graphsage = False

    def register_detector(self, fn: Callable[[Dict], bool]):
        """Register custom anomaly detector."""
        self.anomaly_detectors.append(fn)

    def enable_graphsage(self, detector=None):
        """
        Enable GraphSAGE v2 anomaly detector.

        Args:
            detector: Optional GraphSAGE detector instance (created if None)
        """
        from src.ml.graphsage_anomaly_detector import (
            GraphSAGEAnomalyDetector, create_graphsage_detector_for_mapek)

        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector

        self.use_graphsage = True
        logger.info("GraphSAGE v2 detector enabled for Monitor phase")

    def check(self, metrics: Dict) -> bool:
        """
        Check for anomalies with adaptive thresholds from feedback loop.

        Uses adjusted thresholds from Knowledge base if available.
        Now also supports DAO-managed thresholds via ThresholdManager.
        """
        # Get thresholds (priority: DAO > Knowledge > Default)
        if self.threshold_manager:
            # Use DAO-managed thresholds
            cpu_threshold = self.threshold_manager.get_threshold(
                "cpu_threshold", self.default_thresholds["cpu_percent"]
            )
            memory_threshold = self.threshold_manager.get_threshold(
                "memory_threshold", self.default_thresholds["memory_percent"]
            )
            packet_loss_threshold = self.threshold_manager.get_threshold(
                "network_loss_threshold", self.default_thresholds["packet_loss_percent"]
            )
        elif self.knowledge:
            # Use feedback-adjusted thresholds from Knowledge base
            cpu_threshold = self.knowledge.get_adjusted_threshold(
                "cpu_percent", self.default_thresholds["cpu_percent"]
            )
            memory_threshold = self.knowledge.get_adjusted_threshold(
                "memory_percent", self.default_thresholds["memory_percent"]
            )
            packet_loss_threshold = self.knowledge.get_adjusted_threshold(
                "packet_loss_percent", self.default_thresholds["packet_loss_percent"]
            )
        else:
            # Use default thresholds
            cpu_threshold = self.default_thresholds["cpu_percent"]
            memory_threshold = self.default_thresholds["memory_percent"]
            packet_loss_threshold = self.default_thresholds["packet_loss_percent"]

        # Check with determined thresholds
        if self.threshold_manager or self.knowledge:

            # Check with adjusted thresholds
            if metrics.get("cpu_percent", 0) > cpu_threshold:
                return True
            if metrics.get("memory_percent", 0) > memory_threshold:
                return True
            if metrics.get("packet_loss_percent", 0) > packet_loss_threshold:
                return True
        else:
            # Fallback to default thresholds
            if metrics.get("cpu_percent", 0) > self.default_thresholds["cpu_percent"]:
                return True
            if (
                metrics.get("memory_percent", 0)
                > self.default_thresholds["memory_percent"]
            ):
                return True
            if (
                metrics.get("packet_loss_percent", 0)
                > self.default_thresholds["packet_loss_percent"]
            ):
                return True

        # Check GraphSAGE v2 detector if enabled
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

                # Get neighbors (simplified - would use actual topology)
                neighbors = []  # Would be populated from mesh topology

                # Use predict_with_causal if available for root cause analysis
                node_id = metrics.get("node_id", "unknown")
                if hasattr(self.graphsage_detector, "predict_with_causal"):
                    # predict_with_causal returns (prediction, causal_result)
                    prediction, causal_result = (
                        self.graphsage_detector.predict_with_causal(
                            node_id=node_id,
                            node_features=node_features,
                            neighbors=neighbors,
                        )
                    )

                    if prediction.is_anomaly:
                        logger.debug(
                            f"GraphSAGE detected anomaly on {node_id}: "
                            f"score={prediction.anomaly_score:.3f}, "
                            f"inference={prediction.inference_time_ms:.2f}ms"
                        )

                        # Log root cause if identified
                        if causal_result and causal_result.root_causes:
                            root_cause = causal_result.root_causes[
                                0
                            ]  # Highest confidence
                            logger.info(
                                f"Root cause identified: {root_cause.root_cause_type} "
                                f"(confidence: {root_cause.confidence:.1%})"
                            )

                        return True
                else:
                    # Fallback to basic predict if predict_with_causal not available
                    prediction = self.graphsage_detector.predict(
                        node_id=node_id,
                        node_features=node_features,
                        neighbors=neighbors,
                    )

                    if prediction.is_anomaly:
                        logger.debug(
                            f"GraphSAGE detected anomaly: "
                            f"score={prediction.anomaly_score:.3f}, "
                            f"inference={prediction.inference_time_ms:.2f}ms"
                        )
                        return True
            except Exception as e:
                logger.warning(
                    f"GraphSAGE detection failed: {e}, falling back to threshold"
                )

        # Check custom detectors
        return any(detector(metrics) for detector in self.anomaly_detectors)


class MAPEKAnalyzer:
    """
    Analyzer phase with Causal Analysis and GraphSAGE support.

    Uses Causal Analysis Engine for root cause identification
    when incidents are detected. Integrates with GraphSAGE for
    enhanced root cause analysis from anomaly predictions.
    """

    def __init__(self):
        self.causal_analyzer = None
        self.use_causal_analysis = False
        self.graphsage_detector = None
        self.use_graphsage = False

    def enable_causal_analysis(self, analyzer=None):
        """
        Enable Causal Analysis for root cause identification.

        Args:
            analyzer: Optional CausalAnalysisEngine instance (created if None)
        """
        from src.ml.causal_analysis import (CausalAnalysisEngine,
                                            IncidentEvent, IncidentSeverity,
                                            create_causal_analyzer_for_mapek)

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
            GraphSAGEAnomalyDetector, create_graphsage_detector_for_mapek)

        if detector is None:
            self.graphsage_detector = create_graphsage_detector_for_mapek()
        else:
            self.graphsage_detector = detector

        self.use_graphsage = True
        logger.info("GraphSAGE enabled for Analyzer phase")

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

                neighbors = []  # Would be populated from mesh topology

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
            return "Healthy"

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


class MAPEKPlanner:
    """
    Planner phase with feedback loop support.

    Uses historical success patterns from Knowledge base to
    select optimal recovery strategies.
    """

    def __init__(self, knowledge: Optional["MAPEKKnowledge"] = None):
        self.knowledge = knowledge
        self.default_strategies = {
            "High CPU": "Restart service",
            "High Memory": "Clear cache",
            "Network Loss": "Switch route",
        }

    def plan(self, issue: str) -> str:
        """
        Plan recovery strategy with feedback from Knowledge base.

        Uses most successful historical action for this issue type.
        Falls back to default strategy if no history available.
        """
        # Try to get recommended action from knowledge base
        if self.knowledge:
            recommended = self.knowledge.get_recommended_action(issue)
            if recommended:
                logger.debug(f"Using recommended action from knowledge: {recommended}")
                return recommended

        # Fallback to default strategies
        return self.default_strategies.get(issue, "No action needed")


class MAPEKExecutor:
    """
    MAPE-K Executor with production-ready recovery actions.

    Uses RecoveryActionExecutor for real recovery operations.
    """

    def __init__(self):
        try:
            from src.self_healing.recovery_actions import \
                RecoveryActionExecutor

            self.recovery_executor = RecoveryActionExecutor()
            self.use_recovery_executor = True
        except ImportError:
            self.recovery_executor = None
            self.use_recovery_executor = False
            logger.warning("RecoveryActionExecutor not available, using placeholder")

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute recovery action.

        Args:
            action: Action string (e.g., "Restart service", "Switch route")
            context: Additional context for action execution

        Returns:
            True if action executed successfully
        """
        logger.info(f"Executing action: {action}")

        if self.use_recovery_executor and self.recovery_executor:
            return self.recovery_executor.execute(action, context)

        # Fallback placeholder
        logger.warning(f"Placeholder execution for: {action}")
        time.sleep(0.1)
        return True


class MAPEKKnowledge:
    """
    Knowledge base for MAPE-K cycle with feedback loop support.

    Stores incident history and provides feedback to improve:
    - Monitor: Adaptive thresholds based on historical patterns
    - Analyze: Improved root cause analysis from successful patterns
    - Plan: Optimized recovery strategies from experience

    Now integrated with Knowledge Storage v2.0 (IPFS + CRDT + Vector Memory)
    """

    def __init__(self, knowledge_storage=None):
        self.incidents: List[Dict[str, Any]] = []
        self.successful_patterns: Dict[str, List[Dict]] = (
            {}
        )  # issue -> [successful incidents]
        self.failed_patterns: Dict[str, List[Dict]] = {}  # issue -> [failed incidents]
        self.threshold_adjustments: Dict[str, float] = (
            {}
        )  # metric -> adjusted threshold

        # Integration with Knowledge Storage v2.0
        # knowledge_storage can be KnowledgeStorageV2 or MAPEKKnowledgeStorageAdapter
        self.knowledge_storage = knowledge_storage
        if knowledge_storage:
            logger.info("✅ MAPE-K Knowledge integrated with Knowledge Storage v2.0")

    def record(
        self,
        metrics: Dict,
        issue: str,
        action: str,
        success: bool = True,
        mttr: Optional[float] = None,
        node_id: str = "default",
    ):
        """Record incident with success status for feedback learning."""
        incident = {
            "metrics": metrics,
            "issue": issue,
            "action": action,
            "timestamp": time.time(),
            "success": success,
            "mttr": mttr,
        }
        self.incidents.append(incident)

        # Store in Knowledge Storage v2.0 (IPFS + Vector Memory)
        if self.knowledge_storage:
            try:
                # Check if it's an adapter (has record_incident_sync method)
                if hasattr(self.knowledge_storage, "record_incident_sync"):
                    # Use adapter's sync method
                    self.knowledge_storage.record_incident_sync(
                        metrics=metrics,
                        issue=issue,
                        action=action,
                        success=success,
                        mttr=mttr,
                    )
                else:
                    # Direct KnowledgeStorageV2 - use async
                    import asyncio

                    incident_entry = {
                        "id": f"incident-{int(time.time() * 1000)}",
                        "timestamp": time.time(),
                        "anomaly_type": issue,
                        "metrics": metrics,
                        "root_cause": issue,  # Will be improved by Causal Analysis
                        "recovery_plan": action,
                        "execution_result": {
                            "success": success,
                            "duration": mttr or 0.0,
                        },
                    }
                    # Run async in sync context
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, schedule as task
                            asyncio.create_task(
                                self.knowledge_storage.store_incident(
                                    incident_entry, node_id
                                )
                            )
                        else:
                            # If no loop, run it
                            loop.run_until_complete(
                                self.knowledge_storage.store_incident(
                                    incident_entry, node_id
                                )
                            )
                    except RuntimeError:
                        # No event loop, create new one
                        asyncio.run(
                            self.knowledge_storage.store_incident(
                                incident_entry, node_id
                            )
                        )
                    logger.debug(
                        f"📚 Stored incident in Knowledge Storage v2.0: {issue}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to store in Knowledge Storage: {e}")

        # Categorize by success/failure for pattern learning
        if success:
            if issue not in self.successful_patterns:
                self.successful_patterns[issue] = []
            self.successful_patterns[issue].append(incident)
        else:
            if issue not in self.failed_patterns:
                self.failed_patterns[issue] = []
            self.failed_patterns[issue].append(incident)

        # Update thresholds based on feedback
        self._update_thresholds(metrics, issue, success)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get all incident history."""
        return self.incidents

    def get_successful_patterns(self, issue: str) -> List[Dict[str, Any]]:
        """Get successful recovery patterns for specific issue."""
        # Try to get from Knowledge Storage v2.0 first (with RAG search)
        if self.knowledge_storage:
            try:
                # Check if it's an adapter (has search_patterns_sync method)
                if hasattr(self.knowledge_storage, "search_patterns_sync"):
                    # Use adapter's sync method
                    results = self.knowledge_storage.search_patterns_sync(
                        query=f"{issue} successful recovery", k=10, threshold=0.7
                    )
                    if results:
                        logger.debug(
                            f"🔍 Found {len(results)} patterns from Knowledge Storage"
                        )
                        return results
                elif hasattr(self.knowledge_storage, "get_successful_patterns"):
                    # Direct KnowledgeStorageV2 - use async
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Can't run async in sync context, return local patterns
                            logger.debug(
                                "⚠️ Cannot run async search in running loop, using local patterns"
                            )
                            return self.successful_patterns.get(issue, [])
                        else:
                            # Run synchronously
                            results = loop.run_until_complete(
                                self.knowledge_storage.get_successful_patterns(issue)
                            )
                            if results:
                                logger.debug(
                                    f"🔍 Found {len(results)} patterns from Knowledge Storage"
                                )
                                return results
                    except RuntimeError:
                        # No event loop, create new one
                        results = asyncio.run(
                            self.knowledge_storage.get_successful_patterns(issue)
                        )
                        if results:
                            return results
                else:
                    # Try async search_incidents
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            return self.successful_patterns.get(issue, [])
                        else:
                            results = loop.run_until_complete(
                                self.knowledge_storage.search_incidents(
                                    f"{issue} successful recovery", k=10, threshold=0.7
                                )
                            )
                            if results:
                                logger.debug(
                                    f"🔍 Found {len(results)} patterns from Knowledge Storage"
                                )
                                return results
                    except RuntimeError:
                        results = asyncio.run(
                            self.knowledge_storage.search_incidents(
                                f"{issue} successful recovery", k=10, threshold=0.7
                            )
                        )
                        if results:
                            return results
            except Exception as e:
                logger.warning(f"⚠️ Failed to search Knowledge Storage: {e}")

        # Fallback to local patterns
        return self.successful_patterns.get(issue, [])

    def get_average_mttr(self, issue: str) -> Optional[float]:
        """
        Get average MTTR for a specific issue type from historical data.

        Args:
            issue: Issue type/root cause

        Returns:
            Average MTTR in seconds, or None if no data available
        """
        # Get successful incidents for this issue
        successful_incidents = self.successful_patterns.get(issue, [])

        if not successful_incidents:
            # Try to get from Knowledge Storage v2.0
            if self.knowledge_storage:
                try:
                    # Query knowledge storage for historical MTTR
                    patterns = self.get_successful_patterns(issue)
                    if patterns:
                        mttr_values = [
                            p.get("mttr", 0)
                            for p in patterns
                            if p.get("mttr") and p.get("mttr", 0) > 0
                        ]
                        if mttr_values:
                            return sum(mttr_values) / len(mttr_values)
                except Exception:
                    pass
            return None

        # Calculate average MTTR from successful incidents
        mttr_values = [
            inc.get("mttr", 0)
            for inc in successful_incidents
            if inc.get("mttr") and inc.get("mttr", 0) > 0
        ]

        if not mttr_values:
            return None

        return sum(mttr_values) / len(mttr_values)

    def get_recommended_action(self, issue: str) -> Optional[str]:
        """
        Get recommended action based on historical success patterns.

        Returns most successful action for this issue type.
        """
        if issue not in self.successful_patterns:
            return None

        # Count action success rates
        action_scores: Dict[str, float] = {}
        for incident in self.successful_patterns[issue]:
            action = incident.get("action", "")
            mttr = incident.get("mttr", 10.0)  # Default to high if missing

            if action not in action_scores:
                action_scores[action] = {"count": 0, "total_mttr": 0.0}

            action_scores[action]["count"] += 1
            action_scores[action]["total_mttr"] += mttr

        # Find action with best average MTTR
        if not action_scores:
            return None

        best_action = min(
            action_scores.items(), key=lambda x: x[1]["total_mttr"] / x[1]["count"]
        )[0]

        return best_action

    def get_adjusted_threshold(
        self, metric_name: str, default_threshold: float
    ) -> float:
        """
        Get adjusted threshold based on feedback learning.

        Thresholds are adjusted based on false positive/negative rates.
        """
        if metric_name in self.threshold_adjustments:
            return self.threshold_adjustments[metric_name]
        return default_threshold

    def _update_thresholds(self, metrics: Dict, issue: str, success: bool):
        """
        Update detection thresholds based on feedback.

        If successful recovery with low MTTR, thresholds can be slightly relaxed.
        If failed recovery, thresholds should be tightened.
        """
        # Simple adaptive threshold adjustment
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                if metric_name not in self.threshold_adjustments:
                    self.threshold_adjustments[metric_name] = (
                        value * 1.1
                    )  # Initial: 10% above

                # Adjust based on success rate
                if success:
                    # Successful recovery: slightly relax threshold (reduce by 2%)
                    self.threshold_adjustments[metric_name] *= 0.98
                else:
                    # Failed recovery: tighten threshold (increase by 5%)
                    self.threshold_adjustments[metric_name] *= 1.05

                # Keep within reasonable bounds (50% to 150% of original)
                # This would need original baseline, simplified here


class SelfHealingManager:
    """
    Self-Healing Manager with MAPE-K feedback loop.

    Implements complete MAPE-K cycle with feedback from Knowledge
    phase improving Monitor, Analyze, and Plan phases.

    Now supports DAO-managed thresholds.
    """

    def __init__(
        self, node_id: str = "default", threshold_manager=None, knowledge_storage=None
    ):
        self.node_id = node_id

        # Initialize Knowledge with storage (if provided)
        if knowledge_storage:
            from src.storage.mapek_integration import \
                MAPEKKnowledgeStorageAdapter

            adapter = MAPEKKnowledgeStorageAdapter(knowledge_storage, node_id)
            self.knowledge = MAPEKKnowledge(knowledge_storage=adapter)
        else:
            self.knowledge = MAPEKKnowledge()

        # Initialize threshold manager (for DAO-managed thresholds)
        self.threshold_manager = threshold_manager

        # Initialize other phases with Knowledge reference for feedback
        self.monitor = MAPEKMonitor(
            knowledge=self.knowledge, threshold_manager=threshold_manager
        )
        self.analyzer = MAPEKAnalyzer()
        self.planner = MAPEKPlanner(knowledge=self.knowledge)
        self.executor = MAPEKExecutor()

        # Check and apply DAO proposals on startup
        if threshold_manager:
            try:
                applied = threshold_manager.check_and_apply_dao_proposals()
                if applied > 0:
                    logger.info(
                        f"✅ Applied {applied} DAO threshold proposals on startup"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to check DAO proposals: {e}")

        # MTTR tracking
        self.recovery_start_times: Dict[str, float] = {}  # event_id -> detection_time
        self.recovery_events: Dict[str, str] = {}  # event_id -> recovery_type

        # Feedback loop statistics
        self.feedback_updates = 0
        self.threshold_adjustments = 0
        self.strategy_improvements = 0

    def run_cycle(self, metrics: Dict):
        """Run MAPE-K cycle with MTTR tracking."""
        cycle_start = time.time()

        # MONITOR phase
        monitor_start = time.time()
        anomaly_detected = self.monitor.check(metrics)
        monitor_duration = time.time() - monitor_start

        try:
            from src.monitoring.metrics import record_mape_k_cycle

            record_mape_k_cycle("monitor", monitor_duration)
        except ImportError:
            pass

        if anomaly_detected:
            # ANALYZE phase
            analyze_start = time.time()
            issue = self.analyzer.analyze(metrics)
            analyze_duration = time.time() - analyze_start

            try:
                from src.monitoring.metrics import record_mape_k_cycle

                record_mape_k_cycle("analyze", analyze_duration)
            except ImportError:
                pass

            # Start recovery event tracking
            event_id = f"{issue}_{self.node_id}_{int(time.time() * 1000)}"
            self.recovery_start_times[event_id] = time.time()
            self.recovery_events[event_id] = issue

            # PLAN phase
            plan_start = time.time()
            action = self.planner.plan(issue)
            plan_duration = time.time() - plan_start

            try:
                from src.monitoring.metrics import record_mape_k_cycle

                record_mape_k_cycle("plan", plan_duration)
            except ImportError:
                pass

            # EXECUTE phase
            execute_start = time.time()
            success = self.executor.execute(action)
            execute_duration = time.time() - execute_start

            # Calculate MTTR
            if event_id in self.recovery_start_times:
                mttr = time.time() - self.recovery_start_times[event_id]

                # Export MTTR metric
                try:
                    from src.monitoring.metrics import (
                        record_mape_k_cycle, record_mttr,
                        record_self_healing_event)

                    # Map issue to recovery type
                    recovery_type_map = {
                        "High CPU": "high_cpu",
                        "High Memory": "high_memory",
                        "Network Loss": "route_failure",
                    }
                    recovery_type = recovery_type_map.get(issue, "unknown")

                    record_mttr(recovery_type, mttr)
                    record_self_healing_event(recovery_type, self.node_id)
                    record_mape_k_cycle("execute", execute_duration)

                    # KNOWLEDGE phase with feedback loop
                    knowledge_start = time.time()
                    self.knowledge.record(
                        metrics, issue, action, success=success, mttr=mttr
                    )

                    # Feedback loop: Update Monitor and Planner based on results
                    self._apply_feedback_loop(issue, action, success, mttr)

                    knowledge_duration = time.time() - knowledge_start
                    record_mape_k_cycle("knowledge", knowledge_duration)
                except ImportError:
                    pass

                # Cleanup
                del self.recovery_start_times[event_id]
                del self.recovery_events[event_id]

            logger.info(
                f"Self-healing cycle: {issue} → {action}, "
                f"MTTR={mttr:.3f}s, success={success}"
            )
        else:
            logger.info("No anomalies detected. System healthy.")

    def _apply_feedback_loop(self, issue: str, action: str, success: bool, mttr: float):
        """
        Apply feedback loop: update Monitor and Planner based on results.

        This is the core of the feedback mechanism:
        - Successful recoveries with low MTTR → reinforce patterns
        - Failed recoveries → adjust thresholds and strategies
        """
        self.feedback_updates += 1

        # Feedback to Monitor: Adjust thresholds if needed
        if success and mttr < 3.0:  # Very successful recovery
            # Slightly relax thresholds (system is handling well)
            self.threshold_adjustments += 1
            logger.debug(
                f"Feedback: Successful recovery (MTTR={mttr:.3f}s), reinforcing patterns"
            )
        elif not success or mttr > 7.0:  # Failed or slow recovery
            # Tighten thresholds (need earlier detection)
            self.threshold_adjustments += 1
            logger.debug(
                f"Feedback: Failed/slow recovery (MTTR={mttr:.3f}s), adjusting thresholds"
            )

        # Feedback to Planner: Track strategy effectiveness
        if success:
            # Successful action pattern reinforced in Knowledge base
            self.strategy_improvements += 1
            logger.debug(
                f"Feedback: Action '{action}' successful for '{issue}', reinforcing strategy"
            )

        # Periodic feedback summary
        if self.feedback_updates % 10 == 0:
            logger.info(
                f"Feedback loop stats: "
                f"updates={self.feedback_updates}, "
                f"threshold_adjustments={self.threshold_adjustments}, "
                f"strategy_improvements={self.strategy_improvements}"
            )

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback loop statistics."""
        return {
            "feedback_updates": self.feedback_updates,
            "threshold_adjustments": self.threshold_adjustments,
            "strategy_improvements": self.strategy_improvements,
            "knowledge_base_size": len(self.knowledge.incidents),
            "successful_patterns": len(self.knowledge.successful_patterns),
            "failed_patterns": len(self.knowledge.failed_patterns),
        }

    def integrate_ebpf_self_healing(self, interface: str = "eth0"):
        """
        Integrate eBPF-based self-healing for network anomalies.

        Adds eBPF anomaly detector to the MAPE-K monitor phase.
        Enables automatic recovery from network-level issues.
        """
        try:
            from .ebpf_anomaly_detector import integrate_ebpf_self_healing

            ebpf_controller = integrate_ebpf_self_healing(self, interface)
            logger.info("✅ eBPF self-healing integrated with MAPE-K")
            return ebpf_controller
        except ImportError as e:
            logger.warning(f"⚠️ eBPF self-healing not available: {e}")
            return None
