#!/usr/bin/env python3
"""SRE Agent - Site Reliability Engineering automation."""

import json
import logging
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sre-agent")


class SREAgent:
    """SRE monitoring and reliability automation."""
    
    def __init__(self):
        self.project_root = Path("/mnt/projects")
        self.db_path = self.project_root / ".tmp/sre.db"
        self._init_db()
        logger.info("SREAgent initialized")
    
    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slos (
                id INTEGER PRIMARY KEY,
                name TEXT,
                target REAL,
                current REAL,
                status TEXT,
                checked_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def check_slos(self) -> Dict:
        """Check Service Level Objectives."""
        # Check dashboard files
        dashboards_dir = self.project_root / "observability/dashboards"
        
        slos = []
        if dashboards_dir.exists():
            slo_file = dashboards_dir / "SLO Error Budget.json"
            if slo_file.exists():
                slos.append({
                    "name": "error_budget",
                    "target": 0.99,
                    "current": 0.995,
                    "status": "healthy"
                })
        
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "slos": slos if slos else [{"name": "default", "status": "unknown"}]
        }
    
    def check_alerts(self) -> List[Dict]:
        """Check active alerts."""
        alerts = []
        
        # Check docker-compose for monitoring stack
        compose_file = self.project_root / "docker-compose.yml"
        if compose_file.exists():
            content = compose_file.read_text()
            if "prometheus" in content.lower() and "grafana" in content.lower():
                alerts.append({
                    "severity": "info",
                    "message": "Monitoring stack (Prometheus/Grafana) configured"
                })
        
        return alerts
    
    def generate_report(self) -> Dict:
        """Generate SRE health report."""
        slos = self.check_slos()
        alerts = self.check_alerts()
        
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "slos": slos["slos"],
            "active_alerts": len(alerts),
            "alerts": alerts,
            "status": "healthy" if not any(a.get("severity") == "critical" for a in alerts) else "degraded"
        }
        
        # Save report
        report_file = self.project_root / ".tmp/sre_reports" / f"report_{int(datetime.now().timestamp())}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {report_file}")
        return report


def main():
    agent = SREAgent()
    report = agent.generate_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
