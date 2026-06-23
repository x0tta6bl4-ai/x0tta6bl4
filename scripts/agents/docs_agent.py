#!/usr/bin/env python3
"""Docs Agent - Documentation quality and consistency management."""

import json
import logging
import re
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docs-agent")


class DocsAgent:
    """Documentation quality monitoring and maintenance."""
    
    def __init__(self):
        self.project_root = Path("/mnt/projects")
        self.docs_root = self.project_root / "docs"
        self.db_path = self.project_root / ".tmp/docs.db"
        self._init_db()
        logger.info("DocsAgent initialized")
    
    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_issues (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                issue_type TEXT,
                severity TEXT,
                checked_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def scan_documentation(self) -> Dict:
        """Scan docs for quality issues."""
        issues = []
        
        if not self.docs_root.exists():
            return {"error": "docs directory not found"}
        
        # Check main README.md
        readme = self.docs_root / "README.md"
        if not readme.exists():
            issues.append({
                "file": "docs/README.md",
                "type": "missing_file",
                "severity": "high"
            })
        
        # Check for broken internal links
        md_files = list(self.docs_root.rglob("*.md"))
        broken_links = []
        
        for md_file in md_files[:50]:  # Limit scan
            try:
                content = md_file.read_text(encoding='utf-8')
                # Find markdown links [text](path)
                links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
                for text, link in links:
                    if link.startswith('http'):
                        continue
                    if not link.startswith('/'):
                        target = md_file.parent / link
                        if not target.exists():
                            broken_links.append({
                                "file": str(md_file),
                                "link": link,
                                "target": str(target)
                            })
            except Exception as e:
                logger.warning(f"Error reading {md_file}: {e}")
        
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_docs": len(md_files),
            "issues": issues,
            "broken_links": broken_links[:10]  # Limit report
        }
    
    def check_consistency(self) -> List[Dict]:
        """Check documentation consistency."""
        checks = []
        
        # Check for required sections in key files
        styleguide = self.docs_root / "STYLEGUIDE.md"
        if styleguide.exists():
            content = styleguide.read_text().lower()
            checks.append({
                "file": "STYLEGUIDE.md",
                "has_structure": "heading" in content or "# " in styleguide.read_text(),
                "status": "ok"
            })
        
        return checks
    
    def generate_report(self) -> Dict:
        """Generate documentation health report."""
        scan = self.scan_documentation()
        consistency = self.check_consistency()
        
        total_issues = len(scan.get("issues", [])) + len(scan.get("broken_links", []))
        
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_docs": scan.get("total_docs", 0),
            "total_issues": total_issues,
            "health_score": max(0, 100 - total_issues * 5),
            "issues": scan.get("issues", []),
            "broken_links": scan.get("broken_links", []),
            "consistency_checks": consistency
        }
        
        # Save report
        report_file = self.project_root / ".tmp/docs_reports" / f"report_{int(datetime.now().timestamp())}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {report_file}")
        return report


def main():
    agent = DocsAgent()
    report = agent.generate_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
