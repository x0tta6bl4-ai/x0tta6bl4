"""
Demo: Reinforcement Learning Feedback Loop
==========================================

This script demonstrates how x0tta6bl4 learns from previous recovery 
attempts and optimizes its strategy over time.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.self_healing.mape_k import MAPEKKnowledge, MAPEKPlanner

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Feedback-Loop-Demo")

def run_demo():
    logger.info("🚀 Starting Feedback Loop Demo")
    
    knowledge = MAPEKKnowledge()
    planner = MAPEKPlanner(knowledge=knowledge)
    
    issue = "Network Loss"
    
    # 1. First attempt: Use default
    strategy1 = planner.plan(issue)
    logger.info(f"📅 Round 1: Issue='{issue}'. Strategy chosen: '{strategy1}'")
    
    # 2. Record FAILURE for 'Switch route'
    logger.info(f"❌ Recording FAILURE for '{strategy1}'...")
    knowledge.record(metrics={}, issue=issue, action=strategy1, success=False, mttr=10.0)
    
    # 3. Inject a successful alternative from 'experience' (simulating another node's success)
    alternative = "Restart interface"
    logger.info(f"✅ Recording SUCCESS for alternative '{alternative}'...")
    knowledge.record(metrics={}, issue=issue, action=alternative, success=True, mttr=2.0)
    
    # 4. Second attempt: See if it learns
    strategy2 = planner.plan(issue)
    logger.info(f"📅 Round 2: Issue='{issue}'. Strategy chosen: '{strategy2}'")
    
    if strategy2 == alternative:
        logger.info("🎉 SUCCESS: System learned to prefer the alternative action!")
    else:
        logger.error(f"❌ FAILED: System still chose '{strategy2}'")

if __name__ == "__main__":
    run_demo()
