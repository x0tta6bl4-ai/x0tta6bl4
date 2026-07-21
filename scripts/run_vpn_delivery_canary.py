#!/usr/bin/env python3
"""
Canary test for VPN config delivery.
"""
from __future__ import annotations

import argparse
import base64
import sys
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Canary test for VPN delivery")
    parser.add_argument("--sub-url", required=True, help="Subscription URL")
    args = parser.parse_args()

    try:
        req = Request(args.sub_url)
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")

        try:
            decoded = base64.b64decode(body).decode("utf-8")
        except Exception:
            decoded = body

        lines = [line.strip() for line in decoded.splitlines() if line.strip()]
        if not lines:
            print("Error: Subscription is empty.")
            return 1

        vless_count = sum(1 for ln in lines if ln.startswith("vless://"))
        vmess_count = sum(1 for ln in lines if ln.startswith("vmess://"))

        if vless_count == 0 and vmess_count == 0:
            print("Error: No VLESS or VMess configs found.")
            return 1

        print(f"Success: Found {vless_count} VLESS and {vmess_count} VMess configs.")
        return 0
    except Exception as e:
        print(f"Canary check failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
