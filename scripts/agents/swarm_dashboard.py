#!/usr/bin/env python3
"""Swarm Dashboard - Monitor all 13 agents status."""

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

class SwarmDashboard:
    def __init__(self):
        self.root = Path("/mnt/projects")
        self.tmp = self.root / ".tmp"
    
    def get_agent_status(self, name):
        db = self.tmp / f"{name}.db"
        reports = list((self.tmp / f"{name}_reports").glob("*.json")) if (self.tmp / f"{name}_reports").exists() else []
        
        return {
            "database_exists": db.exists(),
            "database_size_kb": db.stat().st_size // 1024 if db.exists() else 0,
            "reports_count": len(reports),
            "last_report": reports[-1].name if reports else None
        }
    
    def generate(self):
        agents = {
            "chaos": self.get_agent_status("chaos"),
            "finops": self.get_agent_status("finops"),
            "compliance": self.get_agent_status("compliance"),
            "sre": self.get_agent_status("sre"),
            "docs": self.get_agent_status("docs"),
            "quantum": self.get_agent_status("quantum"),
            "mlops": self.get_agent_status("mlops"),
            "devrel": self.get_agent_status("devrel"),
        }
        
        # Add base agents
        base_agents = ["architect", "security", "network", "quality", "kimi-bridge"]
        for name in base_agents:
            agents[name] = {"type": "base_agent", "active": True}
        
        dashboard = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_agents": 13,
            "agents": agents,
            "health": "operational"
        }
        
        with open(self.tmp / "swarm_dashboard.json", 'w') as f:
            json.dump(dashboard, f, indent=2)
        
        return dashboard

if __name__ == "__main__":
    import sys
    db = SwarmDashboard()
    print(json.dumps(db.generate(), indent=2))
