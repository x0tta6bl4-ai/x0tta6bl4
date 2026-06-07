#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 9472
STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
RUNTIME_STATE_PATH = STATE_DIR / "runtime-state.json"
SIGNAL_PATH = STATE_DIR / "listener-loss-signal.json"
HINT_PATH = STATE_DIR / "client-profile-hint.json"
CLIENT_COMPATIBILITY_PATH = Path(
    os.getenv(
        "CLIENT_COMPATIBILITY_PATH",
        "/var/lib/ghost-access/client-compatibility/latest.json",
    )
)

SECRET_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_health() -> dict:
    runtime = load_json(RUNTIME_STATE_PATH)
    signal = load_json(SIGNAL_PATH)
    hint = load_json(HINT_PATH)
    transport_usage = build_transport_usage(runtime)
    return {
        "generated_at": now_iso(),
        "service": "vps-profile-status-api",
        "runtime_mode": runtime.get("mode"),
        "recommended_action": runtime.get("recommended_action"),
        "ghost_xhttp_ready": transport_usage.get("ghost_xhttp_ready"),
        "ghost_https_ws_ready": transport_usage.get("ghost_https_ws_ready"),
        "subscription_health_status": transport_usage.get("subscription_health_status"),
        "transport_usage_ok": transport_usage.get("ok"),
        "transport_usage_60m": transport_usage.get("transport_usage_60m"),
        "listener_signal_status": signal.get("status"),
        "recommended_profile": hint.get("recommended_profile"),
        "ok": bool(runtime),
    }


def _dict_value(payload: dict, key: str) -> dict:
    value = payload.get(key) if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}


def _safe_list(values: object) -> list[str]:
    return [str(value) for value in values] if isinstance(values, list) else []


def _safe_next_required_checks(values: object) -> list[dict]:
    checks = []
    if not isinstance(values, list):
        return checks
    for row in values:
        if not isinstance(row, dict):
            continue
        checks.append(
            {
                "requirement": str(row.get("requirement") or ""),
                "client": str(row.get("client") or ""),
                "network_type": str(row.get("network_type") or ""),
                "transport": str(row.get("transport") or ""),
                "port": row.get("port") if isinstance(row.get("port"), int) else None,
            }
        )
    return checks


def _safe_evidence_session(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    session_bound = _dict_value(value, "session_bound_requirements")
    return {
        "id": str(value.get("id") or ""),
        "started_at": str(value.get("started_at") or ""),
        "required_transport": str(value.get("required_transport") or ""),
        "required_port": value.get("required_port")
        if isinstance(value.get("required_port"), int)
        else None,
        "required_for_network_types": _safe_list(value.get("required_for_network_types")),
        "session_bound_current_passing_checks": value.get(
            "session_bound_current_passing_checks"
        )
        if isinstance(value.get("session_bound_current_passing_checks"), int)
        else 0,
        "session_bound_requirements": {
            "android_happ_or_hiddify": session_bound.get("android_happ_or_hiddify")
            is True,
            "mobile_network": session_bound.get("mobile_network") is True,
            "restricted_or_work_wifi": session_bound.get("restricted_or_work_wifi")
            is True,
        },
    }


def _count_real_client_checks(values: object) -> tuple[int, int]:
    if not isinstance(values, list):
        return 0, 0
    total = sum(1 for row in values if isinstance(row, dict))
    passing = sum(
        1 for row in values if isinstance(row, dict) and row.get("status") == "pass"
    )
    return total, passing


def _safe_dataplane_probe(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {}
    results = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        results.append(
            {
                "transport": str(row.get("transport") or ""),
                "port": row.get("port") if isinstance(row.get("port"), int) else None,
                "ok": row.get("ok") is True,
                "http_code": row.get("http_code") if isinstance(row.get("http_code"), int) else None,
                "total_s": row.get("total_s") if isinstance(row.get("total_s"), (int, float)) else None,
            }
        )
    return {
        "checked_at": str(payload.get("checked_at") or ""),
        "ok": payload.get("ok") is True,
        "passed_transports": _safe_list(payload.get("passed_transports")),
        "profile_count": payload.get("profile_count")
        if isinstance(payload.get("profile_count"), int)
        else None,
        "target_url_class": str(payload.get("target_url_class") or ""),
        "results": results,
    }


def _client_compatibility_payload_from_summary(summary: dict) -> dict:
    completion = _dict_value(summary, "completion")
    payload = {
        "generated_at": now_iso(),
        "service": "vps-profile-status-api",
        "source_generated_at": summary.get("generated_at") or summary.get("source_generated_at"),
        "decision": summary.get("decision"),
        "current_status": summary.get("current_status"),
        "complete": summary.get("complete") is True,
        "completion": {
            "desktop_v2rayn": completion.get("desktop_v2rayn") is True,
            "android_happ_or_hiddify": completion.get("android_happ_or_hiddify") is True,
            "mobile_network": completion.get("mobile_network") is True,
            "restricted_or_work_wifi": completion.get("restricted_or_work_wifi") is True,
        },
        "missing_requirements": _safe_list(summary.get("missing_requirements")),
        "next_required_checks": _safe_next_required_checks(summary.get("next_required_checks")),
        "evidence_session": _safe_evidence_session(summary.get("evidence_session")),
        "real_client_checks": summary.get("real_client_checks")
        if isinstance(summary.get("real_client_checks"), int)
        else 0,
        "passing_real_client_checks": summary.get("passing_real_client_checks")
        if isinstance(summary.get("passing_real_client_checks"), int)
        else 0,
        "local_v2rayn_dataplane_probe": _safe_dataplane_probe(
            summary.get("local_v2rayn_dataplane_probe")
        ),
        "privacy": {
            "output_privacy_ok": True,
            "raw_real_client_rows_returned": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
        },
        "ok": summary.get("ok") is True,
    }
    findings = _privacy_findings(payload)
    if findings:
        payload["ok"] = False
        payload["privacy"]["output_privacy_ok"] = False
        payload["privacy_findings"] = findings
    return payload


def _privacy_findings(payload: dict) -> list[str]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(rendered)]


def build_client_compatibility() -> dict:
    matrix = load_json(CLIENT_COMPATIBILITY_PATH)
    if not matrix:
        return {
            "generated_at": now_iso(),
            "service": "vps-profile-status-api",
            "ok": False,
            "error": "client compatibility summary missing",
            "complete": False,
        }

    if "completion_rule" not in matrix and isinstance(matrix.get("completion"), dict):
        return _client_compatibility_payload_from_summary(matrix)

    rule = _dict_value(matrix, "completion_rule")
    completion = _dict_value(rule, "evidence")
    total_checks, passing_checks = _count_real_client_checks(matrix.get("real_client_checks"))
    payload = {
        "generated_at": now_iso(),
        "service": "vps-profile-status-api",
        "source_generated_at": matrix.get("last_updated_utc") or matrix.get("generated_at"),
        "decision": matrix.get("decision"),
        "current_status": rule.get("current_status"),
        "complete": rule.get("current_status") == "complete",
        "completion": {
            "desktop_v2rayn": completion.get("desktop_v2rayn") is True,
            "android_happ_or_hiddify": completion.get("android_happ_or_hiddify") is True,
            "mobile_network": completion.get("mobile_network") is True,
            "restricted_or_work_wifi": completion.get("restricted_or_work_wifi") is True,
        },
        "missing_requirements": _safe_list(rule.get("missing_requirements")),
        "next_required_checks": _safe_next_required_checks(rule.get("next_required_checks")),
        "evidence_session": _safe_evidence_session(rule.get("evidence_session")),
        "real_client_checks": total_checks,
        "passing_real_client_checks": passing_checks,
        "local_v2rayn_dataplane_probe": _safe_dataplane_probe(
            matrix.get("local_v2rayn_dataplane_probe")
        ),
        "privacy": {
            "output_privacy_ok": True,
            "raw_real_client_rows_returned": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
        },
        "ok": True,
    }
    findings = _privacy_findings(payload)
    if findings:
        payload["ok"] = False
        payload["privacy"]["output_privacy_ok"] = False
        payload["privacy_findings"] = findings
    return payload


def build_transport_usage(runtime: dict | None = None) -> dict:
    runtime = runtime if isinstance(runtime, dict) else load_json(RUNTIME_STATE_PATH)
    probes = _dict_value(runtime, "probes")
    hot_path = _dict_value(runtime, "hot_path_summary")
    usage_evidence = _dict_value(probes, "transport_usage_evidence")
    hot_summary = _dict_value(hot_path, "transport_usage_60m")
    evidence_summary = _dict_value(usage_evidence, "summary_60m")
    summary = hot_summary or evidence_summary

    return {
        "generated_at": now_iso(),
        "service": "vps-profile-status-api",
        "runtime_generated_at": runtime.get("generated_at"),
        "usage_generated_at": usage_evidence.get("generated_at"),
        "runtime_mode": runtime.get("mode"),
        "recommended_action": runtime.get("recommended_action"),
        "ghost_xhttp_ready": bool(probes.get("ghost_xhttp_ready")),
        "ghost_https_ws_ready": bool(probes.get("ghost_https_ws_ready")),
        "subscription_health_status": probes.get("subscription_health_status"),
        "transport_usage_60m": summary,
        "ok": bool(runtime) and bool(summary) and summary.get("privacy_ok") is True,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send_json(build_health())
        if path == "/transport-usage":
            payload = build_transport_usage()
            return self._send_json(payload or {"error": "transport usage missing"}, 200 if payload.get("ok") else 503)
        if path == "/client-compatibility":
            payload = build_client_compatibility()
            return self._send_json(
                payload or {"error": "client compatibility missing"},
                200 if payload.get("ok") else 503,
            )
        if path == "/runtime-state":
            payload = load_json(RUNTIME_STATE_PATH)
            return self._send_json(payload or {"error": "runtime-state missing"}, 200 if payload else 503)
        if path == "/listener-loss-signal":
            payload = load_json(SIGNAL_PATH)
            return self._send_json(payload or {"error": "listener-loss-signal missing"}, 200 if payload else 503)
        if path == "/client-profile-hint":
            payload = load_json(HINT_PATH)
            return self._send_json(payload or {"error": "client-profile-hint missing"}, 200 if payload else 503)
        return self._send_json({"error": "not found", "path": path}, 404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"profile status api listening on http://{HOST}:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
