#!/usr/bin/env python3
from __future__ import annotations

import calendar
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
STATE_PATH = STATE_DIR / "runtime-state.json"
LISTENER_SIGNAL_PATH = STATE_DIR / "listener-loss-signal.json"
VPN_AGENT_STATE_PATH = Path("/var/lib/ghost-access/vpn-service-access-agent/latest.json")
PUBLIC_PROTOCOLS = {"vless", "vmess", "trojan", "shadowsocks"}
PRIMARY_PORT = 443
DEFAULT_PUBLIC_PORTS = [443, 2083, 39829]
DEFAULT_AUXILIARY_PORTS = [2083, 39829]
XUI_CONFIG_PATHS = [
    Path("/usr/local/x-ui/bin/config.json"),
    Path("/usr/local/etc/xray/config.json"),
]
LISTENER_SIGNAL_TTL_SEC = 300


def parse_ports(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return list(default)
    ports: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            port = int(chunk)
        except ValueError:
            continue
        if 0 < port <= 65535:
            ports.append(port)
    return sorted(set(ports)) or list(default)


PUBLIC_PORT_FALLBACKS = parse_ports(
    os.environ.get("X0TTA_PUBLIC_INGRESS_PORTS"),
    DEFAULT_PUBLIC_PORTS,
)
AUXILIARY_PORTS = parse_ports(
    os.environ.get("X0TTA_AUXILIARY_INGRESS_PORTS"),
    DEFAULT_AUXILIARY_PORTS,
)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def tcp_ok(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def http_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=3) as response:  # noqa: S310
            return 200 <= response.status < 500
    except (URLError, OSError):
        return False


def service_ok(name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def established_count(port: int) -> int:
    try:
        result = subprocess.run(
            ["ss", "-tn", "state", "established"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
        return sum(1 for line in result.stdout.splitlines() if f":{port}" in line)
    except Exception:
        return 0


def load_previous() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_listener_signal() -> dict:
    if not LISTENER_SIGNAL_PATH.exists():
        return {}
    try:
        payload = json.loads(LISTENER_SIGNAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    generated_at = payload.get("timestamp") or payload.get("generated_at")
    if not generated_at:
        return {}

    try:
        parsed = time.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
        age_sec = int(time.time() - calendar.timegm(parsed))
    except Exception:
        return {}

    payload["age_sec"] = age_sec
    if age_sec > LISTENER_SIGNAL_TTL_SEC:
        payload["stale"] = True
        return payload

    payload["stale"] = False
    return payload


def load_vpn_agent_state() -> dict:
    if not VPN_AGENT_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(VPN_AGENT_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_public_ports(config_paths: list[Path] | None = None) -> list[int]:
    paths = config_paths if config_paths is not None else XUI_CONFIG_PATHS
    config_path = next((path for path in paths if path.exists()), None)
    if config_path is None:
        return list(PUBLIC_PORT_FALLBACKS)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return list(PUBLIC_PORT_FALLBACKS)

    ports: list[int] = []
    for inbound in config.get("inbounds", []):
        protocol = str(inbound.get("protocol", "")).lower()
        port = inbound.get("port")
        if protocol not in PUBLIC_PROTOCOLS:
            continue
        if not isinstance(port, int):
            continue
        ports.append(port)

    ports = sorted(set(ports)) or list(PUBLIC_PORT_FALLBACKS)
    if PRIMARY_PORT not in ports:
        ports.insert(0, PRIMARY_PORT)
    return ports


def normalize_subscription_health(subscription: dict | None) -> str:
    if not isinstance(subscription, dict):
        return "unknown"
    if subscription.get("direct_ok"):
        return "healthy"
    if subscription.get("http_proxy_ok") or subscription.get("socks5_ok"):
        return "degraded"
    return "unhealthy"


def select_subscription_summary(vpn_agent_state: dict | None) -> dict | None:
    if not isinstance(vpn_agent_state, dict):
        return None
    primary = vpn_agent_state.get("subscription")
    if isinstance(primary, dict):
        return primary
    fallback = vpn_agent_state.get("subscription_check")
    if isinstance(fallback, dict):
        return fallback
    return None


def build_hot_path_summary(probes: dict, mode: str, action: str, reason: str) -> dict:
    transport_summary = probes.get("transport_summary") or {}
    paths = (transport_summary.get("paths") or {}) if isinstance(transport_summary, dict) else {}

    def _path_value(path_id: str, field: str):
        path = paths.get(path_id) or {}
        return path.get(field)

    # Autonomous Failover Logic (for standalone nodes)
    best_path = str(transport_summary.get("best_path") or "")
    best_path_port = _path_value(best_path, "port") if best_path else None

    listener_status = probes.get("public_listener_status", {})

    if not best_path:
        if probes.get("listener_443_ok"):
            best_path = "primary"
            best_path_port = PRIMARY_PORT
        else:
            available_auxiliary = [
                port for port in AUXILIARY_PORTS if listener_status.get(str(port))
            ]
            if available_auxiliary:
                best_path = "secondary"
                best_path_port = available_auxiliary[0]
            else:
                best_path = "none"

    if best_path_port is None:
        available_auxiliary = [
            port for port in AUXILIARY_PORTS if listener_status.get(str(port))
        ]
        if best_path == "secondary" and available_auxiliary:
            best_path_port = available_auxiliary[0]
        elif best_path == "primary":
            best_path_port = PRIMARY_PORT

    secondary_default = AUXILIARY_PORTS[0] if AUXILIARY_PORTS else 2083

    return {
        "runtime_mode": mode,
        "recommended_action": action,
        "reason": reason,
        "transport_health_status": str(transport_summary.get("status") or "unknown"),
        "subscription_health_status": str(probes.get("subscription_health_status") or "unknown"),
        "warp_status": "healthy" if probes.get("warp_ok") else "degraded",
        "ghost_ready": bool(probes.get("ghost_ready")),
        "best_path": best_path or None,
        "best_path_port": best_path_port if isinstance(best_path_port, int) else None,
        "primary_path_latency_s": _path_value("main", "latency_s"),
        "secondary_path_latency_s": _path_value("secondary", "latency_s"),
        "fallback_nl_path_latency_s": _path_value("fallback_nl", "latency_s"),
        "primary_path_port": _path_value("main", "port") or PRIMARY_PORT,
        "secondary_path_port": _path_value("secondary", "port") or secondary_default,
        "fallback_nl_path_port": _path_value("fallback_nl", "port") or 2443,
        "telegram_media_status": str(transport_summary.get("telegram_media_status") or "unknown"),
        "telegram_media_best_target": transport_summary.get("telegram_media_best_target"),
        "telegram_media_best_latency_s": transport_summary.get("telegram_media_best_latency_s"),
        "telegram_media_worst_target": transport_summary.get("telegram_media_worst_target"),
        "telegram_media_worst_latency_s": transport_summary.get("telegram_media_worst_latency_s"),
        "telegram_media_latency_spread_s": transport_summary.get("telegram_media_latency_spread_s"),
        "routing_contract": {
            "ru_private": "direct",
            "foreign": "ghost-canary",
            "emergency_fallback": "nl-beta",
        },
    }


def decide(probes: dict, previous: dict) -> tuple[str, str, str]:
    previous_mode = previous.get("mode")
    secondary_failures = probes.get("secondary_listener_failures", [])
    any_public_sessions = probes.get("established_public_total", 0) > 0
    detector = probes.get("listener_loss_detector", {})
    transport_summary = probes.get("transport_summary", {})
    telegram_media_status = str((transport_summary or {}).get("telegram_media_status") or "")
    detector_active = (
        detector.get("present")
        and not detector.get("stale")
        and detector.get("status") == "ANOMALY_DETECTED"
        and detector.get("confidence", 1.0) < 0.70
    )
    best_path = str((transport_summary or {}).get("best_path") or "")
    transport_status = str((transport_summary or {}).get("status") or "")
    try:
        transport_delta = float((transport_summary or {}).get("main_vs_secondary_delta_s") or 0.0)
    except (TypeError, ValueError):
        transport_delta = 0.0

    if not probes["xui_service_ok"] or not probes["listener_443_ok"]:
        if probes["ghost_ready"]:
            mode = "fallback"
            action = "switch_fallback"
            reason = "primary listener :443 missing or x-ui inactive; ghost fallback ready"
        else:
            mode = "degraded"
            action = "restart_primary"
            reason = "primary listener :443 missing or x-ui inactive"
    elif secondary_failures:
        failed = ",".join(str(port) for port in secondary_failures)
        mode = "degraded"
        action = "switch_profile"
        reason = f"secondary public ingress listeners unavailable: {failed}"
    elif detector_active and probes["ghost_ready"]:
        mode = "anti_block"
        action = "switch_profile"
        reason = "listener-loss detector reported anomaly on primary ingress path"
    elif best_path == "secondary" and transport_status == "advisory" and transport_delta >= 0.25:
        mode = "degraded"
        action = "switch_profile"
        reason = "secondary ingress path is measurably faster than primary"
    elif (
        telegram_media_status in {"degraded", "unhealthy"}
        and transport_status in {"healthy", "advisory"}
    ):
        mode = "advisory"
        action = "observe"
        reason = "telegram media edges are slow, but VPN transport is usable"
    elif telegram_media_status in {"degraded", "unhealthy"}:
        mode = "degraded"
        action = "operator_review"
        reason = "telegram media edges are slow and transport health is not confirmed"
    elif telegram_media_status == "advisory":
        mode = "primary"
        action = "observe"
        reason = "telegram media edges show partial latency spread"
    elif not probes["warp_ok"]:
        mode = "primary"
        action = "observe"
        reason = "warp unavailable, but primary ingress is alive"
    elif not any_public_sessions and probes["ghost_ready"]:
        mode = "anti_block"
        action = "switch_profile"
        reason = "all public listeners alive but no established ingress sessions; possible blocking or drain state"
    else:
        mode = "primary"
        action = "observe"
        reason = "primary and secondary public ingress paths healthy"

    if previous_mode == "fallback" and mode == "primary":
        mode = "degraded"
        action = "observe"
        reason = "holding degraded after fallback until stability is re-verified"
    return mode, action, reason


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    previous = load_previous()
    public_ports = load_public_ports()
    listener_signal = load_listener_signal()
    vpn_agent_state = load_vpn_agent_state()
    auxiliary_listener_map = {str(port): tcp_ok(port) for port in AUXILIARY_PORTS}
    listener_map = {str(port): tcp_ok(port) for port in public_ports}
    established_map = {str(port): established_count(port) for port in public_ports}
    secondary_failures = [
        int(port) for port, ok in listener_map.items() if int(port) != PRIMARY_PORT and not ok
    ]

    subscription_summary = select_subscription_summary(vpn_agent_state)
    probes = {
        "public_ingress_ports": public_ports,
        "public_listener_status": listener_map,
        "public_established_sessions": established_map,
        "xui_auxiliary_ports": AUXILIARY_PORTS,
        "xui_auxiliary_listener_status": auxiliary_listener_map,
        "listener_443_ok": listener_map.get(str(PRIMARY_PORT), False),
        "xui_service_ok": service_ok("x-ui") or service_ok("xray"),
        "warp_ok": tcp_ok(40000),
        "ghost_metrics_ok": http_ok("http://127.0.0.1:9464/metrics"),
        "ghost_tcp_ready": tcp_ok(4434),
        "ghost_udp_ready": service_ok("ghost-vpn"),
        "established_443": established_map.get(str(PRIMARY_PORT), 0),
        "established_public_total": sum(established_map.values()),
        "secondary_listener_failures": secondary_failures,
        "transport_summary": vpn_agent_state.get("transport_summary") or {},
        "subscription_health_status": normalize_subscription_health(subscription_summary),
        "listener_loss_detector": {
            "present": bool(listener_signal),
            "stale": listener_signal.get("stale", False),
            "age_sec": listener_signal.get("age_sec"),
            "status": listener_signal.get("status"),
            "confidence": (
                listener_signal.get("metrics", {}).get("listener_health_confidence")
                if isinstance(listener_signal.get("metrics"), dict)
                else None
            ),
            "syn_rst_rate_per_sec": (
                listener_signal.get("metrics", {}).get("syn_rst_rate_per_sec")
                if isinstance(listener_signal.get("metrics"), dict)
                else None
            ),
        },
    }
    probes["ghost_ready"] = (
        probes["ghost_metrics_ok"] and probes["ghost_tcp_ready"] and probes["ghost_udp_ready"]
    )

    mode, action, reason = decide(probes, previous)
    hot_path_summary = build_hot_path_summary(probes, mode, action, reason)
    payload = {
        "generated_at": now_iso(),
        "mode": mode,
        "recommended_action": action,
        "reason": reason,
        "transition_from": previous.get("mode"),
        "source": "vps-runtime-state",
        "transport_summary": vpn_agent_state.get("transport_summary") or {},
        "hot_path_summary": hot_path_summary,
        "probes": probes,
    }
    STATE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
