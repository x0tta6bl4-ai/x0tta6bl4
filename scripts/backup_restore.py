#!/usr/bin/env python3
"""
Backup and Restore Procedures

Provides backup and restore functionality for production deployment.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

project_root = Path(__file__).parent.parent

def backup_configuration() -> Path:
    """Backup current configuration."""
    backup_dir = project_root / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"config_backup_{timestamp}.json"
    
    # Collect configuration
    config = {
        "timestamp": datetime.now().isoformat(),
        "baseline_metrics": None,
        "deployment_config": None
    }
    
    # Backup baseline metrics
    baseline_file = project_root / "baseline_metrics.json"
    if baseline_file.exists():
        with open(baseline_file) as f:
            config["baseline_metrics"] = json.load(f)
    
    # Save backup
    with open(backup_file, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configuration backed up to: {backup_file}")
    return backup_file

def restore_configuration(backup_file: Path):
    """Restore configuration from backup."""
    if not backup_file.exists():
        print(f"❌ Backup file not found: {backup_file}")
        sys.exit(1)
    
    with open(backup_file) as f:
        config = json.load(f)
    
    # Restore baseline metrics
    if config.get("baseline_metrics"):
        baseline_file = project_root / "baseline_metrics.json"
        with open(baseline_file, "w") as f:
            json.dump(config["baseline_metrics"], f, indent=2)
        print(f"✅ Baseline metrics restored from: {backup_file}")
    
    print(f"✅ Configuration restored from: {backup_file}")

def list_backups() -> list[Path]:
    """List available backups."""
    backup_dir = project_root / "backups"
    if not backup_dir.exists():
        return []
    
    backups = sorted(backup_dir.glob("config_backup_*.json"), reverse=True)
    return backups

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backup and restore procedures")
    parser.add_argument("action", choices=["backup", "restore", "list"], help="Action to perform")
    parser.add_argument("--file", type=str, help="Backup file for restore")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        backup_configuration()
    elif args.action == "restore":
        if not args.file:
            print("❌ --file required for restore")
            sys.exit(1)
        restore_configuration(Path(args.file))
    elif args.action == "list":
        backups = list_backups()
        if backups:
            print("Available backups:")
            for backup in backups:
                print(f"  • {backup.name}")
        else:
            print("No backups found")

if __name__ == "__main__":
    main()

