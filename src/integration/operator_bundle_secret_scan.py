"""Read-only secret scan for integration-spine operator return packets."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_RETURN_PACKET = ".tmp/validation-shards/integration-spine-production-input-return-packet-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-operator-bundle-secret-scan-current.json"

SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token_assignment", re.compile(r"(?i)(api|bot|telegram|github|aws|secret|private)[_-]?(token|key|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _walk_strings(value: Any, path: str = "$") -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(_walk_strings(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk_strings(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        rows.append({"path": path, "value": value})
    return rows


def _findings(text: str, parsed: Optional[Any]) -> List[Dict[str, str]]:
    rows = _walk_strings(parsed) if parsed is not None else [{"path": "$", "value": text}]
    findings: List[Dict[str, str]] = []
    for row in rows:
        value = row["value"]
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(value):
                findings.append(
                    {
                        "kind": label,
                        "path": row["path"],
                        "redacted_preview": value[:8] + "...",
                    }
                )
    return findings


def build_report(root: Path, return_packet_path: Path) -> Dict[str, Any]:
    text = _read_text(return_packet_path)
    source_errors: List[str] = []
    parsed: Optional[Any] = None
    if text is None:
        source_errors.append(f"missing or unreadable return packet: {DEFAULT_RETURN_PACKET}")
        text = ""
    else:
        try:
            parsed = json.loads(text)
        except Exception:
            source_errors.append("return packet is not valid JSON")

    findings = _findings(text, parsed) if not source_errors else []
    clear = not source_errors and not findings
    return {
        "schema_version": "x0tta6bl4-integration-spine-operator-bundle-secret-scan-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "secret_scan_decision": "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR" if clear else "OPERATOR_BUNDLE_SECRET_SCAN_BLOCKED",
        "ready_for_stage": clear,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only secret scan for the operator return packet. It scans "
            "local JSON/string content for obvious private keys and token material. It does "
            "not stage evidence, contact live systems, mutate runtime state, or close /goal."
        ),
        "mutates_files": False,
        "source_artifacts": [DEFAULT_RETURN_PACKET],
        "source_errors": source_errors,
        "findings": findings,
        "not_verified_yet": [] if clear else ["operator return packet secret scan is clear"],
        "summary": {
            "source_errors_total": len(source_errors),
            "secret_scan_findings": len(findings),
            "secret_scan_source_errors": len(source_errors),
            "secret_scan_clear": clear,
            "return_packet_json_valid": parsed is not None,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Operator Bundle Secret Scan",
            f"secret_scan_decision: {report.get('secret_scan_decision')}",
            f"secret_scan_findings: {summary.get('secret_scan_findings')}",
            f"source_errors_total: {summary.get('source_errors_total')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan integration-spine operator return packet for obvious secrets")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--return-packet-json", default=DEFAULT_RETURN_PACKET)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-clear", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    packet_input = Path(args.return_packet_json)
    report = build_report(root, packet_input if packet_input.is_absolute() else root / packet_input)
    output_input = Path(args.output_json)
    write_json(output_input if output_input.is_absolute() else root / output_input, report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_clear and report["secret_scan_decision"] != "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
