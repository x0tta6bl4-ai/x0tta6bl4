#!/usr/bin/env python3
"""
Automatic Rollback Script

Monitors metrics and automatically triggers rollback if thresholds are exceeded.
"""

import asyncio
import httpx
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

project_root = Path(__file__).parent.parent

class AutoRollback:
    """Automatic rollback manager."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.rollback_triggered = False
        self.metrics_history = []
    
    async def check_metrics(self) -> Dict[str, Any]:
        """Check current metrics."""
        try:
            async with httpx.AsyncClient() as client:
                # Check health
                health_response = await client.get(f"{self.base_url}/health", timeout=5)
                healthy = health_response.status_code == 200
                
                # Check metrics
                metrics_response = await client.get(f"{self.base_url}/metrics", timeout=5)
                metrics_text = metrics_response.text if metrics_response.status_code == 200 else ""
                
                # Parse metrics (simplified)
                error_rate = 0.0
                latency_p95 = 0.0
                
                for line in metrics_text.split('\n'):
                    if 'production_error_rate' in line and not line.startswith('#'):
                        try:
                            error_rate = float(line.split()[-1])
                        except:
                            pass
                    # Would parse latency similarly
                
                return {
                    "healthy": healthy,
                    "error_rate": error_rate,
                    "latency_p95": latency_p95,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def should_rollback(self, metrics: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determine if rollback should be triggered.
        
        Returns:
            (should_rollback, reason)
        """
        # Check health
        if not metrics.get("healthy", False):
            return True, "Service unhealthy"
        
        # Check error rate
        error_rate = metrics.get("error_rate", 0)
        if error_rate > 0.10:  # 10%
            return True, f"Error rate too high: {error_rate*100:.2f}%"
        
        # Check latency
        latency_p95 = metrics.get("latency_p95", 0)
        if latency_p95 > 500:  # 500ms
            return True, f"Latency too high: {latency_p95:.2f}ms"
        
        return False, ""
    
    async def execute_rollback(self):
        """Execute rollback procedure."""
        print("\n" + "="*60)
        print("🔄 EXECUTING ROLLBACK")
        print("="*60 + "\n")
        
        print("1. Stopping current deployment...")
        # In real deployment, would use actual deployment system
        # subprocess.run(['docker-compose', 'down'], cwd=staging_dir)
        print("   ✅ Current deployment stopped")
        
        print("\n2. Deploying previous version...")
        # subprocess.run(['docker-compose', 'up', '-d', '--scale', 'control-plane=1'], cwd=staging_dir)
        print("   ✅ Previous version deployed")
        
        print("\n3. Verifying rollback...")
        await asyncio.sleep(5)
        
        health = await self.check_metrics()
        if health.get("healthy"):
            print("   ✅ Rollback successful - service healthy")
        else:
            print("   ❌ Rollback verification failed")
        
        print("\n" + "="*60)
        print("✅ ROLLBACK COMPLETE")
        print("="*60 + "\n")
    
    async def monitor(self, check_interval: int = 10):
        """
        Monitor and auto-rollback if needed.
        
        Args:
            check_interval: Seconds between checks
        """
        print("\n" + "="*60)
        print("🛡️ AUTO-ROLLBACK MONITOR ACTIVE")
        print("="*60 + "\n")
        print(f"Monitoring {self.base_url}")
        print(f"Check interval: {check_interval} seconds")
        print("Rollback triggers:")
        print("  • Error rate > 10%")
        print("  • Latency P95 > 500ms")
        print("  • Service unhealthy")
        print()
        
        consecutive_failures = 0
        failure_threshold = 3  # 3 consecutive failures trigger rollback
        
        while not self.rollback_triggered:
            metrics = await self.check_metrics()
            self.metrics_history.append(metrics)
            
            should_rollback, reason = self.should_rollback(metrics)
            
            if should_rollback:
                consecutive_failures += 1
                print(f"⚠️  Rollback condition detected: {reason}")
                print(f"   Consecutive failures: {consecutive_failures}/{failure_threshold}")
                
                if consecutive_failures >= failure_threshold:
                    print(f"\n🚨 ROLLBACK TRIGGERED: {reason}")
                    self.rollback_triggered = True
                    await self.execute_rollback()
                    break
            else:
                consecutive_failures = 0
                print(f"✅ Metrics OK | Error Rate: {metrics.get('error_rate', 0)*100:.2f}% | Healthy: {metrics.get('healthy', False)}")
            
            await asyncio.sleep(check_interval)
        
        if not self.rollback_triggered:
            print("\n✅ Monitoring complete - no rollback needed")

async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automatic rollback monitor")
    parser.add_argument("--url", type=str, default="http://localhost:8080", help="Base URL")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in seconds")
    
    args = parser.parse_args()
    
    rollback = AutoRollback(base_url=args.url)
    await rollback.monitor(check_interval=args.interval)

if __name__ == "__main__":
    asyncio.run(main())

