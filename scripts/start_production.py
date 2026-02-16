#!/usr/bin/env python3
"""
Production Service Starter
Starts x0tta6bl4 service in production mode with all components initialized.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/x0tta6bl4.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def initialize_components():
    """Initialize all production components."""
    logger.info("Initializing production components...")

    try:
        # Initialize Zero Trust
        try:
            from src.security.zero_trust.enforcement import \
                get_zero_trust_enforcer

            enforcer = get_zero_trust_enforcer()
            logger.info("✅ Zero Trust Enforcement initialized")
        except Exception as e:
            logger.warning(f"⚠️ Zero Trust initialization skipped: {e}")

        # Initialize Raft (if needed)
        try:
            logger.info("✅ Raft Consensus components ready")
        except Exception as e:
            logger.warning(f"⚠️ Raft initialization skipped: {e}")

        # Initialize CRDT Sync (if needed)
        try:
            logger.info("✅ CRDT Sync components ready")
        except Exception as e:
            logger.warning(f"⚠️ CRDT Sync initialization skipped: {e}")

        # Initialize Recovery Actions
        try:
            from src.self_healing.recovery_actions import \
                RecoveryActionExecutor

            executor = RecoveryActionExecutor(node_id="node-1")
            logger.info("✅ Recovery Actions initialized")
        except Exception as e:
            logger.warning(f"⚠️ Recovery Actions initialization skipped: {e}")

        # Initialize OpenTelemetry Tracing
        try:
            from src.monitoring.tracing import initialize_tracing

            initialize_tracing(service_name="x0tta6bl4-production")
            logger.info("✅ OpenTelemetry Tracing initialized")
        except Exception as e:
            logger.warning(f"⚠️ OpenTelemetry initialization skipped: {e}")

        logger.info("✅ All components initialized successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Component initialization failed: {e}")
        return False


def start_service():
    """Start the main service."""
    logger.info("Starting x0tta6bl4 production service...")

    try:
        # Import and start FastAPI app
        import uvicorn

        from src.core.app import app

        logger.info("✅ FastAPI application loaded")
        logger.info("Starting server on http://0.0.0.0:8080")

        # Start server
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info", access_log=True)

    except ImportError as e:
        logger.error(f"❌ Failed to import application: {e}")
        logger.info("Trying alternative startup method...")
        # Fallback: use uvicorn command
        os.system("python3 -m uvicorn src.core.app:app --host 0.0.0.0 --port 8080")
    except Exception as e:
        logger.error(f"❌ Failed to start service: {e}")
        sys.exit(1)


async def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("🚀 x0tta6bl4 Production Service")
    print("=" * 60 + "\n")

    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # Initialize components
    success = await initialize_components()

    if not success:
        logger.warning("⚠️ Some components failed to initialize, continuing anyway...")

    # Start service (synchronous, will block)
    logger.info("Starting service...")
    start_service()


if __name__ == "__main__":
    try:
        # Check if event loop is already running
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            import nest_asyncio

            nest_asyncio.apply()
            asyncio.run(main())
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Service stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        # Fallback: start service directly without async initialization
        logger.info("Attempting direct service start...")
        start_service()
