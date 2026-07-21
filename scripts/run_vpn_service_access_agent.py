#!/usr/bin/env python3
"""
Long-running monitoring agent that checks VPN service accessibility.
"""
from __future__ import annotations

import argparse
import socket
import ssl
import sys
import time

try:
    from prometheus_client import Gauge, start_http_server
except ImportError:
    start_http_server = None
    Gauge = None

VPN_UP = Gauge("vpn_service_up", "VPN service accessibility status") if Gauge else None
CERT_VALID_DAYS = Gauge("vpn_cert_valid_days", "Days until TLS cert expires") if Gauge else None

def check_dns(target: str) -> bool:
    try:
        socket.gethostbyname(target)
        return True
    except OSError:
        return False

def check_tls(target: str, port: int = 443) -> float:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((target, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=target) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return -1
                not_after = ssl.cert_time_to_seconds(cert["notAfter"])
                return (not_after - time.time()) / 86400.0
    except Exception:
        return -1.0

def main() -> int:
    parser = argparse.ArgumentParser(description="VPN Access Agent")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--target", required=True, help="Target host to check")
    parser.add_argument("--metrics-port", type=int, default=8000, help="Prometheus metrics port")
    args = parser.parse_args()

    if start_http_server:
        start_http_server(args.metrics_port)
        print(f"Started metrics on port {args.metrics_port}")
    else:
        print("Warning: prometheus_client not installed, metrics disabled.")

    print(f"Monitoring {args.target} every {args.interval} seconds...")
    try:
        while True:
            dns_ok = check_dns(args.target)
            tls_days = check_tls(args.target)

            is_up = dns_ok and tls_days > 0
            if VPN_UP:
                VPN_UP.set(1 if is_up else 0)
            if CERT_VALID_DAYS:
                CERT_VALID_DAYS.set(tls_days if tls_days > 0 else 0)

            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DNS: {'OK' if dns_ok else 'FAIL'}, "
                  f"TLS Valid Days: {tls_days:.1f}, Status: {'UP' if is_up else 'DOWN'}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopping agent.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
