import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from src.core.consciousness import ConsciousnessEngine
from src.core.mape_k_loop import MAPEKLoop
from src.core.settings import settings
from src.database import ensure_schema_compatible
from src.federated_learning.app_integration import create_fl_integration
from src.mesh.network_manager import MeshNetworkManager
from src.monitoring.prometheus_client import PrometheusExporter
from src.security.zero_trust import ZeroTrustValidator
from src.swarm.parl.controller import PARLController

# Import Edge Computing and Event Sourcing startup/shutdown hooks
try:
    from src.edge.api import edge_startup, edge_shutdown
    EDGE_MODULE_AVAILABLE = True
except ImportError:
    EDGE_MODULE_AVAILABLE = False
    edge_startup = None
    edge_shutdown = None

try:
    from src.event_sourcing.api import event_sourcing_startup, event_sourcing_shutdown
    EVENT_SOURCING_MODULE_AVAILABLE = True
except ImportError:
    EVENT_SOURCING_MODULE_AVAILABLE = False
    event_sourcing_startup = None
    event_sourcing_shutdown = None

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """
    Manages the lifecycle of intelligent background components:
    - MAPE-K Loop (Self-Healing)
    - Swarm (PARL)
    - Consciousness
    - Federated Learning
    """

    def __init__(self):
        self.mape_k_loop: Optional[MAPEKLoop] = None
        self.parl_controller: Optional[PARLController] = None
        self.fl_integration = None
        self.loop_task: Optional[asyncio.Task] = None
        self.network_manager: Optional[MeshNetworkManager] = None

    async def startup(self):
        logger.info("🚀 Initializing Production Intelligence Engine...")

        try:
            testing_mode = (
                settings.is_testing()
                or os.getenv("TESTING", "false").lower() == "true"
                or bool(os.getenv("PYTEST_CURRENT_TEST"))
            )
            enforce_schema = os.getenv("DB_ENFORCE_SCHEMA", "true").lower() == "true"
            auto_default = "true" if settings.is_production() else "false"
            auto_migrate = (
                os.getenv("DB_AUTO_MIGRATE", auto_default).lower() == "true"
            )
            if enforce_schema and not testing_mode:
                ensure_schema_compatible(auto_migrate=auto_migrate)
                logger.info("✅ Database schema validation passed")

            # 1. Initialize Core Components
            self.network_manager = MeshNetworkManager()
            # Note: In a real deployment, we might need to wait for Yggdrasil to be ready
            # or simply let the manager handle retries.

            prometheus = PrometheusExporter()
            zero_trust = ZeroTrustValidator()

            # 2. Initialize Consciousness
            logger.info("🔮 Awakening Consciousness...")
            consciousness = ConsciousnessEngine(enable_advanced_metrics=True)

            # 3. Initialize Swarm (PARL)
            logger.info("🐝 Initializing Swarm Intelligence (PARL)...")
            self.parl_controller = PARLController(max_workers=5, max_parallel_steps=50)
            await self.parl_controller.initialize()

            # 4. Initialize Federated Learning
            logger.info("🧠 Initializing Federated Learning...")
            node_id = settings.node_id
            self.fl_integration = create_fl_integration(node_id=node_id, enable_fl=True)
            await self.fl_integration.startup()

            # 5. Initialize MAPE-K Loop
            logger.info("🌀 Configuring MAPE-K Autonomic Loop...")
            self.mape_k_loop = MAPEKLoop(
                consciousness_engine=consciousness,
                mesh_manager=self.network_manager,
                prometheus=prometheus,
                zero_trust=zero_trust,
                parl_controller=self.parl_controller,
                fl_integration=self.fl_integration,
            )

            # 6. Start the Loop
            self.loop_task = asyncio.create_task(
                self.mape_k_loop.start(fl_integration=True)
            )
            logger.info("✅ MAPE-K Loop started in background")

            # 7. Initialize Edge Computing Module
            if EDGE_MODULE_AVAILABLE and edge_startup:
                logger.info("🌐 Initializing Edge Computing Module...")
                try:
                    await edge_startup()
                    logger.info("✅ Edge Computing Module initialized")
                except Exception as e:
                    logger.warning(f"⚠️ Edge Computing Module initialization failed: {e}")

            # 8. Initialize Event Sourcing Module
            if EVENT_SOURCING_MODULE_AVAILABLE and event_sourcing_startup:
                logger.info("📦 Initializing Event Sourcing Module...")
                try:
                    await event_sourcing_startup()
                    logger.info("✅ Event Sourcing Module initialized")
                except Exception as e:
                    logger.warning(f"⚠️ Event Sourcing Module initialization failed: {e}")

        except Exception as e:
            logger.error(f"❌ Failed to start Intelligence Engine: {e}", exc_info=True)
            # We don't raise here to allow the API to start even if intelligence fails
            # (Zombie mode is better than Dead mode)

    async def shutdown(self):
        logger.info("🔻 Shutting down Intelligence Engine...")

        # Shutdown Event Sourcing Module first (may have pending writes)
        if EVENT_SOURCING_MODULE_AVAILABLE and event_sourcing_shutdown:
            logger.info("📦 Shutting down Event Sourcing Module...")
            try:
                await event_sourcing_shutdown()
                logger.info("✅ Event Sourcing Module shut down")
            except Exception as e:
                logger.warning(f"⚠️ Event Sourcing shutdown error: {e}")

        # Shutdown Edge Computing Module
        if EDGE_MODULE_AVAILABLE and edge_shutdown:
            logger.info("🌐 Shutting down Edge Computing Module...")
            try:
                await edge_shutdown()
                logger.info("✅ Edge Computing Module shut down")
            except Exception as e:
                logger.warning(f"⚠️ Edge Computing shutdown error: {e}")

        if self.mape_k_loop:
            await self.mape_k_loop.stop()

        if self.loop_task:
            self.loop_task.cancel()
            try:
                await self.loop_task
            except asyncio.CancelledError:
                pass

        if self.parl_controller:
            await self.parl_controller.terminate()

        if self.fl_integration:
            await self.fl_integration.shutdown()

        logger.info("✅ Intelligence Engine shutdown complete")


# Global instance
optimization_engine = OptimizationEngine()


@asynccontextmanager
async def production_lifespan(app: FastAPI):
    # Startup
    await optimization_engine.startup()

    yield

    # Shutdown
    await optimization_engine.shutdown()
