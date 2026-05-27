#!/usr/bin/env python3
"""Classify a read-only VPN snapshot.

Input: directory created by collect_vpn_readonly_snapshot.sh.
Output: JSON status summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


VPN_SERVER = "89.125.1.107"
CORE_PORTS = ("443", "2083", "39829")
SNAPSHOT_MAX_AGE_SECONDS = 3600
NON_CRITICAL_FAILED_UNITS = {"ifup@eth0.service", "networking.service"}


def assess_blocking_context(
    *,
    overall_status: str,
    failure_domain: str,
    transport_status: str,
    telegram_status: str,
    runtime_mode: str,
    runtime_recommended_action: str,
    provider_status: str,
    current_core_healthy: bool,
    blocking_probe_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify censorship/blocking likelihood without allowing mutation.

    This is deliberately conservative. A blocking signal is not a restart signal:
    it should guide probes and profile review, not mutate NL automatically.
    """
    base: dict[str, Any] = {
        "category": "none",
        "confidence": "low",
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "recommended_probe": "continue normal health observation",
        "reason": "no blocking-specific signal",
    }

    if overall_status == "provider_outage" or failure_domain == "provider_host":
        return {
            **base,
            "category": "provider_or_host_issue",
            "confidence": "high",
            "recommended_probe": "build provider incident packet; do not restart x-ui for censorship symptoms",
            "reason": f"failure_domain={failure_domain}, provider_status={provider_status}",
        }

    probe_assessment = str((blocking_probe_summary or {}).get("assessment") or "")
    if current_core_healthy and probe_assessment in {
        "exit_ip_or_vpn_rejected",
        "possible_local_isp_block",
        "vpn_path_degraded",
        "app_specific_degradation",
    }:
        category = "app_specific_degradation"
        if probe_assessment == "exit_ip_or_vpn_rejected":
            category = "exit_ip_or_vpn_rejected"
        elif probe_assessment == "possible_local_isp_block":
            category = "possible_local_isp_block"
        elif probe_assessment == "vpn_path_degraded":
            category = "vpn_path_degraded"
        return {
            **base,
            "category": category,
            "confidence": "high",
            "recommended_probe": "review local blocking_probe targets; do not restart x-ui from app/path evidence alone",
            "reason": f"blocking probe assessment={probe_assessment}",
        }

    if failure_domain == "local_client" and overall_status == "critical":
        return {
            **base,
            "category": "local_client_issue",
            "confidence": "high",
            "recommended_probe": "fix local route/SOCKS/client state before testing censorship hypotheses",
            "reason": "local client health is critical",
        }

    if failure_domain == "nl_service" and overall_status == "critical":
        return {
            **base,
            "category": "nl_service_issue",
            "confidence": "high",
            "recommended_probe": "inspect NL services/listeners read-only; NL mutation still requires approval",
            "reason": "NL service or listener evidence is critical",
        }

    if runtime_mode == "anti_block" or runtime_recommended_action == "switch_profile":
        confidence = "high" if current_core_healthy and transport_status in {"healthy", "advisory"} else "medium"
        return {
            **base,
            "category": "anti_block_candidate",
            "confidence": confidence,
            "recommended_probe": "compare direct/http/socks/app probes and review profile switch manually",
            "reason": (
                f"runtime_mode={runtime_mode}, runtime_recommended_action={runtime_recommended_action}, "
                f"transport_status={transport_status}"
            ),
        }

    if telegram_status == "degraded" and transport_status in {"healthy", "advisory"}:
        return {
            **base,
            "category": "app_specific_degradation",
            "confidence": "medium",
            "recommended_probe": "test Telegram media separately from core VPN; do not restart x-ui",
            "reason": "Telegram/media degraded while core transport is healthy/advisory",
        }

    if overall_status == "degraded" and failure_domain == "external_network":
        return {
            **base,
            "category": "external_network_degradation",
            "confidence": "medium",
            "recommended_probe": "compare ISP/mobile/fixed routes and packet loss before changing profiles",
            "reason": "external network degradation without NL service failure",
        }

    return base


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_mixed_json(text: str) -> dict[str, Any]:
    match = re.search(r"(?m)^\{", text)
    if not match:
        return {}
    start = match.start()
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return {}


def non_comment_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def uncommented_text(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def parse_metric(text: str, name: str) -> float | None:
    pattern = re.compile(rf"^{re.escape(name)}\s+([-+]?\d+(?:\.\d+)?)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    return float(match.group(1))


def parse_failed_units(text: str) -> tuple[bool, list[str], list[str]]:
    if "0 loaded units listed" in text:
        return True, [], []
    units: list[str] = []
    for line in uncommented_text(text).splitlines():
        match = re.search(r"(?:●\s*)?(\S+\.service)\s+loaded\s+failed\s+failed", line)
        if match:
            units.append(match.group(1))
    if not text.strip() or not units:
        return False, [], []
    critical = [unit for unit in units if unit not in NON_CRITICAL_FAILED_UNITS]
    return not critical, units, critical


def parse_boot_gap_seconds(boot_history: str) -> int | None:
    previous_last = current_first = None
    for line in boot_history.splitlines():
        stripped = line.strip()
        if stripped.startswith("-1 "):
            match = re.search(
                r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)\s*$",
                stripped,
            )
            if match:
                previous_last = match.group(1)
        elif stripped.startswith("0 "):
            match = re.search(
                r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)",
                stripped,
            )
            if match:
                current_first = match.group(1)
    if not previous_last or not current_first:
        return None
    try:
        previous = datetime.strptime(previous_last, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        current = datetime.strptime(current_first, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, int((current - previous).total_seconds()))


def load_profile_switch_policy():
    path = Path(__file__).with_name("profile_switch_policy.py")
    spec = importlib.util.spec_from_file_location("profile_switch_policy_for_classifier", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["profile_switch_policy_for_classifier"] = module
    spec.loader.exec_module(module)
    return module


def snapshot_fresh(snapshot_dir: Path) -> bool:
    try:
        timestamp = datetime.strptime(snapshot_dir.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age_seconds = max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))
    return age_seconds <= SNAPSHOT_MAX_AGE_SECONDS


def classify(snapshot_dir: Path) -> dict[str, Any]:
    local_vpn = read_text(snapshot_dir / "local" / "vpn_status.txt")
    local_vpn_json = parse_mixed_json(read_text(snapshot_dir / "local" / "vpn_status.json"))
    local_route_vpn = read_text(snapshot_dir / "local" / "route_to_vpn.txt")
    local_route_public = read_text(snapshot_dir / "local" / "route_to_public.txt")
    watchdog_metrics = read_text(snapshot_dir / "local" / "watchdog_metrics.txt")
    blocking_probe = parse_mixed_json(read_text(snapshot_dir / "local" / "blocking_probe.json"))
    nl_failed_units = read_text(snapshot_dir / "nl" / "failed_units.txt")
    nl_key_services = read_text(snapshot_dir / "nl" / "key_services.txt")
    nl_listeners = read_text(snapshot_dir / "nl" / "listeners.txt")
    nl_runtime_raw = read_text(snapshot_dir / "nl" / "runtime_state_summary.txt")
    nl_boot_history = read_text(snapshot_dir / "nl" / "boot_history.txt")
    nl_current_boot_integrity = read_text(snapshot_dir / "nl" / "current_boot_integrity.txt")
    nl_provider_signals = read_text(snapshot_dir / "nl" / "provider_signals.txt")

    runtime = parse_mixed_json(nl_runtime_raw)
    runtime_hot = runtime.get("hot_path_summary", {}) if isinstance(runtime, dict) else {}
    runtime_probes = runtime.get("probes", {}) if isinstance(runtime, dict) else {}
    transport_summary = runtime_probes.get("transport_summary", {})

    evidence: list[str] = []
    problems: list[str] = []
    warnings: list[str] = []

    local_json_status = str(local_vpn_json.get("overall_status", "")) if isinstance(local_vpn_json, dict) else ""
    local_pass = local_json_status in {"ok", "advisory"} if local_json_status else "Result: PASS" in local_vpn
    if local_pass:
        if local_json_status:
            evidence.append(f"local vpn_status_json overall={local_json_status}")
        else:
            evidence.append("local vpn_status PASS")
    else:
        problems.append("local vpn_status is not PASS")

    route_bypass_ok = bool(local_route_vpn.strip()) and "singbox_tun" not in local_route_vpn
    if route_bypass_ok:
        evidence.append("route to VPN server bypasses singbox_tun")
    else:
        problems.append("route to VPN server may loop through tunnel")

    public_route_tun = "singbox_tun" in local_route_public
    if public_route_tun:
        evidence.append("generic traffic routes through singbox_tun")

    exit_ip = str(local_vpn_json.get("exit_ip", "")) if isinstance(local_vpn_json, dict) else ""
    exit_ip_ok = exit_ip == VPN_SERVER if exit_ip else "exit IP is VPN server" in local_vpn
    if exit_ip_ok:
        evidence.append("external exit IP is VPN server")
    else:
        problems.append("external exit IP is not confirmed as VPN server")

    proxy_healthy = parse_metric(watchdog_metrics, "vpn_proxy_healthy")
    packet_loss = None
    fin_wait2 = parse_metric(watchdog_metrics, "vpn_fin_wait2_connections")
    close_wait = parse_metric(watchdog_metrics, "vpn_close_wait_connections")

    if isinstance(local_vpn_json, dict):
        packet_loss_raw = local_vpn_json.get("packet_loss_percent")
        if isinstance(packet_loss_raw, (int, float)):
            packet_loss = float(packet_loss_raw)
    if packet_loss is None:
        packet_loss = parse_metric(watchdog_metrics, "vpn_packet_loss_percent")

    tcp_connections = local_vpn_json.get("tcp_connections", {}) if isinstance(local_vpn_json, dict) else {}
    if fin_wait2 is None and isinstance(tcp_connections, dict) and isinstance(tcp_connections.get("fin_wait_2"), (int, float)):
        fin_wait2 = float(tcp_connections["fin_wait_2"])
    if close_wait is None and isinstance(tcp_connections, dict) and isinstance(tcp_connections.get("close_wait"), (int, float)):
        close_wait = float(tcp_connections["close_wait"])

    if proxy_healthy == 1:
        evidence.append("watchdog proxy healthy")
    elif proxy_healthy is not None:
        problems.append("watchdog proxy unhealthy")

    if packet_loss is not None:
        evidence.append(f"packet_loss_percent={packet_loss:g}")
        if packet_loss >= 50:
            problems.append("critical packet loss")
        elif packet_loss >= 10:
            problems.append("elevated packet loss")

    if fin_wait2 is not None and fin_wait2 > 0:
        problems.append(f"FIN-WAIT-2={fin_wait2:g}")
    if close_wait is not None and close_wait > 0:
        problems.append(f"CLOSE-WAIT={close_wait:g}")

    failed_units_ok, failed_units, critical_failed_units = parse_failed_units(nl_failed_units)
    if failed_units_ok:
        if failed_units:
            evidence.append("NL failed units are known non-critical: " + ",".join(failed_units))
            warnings.append("NL non-critical failed units: " + ",".join(failed_units))
        else:
            evidence.append("NL systemctl --failed empty")
    else:
        if critical_failed_units:
            problems.append("NL critical failed units: " + ",".join(critical_failed_units))
        else:
            problems.append("NL has failed systemd units or failed_units evidence missing")

    services = non_comment_lines(nl_key_services)
    inactive_services = [line for line in services if line != "active"]
    if services and not inactive_services:
        evidence.append("NL key services active")
    elif inactive_services:
        problems.append("one or more NL key services inactive")

    missing_ports = [port for port in CORE_PORTS if f":{port}" not in nl_listeners]
    if not missing_ports:
        evidence.append("NL core listeners 443/2083/39829 present")
    else:
        problems.append("NL core listeners missing: " + ",".join(missing_ports))

    transport_status = (
        transport_summary.get("status")
        or runtime_hot.get("transport_health_status")
        or "unknown"
    )
    telegram_status = (
        transport_summary.get("telegram_media_status")
        or runtime_hot.get("telegram_media_status")
        or "unknown"
    )
    runtime_mode = runtime.get("mode", "unknown") if isinstance(runtime, dict) else "unknown"
    runtime_recommended_action = (
        runtime.get("recommended_action")
        or runtime_hot.get("recommended_action")
        or "unknown"
    ) if isinstance(runtime, dict) else "unknown"

    if transport_status in {"healthy", "advisory"}:
        evidence.append(f"NL transport_status={transport_status}")
    else:
        problems.append(f"NL transport_status={transport_status}")

    if runtime_recommended_action not in {"unknown", "observe", "", None}:
        warnings.append(f"NL runtime recommended_action={runtime_recommended_action}")

    current_core_healthy = (
        local_pass
        and route_bypass_ok
        and exit_ip_ok
        and proxy_healthy == 1
        and failed_units_ok
        and bool(services)
        and not inactive_services
        and not missing_ports
        and transport_status in {"healthy", "advisory"}
    )

    provider_text = uncommented_text(nl_boot_history + "\n" + nl_provider_signals).lower()
    provider_signal = any(
        marker in provider_text
        for marker in (
            "hypervisor initiated shutdown",
            "guest-shutdown called",
            "system is powering down",
        )
    )
    provider_status = "normal"
    boot_gap_seconds = parse_boot_gap_seconds(nl_boot_history)
    boot_integrity_text = uncommented_text(nl_current_boot_integrity).lower()
    unclean_boot = any(
        marker in boot_integrity_text
        for marker in (
            "uncleanly shut down",
            "corrupted or uncleanly",
            "recovering journal",
            "journal recovery",
        )
    )
    if unclean_boot:
        evidence.append("NL current boot reports previous journal uncleanly shut down")

    if provider_signal and current_core_healthy:
        provider_status = "historical_incident"
        evidence.append("historical provider shutdown signal present")
    elif provider_signal:
        provider_status = "suspect_active"
    elif boot_gap_seconds is not None and boot_gap_seconds >= 900:
        provider_status = "recent_boot_gap"
        warnings.append(f"NL boot gap seconds={boot_gap_seconds}")
    elif unclean_boot:
        provider_status = "unclean_reboot"

    if unclean_boot:
        warnings.append("NL previous boot ended uncleanly")

    if provider_signal and not current_core_healthy:
        overall_status = "provider_outage"
        failure_domain = "provider_host"
        recommended_action = "provider_ticket"
    elif not route_bypass_ok or not local_pass or proxy_healthy == 0 or not exit_ip_ok:
        overall_status = "critical"
        failure_domain = "local_client"
        recommended_action = "local_soft_heal"
    elif not failed_units_ok or inactive_services or missing_ports or transport_status not in {"healthy", "advisory"}:
        overall_status = "critical"
        failure_domain = "nl_service"
        recommended_action = "operator_review"
    elif packet_loss is not None and packet_loss >= 10:
        overall_status = "degraded"
        failure_domain = "external_network"
        recommended_action = "operator_review"
    elif runtime_mode == "degraded" or telegram_status == "degraded":
        overall_status = "advisory"
        failure_domain = "external_network"
        recommended_action = "observe"
    else:
        overall_status = "ok"
        failure_domain = "none"
        recommended_action = "observe"

    result = {
        "snapshot_dir": str(snapshot_dir),
        "overall_status": overall_status,
        "transport_status": transport_status,
        "telegram_media_status": telegram_status,
        "provider_status": provider_status,
        "runtime_mode": runtime_mode,
        "runtime_recommended_action": runtime_recommended_action,
        "failure_domain": failure_domain,
        "recommended_action": recommended_action,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "warnings": warnings,
        "problems": problems,
        "evidence": evidence,
    }
    if isinstance(blocking_probe, dict) and blocking_probe:
        result["blocking_probe_summary"] = blocking_probe.get("summary", {})
    result["blocking_assessment"] = assess_blocking_context(
        overall_status=overall_status,
        failure_domain=failure_domain,
        transport_status=transport_status,
        telegram_status=telegram_status,
        runtime_mode=str(runtime_mode),
        runtime_recommended_action=str(runtime_recommended_action),
        provider_status=provider_status,
        current_core_healthy=current_core_healthy,
        blocking_probe_summary=result.get("blocking_probe_summary"),
    )
    policy = load_profile_switch_policy()
    if policy is not None:
        profile_switch_decision = policy.decide_profile_switch(
            result,
            snapshot_fresh=snapshot_fresh(snapshot_dir),
        )
        result["profile_switch_policy"] = profile_switch_decision.to_dict()
        if profile_switch_decision.decision not in {"observe"}:
            warnings.append(f"profile_switch_policy={profile_switch_decision.decision}")

    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: classify_vpn_snapshot.py SNAPSHOT_DIR", file=sys.stderr)
        return 2

    snapshot_dir = Path(sys.argv[1]).resolve()
    if not snapshot_dir.is_dir():
        print(f"snapshot dir not found: {snapshot_dir}", file=sys.stderr)
        return 2

    print(json.dumps(classify(snapshot_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
