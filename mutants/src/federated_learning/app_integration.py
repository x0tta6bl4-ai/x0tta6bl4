"""
Federated Learning Integration with Main Application.

Integrates FL components into app.py startup and lifecycle.
"""
import logging
from typing import Optional, Dict, Any

try:
    from src.federated_learning.graphsage_integration import (
        GraphSAGEFLCoordinator,
        GraphSAGEFLConfig
    )
    from src.federated_learning.secure_aggregators import get_secure_aggregator
    from src.federated_learning.model_sync import ModelSynchronizer
    from src.federated_learning.privacy import DPConfig
    FL_AVAILABLE = True
except ImportError:
    FL_AVAILABLE = False
    GraphSAGEFLCoordinator = None
    GraphSAGEFLConfig = None

logger = logging.getLogger(__name__)


class FLAppIntegration:
    """
    Federated Learning integration for main application.
    
    Manages FL coordinator lifecycle and integration with app.py.
    """
    
    def __init__(
        self,
        node_id: str,
        enable_fl: bool = True,
        fl_config: Optional[Dict[str, Any]] = None
    ):
        self.node_id = node_id
        self.enable_fl = enable_fl and FL_AVAILABLE
        self.fl_config = fl_config or {}
        self.coordinator: Optional[GraphSAGEFLCoordinator] = None
        self.model_sync: Optional[ModelSynchronizer] = None
        
        if self.enable_fl:
            self._initialize_fl()
    
    def _initialize_fl(self) -> None:
        """Initialize Federated Learning components."""
        if not FL_AVAILABLE:
            logger.warning("Federated Learning not available")
            return
        
        try:
            # Create FL config
            config = GraphSAGEFLConfig(
                enable_privacy=self.fl_config.get("enable_privacy", True),
                enable_byzantine_robust=self.fl_config.get("enable_byzantine_robust", True),
                aggregation_method=self.fl_config.get("aggregation_method", "secure_fedavg"),
                sync_interval=self.fl_config.get("sync_interval", 1),
                model_versioning=self.fl_config.get("model_versioning", True)
            )
            
            # Create coordinator
            self.coordinator = GraphSAGEFLCoordinator(
                node_id=self.node_id,
                fl_config=config
            )
            
            # Create model synchronizer if versioning enabled
            if config.model_versioning:
                self.model_sync = ModelSynchronizer(node_id=self.node_id)
            
            logger.info(f"✅ Federated Learning initialized for node {self.node_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Federated Learning: {e}")
            self.coordinator = None
            self.model_sync = None
    
    async def startup(self) -> None:
        """Startup FL components."""
        if not self.enable_fl or not self.coordinator:
            return
        
        try:
            logger.info("Starting Federated Learning coordinator...")
            # Coordinator is ready after initialization
            logger.info("✅ Federated Learning coordinator started")
        except Exception as e:
            logger.error(f"Failed to start FL coordinator: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown FL components."""
        if not self.enable_fl or not self.coordinator:
            return
        
        try:
            logger.info("Shutting down Federated Learning coordinator...")
            # Cleanup if needed
            logger.info("✅ Federated Learning coordinator shut down")
        except Exception as e:
            logger.error(f"Failed to shutdown FL coordinator: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get FL integration status."""
        if not self.enable_fl:
            return {"enabled": False}
        
        status = {
            "enabled": True,
            "coordinator_available": self.coordinator is not None,
            "model_sync_available": self.model_sync is not None
        }
        
        if self.model_sync:
            status.update(self.model_sync.get_sync_status())
        
        return status


def create_fl_integration(
    node_id: str,
    enable_fl: bool = True,
    **kwargs
) -> FLAppIntegration:
    """
    Factory function to create FL integration.
    
    Args:
        node_id: Node identifier
        enable_fl: Enable Federated Learning
        **kwargs: Additional FL configuration
        
    Returns:
        FLAppIntegration instance
    """
    return FLAppIntegration(
        node_id=node_id,
        enable_fl=enable_fl,
        fl_config=kwargs
    )

