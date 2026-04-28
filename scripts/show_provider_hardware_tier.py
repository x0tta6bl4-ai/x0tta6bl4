#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_RESULTS_DIR = Path("/mnt/projects/ebpf/prod/results")

GOLD_DRIVERS = {"ice", "mlx5_core"}
SILVER_DRIVERS = {"i40e", "ixgbe", "bnxt_en", "mlx4_en"}
STANDARD_DRIVERS = {"igb", "virtio_net", "vmxnet3"}
LIMITED_DRIVERS = {"r8169", "e1000", "e1000e"}


@dataclass
class TierProfile:
    tier: str
    af_xdp_zero_copy_ready: bool
    hardware_limited: bool
    reason: str


def run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
        timeout=5,
    )
    return (completed.stdout or "").strip()


def detect_default_iface() -> str:
    output = run_command(["ip", "route", "show", "default"])
    for line in output.splitlines():
        parts = line.split()
        if "dev" in parts:
            try:
                return parts[parts.index("dev") + 1]
            except (ValueError, IndexError):
                continue
    return "eth0"


def detect_driver(iface: str) -> str:
    output = run_command(["ethtool", "-i", iface])
    for line in output.splitlines():
        if line.startswith("driver:"):
            return line.split(":", 1)[1].strip()
    driver_link = Path(f"/sys/class/net/{iface}/device/driver")
    if driver_link.exists():
        return driver_link.resolve().name
    return "unknown"


def detect_speed(iface: str) -> str:
    output = run_command(["ethtool", iface])
    for line in output.splitlines():
        if line.strip().startswith("Speed:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def detect_operstate(iface: str) -> str:
    path = Path(f"/sys/class/net/{iface}/operstate")
    if not path.exists():
        return "unknown"
    return path.read_text(encoding="utf-8").strip() or "unknown"


def classify_driver(driver: str) -> TierProfile:
    normalized = (driver or "").strip().lower()
    if normalized in GOLD_DRIVERS:
        return TierProfile(
            tier="gold",
            af_xdp_zero_copy_ready=True,
            hardware_limited=False,
            reason="top-tier NIC class for AF_XDP zero-copy benchmarking",
        )
    if normalized in SILVER_DRIVERS:
        return TierProfile(
            tier="silver",
            af_xdp_zero_copy_ready=True,
            hardware_limited=False,
            reason="high-throughput NIC class; benchmark still required for real claim",
        )
    if normalized in STANDARD_DRIVERS:
        return TierProfile(
            tier="standard",
            af_xdp_zero_copy_ready=False,
            hardware_limited=False,
            reason="serviceable for normal traffic, but not a zero-copy target by default",
        )
    if normalized in LIMITED_DRIVERS:
        return TierProfile(
            tier="limited",
            af_xdp_zero_copy_ready=False,
            hardware_limited=True,
            reason="known low-PPS or generic-XDP-limited NIC family",
        )
    return TierProfile(
        tier="unknown",
        af_xdp_zero_copy_ready=False,
        hardware_limited=False,
        reason="driver not in current capability table; benchmark evidence required",
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def pick_benchmark(results_dir: Path, benchmark_json: Path | None, iface: str) -> tuple[dict[str, Any], str]:
    if benchmark_json is not None:
        payload = load_json(benchmark_json)
        return payload, str(benchmark_json)

    if not results_dir.exists():
        return {}, ""

    candidates = sorted(results_dir.glob("benchmark*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return {}, ""

    for candidate in candidates:
        payload = load_json(candidate)
        if payload.get("iface") == iface:
            return payload, str(candidate)

    payload = load_json(candidates[0])
    return payload, str(candidates[0])


def benchmark_status(benchmark: dict[str, Any], iface: str) -> tuple[str, str]:
    if not benchmark:
        return "not_benchmarked", "no benchmark evidence found"

    benchmark_iface = str(benchmark.get("iface") or "")
    if benchmark_iface and benchmark_iface != iface:
        return "iface_mismatch", f"latest benchmark is for iface={benchmark_iface}, not iface={iface}"

    measured = benchmark.get("measured_pps")
    target = benchmark.get("target_pps")
    passed = benchmark.get("pass")
    if passed is True:
        return "meets_target", f"benchmark passed with measured_pps={measured} target_pps={target}"
    if measured is not None and target is not None:
        return "below_target", f"benchmark below target: measured_pps={measured} target_pps={target}"
    return "benchmark_present", "benchmark exists but is missing target/measured summary"


def build_payload(
    *,
    iface: str,
    driver: str,
    speed: str,
    operstate: str,
    benchmark: dict[str, Any],
    benchmark_source: str,
) -> dict[str, Any]:
    tier_profile = classify_driver(driver)
    empirical_status, empirical_note = benchmark_status(benchmark, iface)

    if empirical_status == "meets_target":
        verdict = "validated_high_pps"
    elif empirical_status == "below_target" and tier_profile.hardware_limited:
        verdict = "hardware_limited"
    elif empirical_status == "below_target":
        verdict = "benchmark_failed"
    elif empirical_status == "iface_mismatch":
        verdict = "benchmark_iface_mismatch"
    elif tier_profile.af_xdp_zero_copy_ready:
        verdict = "candidate_for_zero_copy_benchmark"
    elif tier_profile.hardware_limited:
        verdict = "standard_only"
    else:
        verdict = "needs_manual_review"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "iface": iface,
        "driver": driver,
        "speed": speed,
        "operstate": operstate,
        "hardware_tier": tier_profile.tier,
        "af_xdp_zero_copy_ready": tier_profile.af_xdp_zero_copy_ready,
        "hardware_limited": tier_profile.hardware_limited,
        "hardware_reason": tier_profile.reason,
        "benchmark_source": benchmark_source or None,
        "benchmark_iface": benchmark.get("iface"),
        "benchmark_timestamp": benchmark.get("timestamp"),
        "measured_pps": benchmark.get("measured_pps"),
        "target_pps": benchmark.get("target_pps"),
        "benchmark_pass": benchmark.get("pass"),
        "empirical_status": empirical_status,
        "empirical_note": empirical_note,
        "verdict": verdict,
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = ["provider-hardware-tier status"]
    lines.append(
        "iface={iface} driver={driver} speed={speed} operstate={operstate}".format(
            iface=payload.get("iface") or "unknown",
            driver=payload.get("driver") or "unknown",
            speed=payload.get("speed") or "unknown",
            operstate=payload.get("operstate") or "unknown",
        )
    )
    lines.append(
        "tier={tier} zero_copy_ready={zero_copy} verdict={verdict}".format(
            tier=payload.get("hardware_tier") or "unknown",
            zero_copy="yes" if payload.get("af_xdp_zero_copy_ready") else "no",
            verdict=payload.get("verdict") or "unknown",
        )
    )
    lines.append(f"hardware_reason={payload.get('hardware_reason') or 'unknown'}")
    lines.append(
        "benchmark_status={status} measured_pps={measured} target_pps={target}".format(
            status=payload.get("empirical_status") or "unknown",
            measured=payload.get("measured_pps"),
            target=payload.get("target_pps"),
        )
    )
    lines.append(f"benchmark_note={payload.get('empirical_note') or 'unknown'}")
    if payload.get("benchmark_source"):
        lines.append(f"benchmark_source={payload['benchmark_source']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show provider hardware tier by combining NIC class and latest PPS benchmark evidence"
    )
    parser.add_argument("--iface", default=None)
    parser.add_argument("--driver", default=None, help="override detected NIC driver")
    parser.add_argument("--speed", default=None, help="override detected link speed")
    parser.add_argument("--operstate", default=None, help="override detected operstate")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--benchmark-json", type=Path, default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    iface = args.iface or detect_default_iface()
    driver = args.driver or detect_driver(iface)
    speed = args.speed or detect_speed(iface)
    operstate = args.operstate or detect_operstate(iface)
    benchmark, benchmark_source = pick_benchmark(args.results_dir, args.benchmark_json, iface)
    payload = build_payload(
        iface=iface,
        driver=driver,
        speed=speed,
        operstate=operstate,
        benchmark=benchmark,
        benchmark_source=benchmark_source,
    )

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
