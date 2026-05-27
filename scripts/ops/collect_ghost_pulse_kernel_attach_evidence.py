#!/usr/bin/env python3
"""Collect read-only kernel attach evidence for x0tta6bl4_pulse.

This collector never attaches XDP programs, changes routes, sends packets, or
touches runtime services. It records the current kernel/eBPF state and marks the
kernel_attach claim VERIFIED only when real command output proves the full proof
gate contract: named interface, visible XDP attach, visible pulse program, and a
positive pulse map counter delta.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_KERNEL_ATTACH_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
CLAIM_ID = "kernel_attach"
STATUS_VERIFIED = "VERIFIED"
STATUS_INCOMPLETE = "INCOMPLETE"
PULSE_MAP_NAME = "pulse_stats"
PULSE_PROGRAM_MARKERS = ("x0tta6bl4_pulse", "x0tta6bl4", "pulse")
PULSE_SOURCE_PATH = "src/network/ebpf/x0tta6bl4_pulse.bpf.c"
PULSE_OBJECT_PATH = "src/network/ebpf/x0tta6bl4_pulse.o"
EM_BPF = 247
CANDIDATE_PATH = "docs/verification/incoming/kernel_attach.json"
LATEST_EVIDENCE_PATH = "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
DEFAULT_CANDIDATE_PATHS = (
    "docs/verification/xdp-live-attach-20260402T081417Z/verify-local-live-attach.log",
    "ebpf/prod/results/benchmark-live.json",
)
BPFTOOL_COMMAND_NAMES = (
    "bpftool_prog_show",
    "bpftool_net",
    "bpftool_map_show",
    "bpftool_map_dump_before",
    "bpftool_map_dump_after",
)
SUDO_NONINTERACTIVE_PREFIX = ["sudo", "-n"]

PACKET_COUNTER_RE = re.compile(
    r"\b(?:packets|packet_count|packet_count_total|rx_packets|tx_packets|pkt_count)\b"
    r"[^0-9]{0,32}([0-9]+)",
    re.IGNORECASE,
)


CommandRunner = Callable[[Path, list[str], float], dict[str, Any]]


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


def read_bytes_safe(path: Path) -> tuple[bytes, str | None]:
    try:
        return path.read_bytes(), None
    except OSError as exc:
        return b"", str(exc)


def read_text_safe(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return "", str(exc)


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


def execution_args_for(args: list[str], *, bpftool_sudo: bool) -> list[str]:
    if bpftool_sudo and args and args[0] == "bpftool":
        return [*SUDO_NONINTERACTIVE_PREFIX, *args]
    return args


def run_observation_command(
    root: Path,
    args: list[str],
    timeout: float,
    command_runner: CommandRunner,
    *,
    bpftool_sudo: bool,
) -> dict[str, Any]:
    execution_args = execution_args_for(args, bpftool_sudo=bpftool_sudo)
    result = normalize_command(command_runner(root, execution_args, timeout))
    if execution_args != args:
        result["args"] = args
        result["execution_args"] = execution_args
        result["privilege_mode"] = "sudo_noninteractive"
    else:
        result.setdefault("args", args)
        result.setdefault("privilege_mode", "direct")
    return result


def normalize_command(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    if "exit_code" not in normalized and "returncode" in normalized:
        normalized["exit_code"] = normalized["returncode"]
    normalized.setdefault("available", normalized.get("exit_code") is not None)
    normalized.setdefault("stdout", "")
    normalized.setdefault("stderr", "")
    return normalized


def output_text(command: dict[str, Any]) -> str:
    return f"{command.get('stdout') or ''}\n{command.get('stderr') or ''}"


def parse_ip_link_json(stdout: str, iface: str) -> dict[str, Any]:
    try:
        links = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return {"interface_seen": False, "xdp_attached": False, "xdp": None}
    if not isinstance(links, list):
        return {"interface_seen": False, "xdp_attached": False, "xdp": None}

    for link in links:
        if not isinstance(link, dict) or link.get("ifname") != iface:
            continue
        xdp = link.get("xdp")
        xdp_attached = False
        if isinstance(xdp, dict):
            xdp_attached = bool(
                xdp.get("prog_id")
                or xdp.get("id")
                or xdp.get("name")
                or xdp.get("mode")
                or xdp.get("attached")
            )
            if str(xdp.get("attached", "")).lower() == "none":
                xdp_attached = False
        elif xdp:
            xdp_attached = True
        return {"interface_seen": True, "xdp_attached": xdp_attached, "xdp": xdp}
    return {"interface_seen": False, "xdp_attached": False, "xdp": None}


def xdp_attached_from_link(link: dict[str, Any]) -> bool:
    xdp = link.get("xdp")
    xdp_attached = False
    if isinstance(xdp, dict):
        xdp_attached = bool(
            xdp.get("prog_id")
            or xdp.get("id")
            or xdp.get("name")
            or xdp.get("mode")
            or xdp.get("attached")
        )
        if str(xdp.get("attached", "")).lower() == "none":
            xdp_attached = False
    elif xdp:
        xdp_attached = True
    return xdp_attached


def interface_scan_summary(stdout: str) -> dict[str, Any]:
    try:
        links = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return {
            "parse_status": "INVALID_JSON",
            "interface_count": 0,
            "interfaces": [],
            "xdp_interfaces": [],
        }
    if not isinstance(links, list):
        return {
            "parse_status": "NOT_A_LIST",
            "interface_count": 0,
            "interfaces": [],
            "xdp_interfaces": [],
        }

    interfaces: list[str] = []
    xdp_interfaces: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        ifname = link.get("ifname")
        if not isinstance(ifname, str) or not ifname:
            continue
        interfaces.append(ifname)
        if xdp_attached_from_link(link):
            xdp_interfaces.append(
                {
                    "ifname": ifname,
                    "xdp": link.get("xdp"),
                }
            )
    return {
        "parse_status": "OK",
        "interface_count": len(interfaces),
        "interfaces": interfaces,
        "xdp_interfaces": xdp_interfaces,
    }


def contains_pulse_program(*texts: str) -> bool:
    haystack = "\n".join(texts).lower()
    return any(marker in haystack for marker in PULSE_PROGRAM_MARKERS)


def contains_interface(text: str, iface: str) -> bool:
    return bool(iface.strip()) and iface in text


def parse_packet_counter(stdout: str) -> int | None:
    values = [int(match.group(1)) for match in PACKET_COUNTER_RE.finditer(stdout or "")]
    if values:
        return max(values)

    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None

    found: list[int] = []

    def walk(value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, str(key))
            return
        if isinstance(value, list):
            for child in value:
                walk(child, key_hint)
            return
        key_name = key_hint.lower()
        if isinstance(value, int) and ("packet" in key_name or key_name == "value"):
            found.append(value)

    walk(payload)
    return max(found) if found else None


def counter_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_value = parse_packet_counter(before.get("stdout") or "")
    after_value = parse_packet_counter(after.get("stdout") or "")
    delta = 0
    if before_value is not None and after_value is not None:
        delta = max(0, after_value - before_value)
    return {
        "before": before_value,
        "after": after_value,
        "delta": delta,
    }


def command_args(command: dict[str, Any]) -> list[str]:
    args = command.get("args")
    if not isinstance(args, list):
        return []
    return [str(part) for part in args]


def stderr_excerpt(command: dict[str, Any], limit: int = 240) -> str:
    stderr = command.get("stderr")
    if not isinstance(stderr, str):
        return ""
    return stderr.strip()[:limit]


def elf_metadata(path: Path) -> dict[str, Any]:
    data, read_error = read_bytes_safe(path)
    metadata: dict[str, Any] = {
        "parse_status": "OK",
        "read_error": read_error,
        "is_elf": False,
        "elf_class": None,
        "byte_order": None,
        "e_machine": None,
        "e_machine_name": None,
        "is_ebpf": False,
        "section_names": [],
    }
    if read_error:
        metadata["parse_status"] = "READ_ERROR"
        return metadata
    if len(data) < 20 or data[:4] != b"\x7fELF":
        metadata["parse_status"] = "NOT_ELF"
        return metadata

    metadata["is_elf"] = True
    elf_class = data[4]
    byte_order = data[5]
    metadata["elf_class"] = {1: "ELF32", 2: "ELF64"}.get(elf_class, f"UNKNOWN_{elf_class}")
    metadata["byte_order"] = {1: "little", 2: "big"}.get(byte_order, f"UNKNOWN_{byte_order}")
    if byte_order not in (1, 2):
        metadata["parse_status"] = "UNSUPPORTED_BYTE_ORDER"
        return metadata
    endian = "<" if byte_order == 1 else ">"
    try:
        metadata["e_machine"] = struct.unpack_from(f"{endian}H", data, 18)[0]
    except struct.error as exc:
        metadata["parse_status"] = "INVALID_HEADER"
        metadata["read_error"] = str(exc)
        return metadata
    metadata["e_machine_name"] = "EM_BPF" if metadata["e_machine"] == EM_BPF else None
    metadata["is_ebpf"] = metadata["e_machine"] == EM_BPF

    if elf_class != 2:
        metadata["parse_status"] = "UNSUPPORTED_ELF_CLASS"
        return metadata
    try:
        e_shoff = struct.unpack_from(f"{endian}Q", data, 40)[0]
        e_shentsize = struct.unpack_from(f"{endian}H", data, 58)[0]
        e_shnum = struct.unpack_from(f"{endian}H", data, 60)[0]
        e_shstrndx = struct.unpack_from(f"{endian}H", data, 62)[0]
    except struct.error as exc:
        metadata["parse_status"] = "INVALID_SECTION_HEADER"
        metadata["read_error"] = str(exc)
        return metadata
    if not e_shoff or not e_shentsize or not e_shnum:
        metadata["parse_status"] = "NO_SECTION_TABLE"
        return metadata
    if e_shstrndx >= e_shnum:
        metadata["parse_status"] = "INVALID_SECTION_NAME_TABLE"
        return metadata

    table_end = e_shoff + (e_shentsize * e_shnum)
    if table_end > len(data):
        metadata["parse_status"] = "SECTION_TABLE_OUT_OF_RANGE"
        return metadata

    def section_header(index: int) -> tuple[int, int, int]:
        offset = e_shoff + (e_shentsize * index)
        sh_name = struct.unpack_from(f"{endian}I", data, offset)[0]
        sh_offset = struct.unpack_from(f"{endian}Q", data, offset + 24)[0]
        sh_size = struct.unpack_from(f"{endian}Q", data, offset + 32)[0]
        return sh_name, sh_offset, sh_size

    try:
        _, shstr_offset, shstr_size = section_header(e_shstrndx)
    except struct.error as exc:
        metadata["parse_status"] = "INVALID_SECTION_NAME_TABLE"
        metadata["read_error"] = str(exc)
        return metadata
    if shstr_offset + shstr_size > len(data):
        metadata["parse_status"] = "SECTION_NAME_TABLE_OUT_OF_RANGE"
        return metadata
    shstr = data[shstr_offset : shstr_offset + shstr_size]

    section_names: list[str] = []
    try:
        for index in range(e_shnum):
            sh_name, _, _ = section_header(index)
            if sh_name >= len(shstr):
                section_names.append("")
                continue
            end = shstr.find(b"\x00", sh_name)
            if end == -1:
                end = len(shstr)
            section_names.append(shstr[sh_name:end].decode("utf-8", errors="replace"))
    except struct.error as exc:
        metadata["parse_status"] = "INVALID_SECTION_TABLE"
        metadata["read_error"] = str(exc)
        return metadata
    metadata["section_names"] = section_names
    return metadata


def inspect_bpf_artifacts(root: Path) -> dict[str, Any]:
    source_path = root / PULSE_SOURCE_PATH
    object_path = root / PULSE_OBJECT_PATH
    source_text, source_error = read_text_safe(source_path) if source_path.exists() else ("", None)
    object_bytes, object_error = read_bytes_safe(object_path) if object_path.exists() else (b"", None)
    elf = elf_metadata(object_path) if object_path.exists() else {
        "parse_status": "MISSING",
        "read_error": None,
        "is_elf": False,
        "elf_class": None,
        "byte_order": None,
        "e_machine": None,
        "e_machine_name": None,
        "is_ebpf": False,
        "section_names": [],
    }
    section_names = [
        item
        for item in elf.get("section_names", [])
        if isinstance(item, str)
    ]
    source_checks = {
        "exists": source_path.exists(),
        "sha256": sha256_file(source_path),
        "read_error": source_error,
        "contains_xdp_section": 'SEC("xdp")' in source_text or "SEC('xdp')" in source_text,
        "contains_pulse_stats": PULSE_MAP_NAME in source_text,
        "contains_pulse_function": "xdp_x0tta6bl4_pulse" in source_text,
    }
    object_checks = {
        "exists": object_path.exists(),
        "sha256": sha256_file(object_path),
        "read_error": object_error,
        "elf": elf,
        "is_ebpf": bool(elf.get("is_ebpf")),
        "has_xdp_section": "xdp" in section_names or b"\x00xdp\x00" in object_bytes,
        "has_maps_section": ".maps" in section_names or b".maps" in object_bytes,
        "has_btf_section": ".BTF" in section_names or b".BTF" in object_bytes,
        "contains_pulse_stats": PULSE_MAP_NAME.encode("utf-8") in object_bytes,
        "contains_pulse_function": b"xdp_x0tta6bl4_pulse" in object_bytes,
    }
    blockers: list[str] = []
    if not source_checks["exists"]:
        blockers.append("pulse_source_missing")
    if source_error:
        blockers.append("pulse_source_unreadable")
    if source_checks["exists"] and not source_checks["contains_xdp_section"]:
        blockers.append("pulse_source_missing_xdp_section")
    if source_checks["exists"] and not source_checks["contains_pulse_stats"]:
        blockers.append("pulse_source_missing_pulse_stats")
    if source_checks["exists"] and not source_checks["contains_pulse_function"]:
        blockers.append("pulse_source_missing_x0tta6bl4_function")
    if not object_checks["exists"]:
        blockers.append("pulse_object_missing")
    if object_error:
        blockers.append("pulse_object_unreadable")
    if object_checks["exists"] and not object_checks["is_ebpf"]:
        blockers.append("pulse_object_not_ebpf")
    if object_checks["exists"] and not object_checks["has_xdp_section"]:
        blockers.append("pulse_object_missing_xdp_section")
    if object_checks["exists"] and not object_checks["has_maps_section"]:
        blockers.append("pulse_object_missing_maps_section")
    if object_checks["exists"] and not object_checks["has_btf_section"]:
        blockers.append("pulse_object_missing_btf_section")
    if object_checks["exists"] and not object_checks["contains_pulse_stats"]:
        blockers.append("pulse_object_missing_pulse_stats")
    if object_checks["exists"] and not object_checks["contains_pulse_function"]:
        blockers.append("pulse_object_missing_x0tta6bl4_function")

    deduped_blockers = list(dict.fromkeys(blockers))
    return {
        "status": "READY_FOR_CONTROLLED_ATTACH_TEST" if not deduped_blockers else "ACTION_REQUIRED",
        "blockers": deduped_blockers,
        "source": {
            "path": PULSE_SOURCE_PATH,
            **source_checks,
        },
        "object": {
            "path": PULSE_OBJECT_PATH,
            **object_checks,
        },
        "claim_boundary": (
            "Disk artifact preflight only. This proves the source/object shape needed for a "
            "controlled attach test, but it does not prove that the program is loaded, attached, "
            "or processing packets in the current kernel."
        ),
        "next_action": (
            "Run the attach proof in a controlled lab or approved temporary interface, then collect "
            "current ip/bpftool/map-counter output. Do not stage kernel_attach until runtime evidence "
            "is VERIFIED."
        ),
    }


def collection_diagnostics(
    commands_by_name: dict[str, dict[str, Any]],
    measurements: dict[str, Any],
    interface_scan: dict[str, Any],
    object_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    bpftool_commands = [
        (name, commands_by_name[name])
        for name in BPFTOOL_COMMAND_NAMES
        if name in commands_by_name
    ]
    unavailable_bpftool_commands = [
        {
            "name": name,
            "args": command_args(command),
            "stderr": stderr_excerpt(command),
        }
        for name, command in bpftool_commands
        if command.get("available") is False
    ]
    failed_bpftool_commands = [
        {
            "name": name,
            "args": command_args(command),
            "exit_code": command.get("exit_code"),
            "stderr": stderr_excerpt(command),
        }
        for name, command in bpftool_commands
        if command.get("exit_code") != 0
    ]
    permission_denied_commands = [
        item
        for item in failed_bpftool_commands
        if "operation not permitted" in item.get("stderr", "").lower()
        or "permission denied" in item.get("stderr", "").lower()
    ]
    sudo_commands = [
        (name, command)
        for name, command in bpftool_commands
        if command.get("privilege_mode") == "sudo_noninteractive"
    ]
    sudo_unavailable_commands = [
        {
            "name": name,
            "args": command_args(command),
            "execution_args": command.get("execution_args", []),
            "stderr": stderr_excerpt(command),
        }
        for name, command in sudo_commands
        if command.get("available") is False
    ]
    sudo_noninteractive_unavailable_commands = [
        {
            "name": name,
            "args": command_args(command),
            "execution_args": command.get("execution_args", []),
            "exit_code": command.get("exit_code"),
            "stderr": stderr_excerpt(command),
        }
        for name, command in sudo_commands
        if command.get("exit_code") != 0
        and (
            "a password is required" in stderr_excerpt(command).lower()
            or "a terminal is required" in stderr_excerpt(command).lower()
            or "no tty present" in stderr_excerpt(command).lower()
            or "not allowed to execute" in stderr_excerpt(command).lower()
        )
    ]
    if not measurements.get("interface"):
        blockers.append("interface_name_empty")
    if measurements.get("interface_seen") is not True:
        blockers.append("interface_not_seen")
    if measurements.get("xdp_attached") is not True:
        blockers.append("xdp_attach_not_visible")
    if unavailable_bpftool_commands:
        blockers.append("bpftool_unavailable")
    if sudo_unavailable_commands:
        blockers.append("sudo_unavailable")
    if sudo_noninteractive_unavailable_commands:
        blockers.append("sudo_noninteractive_unavailable")
    if permission_denied_commands:
        blockers.append("bpftool_permission_denied")
    elif failed_bpftool_commands:
        blockers.append("bpftool_command_failed")
    if measurements.get("bpftool_prog_show_contains_pulse") is not True:
        blockers.append("pulse_program_not_visible")
    if measurements.get("bpftool_net_contains_interface") is not True:
        blockers.append("bpftool_net_missing_interface")
    if not isinstance(measurements.get("map_counter_delta_packets"), int) or measurements.get("map_counter_delta_packets") <= 0:
        blockers.append("pulse_stats_counter_not_positive")

    deduped_blockers = list(dict.fromkeys(blockers))
    return {
        "status": "READY_FOR_PROOF" if not deduped_blockers else "ACTION_REQUIRED",
        "blockers": deduped_blockers,
        "interface": measurements.get("interface"),
        "interface_seen": measurements.get("interface_seen"),
        "xdp_attached": measurements.get("xdp_attached"),
        "xdp_interfaces": interface_scan.get("xdp_interfaces", []),
        "bpftool_unavailable_commands": unavailable_bpftool_commands,
        "bpftool_failed_commands": failed_bpftool_commands,
        "bpftool_permission_denied": bool(permission_denied_commands),
        "bpftool_permission_denied_commands": permission_denied_commands,
        "bpftool_privilege_mode": (
            "sudo_noninteractive" if sudo_commands else "direct"
        ),
        "sudo_noninteractive_enabled": bool(sudo_commands),
        "sudo_unavailable": bool(sudo_unavailable_commands),
        "sudo_unavailable_commands": sudo_unavailable_commands,
        "sudo_noninteractive_unavailable": bool(sudo_noninteractive_unavailable_commands),
        "sudo_noninteractive_unavailable_commands": sudo_noninteractive_unavailable_commands,
        "object_preflight_status": (
            object_preflight.get("status") if isinstance(object_preflight, dict) else None
        ),
        "object_preflight_blockers": (
            object_preflight.get("blockers", []) if isinstance(object_preflight, dict) else []
        ),
        "pulse_marker_visible": measurements.get("bpftool_prog_show_contains_pulse"),
        "bpftool_net_contains_interface": measurements.get("bpftool_net_contains_interface"),
        "map_counter_delta_packets": measurements.get("map_counter_delta_packets"),
        "next_action": (
            "Collect on a host where the x0tta6bl4_pulse XDP program is attached to the target "
            "interface and bpftool can read programs/maps; keep this claim INCOMPLETE until "
            "the pulse_stats packet counter increases."
        ),
    }


def candidate_import_readiness(status: str, diagnostics: dict[str, Any]) -> dict[str, Any]:
    blockers = [
        item
        for item in diagnostics.get("blockers", [])
        if isinstance(item, str)
    ]
    ready = status == STATUS_VERIFIED and not blockers
    blocking_reasons = [] if ready else list(dict.fromkeys(["kernel_evidence_not_verified", *blockers]))
    return {
        "status": "READY_TO_STAGE_CANDIDATE" if ready else "ACTION_REQUIRED",
        "candidate_path": CANDIDATE_PATH,
        "source_latest_evidence": LATEST_EVIDENCE_PATH,
        "can_stage_candidate": ready,
        "do_not_stage_candidate": not ready,
        "blocking_reasons": blocking_reasons,
        "stage_candidate_command": (
            ["cp", LATEST_EVIDENCE_PATH, CANDIDATE_PATH] if ready else None
        ),
        "read_only_import_command": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            CLAIM_ID,
            "--candidate",
            CANDIDATE_PATH,
            "--require-ready",
            "--json",
        ],
        "acceptance_commands": [
            [
                "python3",
                "scripts/ops/verify_ghost_pulse_external_evidence.py",
                "--claim",
                CLAIM_ID,
                "--require-pass",
                "--json",
            ]
        ],
        "claim_boundary": (
            "Candidate readiness only; staging/import is allowed only after the collector "
            "produces VERIFIED evidence. This section does not promote proof-gate claims."
        ),
    }


def audit_candidate_artifacts(root: Path, iface: str, rel_paths: tuple[str, ...] = DEFAULT_CANDIDATE_PATHS) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    accepted: list[str] = []
    for rel_path in rel_paths:
        path = root / rel_path
        text = ""
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
        lower = text.lower()
        contains_pulse = contains_pulse_program(text)
        contains_xdp = "prog/xdp" in lower or "xdpgeneric" in lower or '"prog_id"' in lower
        contains_iface = iface in text
        rejection_reasons: list[str] = []
        if not path.exists():
            rejection_reasons.append("candidate artifact is missing")
        if not contains_pulse:
            rejection_reasons.append("candidate does not contain x0tta6bl4_pulse marker")
        if "xdp_mesh_filter" in lower:
            rejection_reasons.append("candidate references xdp_mesh_filter, not x0tta6bl4_pulse")
        if not contains_xdp:
            rejection_reasons.append("candidate does not show XDP attach")
        if not contains_iface:
            rejection_reasons.append(f"candidate does not reference interface {iface}")
        if path.exists() and contains_pulse and contains_xdp and contains_iface:
            accepted.append(rel_path)
        candidates.append(
            {
                "path": rel_path,
                "exists": path.exists(),
                "sha256": sha256_file(path),
                "contains_pulse_marker": contains_pulse,
                "contains_xdp_attach": contains_xdp,
                "contains_interface": contains_iface,
                "rejection_reasons": rejection_reasons,
            }
        )
    return {
        "status": "NO_ACCEPTED_CANDIDATE" if not accepted else "HAS_ACCEPTED_CANDIDATE",
        "accepted": accepted,
        "candidates": candidates,
        "claim_boundary": "Historical XDP artifacts are advisory only; proof gate still requires current kernel measurements.",
    }


def build_report(
    *,
    root: Path = ROOT,
    iface: str,
    command_runner: CommandRunner = run_cmd,
    counter_wait_seconds: float = 0.2,
    bpftool_sudo: bool = False,
) -> dict[str, Any]:
    observed_at = utc_now()
    commands_by_name: dict[str, dict[str, Any]] = {}

    command_specs = [
        ("uname_r", ["uname", "-r"], 5.0),
        ("ip_link_all_detailed", ["ip", "-d", "-j", "link", "show"], 10.0),
        ("ip_link", ["ip", "-j", "link", "show", iface], 10.0),
        ("ip_link_detailed", ["ip", "-d", "-j", "link", "show", iface], 10.0),
        ("bpftool_prog_show", ["bpftool", "prog", "show"], 10.0),
        ("bpftool_net", ["bpftool", "net"], 10.0),
        ("bpftool_map_show", ["bpftool", "map", "show", "name", PULSE_MAP_NAME], 10.0),
        ("bpftool_map_dump_before", ["bpftool", "map", "dump", "name", PULSE_MAP_NAME], 10.0),
    ]
    for name, args, timeout in command_specs:
        commands_by_name[name] = run_observation_command(
            root,
            args,
            timeout,
            command_runner,
            bpftool_sudo=bpftool_sudo,
        )

    if counter_wait_seconds > 0:
        time.sleep(counter_wait_seconds)

    commands_by_name["bpftool_map_dump_after"] = normalize_command(
        run_observation_command(
            root,
            ["bpftool", "map", "dump", "name", PULSE_MAP_NAME],
            10.0,
            command_runner,
            bpftool_sudo=bpftool_sudo,
        )
    )

    ip_link = parse_ip_link_json(commands_by_name["ip_link_detailed"].get("stdout") or "", iface)
    if not ip_link["xdp_attached"]:
        ip_link = parse_ip_link_json(commands_by_name["ip_link"].get("stdout") or "", iface)
    prog_text = output_text(commands_by_name["bpftool_prog_show"])
    net_text = output_text(commands_by_name["bpftool_net"])
    delta = counter_delta(
        commands_by_name["bpftool_map_dump_before"],
        commands_by_name["bpftool_map_dump_after"],
    )
    command_list = list(commands_by_name.values())
    candidate_audit = audit_candidate_artifacts(root, iface)
    object_preflight = inspect_bpf_artifacts(root)
    interface_scan = interface_scan_summary(commands_by_name["ip_link_all_detailed"].get("stdout") or "")

    measurements = {
        "interface": iface,
        "interface_seen": ip_link["interface_seen"],
        "interface_scan_count": interface_scan["interface_count"],
        "interface_scan_xdp_interfaces": [
            item["ifname"]
            for item in interface_scan["xdp_interfaces"]
            if isinstance(item, dict) and isinstance(item.get("ifname"), str)
        ],
        "xdp_attached": bool(ip_link["xdp_attached"]),
        "bpftool_prog_show_contains_pulse": contains_pulse_program(prog_text, net_text),
        "bpftool_net_contains_interface": contains_interface(net_text, iface),
        "map_counter_before_packets": delta["before"],
        "map_counter_after_packets": delta["after"],
        "map_counter_delta_packets": delta["delta"],
        "historical_candidate_audit_status": candidate_audit["status"],
        "object_preflight_status": object_preflight["status"],
        "object_preflight_source_path": object_preflight["source"]["path"],
        "object_preflight_object_path": object_preflight["object"]["path"],
        "object_preflight_object_is_ebpf": object_preflight["object"]["is_ebpf"],
        "object_preflight_object_has_xdp_section": object_preflight["object"]["has_xdp_section"],
        "object_preflight_object_has_btf_section": object_preflight["object"]["has_btf_section"],
        "object_preflight_object_contains_pulse_stats": object_preflight["object"]["contains_pulse_stats"],
        "object_preflight_object_contains_pulse_function": object_preflight["object"]["contains_pulse_function"],
    }
    failures = []
    if not iface.strip():
        failures.append("interface name is empty")
    if not measurements["interface_seen"]:
        failures.append(f"interface was not found by ip link: {iface}")
    if not measurements["xdp_attached"]:
        failures.append(f"ip link did not show an XDP attach on interface: {iface}")
    if not measurements["bpftool_prog_show_contains_pulse"]:
        failures.append("bpftool output did not contain an x0tta6bl4_pulse marker")
    if not measurements["bpftool_net_contains_interface"]:
        failures.append(f"bpftool net output did not include interface: {iface}")
    if not isinstance(measurements["map_counter_delta_packets"], int) or measurements["map_counter_delta_packets"] <= 0:
        failures.append("pulse map packet counter did not increase")
    for command in command_list:
        if command.get("exit_code") != 0:
            failures.append(f"command failed: {' '.join(str(part) for part in command.get('args', []))}")

    status = STATUS_VERIFIED if not failures else STATUS_INCOMPLETE
    diagnostics = collection_diagnostics(commands_by_name, measurements, interface_scan, object_preflight)
    readiness = candidate_import_readiness(status, diagnostics)
    return {
        "schema": SCHEMA,
        "claim_id": CLAIM_ID,
        "status": status,
        "observed_at_utc": observed_at,
        "simulated": False,
        "dry_run": False,
        "template": False,
        "mode": "READ_ONLY_KERNEL_OBSERVATION",
        "collection_options": {
            "bpftool_sudo": bpftool_sudo,
            "bpftool_sudo_command_prefix": SUDO_NONINTERACTIVE_PREFIX if bpftool_sudo else [],
            "bpftool_sudo_note": (
                "When enabled, only read-only bpftool observation commands run through sudo -n. "
                "The collector never attaches XDP programs or mutates runtime state."
            ),
        },
        "commands": command_list,
        "artifacts": [],
        "measurements": measurements,
        "collection_diagnostics": diagnostics,
        "object_preflight": object_preflight,
        "candidate_import_readiness": readiness,
        "interface_scan": interface_scan,
        "candidate_audit": candidate_audit,
        "failures": failures,
        "claim_boundary": {
            "kernel_attach_verified": status == STATUS_VERIFIED,
            "note": (
                "Verified only when current kernel output shows XDP attach, pulse program visibility, "
                "and a positive pulse map counter delta. The collector itself is read-only."
            ),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    measurements = report["measurements"]
    diagnostics = report.get("collection_diagnostics", {})
    readiness = report.get("candidate_import_readiness", {})
    collection_options = report.get("collection_options", {})
    object_preflight = report.get("object_preflight", {})
    object_checks = object_preflight.get("object", {}) if isinstance(object_preflight, dict) else {}
    lines = [
        "# x0tta6bl4_pulse Kernel Attach Evidence",
        "",
        f"Observed at: `{report['observed_at_utc']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Measurements",
        "",
        f"- Interface: `{measurements['interface']}`",
        f"- Interface seen by ip link: `{measurements['interface_seen']}`",
        f"- Interfaces seen by full scan: `{measurements['interface_scan_count']}`",
        f"- Interfaces with XDP in full scan: `{measurements['interface_scan_xdp_interfaces']}`",
        f"- XDP attached: `{measurements['xdp_attached']}`",
        f"- Pulse marker visible in bpftool output: `{measurements['bpftool_prog_show_contains_pulse']}`",
        f"- Interface visible in bpftool net: `{measurements['bpftool_net_contains_interface']}`",
        f"- Map packet counter delta: `{measurements['map_counter_delta_packets']}`",
        "",
        "## eBPF Artifact Preflight",
        "",
        f"- Status: `{object_preflight.get('status') if isinstance(object_preflight, dict) else None}`",
        f"- Source: `{measurements.get('object_preflight_source_path')}`",
        f"- Object: `{measurements.get('object_preflight_object_path')}`",
        f"- Object is eBPF: `{object_checks.get('is_ebpf')}`",
        f"- Object has XDP section: `{object_checks.get('has_xdp_section')}`",
        f"- Object has BTF section: `{object_checks.get('has_btf_section')}`",
        f"- Object contains pulse_stats: `{object_checks.get('contains_pulse_stats')}`",
        f"- Object contains pulse function: `{object_checks.get('contains_pulse_function')}`",
        f"- Preflight blockers: `{', '.join(object_preflight.get('blockers', [])) if isinstance(object_preflight, dict) else 'none'}`",
        "",
        "## Collection Options",
        "",
        f"- bpftool sudo: `{collection_options.get('bpftool_sudo')}`",
        f"- bpftool privilege mode: `{diagnostics.get('bpftool_privilege_mode')}`",
        f"- sudo non-interactive unavailable: `{diagnostics.get('sudo_noninteractive_unavailable')}`",
        "",
        "## Collection Diagnostics",
        "",
        f"- Status: `{diagnostics.get('status')}`",
        f"- Blockers: `{', '.join(diagnostics.get('blockers', [])) or 'none'}`",
        f"- bpftool permission denied: `{diagnostics.get('bpftool_permission_denied')}`",
        "",
        "## Candidate Import Readiness",
        "",
        f"- Status: `{readiness.get('status')}`",
        f"- Candidate path: `{readiness.get('candidate_path')}`",
        f"- Can stage candidate: `{readiness.get('can_stage_candidate')}`",
        f"- Blocking reasons: `{', '.join(readiness.get('blocking_reasons', [])) or 'none'}`",
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


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def artifact_record(root: Path, path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": display_path(root, path),
        "sha256": sha256_file(path),
    }


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    stamp = stamp_from_timestamp(report["observed_at_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-kernel-attach-{stamp}"
    commands_path = bundle_dir / "commands.json"
    measurements_path = bundle_dir / "measurements.json"
    interface_scan_path = bundle_dir / "interface-scan.json"
    candidate_audit_path = bundle_dir / "candidate-audit.json"
    object_preflight_path = bundle_dir / "object-preflight.json"
    bundle_json = bundle_dir / "evidence.json"
    bundle_md = bundle_dir / "summary.md"

    bundle_dir.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    write_json(commands_path, report["commands"])
    write_json(
        measurements_path,
        {
            "measurements": report["measurements"],
            "failures": report["failures"],
            "claim_boundary": report["claim_boundary"],
        },
    )
    write_json(interface_scan_path, report["interface_scan"])
    write_json(candidate_audit_path, report["candidate_audit"])
    write_json(object_preflight_path, report["object_preflight"])
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = [
        artifact_record(root, commands_path, "kernel_commands"),
        artifact_record(root, measurements_path, "kernel_measurements"),
        artifact_record(root, interface_scan_path, "kernel_interface_scan"),
        artifact_record(root, candidate_audit_path, "kernel_candidate_audit"),
        artifact_record(root, object_preflight_path, "kernel_object_preflight"),
    ]

    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)
    atomic_write_text(bundle_json, rendered_json)
    atomic_write_text(bundle_md, rendered_md)
    atomic_write_text(output_json, rendered_json)
    atomic_write_text(output_md, rendered_md)
    return {
        "bundle_dir": bundle_dir,
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": output_json,
        "latest_md": output_md,
        "commands": commands_path,
        "measurements": measurements_path,
        "interface_scan": interface_scan_path,
        "candidate_audit": candidate_audit_path,
        "object_preflight": object_preflight_path,
    }


def default_iface() -> str:
    return "lo"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--iface", default=default_iface())
    parser.add_argument("--counter-wait-seconds", type=float, default=0.2)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument(
        "--bpftool-sudo",
        action="store_true",
        help=(
            "Run read-only bpftool observation commands through sudo -n. "
            "This never attaches XDP programs or mutates runtime state."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print the full evidence JSON.")
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = build_report(
        root=root,
        iface=args.iface,
        counter_wait_seconds=max(0.0, args.counter_wait_seconds),
        bpftool_sudo=args.bpftool_sudo,
    )
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
                    "bundle": display_path(root, paths["bundle_dir"]),
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
