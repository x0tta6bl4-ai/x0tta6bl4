#!/usr/bin/env python3
"""Score public metadata candidates for a future secondary VPN exit.

The scorer is local planning only. It does not connect to candidates, does not
connect to NL/SPB, does not store profile secrets, and does not mutate VPN
state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_CANDIDATES = DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.md"

NL_IP = "89.125.1.107"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.I),
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
)
SPB_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bspb\b", re.I),
    re.compile(r"saint[-\s]+petersburg", re.I),
    re.compile(r"санкт", re.I),
    re.compile(r"петербург", re.I),
)
NL_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnl\b", re.I),
    re.compile(r"\.nl\b", re.I),
    re.compile(r"\bnetherlands\b", re.I),
    re.compile(r"\bnederland\b", re.I),
    re.compile(r"\bamsterdam\b", re.I),
)
PLACEHOLDER_MARKERS = ("replace_", "tbd", "todo", "example.invalid", "<", "unconfigured")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("candidate file must be a JSON object")
    validate_no_secrets(value)
    return value


def validate_no_secrets(value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("candidate file appears to contain a VPN secret or private credential")


def candidate_text(candidate: dict[str, Any]) -> str:
    keys = ("label", "provider", "region", "host", "country", "notes")
    return " ".join(str(candidate.get(key) or "") for key in keys).lower()


def normalized_ports(raw_ports: Any) -> list[int]:
    if not isinstance(raw_ports, list):
        return []
    ports: list[int] = []
    for raw in raw_ports:
        try:
            port = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 < port < 65536 and port not in ports:
            ports.append(port)
    return ports


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def has_placeholder(value: str) -> bool:
    text = value.lower().strip()
    return not text or any(marker in text for marker in PLACEHOLDER_MARKERS)


def has_text_pattern(value: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def public_host_ok(host: str) -> bool:
    if not host or has_placeholder(host):
        return False
    if host == NL_IP:
        return False
    if is_ip(host):
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)
    return "." in host and " " not in host


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    label = str(candidate.get("label") or "unnamed").strip()
    provider = str(candidate.get("provider") or "").strip()
    region = str(candidate.get("region") or "").strip()
    host = str(candidate.get("host") or "").strip()
    ports = normalized_ports(candidate.get("tcp_ports"))
    text = candidate_text(candidate)

    issues: list[str] = []
    score = 0

    if not provider or has_placeholder(provider):
        issues.append("provider_missing")
    else:
        score += 20
    if not region or has_placeholder(region):
        issues.append("region_missing")
    else:
        score += 15
    if has_text_pattern(text, SPB_TEXT_PATTERNS):
        issues.append("spb_marker")
    else:
        score += 10
    if has_text_pattern(text, NL_TEXT_PATTERNS):
        issues.append("nl_marker")
    else:
        score += 10
    if host == NL_IP:
        issues.append("current_nl_ip")
    if public_host_ok(host):
        score += 25
    else:
        issues.append("public_host_missing_or_invalid")
    if ports:
        score += 15
        if 443 in ports:
            score += 5
    else:
        issues.append("tcp_ports_missing")

    viable = not issues
    return {
        "label": label,
        "provider": provider or "missing",
        "region": region or "missing",
        "host": host if host else "missing",
        "tcp_ports": ports,
        "score": score,
        "viable": viable,
        "issues": issues,
    }


def build_payload(candidate_file: Path) -> dict[str, Any]:
    payload = read_json(candidate_file)
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    rows = [score_candidate(row if isinstance(row, dict) else {}) for row in raw_candidates]
    viable = [row for row in rows if row["viable"]]
    rejected = [row for row in rows if not row["viable"]]
    top = sorted(viable, key=lambda row: (-int(row["score"]), str(row["label"])))
    if viable:
        status = "candidate_pool_ready"
    elif rows:
        status = "candidate_pool_no_viable"
    else:
        status = "missing_candidates"
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/score_secondary_exit_candidates.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_file": str(candidate_file),
        "status": status,
        "summary": {
            "candidate_count": len(rows),
            "viable_count": len(viable),
            "rejected_count": len(rejected),
            "top_candidate_label": top[0]["label"] if top else "none",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidates": rows,
        "next_step": (
            "fill public metadata for at least one non-NL/non-SPB candidate"
            if not viable
            else "generate a secondary probe config for the top viable candidate"
        ),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Candidate Score",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"candidate_file: `{payload['candidate_file']}`",
        "",
        "## Status",
        "",
        "```text",
        f"status={payload['status']}",
        f"candidate_count={summary.get('candidate_count')}",
        f"viable_count={summary.get('viable_count')}",
        f"rejected_count={summary.get('rejected_count')}",
        f"top_candidate_label={summary.get('top_candidate_label')}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        f"Next step: {payload['next_step']}",
        "",
        "## Candidates",
        "",
        "| Label | Viable | Score | Provider | Region | Host | Ports | Issues |",
        "|---|---:|---:|---|---|---|---|---|",
    ]
    for row in payload["candidates"]:
        lines.append(
            "| "
            f"`{row['label']}` | "
            f"`{str(row['viable']).lower()}` | "
            f"`{row['score']}` | "
            f"`{row['provider']}` | "
            f"`{row['region']}` | "
            f"`{row['host']}` | "
            f"`{','.join(str(port) for port in row['tcp_ports']) or 'none'}` | "
            f"`{','.join(row['issues']) or 'none'}` |"
        )
    lines.extend(["", "No NL or SPB writes were performed by this candidate scorer."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score public secondary exit candidates")
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    try:
        payload = build_payload(Path(args.candidates))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "schema_version": 1,
            "source": "nl-diagnostics/score_secondary_exit_candidates.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidate_file": str(args.candidates),
            "status": "candidate_file_error",
            "error": str(exc),
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        }
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
