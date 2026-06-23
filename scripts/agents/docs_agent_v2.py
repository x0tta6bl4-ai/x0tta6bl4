#!/usr/bin/env python3
"""Docs Agent v2 - Improved broken link detection."""

import json
import re
from pathlib import Path
from datetime import datetime, UTC

class DocsAgentV2:
    def __init__(self):
        self.project_root = Path("/mnt/projects")
        self.docs_root = self.project_root / "docs"
    
    def check_link(self, file_path: Path, link: str) -> dict:
        """Check if a link is valid."""
        # Skip external URLs
        if link.startswith(('http://', 'https://', 'mailto:')):
            return {"valid": True, "type": "external"}
        
        # Skip anchor-only links (they're valid within same file)
        if link.startswith('#'):
            return {"valid": True, "type": "anchor"}
        
        # Handle relative paths
        if link.startswith('./'):
            target = file_path.parent / link[2:]
        elif link.startswith('../'):
            target = file_path.parent / link
        elif link.startswith('/'):
            target = self.project_root / link[1:]
        else:
            target = file_path.parent / link
        
        # Remove anchor part for file existence check
        target_path = Path(str(target).split('#')[0])
        
        exists = target_path.exists()
        return {
            "valid": exists,
            "type": "file",
            "target": str(target_path),
            "exists": exists
        }
    
    def scan_file(self, md_file: Path) -> list:
        """Scan single markdown file for broken links."""
        issues = []
        
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception as e:
            return [{"error": str(e)}]
        
        # Find all markdown links [text](url)
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        for text, link in links:
            result = self.check_link(md_file, link)
            if not result["valid"] and result["type"] == "file":
                issues.append({
                    "file": str(md_file.relative_to(self.project_root)),
                    "link_text": text,
                    "link_url": link,
                    "target": result.get("target"),
                    "issue": "file_not_found"
                })
        
        return issues
    
    def scan_all(self) -> dict:
        """Scan all documentation."""
        if not self.docs_root.exists():
            return {"error": "docs directory not found"}
        
        all_issues = []
        files_scanned = 0
        
        for md_file in self.docs_root.rglob("*.md"):
            files_scanned += 1
            issues = self.scan_file(md_file)
            all_issues.extend(issues)
        
        # Also scan root markdown files
        for md_file in self.project_root.glob("*.md"):
            files_scanned += 1
            issues = self.scan_file(md_file)
            all_issues.extend(issues)
        
        return {
            "scanned_at": datetime.now(UTC).isoformat(),
            "files_scanned": files_scanned,
            "broken_links": len(all_issues),
            "issues": all_issues[:20],  # Limit output
            "health_score": max(0, 100 - len(all_issues) * 2)
        }


def main():
    agent = DocsAgentV2()
    report = agent.scan_all()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
