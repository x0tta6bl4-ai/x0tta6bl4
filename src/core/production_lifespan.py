import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

# from src.core.consciousness import ConsciousnessEngine # Purged in Honest Mode
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


def _env_true(name: str, default: bool = False) -> bool:
    """Parse boolean env var consistently."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _validate_enterprise_guardrails(testing_mode: bool) -> bool:
    """
    Validate production guardrails.

    Returns:
        True when running in production mode, else False.

    Raises:
        RuntimeError: if production guardrails are violated.
    """
    production_mode = settings.is_production() or _env_true("X0TTA6BL4_PRODUCTION", False)
    if testing_mode or not production_mode:
        return production_mode

    violations: list[str] = []
    security_flags = settings.security_profile()

    if _env_true("MAAS_LIGHT_MODE", False):
        violations.append("MAAS_LIGHT_MODE must be false in production")
    if not security_flags["mtls_enabled"]:
        violations.append("MTLS_ENABLED must be true in production")
    if not security_flags["rate_limit_enabled"]:
        violations.append("RATE_LIMIT_ENABLED must be true in production")
    if not security_flags["request_validation_enabled"]:
        violations.append("REQUEST_VALIDATION_ENABLED must be true in production")
    if _env_true("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY", False):
        violations.append("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY must be false in production")
    if os.getenv("DB_ENFORCE_SCHEMA") is None:
        violations.append("DB_ENFORCE_SCHEMA must be explicitly set (DB_ENFORCE_SCHEMA=true) in production")
    elif not _env_true("DB_ENFORCE_SCHEMA", True):
        violations.append("DB_ENFORCE_SCHEMA must be true in production")

    if violations:
        details = "\n".join(f"- {item}" for item in violations)
        raise RuntimeError(f"Production guardrails violated:\n{details}")

    return production_mode


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

        # Determine production mode early to prevent fail-open bypass if guardrails fail
        production_mode = settings.is_production() or _env_true("X0TTA6BL4_PRODUCTION", False)

        try:
            testing_mode = (
                settings.is_testing()
                or os.getenv("TESTING", "false").lower() == "true"
                or bool(os.getenv("PYTEST_CURRENT_TEST"))
            )
            # Re-validate and enforce guardrails
            _validate_enterprise_guardrails(testing_mode)

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

            # Initialize Native eBPF Exporter
            try:
                from src.monitoring.ebpf_native_exporter import get_native_exporter
                native_ebpf = get_native_exporter()
                native_ebpf.start()
                logger.info("✅ Native eBPF Exporter started")
            except Exception as e:
                logger.warning(f"⚠️ Native eBPF Exporter failed to start: {e}")

            prometheus = PrometheusExporter()
            zero_trust = ZeroTrustValidator()

            # 2. Initialize Consciousness (Purged in Honest Mode)
            # logger.info("🔮 Awakening Consciousness...")
            # consciousness = ConsciousnessEngine(enable_advanced_metrics=True)
            consciousness = None

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
            try:
                logger.info("🌀 Configuring MAPE-K Autonomic Loop...")

                # TD-008: Initialize modular self-healing manager
                from src.self_healing.mape_k.manager import SelfHealingManager
                self_healing = SelfHealingManager(
                    node_id=settings.node_id,
                    event_project_root=".",
                )

                self.mape_k_loop = MAPEKLoop(
                    consciousness_engine=consciousness,
                    mesh_manager=self.network_manager,
                    prometheus=prometheus,
                    zero_trust=zero_trust,
                    parl_controller=self.parl_controller,
                    fl_integration=self.fl_integration,
                    self_healing_manager=self_healing,
                )

                # 6. Start the Loop
                self.loop_task = asyncio.create_task(
                    self.mape_k_loop.start(fl_integration=True)
                )
                logger.info("✅ MAPE-K Loop started in background")
            except Exception as e:
                logger.warning(f"⚠️ MAPE-K Loop failed to start: {e}. System will run without self-healing.")

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
            fail_open_default = not production_mode
            fail_open = _env_true("X0TTA6BL4_FAIL_OPEN_STARTUP", fail_open_default)

            # Hard-block fail-open if production guardrails are violated
            if "Production guardrails violated" in str(e):
                logger.critical("🛑 CRITICAL: Production guardrails violated. Fail-open DISALLOWED.")
                fail_open = False

            if fail_open:
                logger.warning(
                    "⚠️ Startup fail-open enabled (X0TTA6BL4_FAIL_OPEN_STARTUP=true). "
                    "Continuing in degraded mode."
                )
                return
            raise

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
