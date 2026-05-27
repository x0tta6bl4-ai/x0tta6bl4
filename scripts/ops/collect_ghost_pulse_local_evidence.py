#!/usr/bin/env python3
"""Collect local evidence for the experimental x0tta6bl4_pulse transport.

This collector is intentionally evidence-bounded:
- it only sends UDP packets over 127.0.0.1;
- it performs read-only kernel/eBPF inspection;
- it does not attach XDP programs, alter routes, submit transactions, or start
  long-running services;
- it never upgrades local timing evidence into DPI/whitelist/production claims.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
PULSE_SOURCE = ROOT / "src" / "network" / "ebpf" / "x0tta6bl4_pulse.bpf.c"
PULSE_OBJECT = ROOT / "src" / "network" / "ebpf" / "x0tta6bl4_pulse.o"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(args: list[str], timeout: float = 8.0) -> dict[str, Any]:
    if not shutil.which(args[0]):
        return {
            "args": args,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{args[0]} not found",
        }
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "args": args,
            "available": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "available": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
        }


def static_artifact_evidence() -> dict[str, Any]:
    obj_head = b""
    if PULSE_OBJECT.exists():
        obj_head = PULSE_OBJECT.read_bytes()[:4]

    evidence = {
        "source": {
            "path": str(PULSE_SOURCE.relative_to(ROOT)),
            "exists": PULSE_SOURCE.exists(),
            "size_bytes": PULSE_SOURCE.stat().st_size if PULSE_SOURCE.exists() else 0,
            "sha256": sha256_file(PULSE_SOURCE),
        },
        "object": {
            "path": str(PULSE_OBJECT.relative_to(ROOT)),
            "exists": PULSE_OBJECT.exists(),
            "size_bytes": PULSE_OBJECT.stat().st_size if PULSE_OBJECT.exists() else 0,
            "sha256": sha256_file(PULSE_OBJECT),
            "elf_magic": obj_head.hex(),
            "is_elf": obj_head == b"\x7fELF",
        },
        "file_command": run_cmd(["file", str(PULSE_OBJECT.relative_to(ROOT))]),
    }
    evidence["status"] = (
        "STATIC_OBJECT_PRESENT"
        if evidence["source"]["exists"] and evidence["object"]["is_elf"]
        else "STATIC_OBJECT_INCOMPLETE"
    )
    return evidence


def kernel_read_only_evidence() -> dict[str, Any]:
    bpftool_map = run_cmd(["bpftool", "map", "show", "name", "pulse_stats"])
    bpftool_prog = run_cmd(["bpftool", "prog", "show"])
    bpftool_net = run_cmd(["bpftool", "net"])
    ip_links = run_cmd(["ip", "-j", "link", "show"])

    xdp_links: list[dict[str, Any]] = []
    if ip_links.get("returncode") == 0 and ip_links.get("stdout"):
        try:
            for link in json.loads(ip_links["stdout"]):
                xdp = link.get("xdp")
                if xdp:
                    xdp_links.append({"ifname": link.get("ifname"), "xdp": xdp})
        except json.JSONDecodeError:
            xdp_links = []

    pulse_map_present = bpftool_map.get("returncode") == 0
    prog_text = (bpftool_prog.get("stdout") or "") + (bpftool_net.get("stdout") or "")
    pulse_prog_visible = "x0tta6bl4" in prog_text or "pulse" in prog_text

    if pulse_map_present or pulse_prog_visible or xdp_links:
        status = "KERNEL_EVIDENCE_VISIBLE_READ_ONLY"
    else:
        status = "KERNEL_ATTACH_NOT_VERIFIED"

    return {
        "status": status,
        "pulse_map_present": pulse_map_present,
        "pulse_prog_visible": pulse_prog_visible,
        "xdp_links": xdp_links,
        "commands": {
            "bpftool_map": bpftool_map,
            "bpftool_prog": bpftool_prog,
            "bpftool_net": bpftool_net,
            "ip_links": ip_links,
        },
        "claim_boundary": "Read-only inspection only; absence of visible data means no kernel attach claim.",
    }


@dataclass
class PacketEvent:
    index: int
    monotonic_ns: int
    size_bytes: int
    source: str


class Recorder(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.events: list[PacketEvent] = []
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.events.append(
            PacketEvent(
                index=len(self.events),
                monotonic_ns=time.monotonic_ns(),
                size_bytes=len(data),
                source=f"{addr[0]}:{addr[1]}",
            )
        )


def summarize_events(events: list[PacketEvent]) -> dict[str, Any]:
    sizes = [event.size_bytes for event in events]
    gaps_ms = [
        (events[i].monotonic_ns - events[i - 1].monotonic_ns) / 1_000_000.0
        for i in range(1, len(events))
    ]

    def quantile(values: list[float], q: float) -> float | None:
        if not values:
            return None
        sorted_values = sorted(values)
        idx = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * q)))
        return sorted_values[idx]

    return {
        "packet_count": len(events),
        "size_bytes": {
            "min": min(sizes) if sizes else None,
            "max": max(sizes) if sizes else None,
            "mean": statistics.fmean(sizes) if sizes else None,
        },
        "inter_packet_gap_ms": {
            "count": len(gaps_ms),
            "min": min(gaps_ms) if gaps_ms else None,
            "max": max(gaps_ms) if gaps_ms else None,
            "mean": statistics.fmean(gaps_ms) if gaps_ms else None,
            "stdev": statistics.pstdev(gaps_ms) if len(gaps_ms) > 1 else 0.0,
            "p50": quantile(gaps_ms, 0.50),
            "p95": quantile(gaps_ms, 0.95),
        },
    }


async def run_local_probe(
    packet_count: int,
    mode: str,
    seed: int,
    pcap_path: Path | None = None,
) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    os.environ["PULSE_MODE"] = mode

    from src.network.transport.pulse_transport import PulseUDPTransport

    rng = random.Random(seed)
    loop = asyncio.get_running_loop()
    recorder = Recorder()
    receiver_transport, _ = await loop.create_datagram_endpoint(
        lambda: recorder,
        local_addr=("127.0.0.1", 0),
    )
    receiver_port = receiver_transport.get_extra_info("sockname")[1]

    sender = PulseUDPTransport(
        local_host="127.0.0.1",
        local_port=0,
        traffic_profile="GHOST_PULSE",
        obfuscation="none",
        pulse_seed=seed,
    )
    await sender.start()

    tcpdump: asyncio.subprocess.Process | None = None
    tcpdump_info: dict[str, Any] = {
        "requested": pcap_path is not None,
        "status": "NOT_REQUESTED",
        "path": str(pcap_path.relative_to(ROOT)) if pcap_path else None,
    }
    if pcap_path:
        if not shutil.which("tcpdump"):
            tcpdump_info["status"] = "TOOL_MISSING"
        else:
            tcpdump = await asyncio.create_subprocess_exec(
                "tcpdump",
                "-i",
                "lo",
                "-n",
                "-s",
                "0",
                "-c",
                str(packet_count),
                "-w",
                str(pcap_path),
                "udp",
                "and",
                "dst",
                "port",
                str(receiver_port),
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(0.4)
            if tcpdump.returncode is not None:
                stdout_b, stderr_b = await tcpdump.communicate()
                tcpdump_info.update(
                    {
                        "status": "START_FAILED",
                        "returncode": tcpdump.returncode,
                        "stdout": stdout_b.decode(errors="replace"),
                        "stderr": stderr_b.decode(errors="replace"),
                    }
                )
                tcpdump = None
            else:
                tcpdump_info["status"] = "RUNNING"

    send_results: list[bool] = []
    started_ns = time.monotonic_ns()
    try:
        for index in range(packet_count):
            payload_len = rng.randint(64, 640)
            payload = bytes([index % 251]) * payload_len
            ok = await sender.send_to(payload, ("127.0.0.1", receiver_port))
            send_results.append(ok)
        await asyncio.sleep(0.25)
        stats = sender.get_stats()
    finally:
        await sender.stop()
        receiver_transport.close()
        if tcpdump:
            try:
                stdout_b, stderr_b = await asyncio.wait_for(tcpdump.communicate(), timeout=3.0)
                tcpdump_info.update(
                    {
                        "status": "CAPTURED" if tcpdump.returncode == 0 else "CAPTURE_INCOMPLETE",
                        "returncode": tcpdump.returncode,
                        "stdout": stdout_b.decode(errors="replace"),
                        "stderr": stderr_b.decode(errors="replace"),
                    }
                )
            except asyncio.TimeoutError:
                tcpdump.terminate()
                stdout_b, stderr_b = await tcpdump.communicate()
                tcpdump_info.update(
                    {
                        "status": "TERMINATED_AFTER_TIMEOUT",
                        "returncode": tcpdump.returncode,
                        "stdout": stdout_b.decode(errors="replace"),
                        "stderr": stderr_b.decode(errors="replace"),
                    }
                )
        await asyncio.sleep(0)

    finished_ns = time.monotonic_ns()
    received = len(recorder.events)
    all_sent = all(send_results) and len(send_results) == packet_count
    all_received = received == packet_count
    if pcap_path:
        tcpdump_info["size_bytes"] = pcap_path.stat().st_size if pcap_path.exists() else 0

    return {
        "status": "VERIFIED_LOCAL" if all_sent and all_received else "LOCAL_PROBE_INCOMPLETE",
        "mode": mode,
        "seed": seed,
        "packet_count_requested": packet_count,
        "packets_send_success": sum(1 for ok in send_results if ok),
        "packets_received": received,
        "loss_count_local": packet_count - received,
        "duration_ms": (finished_ns - started_ns) / 1_000_000.0,
        "receiver": f"127.0.0.1:{receiver_port}",
        "transport_stats": stats,
        "packet_events": [event.__dict__ for event in recorder.events],
        "event_summary": summarize_events(recorder.events),
        "pcap_capture": tcpdump_info,
        "claim_boundary": "Loopback timing probe only; this does not prove DPI evasion or whitelist behavior.",
    }


async def run_baseline_probe(packet_count: int, seed: int) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.network.transport.udp_shaped import ShapedUDPTransport

    rng = random.Random(seed)
    loop = asyncio.get_running_loop()
    recorder = Recorder()
    receiver_transport, _ = await loop.create_datagram_endpoint(
        lambda: recorder,
        local_addr=("127.0.0.1", 0),
    )
    receiver_port = receiver_transport.get_extra_info("sockname")[1]

    sender = ShapedUDPTransport(
        local_host="127.0.0.1",
        local_port=0,
        traffic_profile="none",
        obfuscation="none",
    )
    await sender.start()

    send_results: list[bool] = []
    started_ns = time.monotonic_ns()
    try:
        for index in range(packet_count):
            payload_len = rng.randint(64, 640)
            payload = bytes([(index + 17) % 251]) * payload_len
            ok = await sender.send_to(payload, ("127.0.0.1", receiver_port))
            send_results.append(ok)
        await asyncio.sleep(0.25)
        stats = sender.get_stats()
    finally:
        await sender.stop()
        receiver_transport.close()
        await asyncio.sleep(0)

    finished_ns = time.monotonic_ns()
    received = len(recorder.events)
    all_sent = all(send_results) and len(send_results) == packet_count
    all_received = received == packet_count

    return {
        "status": "VERIFIED_LOCAL" if all_sent and all_received else "LOCAL_PROBE_INCOMPLETE",
        "kind": "baseline_unshaped_udp",
        "seed": seed,
        "packet_count_requested": packet_count,
        "packets_send_success": sum(1 for ok in send_results if ok),
        "packets_received": received,
        "loss_count_local": packet_count - received,
        "duration_ms": (finished_ns - started_ns) / 1_000_000.0,
        "receiver": f"127.0.0.1:{receiver_port}",
        "transport_stats": stats,
        "packet_events": [event.__dict__ for event in recorder.events],
        "event_summary": summarize_events(recorder.events),
        "claim_boundary": "Loopback baseline only; it is a local negative control, not network/DPI evidence.",
    }


def build_timing_comparison(
    pulse_probe: dict[str, Any],
    baseline_probe: dict[str, Any] | None,
) -> dict[str, Any]:
    if not baseline_probe:
        return {
            "status": "NOT_REQUESTED",
            "claim_boundary": "No baseline comparison was requested.",
        }

    pulse_gap = pulse_probe["event_summary"]["inter_packet_gap_ms"]["mean"]
    baseline_gap = baseline_probe["event_summary"]["inter_packet_gap_ms"]["mean"]
    if pulse_gap is None or baseline_gap is None:
        status = "COMPARISON_INCOMPLETE"
        delta_ms = None
        ratio = None
    else:
        status = "VERIFIED_LOCAL_COMPARISON"
        delta_ms = pulse_gap - baseline_gap
        ratio = pulse_gap / max(baseline_gap, 0.001)

    timing_plan = pulse_probe.get("transport_stats", {}).get("timing_plan_summary", {})
    planned_gap = timing_plan.get("planned_delay_ms", {}).get("mean")

    return {
        "status": status,
        "pulse_mean_gap_ms": pulse_gap,
        "baseline_mean_gap_ms": baseline_gap,
        "sender_planned_mean_delay_ms": planned_gap,
        "sender_actual_mean_gap_ms": timing_plan.get("actual_gap_ms", {}).get("mean"),
        "sender_relative_error_mean": timing_plan.get("relative_error", {}).get("mean"),
        "mean_gap_delta_ms": delta_ms,
        "mean_gap_ratio": ratio,
        "pulse_received": pulse_probe["packets_received"],
        "baseline_received": baseline_probe["packets_received"],
        "claim_boundary": (
            "Local baseline comparison only; this can show timing modulation "
            "relative to unshaped UDP, not DPI evasion or whitelist behavior."
        ),
    }


def write_packet_files(
    bundle_dir: Path,
    events: list[dict[str, Any]],
    prefix: str = "packet-events",
) -> dict[str, str]:
    jsonl_path = bundle_dir / f"{prefix}.jsonl"
    csv_path = bundle_dir / f"{prefix}.csv"
    key_prefix = prefix.replace("-", "_")

    with jsonl_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "monotonic_ns", "size_bytes", "source"])
        writer.writeheader()
        writer.writerows(events)

    return {
        f"{key_prefix}_jsonl": str(jsonl_path.relative_to(ROOT)),
        f"{key_prefix}_csv": str(csv_path.relative_to(ROOT)),
    }


def write_summary(bundle_dir: Path, evidence: dict[str, Any]) -> Path:
    summary_path = bundle_dir / "summary.md"
    local = evidence["local_probe"]
    baseline = evidence.get("baseline_probe")
    comparison = evidence.get("timing_comparison", {})
    static = evidence["static_artifacts"]
    kernel = evidence["kernel_read_only"]
    gates = evidence["gates"]
    baseline_section = ""
    if baseline:
        baseline_section = f"""
## Baseline Comparison

- Baseline status: `{baseline["status"]}`
- Baseline requested packets: `{baseline["packet_count_requested"]}`
- Baseline received packets: `{baseline["packets_received"]}`
- Baseline mean inter-packet gap ms: `{baseline["event_summary"]["inter_packet_gap_ms"]["mean"]}`
- Comparison status: `{comparison.get("status")}`
- Mean gap delta ms: `{comparison.get("mean_gap_delta_ms")}`
- Mean gap ratio: `{comparison.get("mean_gap_ratio")}`
"""
    proof_items = [
        "Local `PulseUDPTransport` can send and receive UDP packets over loopback.",
        "Seed replay metadata was recorded for deterministic sender-side timing fields.",
        "Static eBPF source/object artifacts exist if marked present below.",
        "Read-only kernel inspection was attempted and recorded.",
    ]
    if baseline:
        proof_items.append(
            "A local unshaped UDP negative control was captured for timing comparison."
        )
    proof_list = "\n".join(f"- {item}" for item in proof_items)

    text = f"""# x0tta6bl4_pulse Local Evidence Bundle

Timestamp: `{evidence["timestamp_utc"]}`

Decision: `{evidence["decision"]}`

## What This Proves

{proof_list}

## What This Does Not Prove

- No DPI bypass claim.
- No VK/Yandex/Teams whitelist claim.
- No production-readiness claim.
- No kernel attach claim. Read-only visible data still requires operator
  validation for the exact interface before any attach claim.

## Local Probe

- Status: `{local["status"]}`
- Mode: `{local["mode"]}`
- Requested packets: `{local["packet_count_requested"]}`
- Send successes: `{local["packets_send_success"]}`
- Received packets: `{local["packets_received"]}`
- Transport evidence status: `{local["transport_stats"].get("evidence_status")}`
- Stealth mode: `{local["transport_stats"].get("stealth_mode")}`
- Pulse RNG seed: `{local["transport_stats"].get("pulse_rng_seed")}`
- Timing replay status: `{local["transport_stats"].get("timing_plan_replay", {}).get("status")}`
- Timing replay sha256: `{local["transport_stats"].get("timing_plan_replay", {}).get("sha256")}`
- Sender planned mean delay ms: `{local["transport_stats"].get("timing_plan_summary", {}).get("planned_delay_ms", {}).get("mean")}`
- Sender actual mean gap ms: `{local["transport_stats"].get("timing_plan_summary", {}).get("actual_gap_ms", {}).get("mean")}`
- Mean inter-packet gap ms: `{local["event_summary"]["inter_packet_gap_ms"]["mean"]}`
- PCAP capture: `{local["pcap_capture"]["status"]}`
{baseline_section}

## Static eBPF

- Source status: `{static["source"]["exists"]}`
- Object status: `{static["object"]["exists"]}`
- Object ELF magic: `{static["object"]["elf_magic"]}`
- Object is ELF: `{static["object"]["is_elf"]}`

## Kernel Read-Only Status

- Status: `{kernel["status"]}`
- pulse_stats map present: `{kernel["pulse_map_present"]}`
- pulse program visible: `{kernel["pulse_prog_visible"]}`
- XDP links visible: `{len(kernel["xdp_links"])}`

## Gates

- Python compile: `{gates["python_compile"]["status"]}`
- Shell syntax: `{gates["ghost_core_shell_syntax"]["status"]}`

Raw JSON: `evidence.json`
Packet events: `packet-events.jsonl`, `packet-events.csv`
"""
    summary_path.write_text(text, encoding="utf-8")
    return summary_path


def gate_status(command: dict[str, Any]) -> str:
    if not command.get("available", True):
        return "TOOL_MISSING"
    return "PASS" if command.get("returncode") == 0 else "FAIL"


async def collect(args: argparse.Namespace) -> int:
    stamp = utc_stamp()
    bundle_dir = VERIFY_ROOT / f"ghost-pulse-local-evidence-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    py_compile = run_cmd(
        [
            sys.executable,
            "-m",
            "py_compile",
            "src/network/transport/pulse_transport.py",
            "src/network/obfuscation/whitelist_mimicry.py",
            "src/network/mesh_node_complete.py",
        ],
        timeout=20,
    )
    shell_syntax = run_cmd(["bash", "-n", "ghost-core.sh"], timeout=10)

    pcap_path = bundle_dir / "loopback-pulse.pcap" if args.capture_pcap else None
    local_probe = await run_local_probe(args.packet_count, args.mode, args.seed, pcap_path)
    artifact_paths = write_packet_files(bundle_dir, local_probe["packet_events"])
    baseline_probe = None
    if args.include_baseline:
        baseline_probe = await run_baseline_probe(args.packet_count, args.seed + 1)
        artifact_paths.update(
            write_packet_files(
                bundle_dir,
                baseline_probe["packet_events"],
                prefix="baseline-packet-events",
            )
        )
    timing_comparison = build_timing_comparison(local_probe, baseline_probe)

    static = static_artifact_evidence()
    kernel = kernel_read_only_evidence()

    local_pass = local_probe["status"] == "VERIFIED_LOCAL"
    static_pass = static["status"] == "STATIC_OBJECT_PRESENT"
    syntax_pass = py_compile.get("returncode") == 0 and shell_syntax.get("returncode") == 0

    if local_pass and static_pass and syntax_pass:
        decision = "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED"
    else:
        decision = "LOCAL_EVIDENCE_INCOMPLETE"

    evidence: dict[str, Any] = {
        "schema": "x0tta6bl4.ghost_pulse.local_evidence.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bundle": str(bundle_dir.relative_to(ROOT)),
        "decision": decision,
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "production_ready": False,
            "kernel_read_only_visible": kernel["status"] == "KERNEL_EVIDENCE_VISIBLE_READ_ONLY",
            "kernel_attach_verified": False,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "kernel": platform.release(),
            "cwd": str(ROOT),
        },
        "gates": {
            "python_compile": {"status": gate_status(py_compile), "command": py_compile},
            "ghost_core_shell_syntax": {"status": gate_status(shell_syntax), "command": shell_syntax},
        },
        "static_artifacts": static,
        "kernel_read_only": kernel,
        "local_probe": {
            key: value for key, value in local_probe.items() if key != "packet_events"
        },
        "timing_comparison": timing_comparison,
        "artifacts": artifact_paths,
    }
    if baseline_probe:
        evidence["baseline_probe"] = {
            key: value for key, value in baseline_probe.items() if key != "packet_events"
        }
    if pcap_path and pcap_path.exists() and pcap_path.stat().st_size > 0:
        evidence["artifacts"]["loopback_pcap"] = str(pcap_path.relative_to(ROOT))

    evidence_path = bundle_dir / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    summary_path = write_summary(bundle_dir, evidence)

    latest_json = VERIFY_ROOT / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    latest_md = VERIFY_ROOT / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.md"
    latest_json.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    latest_md.write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps({
        "decision": decision,
        "bundle": str(bundle_dir.relative_to(ROOT)),
        "evidence": str(evidence_path.relative_to(ROOT)),
        "summary": str(summary_path.relative_to(ROOT)),
    }, indent=2, sort_keys=True))
    return 0 if decision == "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-count", type=int, default=24)
    parser.add_argument("--mode", choices=("corporate", "whitelist"), default="corporate")
    parser.add_argument("--seed", type=int, default=20260521)
    parser.add_argument(
        "--include-baseline",
        action="store_true",
        help="Run an unshaped loopback UDP baseline and include timing comparison evidence.",
    )
    parser.add_argument(
        "--capture-pcap",
        action="store_true",
        help="Attempt a real tcpdump capture on lo. Failure is recorded as an evidence gap.",
    )
    args = parser.parse_args()
    if args.packet_count < 2:
        parser.error("--packet-count must be >= 2")
    if args.packet_count > 200:
        parser.error("--packet-count must be <= 200 for a bounded local probe")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(collect(parse_args())))
