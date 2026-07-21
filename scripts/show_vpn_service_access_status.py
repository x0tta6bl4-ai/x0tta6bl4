#!/usr/bin/env python3
"""
One-shot status reporter for VPN service health.
"""
from __future__ import annotations

import argparse
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Show VPN service access status")
    parser.add_argument("--metrics-url", default="http://localhost:8000/metrics", help="URL to metrics")
    args = parser.parse_args()

    try:
        req = Request(args.metrics_url)
        with urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")

        up_status = "UNKNOWN"
        cert_days = "UNKNOWN"
        for line in data.splitlines():
            if line.startswith("vpn_service_up "):
                val = float(line.split()[1])
                up_status = "HEALTHY" if val == 1 else "DOWN"
            elif line.startswith("vpn_cert_valid_days "):
                val = float(line.split()[1])
                cert_days = f"{val:.1f} days"

        print("=== VPN Service Health ===")
        print(f"Status     : {up_status}")
        print(f"TLS Cert   : {cert_days}")
        print("==========================")
        return 0 if up_status == "HEALTHY" else 1
    except URLError as e:
        print(f"Failed to fetch metrics from {args.metrics_url}: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
