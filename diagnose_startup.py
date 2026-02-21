
import asyncio
import logging
import time
import os

# Mock settings to avoid env dependency
os.environ["DATABASE_URL"] = "sqlite:///./x0tta6bl4.db"
os.environ["MAAS_LIGHT_MODE"] = "false"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("diagnose")

async def run_diagnostics():
    from src.core.production_lifespan import optimization_engine
    
    start_total = time.time()
    
    logger.info("Starting OptimizationEngine.startup()...")
    try:
        # We wrap the startup in a timeout to catch specific hangs
        await asyncio.wait_for(optimization_engine.startup(), timeout=60)
        logger.info(f"OptimizationEngine.startup() finished in {time.time() - start_total:.2f}s")
    except asyncio.TimeoutError:
        logger.error("OptimizationEngine.startup() TIMED OUT after 60s")
    except Exception as e:
        logger.error(f"OptimizationEngine.startup() FAILED: {e}", exc_info=True)
    
    # Check components
    if optimization_engine.parl_controller:
        logger.info(f"PARL Controller: OK ({len(optimization_engine.parl_controller.workers)} workers)")
    
    if optimization_engine.fl_integration:
        logger.info("FL Integration: OK")
        
    if optimization_engine.mape_k_loop:
        logger.info("MAPE-K Loop: OK")

    logger.info("Shutting down...")
    await optimization_engine.shutdown()
    logger.info("Diagnostics complete.")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
