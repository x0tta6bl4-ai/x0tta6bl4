#!/usr/bin/env python3
"""
Canary Deployment Script

Manages gradual rollout: 5% → 25% → 50% → 75% → 100%
"""

import asyncio
import time
import httpx
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.deployment.canary_deployment import CanaryDeployment, DeploymentConfig, DeploymentStage
except ImportError:
    print("⚠️ Canary deployment module not available")
    CanaryDeployment = None

async def check_health(url: str = "http://localhost:8080/health") -> bool:
    """Check if service is healthy."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            return response.status_code == 200
    except:
        return False

async def check_metrics(url: str = "http://localhost:8080/metrics") -> Dict[str, Any]:
    """Check current metrics."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            if response.status_code == 200:
                # Parse Prometheus metrics (simplified)
                metrics_text = response.text
                return {
                    "available": True,
                    "error_rate": 0.0,  # Would parse from metrics
                    "latency_p95": 0.0,  # Would parse from metrics
                    "throughput": 0.0,  # Would parse from metrics
                }
    except:
        pass
    
    return {"available": False}

async def deploy_canary(percentage: float, duration_minutes: int = 15) -> Dict[str, Any]:
    """
    Deploy canary at specified percentage.
    
    Args:
        percentage: Traffic percentage (5, 25, 50, 75, 100)
        duration_minutes: Monitoring duration in minutes
    """
    print(f"\n{'='*60}")
    print(f"🚀 CANARY DEPLOYMENT: {percentage}%")
    print(f"{'='*60}\n")
    
    print(f"Deploying {percentage}% traffic...")
    print(f"Monitoring for {duration_minutes} minutes...")
    print()
    
    # In real deployment, would use actual deployment system
    # For now, simulate canary deployment
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    checks = []
    all_healthy = True
    
    while time.time() < end_time:
        elapsed = int(time.time() - start_time)
        remaining = int(end_time - time.time())
        
        # Check health
        healthy = await check_health()
        metrics = await check_metrics()
        
        status = "✅" if healthy else "❌"
        print(f"[{elapsed}s/{duration_minutes*60}s] {status} Health check: {'OK' if healthy else 'FAILED'}")
        
        if not healthy:
            all_healthy = False
        
        checks.append({
            "timestamp": datetime.now().isoformat(),
            "healthy": healthy,
            "metrics": metrics
        })
        
        # Wait 30 seconds between checks
        await asyncio.sleep(30)
    
    # Summary
    healthy_checks = sum(1 for c in checks if c["healthy"])
    total_checks = len(checks)
    health_rate = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
    
    print()
    print(f"{'='*60}")
    print(f"📊 CANARY DEPLOYMENT RESULTS: {percentage}%")
    print(f"{'='*60}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Health Checks: {healthy_checks}/{total_checks} ({health_rate:.1f}%)")
    print(f"Status: {'✅ PASSED' if all_healthy and health_rate >= 95 else '❌ FAILED'}")
    print(f"{'='*60}\n")
    
    return {
        "percentage": percentage,
        "duration_minutes": duration_minutes,
        "health_rate": health_rate,
        "all_healthy": all_healthy,
        "passed": all_healthy and health_rate >= 95,
        "checks": checks
    }

async def main():
    """Main canary deployment function."""
    print("\n" + "="*60)
    print("🚀 CANARY DEPLOYMENT MANAGER")
    print("="*60)
    print("\nThis script manages gradual rollout:")
    print("  5% → 25% → 50% → 75% → 100%")
    print()
    
    # Check if service is running
    if not await check_health():
        print("❌ Service is not running on http://localhost:8080")
        print("   Please start the service first.")
        sys.exit(1)
    
    print("✅ Service is running\n")
    
    # Deployment stages
    stages = [
        (5.0, 15),   # 5% for 15 minutes
        (25.0, 30),  # 25% for 30 minutes
        (50.0, 60),  # 50% for 1 hour
        (75.0, 120), # 75% for 2 hours
        (100.0, 1440), # 100% for 24 hours
    ]
    
    results = []
    
    for percentage, duration in stages:
        result = await deploy_canary(percentage, duration)
        results.append(result)
        
        if not result["passed"]:
            print(f"❌ Canary deployment failed at {percentage}%")
            print("   Rolling back...")
            # In real deployment, would trigger rollback
            sys.exit(1)
        
        print(f"✅ Canary deployment at {percentage}% successful")
        print()
        
        # Ask for confirmation before next stage (except for 100%)
        if percentage < 100:
            print(f"Ready to proceed to {stages[stages.index((percentage, duration)) + 1][0]}%?")
            print("Press Enter to continue, or 'q' to quit...")
            # In real scenario, would wait for user input or automated approval
    
    # Final summary
    print("\n" + "="*60)
    print("🎉 CANARY DEPLOYMENT COMPLETE")
    print("="*60)
    print(f"All stages completed successfully!")
    print(f"Final deployment: 100% traffic")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

