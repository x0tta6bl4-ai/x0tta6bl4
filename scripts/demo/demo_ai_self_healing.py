"""
Demo: AI-Driven Self-Healing for Connection Stability
=====================================================

This script demonstrates how x0tta6bl4 uses Kimi K2.5 LLM to analyze 
real-world proxy errors and plan autonomous recovery actions.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.self_healing.mape_k import MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor, MAPEKKnowledge
from src.swarm.intelligence import KimiK25Integration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AI-Self-Healing-Demo")

# Sample logs provided by user
USER_LOGS = """
2026/02/26 08:08:23.890678 from 127.0.0.1:41902 accepted http://89.125.1.107:628/LiiqMSLWV8cM2MMlFA/panel/api/server/status [socks -> proxy]
+0100 2026-02-26 08:08:25 ERROR [1047902600 1.22s] connection: connection upload closed: read tcp 89.125.1.107:39829: software caused connection abort
2026/02/26 08:08:26.890147 from 127.0.0.1:41902 accepted http://89.125.1.107:628/LiiqMSLWV8cM2MMlFA/panel/api/server/status [socks -> proxy]
+0100 2026-02-26 08:08:28 ERROR [1767172821 1.22s] connection: connection upload closed: read tcp 89.125.1.107:39829: software caused connection abort
2026/02/26 08:08:36.510439 [Warning] [3441532841] app/proxyman/inbound: connection ends > proxy/http: connection ends > proxy/http: failed to write response > write tcp 127.0.0.1:10808->127.0.0.1:51952: write: broken pipe
"""

async def run_demo():
    logger.info("🚀 Starting AI-Driven Self-Healing Demo")
    
    # 1. Setup MAPE-K components
    knowledge = MAPEKKnowledge()
    monitor = MAPEKMonitor(knowledge=knowledge)
    analyzer = MAPEKAnalyzer()
    planner = MAPEKPlanner(knowledge=knowledge)
    executor = MAPEKExecutor()
    
    # 2. Enable Kimi K2.5 Integration
    # If KIMI_API_KEY is not set, it will use heuristic fallback
    kimi = KimiK25Integration(enabled=True)
    analyzer.enable_llm(integration=kimi)
    
    # 3. Simulate Monitor detecting issue from logs
    logger.info("🔍 Step 1: Monitor detecting instability from logs...")
    # In a real scenario, the monitor would parse these logs or receive error flags
    metrics = {
        "node_id": "ukraine-node-01",
        "service_name": "vless-proxy",
        "error_count": 3,
        "last_error": "software caused connection abort"
    }
    
    # 4. Analyze phase with AI
    logger.info("🤖 Step 2: Analyzer invoking AI (Kimi K2.5) to identify root cause...")
    analysis_result = await analyzer.analyze_with_llm(metrics, logs=USER_LOGS)
    logger.info(f"📋 AI Analysis Result: {analysis_result}")
    
    # 5. Plan phase
    logger.info("📅 Step 3: Planner selecting recovery strategy based on AI analysis...")
    strategy = planner.plan(analysis_result)
    logger.info(f"🎯 Planned Strategy: {strategy}")
    
    # 6. Execute phase
    logger.info(f"🛠️ Step 4: Executor performing recovery: {strategy}")
    success = executor.execute(strategy, context={"node_id": metrics["node_id"], "issue": analysis_result})
    
    if success:
        logger.info("✅ Self-healing completed successfully!")
    else:
        logger.error("❌ Self-healing failed.")

    # 7. Advanced Step: Script-based recovery
    logger.info("\n🛠️ Step 5: Advanced - AI suggesting a custom fix script...")
    AI_SCRIPT_RESPONSE = """
AI-Analysis (Proxy Configuration Error): The local proxy port 10808 is blocked. 
Try checking for process and clearing it:
```bash
echo "Stopping stale xray process..."
ps aux | grep xray | grep -v grep | awk '{print $2}' | xargs -r kill -9
echo "Xray processes cleared."
```
"""
    logger.info(f"📋 AI Response with Script: {AI_SCRIPT_RESPONSE}")
    success_script = executor.execute(AI_SCRIPT_RESPONSE, context={"node_id": metrics["node_id"]})
    
    if success_script:
        logger.info("✅ AI-driven script execution successful!")
    else:
        logger.error("❌ AI-driven script execution failed.")

if __name__ == "__main__":
    asyncio.run(run_demo())
