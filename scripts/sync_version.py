#!/usr/bin/env python3
"""
Version synchronization script for x0tta6bl4

Reads version from VERSION file and updates:
- pyproject.toml
- Dockerfile LABEL
- Any other files that need version

Usage:
    python scripts/sync_version.py
    python scripts/sync_version.py --version 3.2.1
"""

import argparse
import re
from pathlib import Path


def read_version(version_file: Path) -> str:
    """Read version from VERSION file."""
    if not version_file.exists():
        raise FileNotFoundError(f"VERSION file not found: {version_file}")
    
    version = version_file.read_text().strip()
    if not re.match(r'^\d+\.\d+\.\d+', version):
        raise ValueError(f"Invalid version format: {version}")
    
    return version


def update_pyproject_toml(pyproject_path: Path, version: str) -> bool:
    """Update version in pyproject.toml."""
    if not pyproject_path.exists():
        return False
    
    content = pyproject_path.read_text()
    
    # Update version in [project] section
    pattern = r'(version\s*=\s*")[^"]+(")'
    replacement = rf'\g<1>{version}\g<2>'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        pyproject_path.write_text(new_content)
        return True
    return False


def update_dockerfile(dockerfile_path: Path, version: str) -> bool:
    """Update version in Dockerfile LABEL."""
    if not dockerfile_path.exists():
        return False
    
    content = dockerfile_path.read_text()
    
    # Update LABEL version
    pattern = r'(LABEL\s+version=")[^"]+(")'
    replacement = rf'\g<1>{version}\g<2>'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        dockerfile_path.write_text(new_content)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Sync version across project files')
    parser.add_argument('--version', type=str, help='Version to set (overrides VERSION file)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    version_file = project_root / 'VERSION'
    
    if args.version:
        version = args.version
        if args.dry_run:
            print(f"Would write version '{version}' to {version_file}")
        else:
            version_file.write_text(f"{version}\n")
            print(f"✅ Updated VERSION file: {version}")
    else:
        version = read_version(version_file)
        print(f"📖 Reading version from {version_file}: {version}")
    
    updated_files = []
    
    # Update pyproject.toml
    pyproject_path = project_root / 'pyproject.toml'
    if update_pyproject_toml(pyproject_path, version):
        updated_files.append('pyproject.toml')
        if not args.dry_run:
            print(f"✅ Updated {pyproject_path}")
    
    # Update Dockerfile
    dockerfile_path = project_root / 'Dockerfile'
    if update_dockerfile(dockerfile_path, version):
        updated_files.append('Dockerfile')
        if not args.dry_run:
            print(f"✅ Updated {dockerfile_path}")
    
    if args.dry_run:
        print(f"\n📋 Would update: {', '.join(updated_files) if updated_files else 'nothing'}")
    elif updated_files:
        print(f"\n✅ Version synchronized across {len(updated_files)} file(s)")
    else:
        print("\n✅ All files already in sync")


if __name__ == '__main__':
    main()
