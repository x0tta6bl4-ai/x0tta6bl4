#!/usr/bin/env python3
"""
Validate VPN client compatibility (URI format, etc.).
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VPN client compatibility")
    parser.add_argument("--config", required=True, help="URI to validate")
    args = parser.parse_args()

    uri = args.config
    try:
        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()

        if scheme not in ("vless", "vmess", "trojan"):
            print(f"Error: Unsupported scheme '{scheme}'")
            return 1

        if not parsed.netloc:
            print("Error: Invalid URI format (missing authority/netloc)")
            return 1

        if scheme in ("vless", "trojan") and "@" not in parsed.netloc:
            print("Error: Missing credentials in URI")
            return 1

        print(f"Validation passed for scheme {scheme}")
        return 0
    except Exception as e:
        print(f"Failed to parse config: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
