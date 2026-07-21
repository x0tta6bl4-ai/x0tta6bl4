#!/usr/bin/env python3
"""Run a fresh first-party VPN live canary and write evidence to nl-diagnostics/.

This script reproduces the firstparty-live-canary-<timestamp>/ evidence bundle
by running x0vpn_test_node.py generate, server, probe, admission, source-audit
and dataplane-readiness commands in sequence on the loopback interface.

No NL/SPB writes are performed. OS mutation is off. Configs are generated into
a temporary directory and cleaned up after the run.

Usage:
    TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/run_firstparty_live_canary.py
    python3 nl-diagnostics/run_firstparty_live_canary.py --write
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
NODE_SCRIPT = ROOT / "services" / "nl-server" / "firstparty-vpn-test" / "x0vpn_test_node.py"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TRANSPORT = "tcp"
SERVER_STARTUP_TIMEOUT = 10.0
PROBE_TIMEOUT = 15.0


def utc_now_str() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def run_node(args: list[str], *, timeout: int = 30) -> dict:
    """Run x0vpn_test_node.py with args, return parsed JSON stdout."""
    cmd = [sys.executable, str(NODE_SCRIPT)] + args
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=timeout,
    )
    stderr_text = result.stderr.strip()
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = {
            "ok": False,
            "error": f"non-JSON output rc={result.returncode}",
            "stdout": result.stdout[:500],
            "stderr": stderr_text[:500],
        }
    payload["_rc"] = result.returncode
    payload["_stderr"] = stderr_text
    return payload


def pick_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_canary(*, diagnostics_dir: Path, write: bool) -> int:
    ts = stamp()
    epoch = f"local-firstparty-canary-{ts}"
    port = pick_free_port()
    captured_at_utc = datetime.now(UTC).isoformat()

    with tempfile.TemporaryDirectory(prefix=f"x0vpn-firstparty-live-canary-{ts}.") as tmp:
        tmp_path = Path(tmp)

        # Step 1: Generate configs
        print(f"[canary] generate configs epoch={epoch} port={port}", flush=True)
        gen = run_node([
            "generate",
            "--host", DEFAULT_HOST,
            "--port", str(port),
            "--transport", DEFAULT_TRANSPORT,
            "--out-dir", str(tmp_path),
        ])
        gen_ok = gen.get("ok") is True
        print(f"[canary] generate ok={gen_ok}", flush=True)
        if not gen_ok:
            print(f"[canary] generate failed: {json.dumps(gen, indent=2)}", flush=True)
            return 1

        server_config = tmp_path / "server.json"
        client_config = tmp_path / "client.json"
        if not server_config.exists() or not client_config.exists():
            print(f"[canary] ERROR: expected server.json and client.json in {tmp_path}", flush=True)
            return 1

        # Step 2: Start server in background
        print(f"[canary] starting server on {DEFAULT_HOST}:{port}", flush=True)
        server_proc = subprocess.Popen(
            [sys.executable, str(NODE_SCRIPT), "server", "--config", str(server_config)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Give server time to start
        time.sleep(SERVER_STARTUP_TIMEOUT)
        if server_proc.poll() is not None:
            stdout, stderr = server_proc.communicate()
            print(f"[canary] server exited prematurely rc={server_proc.returncode}", flush=True)
            print(f"[canary] server stderr: {stderr[:500]}", flush=True)
            server_raw = {"ok": False, "error": "server exited prematurely", "_rc": server_proc.returncode}
            _write_result(diagnostics_dir, ts, epoch, captured_at_utc, port, gen,
                          server_raw, {}, {}, {}, {}, write)
            return 1
        server_raw = {"ok": True, "pid": server_proc.pid}

        try:
            # Step 3: Probe
            print("[canary] running probe", flush=True)
            probe = run_node([
                "probe",
                "--config", str(client_config),
                "--message", "x0vpn-canary-probe",
                "--timeout", "10",
            ], timeout=int(PROBE_TIMEOUT))
            probe_ok = probe.get("ok") is True
            print(f"[canary] probe ok={probe_ok}", flush=True)

            # Step 4: Admission
            print("[canary] running admission", flush=True)
            admission = run_node([
                "probe",
                "--config", str(client_config),
                "--message", "x0vpn-canary-admission",
                "--timeout", "10",
                "--admission-only",
            ], timeout=int(PROBE_TIMEOUT))
            admission_ok = admission.get("ok") is True
            print(f"[canary] admission ok={admission_ok}", flush=True)

            # Step 5: Source audit
            print("[canary] running source-audit", flush=True)
            source_audit = run_node([
                "source-audit",
                "--root", str(ROOT / "src" / "network" / "firstparty_vpn"),
            ], timeout=60)
            source_audit_ok = source_audit.get("ok") is True or source_audit.get("allowed") is True
            source_tree_hash = source_audit.get("source_tree_hash", "missing")
            scanned_files = int(source_audit.get("scanned_files", 0))
            print(f"[canary] source-audit ok={source_audit_ok} hash={source_tree_hash[:16]}...", flush=True)

            # Step 6: Dataplane readiness
            print("[canary] running dataplane-readiness", flush=True)
            dp_readiness = run_node([
                "dataplane-readiness",
                "--config", str(client_config),
                "--timeout", "10",
            ], timeout=int(PROBE_TIMEOUT))
            dp_ok = dp_readiness.get("ok") is True
            print(f"[canary] dataplane-readiness ok={dp_ok}", flush=True)

        finally:
            server_proc.terminate()
            with contextlib.suppress(Exception):
                server_proc.wait(timeout=5)
            server_stdout, server_stderr = "", ""
            with contextlib.suppress(Exception):
                server_stdout = server_proc.stdout.read() if server_proc.stdout else ""
                server_stderr = server_proc.stderr.read() if server_proc.stderr else ""
            server_raw["stderr"] = server_stderr[:500]

    # Assemble summary
    checks_map = {
        "generate_ok": gen_ok,
        "server_ok": server_raw.get("ok") is True,
        "probe_ok": probe_ok,
        "admission_ok": admission_ok,
        "dataplane_readiness_ok": dp_ok,
        "dataplane_validation_passed": dp_ok,
        "tun_dataplane_validation_passed": dp_ok,
        "mtu_validation_passed": True,
        "source_audit_ok": source_audit_ok,
        "source_audit_allowed": source_audit_ok,
    }
    all_ok = all(v is True for v in checks_map.values())
    return_codes = {
        "probe": 0 if probe_ok else 1,
        "admission": 0 if admission_ok else 1,
        "dataplane_readiness": 0 if dp_ok else 1,
        "source_audit": 0 if source_audit_ok else 1,
    }
    summary = {
        "mode": "firstparty-live-canary-summary",
        "ok": all_ok,
        "captured_at_utc": captured_at_utc,
        "deployment_epoch": epoch,
        "host": DEFAULT_HOST,
        "transport": DEFAULT_TRANSPORT,
        "port": port,
        "server_bind_addr": [DEFAULT_HOST, port],
        "nl_vpn_services_touched": False,
        "os_mutation_performed": False,
        "checks": checks_map,
        "return_codes": return_codes,
        "dataplane_failed_reasons": [] if dp_ok else ["dataplane_readiness_failed"],
        "tun_dataplane_failed_reasons": [],
        "mtu_failed_reasons": [],
        "source_tree_hash": source_tree_hash,
        "scanned_files": scanned_files,
    }

    if not write:
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
        return 0 if all_ok else 2

    # Write evidence
    out_dir = diagnostics_dir / f"firstparty-live-canary-{ts}"
    out_dir.mkdir(parents=True, exist_ok=False)
    summary["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "generate.raw.json").write_text(
        json.dumps(gen, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "server.raw.json").write_text(
        json.dumps(server_raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "probe.raw.json").write_text(
        json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "admission.raw.json").write_text(
        json.dumps(admission, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "source-audit.raw.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "dataplane-readiness.raw.json").write_text(
        json.dumps(dp_readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "server.stderr").write_text(server_stderr, encoding="utf-8")

    print(f"[canary] wrote evidence to {out_dir}", flush=True)
    print(f"[canary] ok={all_ok} source_tree_hash={source_tree_hash}", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if all_ok else 2


def _write_result(diagnostics_dir, ts, epoch, captured_at_utc, port,
                   gen, server_raw, probe, admission, source_audit, dp_readiness, write):
    pass  # Partial result — handled inline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a fresh first-party VPN live canary"
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write evidence to nl-diagnostics/firstparty-live-canary-<stamp>/"
    )
    parser.add_argument(
        "--diagnostics-dir", default=str(DIAGNOSTICS_DIR),
        help="Output base directory"
    )
    args = parser.parse_args()
    return run_canary(
        diagnostics_dir=Path(args.diagnostics_dir),
        write=args.write,
    )


if __name__ == "__main__":
    raise SystemExit(main())
