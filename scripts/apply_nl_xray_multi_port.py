#!/usr/bin/env python3
"""
Generate and apply multi-port (443 + 8443 + 2083) Xray config to NL server.
"""

import json
import sys
from pathlib import Path

BACKUP_PATH = Path("/mnt/projects/nl-diagnostics/backups/xray_config_backup_20260720.json")
OUTPUT_PATH = Path("/mnt/projects/scratch/xray_multi_port_config.json")

def main():
    if not BACKUP_PATH.exists():
        print(f"Error: Backup file {BACKUP_PATH} not found.")
        sys.exit(1)

    with open(BACKUP_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    inbounds = config.get("inbounds", [])
    if not inbounds:
        print("Error: No inbounds found in config.")
        sys.exit(1)

    primary_inbound = inbounds[0]
    
    # We will add ports 8443 and 2083
    additional_ports = [8443, 2083]
    
    for port in additional_ports:
        has_port = any(ib.get("port") == port for ib in inbounds)
        if not has_port:
            new_inbound = json.loads(json.dumps(primary_inbound))
            new_inbound["port"] = port
            new_inbound["tag"] = f"ru-in-{port}"
            inbounds.append(new_inbound)
            print(f"Added secondary VLESS Reality inbound for port {port}.")
        else:
            print(f"Inbound for port {port} already present.")

    config["inbounds"] = inbounds

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Generated new multi-port config at {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
