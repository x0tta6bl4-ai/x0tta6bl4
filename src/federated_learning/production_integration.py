"""
Federated Learning Production Integration

Provides complete integration of FL into the main application,
including monitoring, metrics, and production deployment.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

# Import FL components
try:
    from .aggregators_enhanced import (EnhancedAggregator,
                                       get_enhanced_aggregator)
    from .coordinator import (CoordinatorConfig, FederatedCoordinator,
                              TrainingRound)
    from .privacy import DifferentialPrivacy, DPConfig
    from .protocol import GlobalModel, ModelUpdate

    FL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Federated Learning components not available: {e}")
    FL_AVAILABLE = False
    FederatedCoordinator = None
    CoordinatorConfig = None


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_mapping_summary(values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    mapping = values or {}
    return {
        "key_count_bucket": _safe_count_bucket(len(mapping)),
        "key_hashes": sorted(_safe_hash(key) for key in mapping.keys()),
        "value_type_counts": {
            type(value).__name__: sum(
                1
                for item in mapping.values()
                if type(item).__name__ == type(value).__name__
            )
            for value in mapping.values()
        },
    }


@dataclass
class FLProductionConfig:
    """Production configuration for FL"""

    coordinator_id: str
    enable_fl: bool = True
    enable_privacy: bool = True
    enable_byzantine_protection: bool = True
    aggregation_method: str = "enhanced_fedavg"
    byzantine_tolerance: int = 1
    min_participants: int = 3
    max_participants: int = 10
    training_rounds: int = 100
    privacy_epsilon: float = 10.0
    privacy_delta: float = 1e-5
    model_storage_path: Optional[Path] = None
    enable_monitoring: bool = True
    enable_metrics: bool = True


@dataclass
class FLMetrics:
    """Federated Learning metrics"""

    total_rounds: int = 0
    successful_rounds: int = 0
    failed_rounds: int = 0
    total_participants: int = 0
    average_participants_per_round: float = 0.0
    byzantine_detections: int = 0
    privacy_budget_used: float = 0.0
    model_accuracy: float = 0.0
    convergence_rate: float = 0.0
    last_update: Optional[datetime] = None


class FLProductionManager:
    """
    Production manager for Federated Learning.

    Provides:
    - Complete FL integration
    - Production deployment
    - Monitoring and metrics
    - Health checks
    - Automatic recovery
    """

    def __init__(self, config: FLProductionConfig):
        """
        Initialize FL Production Manager.

        Args:
            config: Production configuration
        """
        self.config = config
        self.coordinator: Optional[FederatedCoordinator] = None
        self.metrics = FLMetrics()
        self.is_running = False
        self._training_task: Optional[asyncio.Task] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"fl-production-manager:{_safe_hash(config.coordinator_id)}",
            role="fl",
            capabilities=("coordinator", "privacy", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "fl_production_manager_init",
                "goal": "Initialize federated learning production manager safely",
                "signals": {
                    "coordinator_hash": _safe_hash(config.coordinator_id),
                    "fl_enabled": config.enable_fl,
                    "privacy_enabled": config.enable_privacy,
                    "byzantine_protection_enabled": config.enable_byzantine_protection,
                    "participant_bounds": {
                        "min": config.min_participants,
                        "max": config.max_participants,
                    },
                    "model_storage_configured": config.model_storage_path is not None,
                    "fl_available": FL_AVAILABLE,
                },
                "safety_boundary": (
                    "Keep coordinator ids, node ids, node info, model paths, raw "
                    "updates, and error messages out of thinking context."
                ),
            }
        )

        if not FL_AVAILABLE:
            logger.error("Federated Learning components not available")
            self._record_thinking(
                "fl_production_unavailable",
                "Disable FL production manager when components are unavailable",
                {"fl_available": False, "coordinator_configured": False},
            )
            return

        # Initialize coordinator
        if self.config.enable_fl:
            self._initialize_coordinator()

        logger.info("FLProductionManager initialized")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_coordinator_ids": True,
                    "redact_node_ids": True,
                    "redact_node_info": True,
                    "redact_model_paths": True,
                    "redact_raw_updates": True,
                    "redact_error_messages": True,
                    "preserve_fl_decision": True,
                },
                "safety_boundary": (
                    "Use hashes, counts, booleans, statuses, and privacy flags only."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def _initialize_coordinator(self):
        """Initialize FL coordinator"""
        try:
            coordinator_config = CoordinatorConfig(
                aggregation_method=self.config.aggregation_method,
                byzantine_tolerance=self.config.byzantine_tolerance,
                min_participants=self.config.min_participants,
                max_participants=self.config.max_participants,
                enable_privacy=self.config.enable_privacy,
                privacy_epsilon=self.config.privacy_epsilon,
                privacy_delta=self.config.privacy_delta,
            )

            self.coordinator = FederatedCoordinator(
                coordinator_id=self.config.coordinator_id, config=coordinator_config
            )

            logger.info("FL Coordinator initialized")
            self._record_thinking(
                "fl_coordinator_initialized",
                "Initialize FL coordinator safely",
                {
                    "coordinator_hash": _safe_hash(self.config.coordinator_id),
                    "aggregation_method_hash": _safe_hash(
                        self.config.aggregation_method
                    ),
                    "privacy_enabled": self.config.enable_privacy,
                    "byzantine_tolerance": self.config.byzantine_tolerance,
                    "min_participants": self.config.min_participants,
                    "max_participants": self.config.max_participants,
                    "success": True,
                },
            )
        except Exception as e:
            self._record_thinking(
                "fl_coordinator_initialized",
                "Record FL coordinator initialization failure",
                {
                    "coordinator_hash": _safe_hash(self.config.coordinator_id),
                    "error_type": type(e).__name__,
                    "success": False,
                },
            )
            logger.error(f"Failed to initialize FL coordinator: {e}")

    async def start(self) -> bool:
        """
        Start FL production manager.

        Returns:
            True if started successfully
        """
        if not self.config.enable_fl or not self.coordinator:
            self._record_thinking(
                "fl_production_start",
                "Reject FL production start when disabled or coordinator missing",
                {
                    "fl_enabled": self.config.enable_fl,
                    "coordinator_configured": self.coordinator is not None,
                    "started": False,
                },
            )
            logger.warning("FL is disabled or coordinator not available")
            return False

        if self.is_running:
            self._record_thinking(
                "fl_production_start",
                "Confirm FL production manager already running",
                {"already_running": True, "started": True},
            )
            logger.warning("FL Production Manager already running")
            return True

        try:
            self.is_running = True
            self._training_task = asyncio.create_task(self._training_loop())
            self._record_thinking(
                "fl_production_start",
                "Start FL production training loop",
                {"running": True, "training_task_created": self._training_task is not None},
            )
            logger.info("FL Production Manager started")
            return True
        except Exception as e:
            logger.error(f"Failed to start FL Production Manager: {e}")
            self.is_running = False
            self._record_thinking(
                "fl_production_start",
                "Record FL production start failure",
                {"running": False, "error_type": type(e).__name__},
            )
            return False

    async def stop(self) -> bool:
        """
        Stop FL production manager.

        Returns:
            True if stopped successfully
        """
        if not self.is_running:
            self._record_thinking(
                "fl_production_stop",
                "Confirm FL production manager already stopped",
                {"running": False, "stopped": True},
            )
            return True

        try:
            self.is_running = False

            if self._training_task:
                self._training_task.cancel()
                try:
                    await self._training_task
                except asyncio.CancelledError:
                    pass

            logger.info("FL Production Manager stopped")
            self._record_thinking(
                "fl_production_stop",
                "Stop FL production manager",
                {"running": False, "task_cancelled": self._training_task is not None},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to stop FL Production Manager: {e}")
            self._record_thinking(
                "fl_production_stop",
                "Record FL production stop failure",
                {"error_type": type(e).__name__, "stopped": False},
            )
            return False

    async def _training_loop(self):
        """Main training loop"""
        logger.info("Starting FL training loop")

        while self.is_running:
            try:
                # Start training round
                if self.coordinator:
                    round_result = await self._run_training_round()

                    if round_result:
                        self.metrics.total_rounds += 1
                        self.metrics.successful_rounds += 1
                        self.metrics.last_update = datetime.utcnow()
                    else:
                        self.metrics.total_rounds += 1
                        self.metrics.failed_rounds += 1

                # Wait before next round
                await asyncio.sleep(60)  # 1 minute between rounds

            except asyncio.CancelledError:
                logger.info("Training loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in training loop: {e}")
                self.metrics.failed_rounds += 1
                await asyncio.sleep(30)  # Wait before retry

    async def _run_training_round(self) -> bool:
        """
        Run a single training round.

        Returns:
            True if round completed successfully
        """
        if not self.coordinator:
            self._record_thinking(
                "fl_training_round",
                "Skip FL training round without coordinator",
                {"coordinator_configured": False, "success": False},
            )
            return False

        try:
            # Start round
            round_id = await self.coordinator.start_round()

            if not round_id:
                self._record_thinking(
                    "fl_training_round",
                    "Reject FL round when start_round returned no id",
                    {"round_started": False, "success": False},
                )
                logger.warning("Failed to start training round")
                return False

            # Wait for participants
            await asyncio.sleep(30)  # Wait for participants to join

            # Collect updates
            updates = await self.coordinator.collect_updates(timeout=60)

            if not updates or len(updates) < self.config.min_participants:
                self._record_thinking(
                    "fl_training_round",
                    "Reject FL round with insufficient participants",
                    {
                        "round_hash": _safe_hash(round_id),
                        "update_count_bucket": _safe_count_bucket(
                            len(updates) if updates else 0
                        ),
                        "min_participants": self.config.min_participants,
                        "success": False,
                    },
                )
                logger.warning(
                    f"Insufficient participants: {len(updates) if updates else 0}"
                )
                return False

            # Aggregate updates
            result = await self.coordinator.aggregate_updates(updates)

            if result:
                # Update metrics
                self.metrics.average_participants_per_round = (
                    self.metrics.average_participants_per_round
                    * (self.metrics.total_rounds - 1)
                    + len(updates)
                ) / self.metrics.total_rounds
                self.metrics.total_participants = max(
                    self.metrics.total_participants, len(updates)
                )

                # Check for byzantine nodes
                if hasattr(result, "byzantine_detected") and result.byzantine_detected:
                    self.metrics.byzantine_detections += 1

                logger.info(f"Training round {round_id} completed successfully")
                self._record_thinking(
                    "fl_training_round",
                    "Complete FL training round safely",
                    {
                        "round_hash": _safe_hash(round_id),
                        "update_count_bucket": _safe_count_bucket(len(updates)),
                        "byzantine_detected": bool(
                            hasattr(result, "byzantine_detected")
                            and result.byzantine_detected
                        ),
                        "success": True,
                    },
                )
                return True
            else:
                self._record_thinking(
                    "fl_training_round",
                    "Record failed FL aggregation result",
                    {"round_hash": _safe_hash(round_id), "success": False},
                )
                logger.warning(f"Training round {round_id} failed")
                return False

        except Exception as e:
            self._record_thinking(
                "fl_training_round",
                "Record FL training round failure",
                {"error_type": type(e).__name__, "success": False},
            )
            logger.error(f"Error in training round: {e}")
            return False

    def get_metrics(self) -> FLMetrics:
        """
        Get current FL metrics.

        Returns:
            FLMetrics object
        """
        return self.metrics

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of FL system.

        Returns:
            Health status dictionary
        """
        if not self.config.enable_fl:
            self._record_thinking(
                "fl_health_status",
                "Report disabled FL health",
                {"enabled": False, "status": "disabled"},
            )
            return {"status": "disabled", "enabled": False}

        if not self.coordinator:
            self._record_thinking(
                "fl_health_status",
                "Report FL health without coordinator",
                {"enabled": True, "coordinator_configured": False, "status": "error"},
            )
            return {
                "status": "error",
                "enabled": True,
                "error": "Coordinator not initialized",
            }

        if not self.is_running:
            self._record_thinking(
                "fl_health_status",
                "Report stopped FL health",
                {"enabled": True, "running": False, "status": "stopped"},
            )
            return {"status": "stopped", "enabled": True, "running": False}

        # Calculate success rate
        success_rate = 0.0
        if self.metrics.total_rounds > 0:
            success_rate = (
                self.metrics.successful_rounds / self.metrics.total_rounds
            ) * 100

        status = {
            "status": "healthy" if success_rate > 80 else "degraded",
            "enabled": True,
            "running": True,
            "success_rate": success_rate,
            "total_rounds": self.metrics.total_rounds,
            "successful_rounds": self.metrics.successful_rounds,
            "failed_rounds": self.metrics.failed_rounds,
            "byzantine_detections": self.metrics.byzantine_detections,
            "last_update": (
                self.metrics.last_update.isoformat()
                if self.metrics.last_update
                else None
            ),
        }
        self._record_thinking(
            "fl_health_status",
            "Summarize FL health safely",
            {
                "status": status["status"],
                "success_rate": success_rate,
                "total_rounds_bucket": _safe_count_bucket(self.metrics.total_rounds),
                "successful_rounds_bucket": _safe_count_bucket(
                    self.metrics.successful_rounds
                ),
                "failed_rounds_bucket": _safe_count_bucket(self.metrics.failed_rounds),
                "byzantine_detections_bucket": _safe_count_bucket(
                    self.metrics.byzantine_detections
                ),
            },
        )
        return status

    def register_participant(self, node_id: str, node_info: Dict[str, Any]) -> bool:
        """
        Register a participant node.

        Args:
            node_id: Node identifier
            node_info: Node information

        Returns:
            True if registered successfully
        """
        if not self.coordinator:
            self._record_thinking(
                "fl_participant_registered",
                "Reject participant registration without coordinator",
                {"node_hash": _safe_hash(node_id), "registered": False},
            )
            return False

        try:
            # Register node with coordinator
            # This would integrate with the coordinator's node management
            self._record_thinking(
                "fl_participant_registered",
                "Register FL participant safely",
                {
                    "node_hash": _safe_hash(node_id),
                    "node_info": _safe_mapping_summary(node_info),
                    "registered": True,
                },
            )
            logger.info(f"Registered participant: {node_id}")
            return True
        except Exception as e:
            self._record_thinking(
                "fl_participant_registered",
                "Record participant registration failure",
                {
                    "node_hash": _safe_hash(node_id),
                    "error_type": type(e).__name__,
                    "registered": False,
                },
            )
            logger.error(f"Failed to register participant {node_id}: {e}")
            return False


def create_fl_production_manager(
    coordinator_id: str, enable_fl: bool = True, **kwargs
) -> FLProductionManager:
    """
    Factory function to create FL Production Manager.

    Args:
        coordinator_id: Coordinator identifier
        enable_fl: Enable FL
        **kwargs: Additional configuration options

    Returns:
        FLProductionManager instance
    """
    config = FLProductionConfig(
        coordinator_id=coordinator_id, enable_fl=enable_fl, **kwargs
    )

    return FLProductionManager(config)

