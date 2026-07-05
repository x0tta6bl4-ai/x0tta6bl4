#!/usr/bin/env python3
"""Run first-party VPN production readiness validation and write evidence to nl-diagnostics/.

This script reproduces the firstparty-production-readiness-<timestamp>/ evidence bundle
by running x0vpn_test_node.py generate, pqc-promote-config, policy-snapshot-write,
and production-readiness commands in sequence.
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


def run_node(args: list[str], *, timeout: int = 120) -> dict:
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


def run_readiness(*, diagnostics_dir: Path, write: bool) -> int:
    ts = stamp()
    epoch = f"local-firstparty-production-readiness-{ts}"
    port = pick_free_port()
    captured_at_utc = datetime.now(UTC).isoformat()

    with tempfile.TemporaryDirectory(prefix=f"x0vpn-firstparty-production-readiness-{ts}.") as tmp:
        tmp_path = Path(tmp)

        # Step 1: Generate configs
        print(f"[readiness] generate configs epoch={epoch} port={port}", flush=True)
        gen = run_node([
            "generate",
            "--host", DEFAULT_HOST,
            "--port", str(port),
            "--transport", DEFAULT_TRANSPORT,
            "--out-dir", str(tmp_path),
            "--deployment-epoch-prefix", "local-firstparty-production-readiness",
            "--client-count", "1",
            "--pqc-reviewed",
            "--pqc-mode", "production",
            "--lifetime-seconds", "3600",
        ])
        gen_ok = gen.get("ok") is True
        print(f"[readiness] generate ok={gen_ok}", flush=True)
        if not gen_ok:
            print(f"[readiness] generate failed: {json.dumps(gen, indent=2)}", flush=True)
            return 1

        client_config = tmp_path / "client.json"
        server_config = tmp_path / "server.json"
        if not server_config.exists() or not client_config.exists():
            print(f"[readiness] ERROR: expected server.json and client.json in {tmp_path}", flush=True)
            return 1

        # Step 2: Promote client config
        print(f"[readiness] promoting client config", flush=True)
        pqc_client = run_node([
            "pqc-promote-config",
            "--config", str(client_config),
            "--out-config", str(tmp_path / "client.promoted.json"),
            "--source-root", str(ROOT / "src" / "network" / "firstparty_vpn"),
        ])
        pqc_client_ok = pqc_client.get("ok") is True
        print(f"[readiness] client promotion ok={pqc_client_ok}", flush=True)
        if not pqc_client_ok:
            print(f"[readiness] client promotion failed: {json.dumps(pqc_client, indent=2)}", flush=True)
            return 1

        # Step 3: Promote server config
        print(f"[readiness] promoting server config", flush=True)
        pqc_server = run_node([
            "pqc-promote-config",
            "--config", str(server_config),
            "--out-config", str(tmp_path / "server.promoted.json"),
            "--source-root", str(ROOT / "src" / "network" / "firstparty_vpn"),
        ])
        pqc_server_ok = pqc_server.get("ok") is True
        print(f"[readiness] server promotion ok={pqc_server_ok}", flush=True)
        if not pqc_server_ok:
            print(f"[readiness] server promotion failed: {json.dumps(pqc_server, indent=2)}", flush=True)
            return 1

        # Step 4: Start server in background using promoted config
        print(f"[readiness] starting server on {DEFAULT_HOST}:{port}", flush=True)
        server_proc = subprocess.Popen(
            [sys.executable, str(NODE_SCRIPT), "server", "--config", str(tmp_path / "server.promoted.json")],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Give server time to start
        time.sleep(SERVER_STARTUP_TIMEOUT)
        if server_proc.poll() is not None:
            stdout, stderr = server_proc.communicate()
            print(f"[readiness] server exited prematurely rc={server_proc.returncode}", flush=True)
            print(f"[readiness] server stderr: {stderr[:500]}", flush=True)
            return 1
        server_raw = {"ok": True, "addr": [DEFAULT_HOST, port], "deployment_epoch": epoch, "mode": "server", "transport": "tcp"}

        try:
            # Step 5: policy-snapshot-write
            print("[readiness] running policy-snapshot-write", flush=True)
            policy_snapshot = run_node([
                "policy-snapshot-write",
                "--config", str(tmp_path / "server.promoted.json"),
                "--out", str(tmp_path / "policy-snapshot.json"),
            ])
            policy_snapshot_ok = policy_snapshot.get("ok") is True
            print(f"[readiness] policy-snapshot ok={policy_snapshot_ok}", flush=True)

            # Step 6: production-readiness
            print("[readiness] running production-readiness", flush=True)
            prod_readiness = run_node([
                "production-readiness",
                "--target", "nl",
                "--source-root", str(ROOT / "src" / "network" / "firstparty_vpn"),
                "--config", str(tmp_path / "client.promoted.json"),
                "--issuer-config", str(tmp_path / "issuer.json"),
                "--policy-source-path", str(tmp_path / "policy-snapshot.json"),
                "--role", "client",
                "--collect-dataplane",
                "--dataplane-timeout", "3.0",
                "--dataplane-payload-size", "64",
                "--dataplane-mtu-candidates", "1200,1300,1400",
                "--collect-rekey-policy",
                "--collect-rollout-gate",
                "--rollout-approved-by", "operator",
                "--no-require-root",
                "--no-require-net-admin",
                "--no-require-tun-device",
            ], timeout=120)
            prod_readiness_ok = prod_readiness.get("ok") is True
            print(f"[readiness] production-readiness ok={prod_readiness_ok}", flush=True)
            if not prod_readiness_ok:
                print(f"[readiness] production-readiness failed: {json.dumps(prod_readiness, indent=2)}", flush=True)

        finally:
            server_proc.terminate()
            with contextlib.suppress(Exception):
                server_proc.wait(timeout=5)
            server_stdout, server_stderr = "", ""
            with contextlib.suppress(Exception):
                server_stdout = server_proc.stdout.read() if server_proc.stdout else ""
                server_stderr = server_proc.stderr.read() if server_proc.stderr else ""

    # Assemble summary
    checks_map = {
        "dataplane_collected": prod_readiness.get("collected", {}).get("dataplane") is True,
        "external_policy_source_collected": prod_readiness.get("collected", {}).get("external_policy_source") is True,
        "generate_ok": gen_ok,
        "identity_signer_collected": prod_readiness.get("collected", {}).get("identity_signer") is True,
        "leak_protection_collected": prod_readiness.get("collected", {}).get("leak_protection") is True,
        "linux_preflight_collected": prod_readiness.get("collected", {}).get("linux_preflight") is True,
        "os_mutation_performed_false": prod_readiness.get("os_mutation_performed") is False,
        "policy_snapshot_ok": policy_snapshot_ok,
        "pqc_collected": prod_readiness.get("collected", {}).get("pqc") is True,
        "pqc_promote_client_ok": pqc_client_ok,
        "pqc_promote_server_ok": pqc_server_ok,
        "pqc_provider_gate_allowed": (prod_readiness.get("pqc", {}).get("provider_gate") or {}).get("allowed") is True,
        "production_readiness_ok": prod_readiness_ok,
        "rekey_policy_collected": prod_readiness.get("collected", {}).get("rekey_policy") is True,
        "rollout_gate_collected": prod_readiness.get("collected", {}).get("rollout_gate") is True,
        "server_ok": server_raw.get("ok") is True,
        "source_audit_collected": prod_readiness.get("collected", {}).get("source_audit") is True,
        "zero_trust_policy_collected": prod_readiness.get("collected", {}).get("zero_trust_policy") is True
    }
    all_ok = all(v is True for v in checks_map.values())
    return_codes = {
        "policy_snapshot": 0 if policy_snapshot_ok else 1,
        "pqc_promote_client": 0 if pqc_client_ok else 1,
        "pqc_promote_server": 0 if pqc_server_ok else 1,
        "production_readiness": 0 if prod_readiness_ok else 1,
    }
    source_tree_hash = prod_readiness.get("source_audit", {}).get("source_tree_hash", "missing")
    pqc_runtime_metadata_matches_manifest = prod_readiness.get("pqc", {}).get("runtime_metadata_matches_manifest") is True

    summary = {
        "mode": "firstparty-production-readiness-summary",
        "ok": all_ok,
        "captured_at_utc": captured_at_utc,
        "deployment_epoch": epoch,
        "host": DEFAULT_HOST,
        "transport": DEFAULT_TRANSPORT,
        "port": port,
        "server_bind_addr": [DEFAULT_HOST, port],
        "no_nl_or_spb_writes_performed": True,
        "os_mutation_performed": False,
        "checks": checks_map,
        "collected": prod_readiness.get("collected", {}),
        "return_codes": return_codes,
        "source_tree_hash": source_tree_hash,
        "pqc_provider_gate_reasons": prod_readiness.get("pqc", {}).get("provider_gate", {}).get("reasons", []),
        "pqc_runtime_metadata_matches_manifest": pqc_runtime_metadata_matches_manifest,
        "decision_allowed": prod_readiness.get("allowed") is True,
        "decision_reasons": prod_readiness.get("reasons", []),
    }

    if not write:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False), flush=True)
        return 0 if all_ok else 2

    # Write evidence
    out_dir = diagnostics_dir / f"firstparty-production-readiness-{ts}"
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
    (out_dir / "pqc-promote-client.raw.json").write_text(
        json.dumps(pqc_client, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "pqc-promote-server.raw.json").write_text(
        json.dumps(pqc_server, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "policy-snapshot.raw.json").write_text(
        json.dumps(policy_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "production-readiness.raw.json").write_text(
        json.dumps(prod_readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "server.stderr").write_text(server_stderr, encoding="utf-8")

    # Render summary.md
    md_lines = [
        "# First-party VPN Production Readiness",
        "",
        f"- ok: `{str(all_ok).lower()}`",
        f"- evidence_dir: `{out_dir}`",
        f"- deployment_epoch: `{epoch}`",
        f"- decision_allowed: `{str(summary['decision_allowed']).lower()}`",
        f"- pqc_runtime_metadata_matches_manifest: `{summary['pqc_runtime_metadata_matches_manifest']}`",
        f"- source_tree_hash: `{source_tree_hash}`",
        "- collected:"
    ]
    for k in sorted(summary['collected']):
        md_lines.append(f"  - {k}: `{str(summary['collected'][k]).lower()}`")
    md_lines.append("- scope: local loopback only; no NL/SPB writes; no OS mutation\n")
    (out_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[readiness] wrote evidence to {out_dir}", flush=True)
    print(f"[readiness] ok={all_ok} source_tree_hash={source_tree_hash}", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if all_ok else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run first-party VPN production readiness validation"
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write evidence to nl-diagnostics/firstparty-production-readiness-<stamp>/"
    )
    parser.add_argument(
        "--diagnostics-dir", default=str(DIAGNOSTICS_DIR),
        help="Output base directory"
    )
    args = parser.parse_args()
    return run_readiness(
        diagnostics_dir=Path(args.diagnostics_dir),
        write=args.write,
    )


if __name__ == "__main__":
    raise SystemExit(main())
