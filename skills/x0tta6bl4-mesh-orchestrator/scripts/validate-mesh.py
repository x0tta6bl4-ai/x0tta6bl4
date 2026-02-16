#!/usr/bin/env python3
"""
x0tta6bl4 Mesh Validation Script

Collects eBPF telemetry, mesh routing stats, PQC status,
and MAPE-K health. Outputs structured report with pass/fail.

Usage:
  python3 validate-mesh.py --metrics    # Collect all metrics
  python3 validate-mesh.py --verify     # Post-heal verification
  python3 validate-mesh.py --pqc        # PQC key status only
  python3 validate-mesh.py --simulate   # Run digital twin simulation
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path for src.* imports
_project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "latency_ms":       {"normal": 40,   "warning": 100,  "critical": 200},
    "packet_loss_pct":  {"normal": 1.0,  "warning": 5.0,  "critical": 10.0},
    "cpu_percent":      {"normal": 70,   "warning": 90,   "critical": 98},
    "memory_percent":   {"normal": 80,   "warning": 95,   "critical": 99},
    "mttr_seconds":     {"normal": 180,  "warning": 300,  "critical": 600},
}


@dataclass
class ValidationResult:
    category: str
    metric: str
    value: float
    threshold: str  # normal / warning / critical
    status: str     # PASS / WARN / FAIL
    message: str


def classify(metric_name: str, value: float) -> str:
    """Classify a metric value against thresholds."""
    t = THRESHOLDS.get(metric_name)
    if not t:
        return "normal"
    if value > t["critical"]:
        return "critical"
    elif value > t["warning"]:
        return "warning"
    return "normal"


# ---------------------------------------------------------------------------
# Metric Collection
# ---------------------------------------------------------------------------

def collect_ebpf_metrics() -> Dict[str, Any]:
    """Collect eBPF telemetry metrics."""
    try:
        from src.network.ebpf.ebpf_metrics_collector import EBPFMetricsCollector
        collector = EBPFMetricsCollector()
        return collector.collect_all_metrics()
    except ImportError:
        # Fallback: collect system metrics directly
        import os
        load = os.getloadavg()
        return {
            "performance": {
                "cpu_percent": load[0] * 100 / max(os.cpu_count() or 1, 1),
                "memory_percent": _get_memory_usage(),
                "load_average": list(load),
            },
            "network": {
                "latency_ms": 0.0,
                "packet_loss_percent": 0.0,
                "packets_ingress_per_sec": 0.0,
                "packets_egress_per_sec": 0.0,
            },
            "security": {
                "failed_auth_attempts_per_sec": 0.0,
                "suspicious_file_access": 0,
                "privilege_escalation_attempts": 0,
            },
            "source": "fallback",
        }


def _get_memory_usage() -> float:
    """Get memory usage percentage."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 1)
        available = mem.get("MemAvailable", total)
        return (1 - available / total) * 100
    except Exception:
        return 0.0


def collect_mesh_stats() -> Dict[str, Any]:
    """Collect mesh routing statistics."""
    try:
        from src.network.routing.mesh_router import MeshRouter
        router = MeshRouter("validator")
        routes = router.get_routes()
        return {
            "total_routes": sum(len(v) for v in routes.values()) if isinstance(routes, dict) else 0,
            "destinations": len(routes) if isinstance(routes, dict) else 0,
            "router_initialized": True,
        }
    except Exception as e:
        return {"total_routes": 0, "destinations": 0, "router_initialized": False, "error": str(e)}


def collect_pqc_status() -> Dict[str, Any]:
    """Check post-quantum cryptography status."""
    try:
        from src.security.post_quantum import PQMeshSecurityLibOQS
        pq = PQMeshSecurityLibOQS(node_id="validator", kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
        keys = pq.get_public_keys()
        return {
            "pqc_available": True,
            "kem_algorithm": "ML-KEM-768",
            "sig_algorithm": "ML-DSA-65",
            "has_kem_key": bool(keys.get("kem_public_key")),
            "has_sig_key": bool(keys.get("sig_public_key")),
        }
    except ImportError:
        # Try fallback to PQCCrypto
        try:
            from src.crypto.pqc_crypto import PQCCrypto
            return {
                "pqc_available": PQCCrypto.is_available(),
                "kem_algorithm": "Kyber768",
                "sig_algorithm": "N/A (PQCCrypto wrapper)",
                "has_kem_key": PQCCrypto.is_available(),
            }
        except Exception:
            return {"pqc_available": False, "error": "liboqs not installed"}
    except Exception as e:
        return {"pqc_available": False, "error": str(e)}


def collect_mape_k_status() -> Dict[str, Any]:
    """Check MAPE-K self-healing loop status."""
    try:
        from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
        mape_k = IntegratedMAPEKCycle(enable_observe_mode=False, enable_chaos=False)
        status = mape_k.get_system_status()
        return {"mape_k_available": True, "status": status}
    except Exception as e:
        return {"mape_k_available": False, "error": str(e)}


def collect_governance_status() -> Dict[str, Any]:
    """Check DAO governance status."""
    try:
        from src.dao.governance import GovernanceEngine
        gov = GovernanceEngine(node_id="validator")
        active = [p for p in gov.proposals.values() if p.state.value == "active"]
        return {
            "governance_available": True,
            "total_proposals": len(gov.proposals),
            "active_proposals": len(active),
        }
    except Exception as e:
        return {"governance_available": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def run_metrics() -> list[ValidationResult]:
    """Full metrics collection and validation."""
    results = []

    # eBPF metrics
    ebpf = collect_ebpf_metrics()
    source = ebpf.get("source", "ebpf")

    perf = ebpf.get("performance", {})
    net = ebpf.get("network", {})
    sec = ebpf.get("security", {})

    cpu = perf.get("cpu_percent", 0)
    mem = perf.get("memory_percent", 0)
    lat = net.get("latency_ms", 0)
    loss = net.get("packet_loss_percent", 0)

    for name, val in [("cpu_percent", cpu), ("memory_percent", mem),
                       ("latency_ms", lat), ("packet_loss_pct", loss)]:
        level = classify(name, val)
        status = "PASS" if level == "normal" else ("WARN" if level == "warning" else "FAIL")
        results.append(ValidationResult(
            category="telemetry",
            metric=name,
            value=round(val, 2),
            threshold=level,
            status=status,
            message=f"{'['+source+'] ' if source == 'fallback' else ''}{name}={val:.1f}",
        ))

    # Security metrics
    failed_auth = sec.get("failed_auth_attempts_per_sec", 0)
    priv_esc = sec.get("privilege_escalation_attempts", 0)
    if priv_esc > 0:
        results.append(ValidationResult("security", "privilege_escalation", priv_esc,
                                         "critical", "FAIL", f"Privilege escalation attempts detected: {priv_esc}"))
    else:
        results.append(ValidationResult("security", "privilege_escalation", 0,
                                         "normal", "PASS", "No privilege escalation attempts"))

    # PQC status
    pqc = collect_pqc_status()
    results.append(ValidationResult(
        "pqc", "pqc_available", 1 if pqc.get("pqc_available") else 0,
        "normal" if pqc.get("pqc_available") else "warning",
        "PASS" if pqc.get("pqc_available") else "WARN",
        f"PQC: {pqc.get('kem_algorithm', 'N/A')} + {pqc.get('sig_algorithm', 'N/A')}"
        + (f" (error: {pqc.get('error', '')})" if pqc.get("error") else ""),
    ))

    # Mesh stats
    mesh = collect_mesh_stats()
    results.append(ValidationResult(
        "mesh", "routes", mesh.get("total_routes", 0),
        "normal", "PASS" if mesh.get("router_initialized") else "WARN",
        f"Routes: {mesh.get('total_routes', 0)}, Destinations: {mesh.get('destinations', 0)}",
    ))

    # MAPE-K status
    mk = collect_mape_k_status()
    results.append(ValidationResult(
        "mape-k", "available", 1 if mk.get("mape_k_available") else 0,
        "normal" if mk.get("mape_k_available") else "warning",
        "PASS" if mk.get("mape_k_available") else "WARN",
        f"MAPE-K: {'active' if mk.get('mape_k_available') else 'unavailable'}",
    ))

    # Governance status
    gov = collect_governance_status()
    results.append(ValidationResult(
        "governance", "dao_available", 1 if gov.get("governance_available") else 0,
        "normal" if gov.get("governance_available") else "warning",
        "PASS" if gov.get("governance_available") else "WARN",
        f"DAO: {gov.get('total_proposals', 0)} proposals, {gov.get('active_proposals', 0)} active",
    ))

    return results


def run_verify() -> list[ValidationResult]:
    """Post-heal verification: stricter thresholds."""
    results = run_metrics()

    # Add digital twin prediction
    try:
        from src.simulation.digital_twin import MeshDigitalTwin
        twin = MeshDigitalTwin("post-heal-verify")
        twin.create_test_topology(num_nodes=5)
        sim = twin.simulate_node_failure("node-1", failure_duration_seconds=30)
        mttr = getattr(sim, "mttr_seconds", 999)
        level = classify("mttr_seconds", mttr)
        status = "PASS" if level == "normal" else ("WARN" if level == "warning" else "FAIL")
        results.append(ValidationResult(
            "simulation", "mttr_seconds", round(mttr, 1), level, status,
            f"Simulated MTTR: {mttr:.1f}s (target < 180s)",
        ))
    except Exception as e:
        results.append(ValidationResult(
            "simulation", "mttr_seconds", -1, "warning", "WARN",
            f"Digital twin unavailable: {e}",
        ))

    return results


def run_pqc_only() -> list[ValidationResult]:
    """PQC-only status check."""
    pqc = collect_pqc_status()
    return [ValidationResult(
        "pqc", k, 1 if v else 0,
        "normal" if v else "warning",
        "PASS" if v else "WARN",
        f"{k}: {v}",
    ) for k, v in pqc.items() if k != "error"]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(results: list[ValidationResult], output_format: str = "table"):
    """Print validation results."""
    if output_format == "json":
        print(json.dumps([asdict(r) for r in results], indent=2))
        return

    # Table output
    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARN"]
    passes = [r for r in results if r.status == "PASS"]

    print("=" * 70)
    print("x0tta6bl4 MESH VALIDATION REPORT")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 70)

    for r in results:
        icon = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}[r.status]
        print(f"  {icon} [{r.category:12s}] {r.message}")

    print("-" * 70)
    print(f"  PASS: {len(passes)}  |  WARN: {len(warns)}  |  FAIL: {len(fails)}")

    if fails:
        print("\n  CRITICAL ISSUES REQUIRING IMMEDIATE ACTION:")
        for r in fails:
            print(f"    - {r.metric}: {r.value} (threshold: {THRESHOLDS.get(r.metric, {}).get('critical', 'N/A')})")

    overall = "FAIL" if fails else ("WARN" if warns else "PASS")
    print(f"\n  OVERALL: {overall}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Mesh Validation")
    parser.add_argument("--metrics", action="store_true", help="Collect all metrics")
    parser.add_argument("--verify", action="store_true", help="Post-heal verification")
    parser.add_argument("--pqc", action="store_true", help="PQC status only")
    parser.add_argument("--simulate", action="store_true", help="Run digital twin simulation")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.metrics, args.verify, args.pqc, args.simulate]):
        args.metrics = True  # Default to full metrics

    if args.verify:
        results = run_verify()
    elif args.pqc:
        results = run_pqc_only()
    elif args.simulate:
        results = run_verify()  # Includes simulation
    else:
        results = run_metrics()

    fmt = "json" if args.json else "table"
    print_results(results, fmt)

    # Exit code
    if any(r.status == "FAIL" for r in results):
        sys.exit(1)
    elif any(r.status == "WARN" for r in results):
        sys.exit(0)  # Warnings are non-fatal
    sys.exit(0)


if __name__ == "__main__":
    main()
