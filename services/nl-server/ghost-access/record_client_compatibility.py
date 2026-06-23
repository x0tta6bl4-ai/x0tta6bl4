#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import copy
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
CURRENT_EVIDENCE_REQUIRED_TRANSPORT = "reality"
CURRENT_EVIDENCE_REQUIRED_PORT = 443

ALLOWED_RESULTS = {"pass", "fail", "not_tested"}
ALLOWED_TRANSPORTS = {"xhttp", "ws", "reality", "preferred-working-fallback"}
ALLOWED_NETWORK_TYPES = {
    "desktop",
    "windows",
    "mobile",
    "work-wifi",
    "restricted-wifi",
    "home-wifi",
    "unknown",
}
SESSION_BOUND_NETWORK_TYPES = {"mobile", "work-wifi", "restricted-wifi"}

COMPLETION_REQUIREMENTS = {
    "desktop_v2rayn": "Desktop v2rayN",
    "android_happ_or_hiddify": "Android Happ/Hiddify",
    "mobile_network": "Mobile network",
    "restricted_or_work_wifi": "Restricted/work Wi-Fi",
}

NEXT_REQUIRED_CHECKS = {
    "desktop_v2rayn": [
        {
            "client": "v2rayN",
            "network_type": "desktop",
            "transport": "reality",
            "port": 443,
        }
    ],
    "android_happ_or_hiddify": [
        {
            "client": "Happ",
            "network_type": "mobile",
            "transport": "reality",
            "port": 443,
        }
    ],
    "mobile_network": [
        {
            "client": "Happ",
            "network_type": "mobile",
            "transport": "reality",
            "port": 443,
        }
    ],
    "restricted_or_work_wifi": [
        {
            "client": "any",
            "network_type": "work-wifi",
            "transport": "reality",
            "port": 443,
        }
    ],
}

FORBIDDEN_PATTERNS = {
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
    "secret_key": re.compile(r"\b(?:token|secret|uuid|password|subid|sub_id)\s*=", re.IGNORECASE),
}


class CompatibilityError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_datetime(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        return datetime.now(UTC).replace(microsecond=0)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CompatibilityError(f"checked_at must be ISO timestamp, got {value!r}") from exc
    if parsed.tzinfo is None:
        raise CompatibilityError("checked_at must include timezone")
    return parsed.astimezone(UTC).replace(microsecond=0)


def parse_utc_timestamp(value: str) -> str:
    return parse_utc_datetime(value).isoformat().replace("+00:00", "Z")


def normalize_client(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        raise CompatibilityError("client is required")
    aliases = {
        "v2rayn": "v2rayN",
        "happ": "Happ",
        "happ or hiddify": "Happ",
        "happ/hiddify": "Happ",
        "hiddify": "Hiddify",
        "v2rayng": "v2rayNG",
        "any": "any",
        "remote-user-city-case": "remote-user-city-case",
    }
    return aliases.get(text.lower(), text)


def normalize_transport(value: str) -> str:
    text = (value or "").strip().lower()
    aliases = {"websocket": "ws", "x-http": "xhttp"}
    text = aliases.get(text, text)
    if text not in ALLOWED_TRANSPORTS:
        raise CompatibilityError(f"unsupported transport: {value!r}")
    return text


def normalize_network_type(value: str) -> str:
    text = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "android": "mobile",
        "cellular": "mobile",
        "linux": "desktop",
        "mobile-operator": "mobile",
        "pc": "desktop",
        "windows": "desktop",
        "work": "work-wifi",
        "office-wifi": "work-wifi",
        "restricted": "restricted-wifi",
    }
    text = aliases.get(text, text)
    if text not in ALLOWED_NETWORK_TYPES:
        raise CompatibilityError(f"unsupported network_type: {value!r}")
    return text


def normalize_result(value: str) -> str:
    text = (value or "").strip().lower()
    aliases = {"ok": "pass", "passed": "pass", "failed": "fail"}
    text = aliases.get(text, text)
    if text not in ALLOWED_RESULTS:
        raise CompatibilityError(f"unsupported result: {value!r}")
    return text


def normalize_evidence_session_id(value: str) -> str:
    text = (value or CURRENT_EVIDENCE_SESSION_ID).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{3,80}", text):
        raise CompatibilityError("evidence_session_id must be a safe lowercase id")
    return text


def checked_at_in_current_session(value: str) -> bool:
    if not (value or "").strip():
        return False
    return parse_utc_datetime(value) >= parse_utc_datetime(CURRENT_EVIDENCE_SESSION_STARTED_AT)


def required_rollout_transport_ok(row: dict[str, Any]) -> bool:
    try:
        transport = normalize_transport(str(row.get("transport") or ""))
    except CompatibilityError:
        return False
    return transport == CURRENT_EVIDENCE_REQUIRED_TRANSPORT and row.get("port") == CURRENT_EVIDENCE_REQUIRED_PORT


def check_no_secret_text(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(check_no_secret_text(nested, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(check_no_secret_text(nested, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings

    for name, pattern in FORBIDDEN_PATTERNS.items():
        if pattern.search(value):
            findings.append({"path": path, "kind": name})
    return findings


def validate_report(report: dict[str, Any]) -> list[dict[str, str]]:
    findings = check_no_secret_text(report)
    for index, row in enumerate(report.get("real_client_checks") or []):
        if not isinstance(row, dict):
            findings.append({"path": f"$.real_client_checks[{index}]", "kind": "row_not_object"})
            continue
        if row.get("raw_secret_material_stored") is not False and row.get("status") != "not_tested":
            findings.append(
                {
                    "path": f"$.real_client_checks[{index}].raw_secret_material_stored",
                    "kind": "raw_secret_material_not_false",
                }
            )
    return findings


def load_matrix(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompatibilityError(f"matrix not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CompatibilityError(f"matrix is not valid JSON: {exc}") from exc


def write_matrix(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    findings = validate_report(payload)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise CompatibilityError(f"refusing to render unsafe matrix: {details}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def build_check_row(
    *,
    checked_at: str,
    client: str,
    client_version: str,
    network_type: str,
    transport: str,
    port: int | None,
    result: str,
    symptom: str,
    evidence_session_id: str = CURRENT_EVIDENCE_SESSION_ID,
) -> dict[str, Any]:
    row = {
        "checked_at": parse_utc_timestamp(checked_at),
        "client": normalize_client(client),
        "client_version": (client_version or "unknown").strip() or "unknown",
        "network_type": normalize_network_type(network_type),
        "transport": normalize_transport(transport),
        "port": port,
        "status": normalize_result(result),
        "symptom": " ".join((symptom or "").strip().split()) or "none",
        "evidence_session_id": normalize_evidence_session_id(evidence_session_id),
        "raw_secret_material_stored": False,
    }
    if (
        row["status"] == "pass"
        and row["evidence_session_id"] == CURRENT_EVIDENCE_SESSION_ID
        and row["network_type"] in SESSION_BOUND_NETWORK_TYPES
        and not checked_at_in_current_session(str(row["checked_at"]))
    ):
        raise CompatibilityError(
            f"session-bound pass evidence must be checked at or after {CURRENT_EVIDENCE_SESSION_STARTED_AT}"
        )
    if (
        row["status"] == "pass"
        and row["evidence_session_id"] == CURRENT_EVIDENCE_SESSION_ID
        and row["network_type"] in SESSION_BOUND_NETWORK_TYPES
        and not required_rollout_transport_ok(row)
    ):
        raise CompatibilityError(
            f"session-bound pass evidence must use {CURRENT_EVIDENCE_REQUIRED_TRANSPORT}:{CURRENT_EVIDENCE_REQUIRED_PORT}"
        )
    findings = check_no_secret_text(row)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise CompatibilityError(f"unsafe client compatibility evidence: {details}")
    return row


def _same_check(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        normalize_client(str(left.get("client") or "")) == normalize_client(str(right.get("client") or ""))
        and normalize_network_type(str(left.get("network_type") or "unknown"))
        == normalize_network_type(str(right.get("network_type") or "unknown"))
        and normalize_transport(str(left.get("transport") or "preferred-working-fallback"))
        == normalize_transport(str(right.get("transport") or "preferred-working-fallback"))
        and left.get("port") == right.get("port")
    )


def add_or_update_check(matrix: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    next_matrix = copy.deepcopy(matrix)
    checks = next_matrix.setdefault("real_client_checks", [])
    if not isinstance(checks, list):
        raise CompatibilityError("real_client_checks must be a list")

    for index, existing in enumerate(checks):
        if isinstance(existing, dict) and _same_check(existing, row):
            checks[index] = {**existing, **row}
            break
    else:
        checks.append(row)

    refresh_completion(next_matrix)
    findings = validate_report(next_matrix)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise CompatibilityError(f"matrix failed privacy validation: {details}")
    return next_matrix


def _passing_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in matrix.get("real_client_checks") or []
        if isinstance(row, dict) and row.get("status") == "pass"
    ]


def _current_session_required(row: dict[str, Any]) -> bool:
    network = normalize_network_type(str(row.get("network_type") or "unknown"))
    return network in SESSION_BOUND_NETWORK_TYPES


def _current_session_ok(row: dict[str, Any]) -> bool:
    if not _current_session_required(row):
        return True
    return (
        row.get("evidence_session_id") == CURRENT_EVIDENCE_SESSION_ID
        and checked_at_in_current_session(str(row.get("checked_at") or ""))
        and required_rollout_transport_ok(row)
    )


def _current_session_passing_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in _passing_checks(matrix) if _current_session_ok(row)]


def _session_bound_current_passing_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in _passing_checks(matrix)
        if _current_session_required(row) and _current_session_ok(row)
    ]


def completion_status(matrix: dict[str, Any]) -> dict[str, bool]:
    rows = _passing_checks(matrix)
    current_session_rows = _current_session_passing_checks(matrix)
    desktop_v2rayn = any(
        normalize_client(str(row.get("client") or "")).lower() == "v2rayn"
        and normalize_network_type(str(row.get("network_type") or "unknown")) in {"desktop", "windows"}
        for row in rows
    )
    android_happ_or_hiddify = any(
        normalize_client(str(row.get("client") or "")).lower() in {"happ", "hiddify"}
        and normalize_network_type(str(row.get("network_type") or "unknown")) == "mobile"
        for row in current_session_rows
    )
    mobile_network = any(
        normalize_network_type(str(row.get("network_type") or "unknown")) == "mobile"
        for row in current_session_rows
    )
    restricted_or_work_wifi = any(
        normalize_network_type(str(row.get("network_type") or "unknown")) in {"work-wifi", "restricted-wifi"}
        for row in current_session_rows
    )
    return {
        "desktop_v2rayn": desktop_v2rayn,
        "android_happ_or_hiddify": android_happ_or_hiddify,
        "mobile_network": mobile_network,
        "restricted_or_work_wifi": restricted_or_work_wifi,
    }


def missing_requirements(matrix: dict[str, Any]) -> list[str]:
    status = completion_status(matrix)
    return [key for key, proven in status.items() if not proven]


def next_required_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int | None]] = set()
    for requirement in missing_requirements(matrix):
        for row in NEXT_REQUIRED_CHECKS.get(requirement, []):
            identity = (
                str(row.get("client")),
                str(row.get("network_type")),
                str(row.get("transport")),
                row.get("port"),
            )
            if identity in seen:
                continue
            seen.add(identity)
            planned.append({"requirement": requirement, **row})
    return planned


def refresh_completion(matrix: dict[str, Any]) -> None:
    status = completion_status(matrix)
    complete = all(status.values())
    missing = [key for key, proven in status.items() if not proven]
    matrix["decision"] = (
        "CLIENT_MATRIX_COMPLETE" if complete else "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED"
    )
    matrix["last_updated_utc"] = utc_now()
    rule = matrix.setdefault("completion_rule", {})
    if isinstance(rule, dict):
        rule.pop("windows_v2rayn_required", None)
        rule["desktop_v2rayn_required"] = True
        rule["android_happ_or_hiddify_required"] = True
        rule["mobile_network_required"] = True
        rule["restricted_or_work_wifi_required"] = True
        rule["evidence"] = status
        rule["evidence_session"] = {
            "id": CURRENT_EVIDENCE_SESSION_ID,
            "started_at": CURRENT_EVIDENCE_SESSION_STARTED_AT,
            "required_transport": CURRENT_EVIDENCE_REQUIRED_TRANSPORT,
            "required_port": CURRENT_EVIDENCE_REQUIRED_PORT,
            "required_for_network_types": sorted(SESSION_BOUND_NETWORK_TYPES),
            "session_bound_current_passing_checks": len(
                _session_bound_current_passing_checks(matrix)
            ),
            "session_bound_requirements": {
                "android_happ_or_hiddify": status["android_happ_or_hiddify"],
                "mobile_network": status["mobile_network"],
                "restricted_or_work_wifi": status["restricted_or_work_wifi"],
            },
        }
        rule["missing_requirements"] = missing
        rule["next_required_checks"] = next_required_checks(matrix)
        rule["current_status"] = "complete" if complete else "not_complete"


def build_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    findings = validate_report(matrix)
    status = completion_status(matrix)
    refresh_completion(matrix)
    rule = matrix.get("completion_rule") if isinstance(matrix.get("completion_rule"), dict) else {}
    return {
        "ok": not findings,
        "decision": matrix.get("decision"),
        "privacy_findings": findings,
        "completion": status,
        "missing_requirements": missing_requirements(matrix),
        "next_required_checks": next_required_checks(matrix),
        "complete": all(status.values()),
        "evidence_session": rule.get("evidence_session") if isinstance(rule, dict) else {},
        "real_client_checks": len(matrix.get("real_client_checks") or []),
        "passing_real_client_checks": len(_passing_checks(matrix)),
        "session_bound_current_passing_checks": len(_session_bound_current_passing_checks(matrix)),
    }


def markdown_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (list, tuple)):
        text = ", ".join(markdown_cell(item) for item in value)
    elif isinstance(value, dict):
        text = ", ".join(f"{key}={markdown_cell(nested)}" for key, nested in value.items())
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_server_evidence(matrix: dict[str, Any]) -> str:
    rows = matrix.get("server_side_evidence") or []
    lines = [
        "| Case | Transport | Port | Evidence | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence_parts = []
        for key in (
            "line_count",
            "counts",
            "ports",
            "http_code",
            "total_s",
            "ghost_xhttp_ready",
            "ghost_https_ws_ready",
            "nginx_counter_present",
            "decision",
            "critical_services_stayed_active",
        ):
            if key in row:
                evidence_parts.append(f"{key}={markdown_cell(row[key])}")
        transport = row.get("transport") or row.get("transports") or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.get("case")),
                    markdown_cell(transport),
                    markdown_cell(row.get("port")),
                    markdown_cell("; ".join(evidence_parts) if evidence_parts else "recorded"),
                    markdown_cell(row.get("status")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_real_client_checks(matrix: dict[str, Any]) -> str:
    rows = matrix.get("real_client_checks") or []
    lines = [
        "| Client | Version | Network | Transport | Port | Status | Evidence Session | Checked At | Symptom |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.get("client")),
                    markdown_cell(row.get("client_version", "unknown")),
                    markdown_cell(row.get("network_type")),
                    markdown_cell(row.get("transport")),
                    markdown_cell(row.get("port")),
                    markdown_cell(row.get("status")),
                    markdown_cell(row.get("evidence_session_id", "")),
                    markdown_cell(row.get("checked_at", "")),
                    markdown_cell(row.get("symptom", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_local_client_inventory(matrix: dict[str, Any]) -> str:
    inventory = matrix.get("local_client_inventory")
    if not isinstance(inventory, dict):
        return "No local client inventory evidence recorded."
    profile = inventory.get("profile_inventory") or {}
    subscription = (inventory.get("subscription_inventory") or {}).get("aggregate") or {}
    lines = [
        "| Source | Diagnosis | Reality | XHTTP | WS | Ports |",
        "| --- | --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(inventory.get("source")),
                markdown_cell(inventory.get("diagnosis")),
                markdown_cell((profile.get("counts") or {}).get("reality")),
                markdown_cell((profile.get("counts") or {}).get("xhttp")),
                markdown_cell((profile.get("counts") or {}).get("ws")),
                markdown_cell(profile.get("ports")),
            ]
        )
        + " |",
        "| "
        + " | ".join(
            [
                "enabled_subscription_fetch",
                "subscription_aggregate",
                markdown_cell((subscription.get("counts") or {}).get("reality")),
                markdown_cell((subscription.get("counts") or {}).get("xhttp")),
                markdown_cell((subscription.get("counts") or {}).get("ws")),
                markdown_cell(subscription.get("ports")),
            ]
        )
        + " |",
    ]
    return "\n".join(lines)


def render_local_import_copy_test(matrix: dict[str, Any]) -> str:
    result = matrix.get("local_v2rayn_fallback_import_copy_test")
    if not isinstance(result, dict):
        return "No local v2rayN fallback import copy-test recorded."
    inserted = result.get("inserted_profiles") or {}
    remaining = result.get("remaining_missing_after_copy") or {}
    after = result.get("copy_inventory_after_import") or {}
    lines = [
        "| Decision | Live DB Mutated | Inserted XHTTP | Inserted WS | Remaining Missing | Copy Counts After Import |",
        "| --- | --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(result.get("decision")),
                markdown_cell(result.get("applied_to_live_db")),
                markdown_cell((inserted.get("counts") or {}).get("xhttp")),
                markdown_cell((inserted.get("counts") or {}).get("ws")),
                markdown_cell(remaining.get("total")),
                markdown_cell(after.get("counts")),
            ]
        )
        + " |",
    ]
    return "\n".join(lines)


def render_local_import_live(matrix: dict[str, Any]) -> str:
    result = matrix.get("local_v2rayn_fallback_import_live")
    if not isinstance(result, dict):
        return "No local v2rayN live fallback import recorded."
    inserted = result.get("inserted_profiles") or {}
    remaining = result.get("remaining_missing_after_live") or {}
    lines = [
        "| Decision | Live DB Mutated | Restarted v2rayN | Inserted XHTTP | Inserted WS | Remaining Missing | Backup |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(result.get("decision")),
                markdown_cell(result.get("applied_to_live_db")),
                markdown_cell(result.get("restarted_v2rayn")),
                markdown_cell((inserted.get("counts") or {}).get("xhttp")),
                markdown_cell((inserted.get("counts") or {}).get("ws")),
                markdown_cell(remaining.get("total")),
                markdown_cell("recorded" if result.get("backup_path") else "missing"),
            ]
        )
        + " |",
    ]
    return "\n".join(lines)


def render_local_dataplane_probe(matrix: dict[str, Any]) -> str:
    result = matrix.get("local_v2rayn_dataplane_probe")
    if not isinstance(result, dict):
        return "No local v2rayN dataplane probe recorded."
    lines = [
        "| Source | OK | Passed Transports | Profile Count |",
        "| --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(result.get("source")),
                markdown_cell(result.get("ok")),
                markdown_cell(result.get("passed_transports")),
                markdown_cell(result.get("profile_count")),
            ]
        )
        + " |",
        "",
        "| Transport | Port | HTTP Code | Total Seconds | OK |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result.get("results") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.get("transport")),
                    markdown_cell(row.get("port")),
                    markdown_cell(row.get("http_code")),
                    markdown_cell(row.get("total_s")),
                    markdown_cell(row.get("ok")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_completion(matrix: dict[str, Any]) -> str:
    rule = matrix.get("completion_rule") or {}
    evidence = rule.get("evidence") if isinstance(rule, dict) else None
    if not isinstance(evidence, dict):
        evidence = completion_status(matrix)
    lines = [
        f"`evidence_session_id={markdown_cell(CURRENT_EVIDENCE_SESSION_ID)}`. Mobile/work-Wi-Fi pass evidence must use this session id.",
        "",
        "| Requirement | Proven |",
        "| --- | --- |",
        f"| Desktop v2rayN | {markdown_cell(evidence.get('desktop_v2rayn'))} |",
        f"| Android Happ/Hiddify | {markdown_cell(evidence.get('android_happ_or_hiddify'))} |",
        f"| Mobile network | {markdown_cell(evidence.get('mobile_network'))} |",
        f"| Restricted/work Wi-Fi | {markdown_cell(evidence.get('restricted_or_work_wifi'))} |",
    ]
    return "\n".join(lines)


def render_next_required_checks(matrix: dict[str, Any]) -> str:
    rows = next_required_checks(matrix)
    lines = [
        "| Requirement | Client | Network | Transport | Port |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(COMPLETION_REQUIREMENTS.get(str(row.get("requirement")), row.get("requirement"))),
                    markdown_cell(row.get("client")),
                    markdown_cell(row.get("network_type")),
                    markdown_cell(row.get("transport")),
                    markdown_cell(row.get("port")),
                ]
            )
            + " |"
        )
    if not rows:
        lines.append("| none |  |  |  |  |")
    return "\n".join(lines)


def render_markdown(matrix: dict[str, Any]) -> str:
    summary = build_summary(matrix)
    recorder = matrix.get("evidence_recorder") or {}
    recorder_path = recorder.get("path") or "services/nl-server/ghost-access/record_client_compatibility.py"
    return (
        "# NL Anti-Block Client Compatibility Matrix - 2026-06-02\n\n"
        "## Decision\n\n"
        f"`{markdown_cell(matrix.get('decision'))}`\n\n"
        "This file is generated from the JSON matrix. Keep JSON as the source of truth and use the recorder CLI to add real checks.\n\n"
        "No VPN links, UUIDs, raw IPs, emails, subscription tokens, or client hashes are stored here.\n\n"
        "## Completion\n\n"
        f"`complete={markdown_cell(summary['complete'])}`; "
        f"`passing_real_client_checks={markdown_cell(summary['passing_real_client_checks'])}`; "
        f"`real_client_checks={markdown_cell(summary['real_client_checks'])}`.\n\n"
        f"`missing_requirements={markdown_cell(summary['missing_requirements'])}`.\n\n"
        f"{render_completion(matrix)}\n\n"
        "## Next Required Checks\n\n"
        f"{render_next_required_checks(matrix)}\n\n"
        "## Proven Server-Side\n\n"
        f"{render_server_evidence(matrix)}\n\n"
        "## Required Real Client Checks\n\n"
        f"{render_real_client_checks(matrix)}\n\n"
        "## Local Client Inventory\n\n"
        f"{render_local_client_inventory(matrix)}\n\n"
        "## Local Import Copy-Test\n\n"
        f"{render_local_import_copy_test(matrix)}\n\n"
        "## Local Live Import\n\n"
        f"{render_local_import_live(matrix)}\n\n"
        "## Local Dataplane Probe\n\n"
        f"{render_local_dataplane_probe(matrix)}\n\n"
        "## Safe Recorder\n\n"
        "Add real client evidence with the local privacy-safe recorder:\n\n"
        "```bash\n"
        f"python3 {recorder_path} \\\n"
        "  --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json \\\n"
        "  --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md \\\n"
        "  --add-check \\\n"
        "  --checked-at 2026-06-02T01:00:00Z \\\n"
        "  --client v2rayN \\\n"
        "  --client-version unknown \\\n"
        "  --network-type desktop \\\n"
        "  --transport reality \\\n"
        "  --port 443 \\\n"
        "  --result pass \\\n"
        "  --symptom \"connected normal HTTPS sites\" \\\n"
        f"  --evidence-session-id {CURRENT_EVIDENCE_SESSION_ID} \\\n"
        "  --json\n"
        "```\n\n"
        "Validate and regenerate Markdown without adding a result:\n\n"
        "```bash\n"
        f"python3 {recorder_path} \\\n"
        "  --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json \\\n"
        "  --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md \\\n"
        "  --validate \\\n"
        "  --json\n"
        "```\n\n"
        "Do not store subscription URLs, `/sub/...` tokens, VLESS links, UUIDs, raw IP addresses, emails, Telegram IDs, usernames, QR codes, or screenshots that show secrets.\n"
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Record privacy-safe NL client compatibility evidence.")
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--markdown", type=Path, default=None, help="write synced Markdown matrix")
    p.add_argument("--json", action="store_true", help="print JSON summary")
    p.add_argument("--validate", action="store_true", help="validate matrix and exit")
    p.add_argument("--sync", action="store_true", help="refresh matrix status and write JSON/Markdown")
    p.add_argument("--add-check", action="store_true", help="add or update one real client check")
    p.add_argument("--checked-at", default="")
    p.add_argument("--client", default="")
    p.add_argument("--client-version", default="unknown")
    p.add_argument("--network-type", default="")
    p.add_argument("--transport", default="")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--result", default="")
    p.add_argument("--symptom", default="")
    p.add_argument("--evidence-session-id", default=CURRENT_EVIDENCE_SESSION_ID)
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        matrix = load_matrix(args.matrix)
        if args.add_check:
            row = build_check_row(
                checked_at=args.checked_at,
                client=args.client,
                client_version=args.client_version,
                network_type=args.network_type,
                transport=args.transport,
                port=args.port,
                result=args.result,
                symptom=args.symptom,
                evidence_session_id=args.evidence_session_id,
            )
            matrix = add_or_update_check(matrix, row)
            write_matrix(args.matrix, matrix)
        elif args.sync:
            refresh_completion(matrix)
            findings = validate_report(matrix)
            if findings:
                details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
                raise CompatibilityError(f"matrix failed privacy validation: {details}")
            write_matrix(args.matrix, matrix)
        elif args.validate:
            refresh_completion(matrix)
        else:
            raise CompatibilityError("use --validate, --sync, or --add-check")
        if args.markdown:
            write_markdown(args.markdown, matrix)
        summary = build_summary(matrix)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ok={str(summary['ok']).lower()} decision={summary['decision']}")
        return 0 if summary["ok"] else 1
    except CompatibilityError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
