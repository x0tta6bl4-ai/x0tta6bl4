#!/usr/bin/env python3
"""
Manage Xray runtime users (add/remove/list inbounds). Uses config file manipulation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_path: Path, data: dict) -> None:
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Xray runtime users")
    parser.add_argument("--action", choices=["list", "add", "remove"], required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--uuid", help="UUID for the user (add)")
    parser.add_argument("--email", help="Email for the user (add/remove)")
    parser.add_argument("--tag", default="vless-in", help="Inbound tag")

    args = parser.parse_args()

    config = load_config(args.config)
    if not config:
        print(f"Error: Config {args.config} not found or empty.")
        return 1

    inbound = None
    for ib in config.get("inbounds", []):
        if ib.get("tag") == args.tag:
            inbound = ib
            break

    if not inbound:
        print(f"Error: Inbound with tag {args.tag} not found.")
        return 1

    clients = inbound.setdefault("settings", {}).setdefault("clients", [])

    if args.action == "list":
        for c in clients:
            print(f"- {c.get('email')}: {c.get('id')}")

    elif args.action == "add":
        if not args.uuid or not args.email:
            print("Error: --uuid and --email are required for add")
            return 1
        for c in clients:
            if c.get("email") == args.email:
                print(f"User {args.email} already exists.")
                return 0
        clients.append({"id": args.uuid, "email": args.email})
        save_config(args.config, config)
        print(f"Added {args.email}")

    elif args.action == "remove":
        if not args.email:
            print("Error: --email is required for remove")
            return 1
        original_len = len(clients)
        inbound["settings"]["clients"] = [c for c in clients if c.get("email") != args.email]
        if len(inbound["settings"]["clients"]) < original_len:
            save_config(args.config, config)
            print(f"Removed {args.email}")
        else:
            print(f"User {args.email} not found.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
