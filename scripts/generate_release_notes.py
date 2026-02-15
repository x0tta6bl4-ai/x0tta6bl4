#!/usr/bin/env python3
"""
Generate release notes from git commits and conventional commits

Usage:
  python scripts/generate_release_notes.py <version>
"""

import re
import subprocess
import sys
from datetime import datetime


def run_git_command(cmd):
    """Execute git command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        return ""


def get_previous_tag():
    """Get the previous version tag"""
    result = run_git_command("git tag --sort=-version:refname | head -2 | tail -1")
    return result if result else "HEAD~20"


def get_commits_since(from_ref):
    """Get all commits since a reference"""
    cmd = f"git log {from_ref}..HEAD --pretty=format:%H%n%s%n%b%n---"
    return run_git_command(cmd)


def parse_conventional_commits(commits_str):
    """Parse conventional commits into categories"""
    categories = {
        "Features": [],
        "Bug Fixes": [],
        "Performance": [],
        "Security": [],
        "Breaking Changes": [],
        "Other": [],
    }

    commits = commits_str.split("---")

    for commit in commits:
        if not commit.strip():
            continue

        lines = commit.strip().split("\n")
        if not lines:
            continue

        commit_hash = lines[0][:7] if lines else ""
        subject = lines[1] if len(lines) > 1 else ""

        if not subject:
            continue

        # Parse conventional commit format
        if subject.startswith("feat"):
            categories["Features"].append((subject, commit_hash))
        elif subject.startswith("fix"):
            categories["Bug Fixes"].append((subject, commit_hash))
        elif subject.startswith("perf"):
            categories["Performance"].append((subject, commit_hash))
        elif subject.startswith("security") or "security" in subject.lower():
            categories["Security"].append((subject, commit_hash))
        elif "BREAKING" in subject:
            categories["Breaking Changes"].append((subject, commit_hash))
        else:
            categories["Other"].append((subject, commit_hash))

    return categories


def format_release_notes(version, categories):
    """Format release notes in markdown"""
    notes = []
    notes.append(f"# Release {version}\n")
    notes.append(f"*Released on {datetime.now().strftime('%Y-%m-%d')}*\n")

    # Add summary
    total_changes = sum(len(items) for items in categories.values())
    notes.append(f"This release includes {total_changes} changes.\n")

    for category, commits in categories.items():
        if not commits:
            continue

        notes.append(f"## {category}\n")
        for subject, commit_hash in commits:
            # Clean up conventional commit prefix
            subject = re.sub(
                r"^(feat|fix|perf|security|refactor|docs|style|test)(\(.+\))?:\s*",
                "",
                subject,
            )
            notes.append(
                f"- {subject} ([{commit_hash}](https://github.com/x0tta6bl4/x0tta6bl4/commit/{commit_hash}))"
            )
        notes.append("")

    # Add stats
    notes.append("## Statistics\n")
    notes.append(f"- Total commits: {total_changes}")

    return "\n".join(notes)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_release_notes.py <version>")
        sys.exit(1)

    version = sys.argv[1]
    previous_tag = get_previous_tag()

    print(f"Generating release notes for {version}", file=sys.stderr)
    print(f"Previous tag: {previous_tag}", file=sys.stderr)

    commits = get_commits_since(previous_tag)
    categories = parse_conventional_commits(commits)
    release_notes = format_release_notes(version, categories)

    print(release_notes)


if __name__ == "__main__":
    main()
