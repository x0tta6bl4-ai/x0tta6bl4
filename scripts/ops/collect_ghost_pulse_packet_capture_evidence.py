#!/usr/bin/env python3
"""Collect local packet-capture evidence for x0tta6bl4_pulse.

The collector sends real UDP datagrams over loopback with the experimental pulse
transport and writes rootless sender/receiver PCAP files from the observed
datagram bytes. It does not require tcpdump privileges, does not touch routes,
does not attach eBPF programs, and does not prove DPI or provider behavior.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_PACKET_CAPTURE_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_PACKET_CAPTURE_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
CLAIM_ID = "packet_capture"
STATUS_VERIFIED = "VERIFIED"
STATUS_INCOMPLETE = "INCOMPLETE"


@dataclass
class CapturedPacket:
    index: int
    realtime_ns: int
    monotonic_ns: int
    src_host: str
    src_port: int
    dst_host: str
    dst_port: int
    payload_hex: str

    @property
    def payload(self) -> bytes:
        return bytes.fromhex(self.payload_hex)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "realtime_ns": self.realtime_ns,
            "monotonic_ns": self.monotonic_ns,
            "src_host": self.src_host,
            "src_port": self.src_port,
            "dst_host": self.dst_host,
            "dst_port": self.dst_port,
            "payload_sha256": hashlib.sha256(self.payload).hexdigest(),
            "payload_size_bytes": len(self.payload),
        }


class PacketRecorder(asyncio.DatagramProtocol):
    def __init__(self, dst_host: str, dst_port_getter) -> None:
        self.events: list[CapturedPacket] = []
        self.dst_host = dst_host
        self.dst_port_getter = dst_port_getter

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.events.append(
            CapturedPacket(
                index=len(self.events),
                realtime_ns=time.time_ns(),
                monotonic_ns=time.monotonic_ns(),
                src_host=addr[0],
                src_port=addr[1],
                dst_host=self.dst_host,
                dst_port=self.dst_port_getter(),
                payload_hex=data.hex(),
            )
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_cmd(root: Path, args: list[str], timeout: float = 10.0) -> dict[str, Any]:
    executable = args[0]
    if executable != sys.executable and not shutil.which(executable):
        return {
            "args": args,
            "available": False,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{executable} not found",
        }
    try:
        proc = subprocess.run(
            args,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "args": args,
            "available": True,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "available": True,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
        }


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def raw_ipv4_udp_packet(packet: CapturedPacket) -> bytes:
    payload = packet.payload
    src = socket.inet_aton(packet.src_host)
    dst = socket.inet_aton(packet.dst_host)
    total_length = 20 + 8 + len(payload)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        packet.index & 0xFFFF,
        0x4000,
        64,
        socket.IPPROTO_UDP,
        0,
        src,
        dst,
    )
    ip_header = ip_header[:10] + struct.pack("!H", checksum(ip_header)) + ip_header[12:]
    udp_header = struct.pack("!HHHH", packet.src_port, packet.dst_port, 8 + len(payload), 0)
    return ip_header + udp_header + payload


def write_pcap(path: Path, packets: list[CapturedPacket]) -> None:
    with path.open("wb") as f:
        f.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101))
        for packet in packets:
            raw = raw_ipv4_udp_packet(packet)
            ts_sec = packet.realtime_ns // 1_000_000_000
            ts_usec = (packet.realtime_ns % 1_000_000_000) // 1000
            f.write(struct.pack("<IIII", ts_sec, ts_usec, len(raw), len(raw)))
            f.write(raw)


def write_jsonl(path: Path, packets: list[CapturedPacket]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for packet in packets:
            f.write(json.dumps(packet.as_dict(), sort_keys=True) + "\n")


async def send_instrumented_pulse_packet(sender, payload: bytes, address: tuple[str, int]) -> CapturedPacket | None:
    from src.network.transport.udp_shaped import PeerInfo

    if not sender._socket or not sender._running:
        return None

    now = time.time()
    time_since_last = now - sender.last_send_ts
    delay_plan = sender.plan_next_delay()
    dynamic_delay = delay_plan["planned_delay"]
    wait_time = max(0.0, dynamic_delay - time_since_last)
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    packet_data = sender._prepare_packet(payload, requires_ack=False)
    previous_send_ts = sender.last_send_ts
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, lambda: sender._socket.sendto(packet_data, address))
    except Exception:
        return None

    sent_realtime_ns = time.time_ns()
    sent_monotonic_ns = time.monotonic_ns()
    sent_ts = time.time()
    sender.last_send_ts = sent_ts
    sender.pulse_packets_sent += 1

    actual_gap = None
    error = None
    if previous_send_ts:
        actual_gap = max(0.0, sent_ts - previous_send_ts)
        error = min(1.0, abs(actual_gap - dynamic_delay) / max(dynamic_delay, 0.001))
        sender.pulse_delay_error_total += error
        sender.pulse_coherence = max(0.0, 1.0 - (sender.pulse_delay_error_total / sender.pulse_packets_sent))

    sender._record_timing_sample(
        planned_delay=dynamic_delay,
        wait_time=wait_time,
        actual_gap=actual_gap,
        error=error,
        profile_label=delay_plan["profile_label"],
        payload_size=len(payload),
        mode_shift_roll=delay_plan["mode_shift_roll"],
        mode_shifted=delay_plan["mode_shifted"],
        next_profile_label=delay_plan["next_profile_label"],
    )
    if address not in sender._peers:
        sender._peers[address] = PeerInfo(address=address)
    sender._peers[address].packets_sent += 1
    sender._peers[address].last_seen = sent_ts
    sender._total_sent += 1
    sender._analyzer.record_packet(len(packet_data))

    local_host, local_port = sender._socket.getsockname()
    return CapturedPacket(
        index=sender.pulse_packets_sent - 1,
        realtime_ns=sent_realtime_ns,
        monotonic_ns=sent_monotonic_ns,
        src_host=local_host,
        src_port=local_port,
        dst_host=address[0],
        dst_port=address[1],
        payload_hex=packet_data.hex(),
    )


async def run_capture_probe(packet_count: int, mode: str, seed: int) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ["PULSE_MODE"] = mode

    from src.network.transport.pulse_transport import PulseUDPTransport

    receiver_port_holder = {"port": 0}
    loop = asyncio.get_running_loop()
    recorder = PacketRecorder("127.0.0.1", lambda: receiver_port_holder["port"])
    receiver_transport, _ = await loop.create_datagram_endpoint(
        lambda: recorder,
        local_addr=("127.0.0.1", 0),
    )
    receiver_port_holder["port"] = receiver_transport.get_extra_info("sockname")[1]

    sender = PulseUDPTransport(
        local_host="127.0.0.1",
        local_port=0,
        traffic_profile="GHOST_PULSE",
        obfuscation="none",
        pulse_seed=seed,
    )
    await sender.start()

    rng = random.Random(seed)
    sender_packets: list[CapturedPacket] = []
    try:
        for index in range(packet_count):
            payload_len = rng.randint(64, 640)
            payload = bytes([(index + 31) % 251]) * payload_len
            sent = await send_instrumented_pulse_packet(
                sender,
                payload,
                ("127.0.0.1", receiver_port_holder["port"]),
            )
            if sent:
                sender_packets.append(sent)

        deadline = time.monotonic() + 2.0
        while len(recorder.events) < len(sender_packets) and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        stats = sender.get_stats()
    finally:
        await sender.stop()
        receiver_transport.close()
        await asyncio.sleep(0)

    receiver_packets = list(recorder.events)
    status = (
        "VERIFIED_LOCAL_PACKET_CAPTURE"
        if len(sender_packets) == packet_count and len(receiver_packets) == packet_count
        else "LOCAL_PACKET_CAPTURE_INCOMPLETE"
    )
    return {
        "status": status,
        "mode": mode,
        "seed": seed,
        "packet_count_requested": packet_count,
        "sender_packets": sender_packets,
        "receiver_packets": receiver_packets,
        "transport_stats": stats,
    }


def artifact_record(root: Path, path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": display_path(root, path),
        "sha256": sha256_file(path),
    }


def render_markdown(report: dict[str, Any]) -> str:
    measurements = report["measurements"]
    lines = [
        "# x0tta6bl4_pulse Packet Capture Evidence",
        "",
        f"Observed at: `{report['observed_at_utc']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Scope",
        "",
        "- Local loopback UDP datagrams only.",
        "- Rootless PCAP files generated from observed sender/receiver datagram bytes.",
        "- No DPI, provider whitelist, or production-readiness claim.",
        "",
        "## Measurements",
        "",
        f"- Sender PCAP packets: `{measurements['sender_pcap_packets']}`",
        f"- Receiver PCAP packets: `{measurements['receiver_pcap_packets']}`",
        f"- Sender PCAP sha256: `{measurements['sender_pcap_sha256']}`",
        f"- Receiver PCAP sha256: `{measurements['receiver_pcap_sha256']}`",
        "",
        "## Failures",
        "",
    ]
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


async def collect_report(root: Path, packet_count: int, mode: str, seed: int) -> dict[str, Any]:
    observed_at = utc_now()
    stamp = datetime.fromisoformat(observed_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-packet-capture-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        run_cmd(root, ["uname", "-r"], 5.0),
        run_cmd(root, ["ip", "-j", "link", "show", "lo"], 10.0),
        run_cmd(
            root,
            [
                sys.executable,
                "-m",
                "py_compile",
                "src/network/transport/pulse_transport.py",
                "src/network/transport/udp_shaped.py",
            ],
            20.0,
        ),
    ]
    capture = await run_capture_probe(packet_count, mode, seed)

    sender_pcap = bundle_dir / "sender.pcap"
    receiver_pcap = bundle_dir / "receiver.pcap"
    sender_events = bundle_dir / "sender-events.jsonl"
    receiver_events = bundle_dir / "receiver-events.jsonl"
    capture_summary = bundle_dir / "capture-summary.json"
    write_pcap(sender_pcap, capture["sender_packets"])
    write_pcap(receiver_pcap, capture["receiver_packets"])
    write_jsonl(sender_events, capture["sender_packets"])
    write_jsonl(receiver_events, capture["receiver_packets"])

    sender_sha = sha256_file(sender_pcap)
    receiver_sha = sha256_file(receiver_pcap)
    measurements = {
        "sender_pcap_packets": len(capture["sender_packets"]),
        "receiver_pcap_packets": len(capture["receiver_packets"]),
        "sender_pcap_sha256": sender_sha,
        "receiver_pcap_sha256": receiver_sha,
    }
    failures: list[str] = []
    if capture["status"] != "VERIFIED_LOCAL_PACKET_CAPTURE":
        failures.append(f"local capture status is {capture['status']}")
    if measurements["sender_pcap_packets"] <= 0:
        failures.append("sender PCAP has no packets")
    if measurements["receiver_pcap_packets"] <= 0:
        failures.append("receiver PCAP has no packets")
    if not sender_sha:
        failures.append("sender PCAP sha256 is missing")
    if not receiver_sha:
        failures.append("receiver PCAP sha256 is missing")
    for command in commands:
        if command.get("exit_code") != 0:
            failures.append(f"command failed: {' '.join(str(part) for part in command.get('args', []))}")

    status = STATUS_VERIFIED if not failures else STATUS_INCOMPLETE
    summary_payload = {
        "capture_status": capture["status"],
        "mode": capture["mode"],
        "seed": capture["seed"],
        "packet_count_requested": capture["packet_count_requested"],
        "transport_stats": capture["transport_stats"],
        "measurements": measurements,
        "failures": failures,
    }
    capture_summary.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "schema": SCHEMA,
        "claim_id": CLAIM_ID,
        "status": status,
        "observed_at_utc": observed_at,
        "simulated": False,
        "dry_run": False,
        "template": False,
        "mode": "LOCAL_LOOPBACK_INSTRUMENTED_PCAP",
        "commands": commands,
        "artifacts": [
            artifact_record(root, sender_pcap, "sender_pcap"),
            artifact_record(root, receiver_pcap, "receiver_pcap"),
            artifact_record(root, sender_events, "sender_events"),
            artifact_record(root, receiver_events, "receiver_events"),
            artifact_record(root, capture_summary, "capture_summary"),
        ],
        "measurements": measurements,
        "failures": failures,
        "bundle": display_path(root, bundle_dir),
        "claim_boundary": {
            "packet_capture_verified": status == STATUS_VERIFIED,
            "note": "Local loopback packet capture only; this is not remote-path, DPI, whitelist, or production evidence.",
        },
    }


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    bundle_dir = root / report["bundle"]
    bundle_json = bundle_dir / "evidence.json"
    bundle_md = bundle_dir / "summary.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)
    bundle_json.write_text(rendered_json, encoding="utf-8")
    bundle_md.write_text(rendered_md, encoding="utf-8")
    output_json.write_text(rendered_json, encoding="utf-8")
    output_md.write_text(rendered_md, encoding="utf-8")
    return {
        "bundle_dir": bundle_dir,
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": output_json,
        "latest_md": output_md,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--packet-count", type=int, default=12)
    parser.add_argument("--mode", choices=("corporate", "whitelist"), default="corporate")
    parser.add_argument("--seed", type=int, default=20260522)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)
    if args.packet_count < 2:
        parser.error("--packet-count must be >= 2")
    if args.packet_count > 200:
        parser.error("--packet-count must be <= 200 for bounded local evidence")

    root = args.root.resolve()
    report = asyncio.run(collect_report(root, args.packet_count, args.mode, args.seed))
    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
    paths = write_report_outputs(root, report, output_json, output_md)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "bundle": report["bundle"],
                    "output_json": display_path(root, paths["latest_json"]),
                    "output_md": display_path(root, paths["latest_md"]),
                    "failures": report["failures"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    if args.require_verified and report["status"] != STATUS_VERIFIED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
