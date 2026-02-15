#!/usr/bin/env python3
"""
inject_frontmatter.py

Batch inject YAML front-matter into Markdown files that lack it.

Usage:
    python scripts/inject_frontmatter.py --glob="docs/**/*.md" --template=.frontmatter_template.yaml --dry-run
    python scripts/inject_frontmatter.py --glob="docs/**/*.md" --template=.frontmatter_template.yaml

Features:
- Scans for .md files matching glob pattern
- Checks if file already has front-matter (starts with '---')
- Injects template front-matter with auto-detected metadata
- Supports dry-run mode
- Generates report of modified files
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml


def has_frontmatter(content: str) -> bool:
    """Check if file already has YAML front-matter."""
    return content.strip().startswith("---")


def extract_title_from_markdown(content: str) -> str:
    """Extract first # heading as title."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled Document"


def detect_domain(filepath: Path) -> str:
    """Auto-detect domain based on file path."""
    path_str = str(filepath).lower()

    if "core" in path_str or "architecture" in path_str:
        return "Core"
    elif "devops" in path_str or "ci" in path_str or "deployment" in path_str:
        return "DevOps"
    elif "security" in path_str or "zero-trust" in path_str:
        return "Security"
    elif "infrastructure" in path_str or "infra" in path_str or "k8s" in path_str:
        return "Infrastructure"
    elif "research" in path_str or "experiment" in path_str:
        return "Research"
    elif "governance" in path_str or "dao" in path_str:
        return "Governance"
    elif "operations" in path_str or "ops" in path_str or "monitoring" in path_str:
        return "Operations"
    elif "ml" in path_str or "lora" in path_str or "rag" in path_str:
        return "ML"
    elif "quantum" in path_str:
        return "Quantum"
    elif "network" in path_str or "mesh" in path_str:
        return "Network"
    else:
        return "General"


def detect_status(filepath: Path, content: str) -> str:
    """Auto-detect status based on content and path."""
    path_str = str(filepath).lower()
    content_lower = content.lower()

    if "draft" in path_str or "wip" in path_str or "todo" in content_lower[:500]:
        return "Draft"
    elif (
        "deprecated" in path_str
        or "legacy" in path_str
        or "deprecated" in content_lower[:500]
    ):
        return "Deprecated"
    elif "review" in content_lower[:500] or "pending" in content_lower[:500]:
        return "Review"
    else:
        return "Stable"


def detect_criticality(filepath: Path, content: str) -> str:
    """Auto-detect criticality based on keywords."""
    content_lower = content.lower()
    path_str = str(filepath).lower()

    critical_keywords = [
        "critical",
        "security",
        "authentication",
        "authorization",
        "production",
    ]
    high_keywords = ["important", "core", "architecture", "api", "infrastructure"]

    if any(kw in content_lower[:1000] or kw in path_str for kw in critical_keywords):
        return "Critical"
    elif any(kw in content_lower[:1000] or kw in path_str for kw in high_keywords):
        return "High"
    elif "example" in path_str or "tutorial" in path_str:
        return "Low"
    else:
        return "Medium"


def extract_tags(content: str, domain: str) -> list:
    """Extract potential tags from content and domain."""
    tags = []
    content_lower = content.lower()

    # Domain-specific tags
    domain_tag_map = {
        "Core": ["architecture", "design"],
        "Security": ["security", "zero-trust"],
        "ML": ["machine-learning", "ai"],
        "Quantum": ["quantum-computing"],
        "Network": ["networking", "mesh"],
        "DevOps": ["ci-cd", "deployment"],
        "Operations": ["monitoring", "observability"],
        "Governance": ["dao", "governance"],
    }

    tags.extend(domain_tag_map.get(domain, []))

    # Keyword detection
    keyword_map = {
        "kubernetes": "k8s",
        "docker": "containerization",
        "terraform": "iac",
        "spire": "spiffe",
        "prometheus": "monitoring",
        "grafana": "observability",
        "mape-k": "self-healing",
        "mesh": "networking",
        "quantum": "quantum-computing",
    }

    for keyword, tag in keyword_map.items():
        if keyword in content_lower[:2000]:
            tags.append(tag)

    return list(set(tags))[:5]  # Limit to 5 unique tags


def generate_frontmatter(filepath: Path, content: str) -> dict:
    """Generate front-matter metadata for a file."""
    title = extract_title_from_markdown(content)
    domain = detect_domain(filepath)
    status = detect_status(filepath, content)
    criticality = detect_criticality(filepath, content)
    tags = extract_tags(content, domain)

    frontmatter = {
        "title": title,
        "domain": domain,
        "status": status,
        "criticality": criticality,
        "maturity": "Production" if status == "Stable" else "Development",
        "owner": "@core-team",  # Default, should be updated manually
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "tags": tags,
        "dependencies": [],
        "copilot_context": f"Reference for {domain} domain context.",
        "audience": "Internal",
        "classification": "Internal",
        "review_cycle": "Quarterly",
    }

    return frontmatter


def inject_frontmatter_into_file(filepath: Path, dry_run: bool = False) -> bool:
    """Inject front-matter into a single file."""
    try:
        content = filepath.read_text(encoding="utf-8")

        if has_frontmatter(content):
            print(f"  ⏭️  SKIP: {filepath} (already has front-matter)")
            return False

        frontmatter = generate_frontmatter(filepath, content)

        # Format front-matter as YAML
        yaml_header = "---\n"
        yaml_header += yaml.dump(
            frontmatter, default_flow_style=False, allow_unicode=True
        )
        yaml_header += "---\n\n"

        new_content = yaml_header + content

        if dry_run:
            print(f"  🔍 DRY-RUN: Would inject front-matter into {filepath}")
            print(f"     Title: {frontmatter['title']}")
            print(f"     Domain: {frontmatter['domain']}")
            print(f"     Status: {frontmatter['status']}")
            print(f"     Criticality: {frontmatter['criticality']}")
            print(
                f"     Tags: {', '.join(frontmatter['tags']) if frontmatter['tags'] else 'None'}"
            )
        else:
            filepath.write_text(new_content, encoding="utf-8")
            print(f"  ✅ INJECTED: {filepath}")

        return True

    except Exception as e:
        print(f"  ❌ ERROR: {filepath} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Batch inject YAML front-matter into Markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (preview only)
  python scripts/inject_frontmatter.py --glob="docs/**/*.md" --dry-run
  
  # Actual injection
  python scripts/inject_frontmatter.py --glob="docs/**/*.md"
  
  # Specific directory
  python scripts/inject_frontmatter.py --glob="x0tta6bl4_paradox_zone/docs/**/*.md"
        """,
    )

    parser.add_argument(
        "--glob",
        required=True,
        help='Glob pattern for Markdown files (e.g., "docs/**/*.md")',
    )
    parser.add_argument(
        "--template",
        default=".frontmatter_template.yaml",
        help="Path to front-matter template (default: .frontmatter_template.yaml)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to search from (default: current directory)",
    )

    args = parser.parse_args()

    root_path = Path(args.root).resolve()

    if not root_path.exists():
        print(f"❌ Error: Root path does not exist: {root_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"🚀 x0tta6bl4 Front-Matter Injection Tool")
    print(f"{'='*60}\n")
    print(f"Root: {root_path}")
    print(f"Pattern: {args.glob}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"\n{'='*60}\n")

    # Find matching files
    matching_files = list(root_path.glob(args.glob))

    if not matching_files:
        print(f"⚠️  No files found matching pattern: {args.glob}")
        sys.exit(0)

    print(f"📂 Found {len(matching_files)} Markdown files\n")

    # Process files
    modified_count = 0
    skipped_count = 0
    error_count = 0

    for filepath in sorted(matching_files):
        result = inject_frontmatter_into_file(filepath, args.dry_run)
        if result:
            modified_count += 1
        elif result is False and "SKIP" in str(filepath):
            skipped_count += 1
        else:
            error_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Total files scanned: {len(matching_files)}")
    print(f"✅ Modified: {modified_count}")
    print(f"⏭️  Skipped: {skipped_count}")
    print(f"❌ Errors: {error_count}")

    if args.dry_run:
        print(f"\n💡 This was a dry-run. Run without --dry-run to apply changes.")
    else:
        print(f"\n✅ Front-matter injection complete!")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
