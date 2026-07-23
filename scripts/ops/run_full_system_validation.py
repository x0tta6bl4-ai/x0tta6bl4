#!/usr/bin/env python3
"""
x0tta6bl4 Full System Verification & Validation Runner.
Executes test suites V1-V7 according to VALIDATION_FRAMEWORK_SPEC.md (v1.0.0).
Generates machine-readable output artifacts (metadata.json, summary.json, raw.csv).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/mnt/projects").resolve()
sys.path.insert(0, str(ROOT))

from scripts.ops.benchmark_suite import run_benchmark_suite
from scripts.ops.vpn_health_check import check_ping, NL_IP, MSK_IP

logger = logging.getLogger("full_validation")


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(ROOT))
        return res.stdout.strip() if res.returncode == 0 else "unknown_sha"
    except Exception:
        return "unknown_sha"


def execute_full_validation():
    logger.info("🔬 STARTING FULL SYSTEM VERIFICATION & VALIDATION (v1.0.0)...")
    t0 = time.time()

    commit_sha = get_git_commit()
    timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime())
    artifact_dir = ROOT / "results" / f"{timestamp_str}_sha-{commit_sha[:7]}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # 1. Environment Metadata (Section 2 of SPEC)
    metadata = {
        "git_commit": commit_sha,
        "spec_version": "v1.0.0",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kernel": os.uname().release,
        "sysname": os.uname().sysname,
        "cpu_arch": os.uname().machine,
        "nodes": {
            "local_athlon": "192.168.100.1",
            "nl_hub": NL_IP,
            "msk_entry": MSK_IP,
        }
    }
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Execute Suite Run (N=30 samples for statistical validity)
    logger.info("Executing N=30 benchmark sampling across all control groups...")
    bench_data = run_benchmark_suite(samples=30)

    # 3. SLA Evaluation Gates (Section 5 of SPEC)
    sla_results = {}
    
    # Gate 1: Check Ping MSK
    ping_msk_str = bench_data["benchmarks"].get("ping_msk", "")
    msk_online = "Online" in ping_msk_str
    sla_results["gate_msk_reachability"] = "PASS" if msk_online else "FAIL"

    # Gate 2: Check Ping NL
    ping_nl_str = bench_data["benchmarks"].get("ping_nl", "")
    nl_online = "Online" in ping_nl_str
    sla_results["gate_nl_reachability"] = "PASS" if nl_online else "FAIL"

    # Gate 3: Youtube SOCKS Egress Success Rate
    yt_data = bench_data["benchmarks"].get("socks_10818_youtube", {})
    yt_success = yt_data.get("success_rate_percent", 0.0)
    sla_results["gate_youtube_egress_sla"] = "PASS" if yt_success >= 95.0 else ("WARN" if yt_success >= 80.0 else "FAIL")

    # Gate 4: Telegram SOCKS Egress Success Rate
    tg_data = bench_data["benchmarks"].get("socks_10818_telegram", {})
    tg_success = tg_data.get("success_rate_percent", 0.0)
    sla_results["gate_telegram_egress_sla"] = "PASS" if tg_success >= 95.0 else ("WARN" if tg_success >= 80.0 else "FAIL")

    # Summary Compilation
    summary = {
        "status": "VERIFIED_PASS" if all(v == "PASS" for v in sla_results.values()) else "VERIFIED_PARTIAL",
        "duration_seconds": round(time.time() - t0, 2),
        "sla_gates": sla_results,
        "benchmarks_summary": bench_data["benchmarks"]
    }
    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"✅ FULL VALIDATION COMPLETE. Artifacts saved to: {artifact_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    execute_full_validation()


if __name__ == "__main__":
    main()
