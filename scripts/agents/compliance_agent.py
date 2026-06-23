#!/usr/bin/env python3
"""Compliance Agent - SOC2/GDPR audit automation."""

import json
import logging
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compliance-agent")


class ComplianceAgent:
    """Automated compliance monitoring for SOC2/GDPR."""
    
    def __init__(self):
        self.project_root = Path("/mnt/projects")
        self.db_path = self.project_root / ".tmp/compliance.db"
        self._init_db()
        logger.info("ComplianceAgent initialized")
    
    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY,
                control_id TEXT,
                framework TEXT,
                status TEXT,
                checked_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def run_checks(self) -> Dict:
        """Run compliance checks."""
        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": []
        }
        
        # Check PQC key rotation
        rotation_file = self.project_root / "k8s/cronjob-key-rotation.yaml"
        results["checks"].append({
            "control": "CC6.1",
            "framework": "SOC2",
            "description": "PQC key rotation",
            "status": "pass" if rotation_file.exists() else "fail",
            "evidence": str(rotation_file) if rotation_file.exists() else "not found"
        })
        
        # Check tenant isolation
        values_file = self.project_root / "charts/multi-tenant/values-enterprise.yaml"
        results["checks"].append({
            "control": "CC6.3",
            "framework": "SOC2",
            "description": "Tenant isolation",
            "status": "pass" if values_file.exists() else "warning",
            "evidence": str(values_file) if values_file.exists() else "not found"
        })
        
        # Check evidence matrix
        matrix_file = self.project_root / "compliance/soc2/evidence-matrix.md"
        results["checks"].append({
            "control": "CC7.2",
            "framework": "SOC2",
            "description": "Audit evidence",
            "status": "pass" if matrix_file.exists() else "fail",
            "evidence": str(matrix_file) if matrix_file.exists() else "not found"
        })
        
        return results
    
    def generate_report(self) -> Dict:
        """Generate compliance report."""
        results = self.run_checks()
        passed = sum(1 for c in results["checks"] if c["status"] == "pass")
        failed = sum(1 for c in results["checks"] if c["status"] == "fail")
        
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_checks": len(results["checks"]),
            "passed": passed,
            "failed": failed,
            "compliance_rate": passed / len(results["checks"]) if results["checks"] else 0,
            "checks": results["checks"]
        }
        
        # Save report
        report_file = self.project_root / ".tmp/compliance_reports" / f"report_{int(datetime.now().timestamp())}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {report_file}")
        return report


def main():
    agent = ComplianceAgent()
    report = agent.generate_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
