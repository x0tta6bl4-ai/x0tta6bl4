#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_STATUS_API_CANDIDATES = [
    ROOT / "mesh-runtime" / "profile_status_api.py",
    Path("/opt/x0tta6bl4-mesh/scripts/profile_status_api.py"),
]
DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.md"
)


class RuntimeSummaryError(ValueError):
    pass


def profile_status_api_path() -> Path:
    env_path = os.getenv("PROFILE_STATUS_API_PATH")
    candidates = [Path(env_path)] if env_path else []
    candidates.extend(PROFILE_STATUS_API_CANDIDATES)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    rendered = ", ".join(str(candidate) for candidate in candidates)
    raise RuntimeSummaryError(f"profile status API source not found: {rendered}")


def load_status_api_module(path: Path | None = None) -> Any:
    status_api_path = path or profile_status_api_path()
    spec = importlib.util.spec_from_file_location("profile_status_api", status_api_path)
    if spec is None or spec.loader is None:
        raise RuntimeSummaryError(f"cannot load profile status API: {status_api_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_summary(matrix_path: Path) -> dict[str, Any]:
    module = load_status_api_module()
    module.CLIENT_COMPATIBILITY_PATH = matrix_path
    payload = module.build_client_compatibility()
    if not isinstance(payload, dict):
        raise RuntimeSummaryError("runtime summary is not a JSON object")
    if payload.get("ok") is not True:
        detail = payload.get("error") or payload.get("privacy_findings") or "unknown"
        raise RuntimeSummaryError(f"runtime summary is not safe/available: {detail}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def render_markdown(payload: dict[str, Any]) -> str:
    completion = payload.get("completion") if isinstance(payload.get("completion"), dict) else {}
    evidence_session = (
        payload.get("evidence_session")
        if isinstance(payload.get("evidence_session"), dict)
        else {}
    )
    lines = [
        "# NL Anti-Block Client Compatibility Runtime Summary - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(payload.get('decision'))}`",
        "",
        "This is the safe summary intended for the local status API `/client-compatibility`. It does not include raw client rows, symptoms, VPN links, UUIDs, raw IPs, emails, Telegram handles, phone numbers, QR codes, or screenshots.",
        "",
        "## Completion",
        "",
        "| Requirement | Proven |",
        "| --- | --- |",
        f"| desktop_v2rayN | {markdown_cell(completion.get('desktop_v2rayn'))} |",
        f"| android_happ_or_hiddify | {markdown_cell(completion.get('android_happ_or_hiddify'))} |",
        f"| mobile_network | {markdown_cell(completion.get('mobile_network'))} |",
        f"| restricted_or_work_wifi | {markdown_cell(completion.get('restricted_or_work_wifi'))} |",
        "",
        "## Counts",
        "",
        "| Complete | Missing | Real Checks | Passing Checks |",
        "| --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(payload.get("complete")),
                markdown_cell(payload.get("missing_requirements")),
                markdown_cell(payload.get("real_client_checks")),
                markdown_cell(payload.get("passing_real_client_checks")),
            ]
        )
        + " |",
        "",
        "## Evidence Session",
        "",
        "| ID | Started At | Required Transport | Required Port | Current Session Passes |",
        "| --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(evidence_session.get("id")),
                markdown_cell(evidence_session.get("started_at")),
                markdown_cell(evidence_session.get("required_transport")),
                markdown_cell(evidence_session.get("required_port")),
                markdown_cell(
                    evidence_session.get("session_bound_current_passing_checks")
                ),
            ]
        )
        + " |",
        "",
    ]
    return "\n".join(lines)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build the privacy-safe client compatibility summary consumed by /client-compatibility."
    )
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = build_summary(args.matrix)
        if args.write:
            write_json(args.json_out, payload)
            write_markdown(args.markdown_out, payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={payload.get('decision')} "
                f"complete={str(payload.get('complete')).lower()}"
            )
        return 0
    except RuntimeSummaryError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
