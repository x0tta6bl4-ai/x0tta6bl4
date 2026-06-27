#!/usr/bin/env python3
"""Build a local provider incident evidence packet from read-only snapshots.

The script reads local files only. It does not connect to NL and does not
change local or remote VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
DEFAULT_OUTPUT_DIR = DIAGNOSTICS_DIR / "provider-incident-packets"
DEFAULT_INCIDENT_REPORT = DIAGNOSTICS_DIR / "incident-2026-05-26.md"
SNAPSHOT_MAX_AGE_SECONDS = 3600
VPN_SERVER = "89.125.1.107"
HOSTNAME = "01164.com"


SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35,}"), "REDACTED_BOT_TOKEN"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "REDACTED_PRIVATE_KEY"),
    (re.compile(r"\b(vless|vmess|trojan|ss)://[^\s)]+", re.I), "REDACTED_VPN_URI"),
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "REDACTED_UUID"),
    (re.compile(r"(?i)(token|secret|password|privateKey|publicKey|webBasePath)\s*[:=]\s*['\"]?[^,'\"\s}]+"), r"\1=REDACTED"),
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def redact(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def parse_snapshot_timestamp(snapshot_dir: Path | None) -> datetime | None:
    if snapshot_dir is None:
        return None
    try:
        return datetime.strptime(snapshot_dir.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def snapshot_age_seconds(snapshot_dir: Path | None, now: datetime | None = None) -> int | None:
    timestamp = parse_snapshot_timestamp(snapshot_dir)
    if timestamp is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - timestamp).total_seconds()))


def parse_mixed_json(text: str) -> dict[str, Any]:
    match = re.search(r"(?m)^\{", text)
    if not match:
        return {}
    try:
        value = json.loads(text[match.start():])
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_classifier():
    path = DIAGNOSTICS_DIR / "classify_vpn_snapshot.py"
    spec = importlib.util.spec_from_file_location("classify_vpn_snapshot_for_packet", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load classifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify_vpn_snapshot_for_packet"] = module
    spec.loader.exec_module(module)
    return module


def extract_matching_lines(text: str, patterns: tuple[str, ...], *, limit: int = 12) -> list[str]:
    compiled = [re.compile(pattern, re.I) for pattern in patterns]
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not re.match(r"^(?:[A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d|\d{4}-\d\d-\d\d[T\s]\d\d:\d\d:\d\d)", line):
            continue
        if any(pattern.search(line) for pattern in compiled):
            redacted = redact(line)
            if redacted not in seen:
                lines.append(redacted)
                seen.add(redacted)
    return lines[-limit:]


def parse_boot_window(boot_history: str) -> dict[str, str | None]:
    previous_first = previous_last = current_first = None
    for line in boot_history.splitlines():
        if line.strip().startswith("-1 "):
            match = re.search(r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)\s+([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)$", line)
            if match:
                previous_first, previous_last = match.group(1), match.group(2)
        elif line.strip().startswith("0 "):
            match = re.search(r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)", line)
            if match:
                current_first = match.group(1)
    return {
        "previous_boot_first_entry": previous_first,
        "previous_boot_last_entry": previous_last,
        "current_boot_first_entry": current_first,
    }


def parse_current_cpu_steal(provider_signals: str) -> float | None:
    for line in provider_signals.splitlines():
        if not line.startswith("Average:"):
            continue
        parts = line.split()
        # Average: all %usr %nice %sys %iowait %irq %soft %steal %guest %gnice %idle
        if len(parts) >= 9 and parts[1] == "all":
            try:
                return float(parts[8])
            except ValueError:
                return None
    return None


def extract_historical_metrics(incident_report: str) -> dict[str, str | None]:
    metrics = {
        "max_cpu_steal": None,
        "max_load_average": None,
        "max_disk_await": None,
    }
    steal = re.search(r"CPU steal reached\s+([0-9.]+%)", incident_report)
    load = re.search(r"load average reached\s+([0-9.]+)", incident_report)
    await_match = re.search(r"vda disk await reached\s+([0-9.]+\s*ms)", incident_report)
    if steal:
        metrics["max_cpu_steal"] = steal.group(1)
    if load:
        metrics["max_load_average"] = load.group(1)
    if await_match:
        metrics["max_disk_await"] = await_match.group(1)
    return metrics


def decide_packet_type(
    classification: dict[str, Any],
    current_shutdown_lines: list[str],
    historical_shutdown_lines: list[str],
) -> tuple[str, str]:
    overall = classification.get("overall_status")
    failure_domain = classification.get("failure_domain")
    action = classification.get("recommended_action")
    provider_status = classification.get("provider_status")

    if overall == "provider_outage" or failure_domain == "provider_host" or action == "provider_ticket":
        return "provider_ticket", "current evidence points to provider or host failure"
    if provider_status == "recent_boot_gap":
        return "provider_watch", "recent NL boot gap is present; current VPN transport is healthy"
    if current_shutdown_lines and provider_status == "historical_incident":
        return "historical_provider_incident", "historical hypervisor shutdown evidence is present; current VPN is not in provider outage"
    if current_shutdown_lines:
        return "provider_watch", "provider shutdown evidence exists, but current classification needs review"
    if historical_shutdown_lines:
        return "historical_provider_incident", "historical provider shutdown evidence is present; current VPN is not in provider outage"
    return "observe", "no provider outage evidence in the selected snapshot"


def build_provider_ticket_text(
    boot_window: dict[str, str | None],
    current_shutdown_lines: list[str],
    current_unclean_boot_lines: list[str],
    historical_metrics: dict[str, str | None],
    historical_shutdown_lines: list[str] | None = None,
) -> str:
    lines = [
        f"Hello. Please check the host node for VPS {HOSTNAME} / IP {VPN_SERVER}.",
        "",
    ]
    if current_shutdown_lines:
        lines.append("The selected guest snapshot shows evidence of a hypervisor-initiated shutdown:")
        lines.extend(f"- {line}" for line in current_shutdown_lines[:4])
    else:
        lines.append(
            "The selected guest snapshot shows a boot gap, but no explicit "
            "hypervisor-initiated shutdown line was found in the available journal."
        )
        if historical_shutdown_lines:
            lines.append("")
            lines.append("Historical related shutdown evidence from a previous incident:")
            lines.extend(f"- {line}" for line in historical_shutdown_lines[:4])
    if current_unclean_boot_lines:
        lines.append("")
        lines.append("The current boot journal also reports an unclean previous shutdown:")
        lines.extend(f"- {line}" for line in current_unclean_boot_lines[:4])
    lines.extend(
        [
            "",
            "Boot window from guest journal:",
            f"- previous boot last entry: {boot_window.get('previous_boot_last_entry') or 'unknown'}",
            f"- current boot first entry: {boot_window.get('current_boot_first_entry') or 'unknown'}",
            "",
            "Host-side degradation observed before shutdown:",
            f"- CPU steal reached: {historical_metrics.get('max_cpu_steal') or 'unknown'}",
            f"- load average reached: {historical_metrics.get('max_load_average') or 'unknown'}",
            f"- vda disk await reached: {historical_metrics.get('max_disk_await') or 'unknown'}",
            "",
            "Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.",
        ]
    )
    return redact("\n".join(lines))


def build_packet(snapshot_dir: Path, incident_report: Path, now: datetime | None = None) -> dict[str, Any]:
    classifier = load_classifier()
    classification = classifier.classify(snapshot_dir)

    local_status = parse_mixed_json(read_text(snapshot_dir / "local" / "vpn_status.json"))
    runtime_state = parse_mixed_json(read_text(snapshot_dir / "nl" / "runtime_state_summary.txt"))
    provider_signals = read_text(snapshot_dir / "nl" / "provider_signals.txt")
    boot_history = read_text(snapshot_dir / "nl" / "boot_history.txt")
    current_boot_integrity = read_text(snapshot_dir / "nl" / "current_boot_integrity.txt")
    incident_text = read_text(incident_report)

    current_shutdown_lines = extract_matching_lines(
        provider_signals,
        (
            r"guest-shutdown called",
            r"hypervisor initiated shutdown",
            r"System is powering down",
        ),
        limit=8,
    )
    historical_shutdown_lines = extract_matching_lines(
        incident_text,
        (
            r"guest-shutdown called",
            r"hypervisor initiated shutdown",
            r"System is powering down",
        ),
        limit=8,
    )
    current_unclean_boot_lines = extract_matching_lines(
        current_boot_integrity,
        (
            r"uncleanly shut down",
            r"corrupted or uncleanly",
            r"recovering journal",
            r"journal recovery",
        ),
        limit=8,
    )
    boot_window = parse_boot_window(boot_history)
    historical_metrics = extract_historical_metrics(incident_text)
    current_cpu_steal = parse_current_cpu_steal(provider_signals)
    packet_type, decision_reason = decide_packet_type(
        classification,
        current_shutdown_lines,
        historical_shutdown_lines,
    )
    age_seconds = snapshot_age_seconds(snapshot_dir, now)

    hot_path = runtime_state.get("hot_path_summary", {}) if isinstance(runtime_state, dict) else {}
    ticket_text = build_provider_ticket_text(
        boot_window,
        current_shutdown_lines,
        current_unclean_boot_lines,
        historical_metrics,
        historical_shutdown_lines,
    )

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_provider_incident_packet.py",
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "snapshot_dir": str(snapshot_dir),
        "snapshot_age_seconds": age_seconds,
        "snapshot_max_age_seconds": SNAPSHOT_MAX_AGE_SECONDS,
        "snapshot_stale": age_seconds is None or age_seconds > SNAPSHOT_MAX_AGE_SECONDS,
        "packet_type": packet_type,
        "decision_reason": decision_reason,
        "nl_write_performed": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
        "vpn_server": VPN_SERVER,
        "hostname": HOSTNAME,
        "classification": classification,
        "local_status": {
            "overall_status": local_status.get("overall_status"),
            "failure_domain": local_status.get("failure_domain"),
            "recommended_action": local_status.get("recommended_action"),
            "exit_ip": local_status.get("exit_ip"),
            "packet_loss_percent": local_status.get("packet_loss_percent"),
            "tcp_connections": local_status.get("tcp_connections"),
        },
        "nl_runtime": {
            "mode": runtime_state.get("mode"),
            "reason": hot_path.get("reason") or runtime_state.get("reason"),
            "recommended_action": runtime_state.get("recommended_action") or hot_path.get("recommended_action"),
            "transport_health_status": hot_path.get("transport_health_status"),
            "telegram_media_status": hot_path.get("telegram_media_status"),
            "best_path_port": hot_path.get("best_path_port"),
        },
        "provider_evidence": {
            "shutdown_lines": current_shutdown_lines or historical_shutdown_lines,
            "current_shutdown_lines": current_shutdown_lines,
            "current_unclean_boot_lines": current_unclean_boot_lines,
            "historical_shutdown_lines": historical_shutdown_lines,
            "boot_window": boot_window,
            "historical_metrics": historical_metrics,
            "current_cpu_steal_percent": current_cpu_steal,
        },
        "provider_ticket_text": ticket_text,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    classification = packet["classification"]
    local_status = packet["local_status"]
    nl_runtime = packet["nl_runtime"]
    provider = packet["provider_evidence"]
    lines = [
        f"# Provider Incident Packet, {packet['generated_at']}",
        "",
        "## Status",
        "",
        "```text",
        f"packet_type: {packet['packet_type']}",
        f"decision_reason: {packet['decision_reason']}",
        f"snapshot: {packet['snapshot_dir']}",
        f"snapshot_age_seconds: {packet['snapshot_age_seconds']}",
        f"snapshot_stale: {packet['snapshot_stale']}",
        "NL writes: 0",
        "```",
        "",
        "## Current VPN Classification",
        "",
        "```text",
        f"overall_status: {classification.get('overall_status')}",
        f"failure_domain: {classification.get('failure_domain')}",
        f"recommended_action: {classification.get('recommended_action')}",
        f"transport_status: {classification.get('transport_status')}",
        f"telegram_media_status: {classification.get('telegram_media_status')}",
        f"provider_status: {classification.get('provider_status')}",
        f"runtime_recommended_action: {classification.get('runtime_recommended_action')}",
        f"warnings: {classification.get('warnings')}",
        "```",
    ]
    if classification.get("profile_switch_policy"):
        lines.extend(
            [
                "",
                "Profile switch policy:",
                "",
                "```json",
                json.dumps(classification["profile_switch_policy"], indent=2, ensure_ascii=False, sort_keys=True),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Local Client Evidence",
            "",
            "```text",
            f"local_overall_status: {local_status.get('overall_status')}",
            f"local_failure_domain: {local_status.get('failure_domain')}",
            f"exit_ip: {local_status.get('exit_ip')}",
            f"packet_loss_percent: {local_status.get('packet_loss_percent')}",
            f"tcp_connections: {local_status.get('tcp_connections')}",
            "```",
            "",
            "## NL Runtime Evidence",
            "",
            "```text",
            f"mode: {nl_runtime.get('mode')}",
            f"reason: {nl_runtime.get('reason')}",
            f"recommended_action: {nl_runtime.get('recommended_action')}",
            f"transport_health_status: {nl_runtime.get('transport_health_status')}",
            f"telegram_media_status: {nl_runtime.get('telegram_media_status')}",
            f"best_path_port: {nl_runtime.get('best_path_port')}",
            "```",
            "",
            "## Provider Evidence",
            "",
            "Current snapshot shutdown lines:",
            "",
            "```text",
        ]
    )
    lines.extend(provider.get("current_shutdown_lines") or ["none"])
    lines.extend(
        [
            "```",
            "",
            "Current boot unclean-shutdown lines:",
            "",
            "```text",
        ]
    )
    lines.extend(provider.get("current_unclean_boot_lines") or ["none"])
    lines.extend(
        [
            "```",
            "",
            "Historical shutdown lines:",
            "",
            "```text",
        ]
    )
    lines.extend(provider.get("historical_shutdown_lines") or ["none"])
    lines.extend(
        [
            "```",
            "",
            "Boot window:",
            "",
            "```text",
        ]
    )
    for key, value in provider["boot_window"].items():
        lines.append(f"{key}: {value}")
    lines.extend(
        [
            "```",
            "",
            "Host metrics:",
            "",
            "```text",
            f"historical_max_cpu_steal: {provider['historical_metrics'].get('max_cpu_steal')}",
            f"historical_max_load_average: {provider['historical_metrics'].get('max_load_average')}",
            f"historical_max_disk_await: {provider['historical_metrics'].get('max_disk_await')}",
            f"current_cpu_steal_percent: {provider.get('current_cpu_steal_percent')}",
            "```",
            "",
            "## Provider Ticket Text",
            "",
            "```text",
            packet["provider_ticket_text"],
            "```",
            "",
            "## Local Rule",
            "",
            "This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.",
            "",
        ]
    )
    return redact("\n".join(str(line) for line in lines))


def output_paths(output_dir: Path, snapshot_dir: Path) -> tuple[Path, Path]:
    stem = f"provider-incident-packet-{snapshot_dir.name}"
    return output_dir / f"{stem}.json", output_dir / f"{stem}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", help="Snapshot directory. Defaults to latest local snapshot.")
    parser.add_argument("--snapshots-dir", default=str(SNAPSHOTS_DIR))
    parser.add_argument("--incident-report", default=str(DEFAULT_INCIDENT_REPORT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--json", action="store_true", help="Print packet JSON to stdout")
    parser.add_argument("--no-write", action="store_true", help="Do not write output files")
    args = parser.parse_args()

    snapshots_dir = Path(args.snapshots_dir).resolve()
    snapshot_dir = Path(args.snapshot_dir).resolve() if args.snapshot_dir else latest_snapshot(snapshots_dir)
    if snapshot_dir is None or not snapshot_dir.is_dir():
        print("snapshot dir not found", file=sys.stderr)
        return 2

    packet = build_packet(snapshot_dir, Path(args.incident_report).resolve())
    markdown = render_markdown(packet)

    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))

    if not args.no_write:
        json_path, markdown_path = output_paths(Path(args.output_dir).resolve(), snapshot_dir)
        write_text(json_path, json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        write_text(markdown_path, markdown)
        if not args.json:
            print(f"json: {json_path}")
            print(f"markdown: {markdown_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
