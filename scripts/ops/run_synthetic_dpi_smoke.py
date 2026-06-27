#!/usr/bin/env python3
"""Run an intentionally synthetic, local-only DPI smoke test.

This checks only that the reporting mechanics can distinguish a blocked path
from a reachable path. It does not perform an external DPI probe and cannot
satisfy the external-dpi-proof-missing production gap.
"""

from __future__ import annotations

import argparse
import http.server
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from socketserver import ThreadingTCPServer
from typing import Any


DEFAULT_OUTPUT = ".tmp/validation-shards/synthetic-dpi-smoke-current.json"


class _SyntheticDpiHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/blocked":
            self.send_response(451)
            body = b"SYNTHETIC_BLOCKED"
        else:
            self.send_response(200)
            body = b"OK"
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class _ReusableTcpServer(ThreadingTCPServer):
    allow_reuse_address = True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a synthetic local-only DPI smoke test.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def run_probe(url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = int(response.status)
            response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    except OSError as exc:
        return {"reachable": False, "http_status": None, "error": exc.__class__.__name__}
    return {"reachable": status == 200, "http_status": status, "error": None}


def build_report(*, output_path: Path, port: int = 0) -> dict[str, Any]:
    with _ReusableTcpServer(("127.0.0.1", port), _SyntheticDpiHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, bound_port = server.server_address
            baseline_url = f"http://{host}:{bound_port}/blocked"
            treatment_url = f"http://{host}:{bound_port}/treatment"
            baseline = run_probe(baseline_url)
            treatment = run_probe(treatment_url)
        finally:
            server.shutdown()
            thread.join(timeout=2.0)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mechanics_verified = baseline["http_status"] == 451 and treatment["reachable"] is True
    return {
        "artifact_identity": {
            "artifact_id": f"synthetic-dpi-smoke-{timestamp.replace(':', '').replace('-', '')}",
            "captured_at_utc": timestamp,
            "claim_id": "synthetic_dpi_smoke",
            "schema_version": "x0tta6bl4.synthetic_dpi_smoke.v1",
        },
        "claim_boundary": {
            "customer_traffic_confirmed": False,
            "durable_censorship_bypass_confirmed": False,
            "external_dpi_tested": False,
            "limitations": [
                "Uses loopback-only HTTP endpoints on 127.0.0.1.",
                "Does not transit external network boundaries.",
                "Does not encounter real DPI or middleboxes.",
                "Does not satisfy external-dpi-proof-missing.",
            ],
            "production_ready": False,
            "summary": "This is a synthetic local-only smoke test.",
        },
        "measurements": {
            "baseline": baseline,
            "baseline_url": baseline_url,
            "output_path": str(output_path),
            "treatment": treatment,
            "treatment_url": treatment_url,
        },
        "result_summary": {
            "decision": "SYNTHETIC_SMOKE_PASS" if mechanics_verified else "SYNTHETIC_SMOKE_FAIL",
            "mechanics_verified": mechanics_verified,
        },
        "status": "SYNTHETIC_TEST_ONLY",
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)
    report = build_report(output_path=output_path, port=args.port)
    write_report(report, output_path)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        decision = report["result_summary"]["decision"]
        print(f"Synthetic smoke test complete. Decision: {decision}")
        print(f"Report written to: {output_path}")
        print(
            "NOTE: this synthetic artifact does not satisfy "
            "external-dpi-proof-missing."
        )
    return 0 if report["result_summary"]["mechanics_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
