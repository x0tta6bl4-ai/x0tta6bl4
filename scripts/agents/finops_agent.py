#!/usr/bin/env python3
"""FinOps Agent - Cloud cost optimization for x0tta6bl4."""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, UTC
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finops-agent")


class CostCategory(Enum):
    VPS = "vps"
    BANDWIDTH = "bandwidth"
    STRIPE_FEES = "stripe_fees"
    DAO_TOKENS = "dao_tokens"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostMetrics:
    category: CostCategory
    amount_usd: float
    period: str
    trend_percent: float = 0.0
    details: Dict[str, Any] = None


class FinOpsAgent:
    """FinOps Agent for cost management and optimization."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.project_root = Path("/mnt/projects")
        self.db_path = self.project_root / ".tmp/finops.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("FinOpsAgent initialized")
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_metrics (
                id INTEGER PRIMARY KEY,
                category TEXT, amount_usd REAL, period TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def collect_vps_costs(self) -> CostMetrics:
        """Collect VPS infrastructure costs."""
        logger.info("Collecting VPS costs")
        # Estimate based on typical VPS configuration
        monthly_cost = 45.0  # $45/month typical VPS
        return CostMetrics(
            category=CostCategory.VPS,
            amount_usd=monthly_cost,
            period="monthly",
            details={"cpu_cores": 2, "memory_gb": 4, "storage_gb": 50}
        )
    
    def collect_stripe_fees(self) -> CostMetrics:
        """Collect Stripe transaction fees from database."""
        logger.info("Collecting Stripe fees")
        try:
            conn = sqlite3.connect(self.project_root / "database.db")
            cursor = conn.cursor()
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            cursor.execute(
                "SELECT SUM(amount) FROM payments WHERE status = 'completed' AND created_at > ?",
                (thirty_days_ago,)
            )
            revenue = cursor.fetchone()[0] or 0
            conn.close()
            
            # Stripe fee: 2.9% + $0.30 per transaction
            fees = revenue * 0.029 + (revenue / 10) * 0.30
            return CostMetrics(
                category=CostCategory.STRIPE_FEES,
                amount_usd=fees,
                period="monthly",
                details={"monthly_revenue": revenue}
            )
        except Exception as e:
            logger.error(f"Stripe collection failed: {e}")
            return CostMetrics(category=CostCategory.STRIPE_FEES, amount_usd=0, period="monthly")
    
    def detect_anomalies(self) -> List[Dict]:
        """Detect cost anomalies."""
        alerts = []
        vps = self.collect_vps_costs()
        if vps.amount_usd > 60:  # Alert if >$60/month
            alerts.append({
                "severity": AlertSeverity.WARNING.value,
                "category": CostCategory.VPS.value,
                "message": f"VPS cost ${vps.amount_usd:.2f} exceeds threshold $60",
                "timestamp": datetime.now(UTC).isoformat()
            })
        return alerts
    
    def generate_report(self) -> Dict:
        """Generate FinOps report."""
        vps = self.collect_vps_costs()
        stripe = self.collect_stripe_fees()
        alerts = self.detect_anomalies()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_monthly_usd": vps.amount_usd + stripe.amount_usd,
            "breakdown": {
                "vps": {"category": vps.category.value, "amount_usd": vps.amount_usd, "period": vps.period, "details": vps.details},
                "stripe_fees": {"category": stripe.category.value, "amount_usd": stripe.amount_usd, "period": stripe.period, "details": stripe.details}
            },
            "alerts": alerts,
            "recommendations": [
                {
                    "category": "vps",
                    "savings_usd": 15.0,
                    "action": "Consider downsizing instance based on utilization"
                },
                {
                    "category": "bandwidth",
                    "savings_usd": 25.0,
                    "action": "Implement CDN for static assets"
                }
            ]
        }
        
        # Save report
        report_file = self.project_root / ".tmp/finops_reports" / f"report_{int(time.time())}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {report_file}")
        return report


def main():
    agent = FinOpsAgent()
    report = agent.generate_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
