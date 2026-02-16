import asyncio
import logging
import os
import signal
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.core.consciousness import ConsciousnessEngine
from src.core.mape_k_loop import MAPEKLoop
from src.swarm.parl.controller import PARLController

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MVP_Launcher")

# Global stop event
stop_event = asyncio.Event()


def signal_handler(sig, frame):
    logger.info("🛑 Received termination signal. Shutting down...")
    stop_event.set()


async def check_vpn_service():
    """Verify Xray VPN service is active."""
    # Check if we are in Docker mode
    if os.environ.get("MVP_MODE") == "docker":
        xray_host = os.environ.get("XRAY_HOST", "xray")
        xray_port = int(os.environ.get("XRAY_PORT", 10808))
        logger.info(
            f"🐳 Running in Docker mode. Checking Xray at {xray_host}:{xray_port}..."
        )
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(xray_host, xray_port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            logger.info("✅ VPN Service (Xray Container): REACHABLE")
            return True
        except (OSError, asyncio.TimeoutError) as e:
            logger.warning(f"⚠️ VPN Service (Xray Container) unreachable: {e}")
            return False

    # Fallback to systemctl for local/VM execution
    try:
        proc = await asyncio.create_subprocess_shell(
            "systemctl is-active xray",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        status = stdout.decode().strip()

        if status == "active":
            logger.info("✅ VPN Service (Xray Systemd): ACTIVE")
            return True
        else:
            logger.warning(f"⚠️ VPN Service (Xray Systemd): {status}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to check Xray service: {e}")
        return False


async def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("🚀 Initializing MVP Commercialization System...")

    # 1. Check VPN Service
    vpn_active = await check_vpn_service()
    if not vpn_active:
        logger.warning(
            "⚠️ VPN service is NOT active. MAPE-K Self-Healing should address this."
        )

    # 2. Initialize Consciousness (with Local LLM)
    logger.info("🔮 awakening Consciousness...")
    consciousness = ConsciousnessEngine(enable_advanced_metrics=True)
    if consciousness.llm and consciousness.llm.is_ready():
        logger.info("🧠 Local LLM is READY.")
    else:
        logger.warning("⚠️ Local LLM not ready (running in fallback mode).")

    # 3. Initialize Swarm (PARL)
    logger.info("🐝 Initializing Swarm Intelligence (PARL)...")
    parl_controller = PARLController(
        max_workers=5, max_parallel_steps=50
    )  # Lightweight for MVP
    await parl_controller.initialize()

    # 4. Initialize Core Mock Dependencies for Loop
    # In a real app, these would be real singletons.
    from unittest.mock import MagicMock

    # Define async mock functions
    async def mock_return_empty(*args, **kwargs):
        return {}

    async def mock_return_true(*args, **kwargs):
        return True

    async def mock_return_zero(*args, **kwargs):
        return 0

    async def mock_return_none(*args, **kwargs):
        return None

    mesh = MagicMock()  # Placeholder for MeshManager
    mesh.get_statistics.side_effect = mock_return_empty
    mesh.set_route_preference.side_effect = mock_return_true
    mesh.trigger_aggressive_healing.side_effect = mock_return_zero
    mesh.trigger_preemptive_checks.side_effect = mock_return_none

    prometheus = MagicMock()  # Placeholder

    zero_trust = MagicMock()  # Placeholder
    zero_trust.get_validation_stats.return_value = {}  # Sync method (standard mock)

    # 5. Start MAPE-K Loop
    logger.info("🌀 Starting MAPE-K Autonomic Loop...")
    mape_k = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        parl_controller=parl_controller,
    )

    # Start loop as a background task
    loop_task = asyncio.create_task(mape_k.start(fl_integration=True))

    logger.info("✅ MVP System FULLY OPERATIONAL. Press Ctrl+C to stop.")

    # 6. Main Event Loop
    try:
        # Wait until stop signal
        await stop_event.wait()
    finally:
        logger.info("🔻 Shutting down MVP System...")
        await mape_k.stop()
        await parl_controller.terminate()
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        logger.info("👋 Goodnight.")


if __name__ == "__main__":
    asyncio.run(main())
