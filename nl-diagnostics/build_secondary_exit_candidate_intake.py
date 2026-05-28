#!/usr/bin/env python3
"""Build a safe intake checklist for secondary exit candidates.

The intake report tells an operator what public metadata can be added to the
candidate file. It does not choose a provider, does not store secrets, does
not connect to NL/SPB, and does not mutate VPN state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_CANDIDATE_FILE = DIAGNOSTICS_DIR / "secondary-exit-candidates.example.json"
DEFAULT_CANDIDATE_SCORE = DIAGNOSTICS_DIR / "secondary-exit-candidate-score-2026-05-28.json"
DEFAULT_REQUIREMENTS = DIAGNOSTICS_DIR / "secondary-exit-requirements-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-candidate-intake-2026-05-28.md"


ALLOWED_FIELDS = [
    "label",
    "provider",
    "region",
    "country",
    "host",
    "tcp_ports",
    "notes",
]
FORBIDDEN_MATERIAL = [
    "raw VPN URI",
    "UUID",
    "private key",
    "bot token",
    "subscription link",
    "NL endpoint",
    "SPB endpoint",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def candidate_template() -> dict[str, Any]:
    return {
        "label": "secondary-1",
        "provider": "FILL_PUBLIC_PROVIDER_NAME",
        "region": "FILL_PUBLIC_REGION",
        "country": "FILL_PUBLIC_COUNTRY",
        "host": "FILL_PUBLIC_HOST_OR_IP",
        "tcp_ports": [443],
        "notes": "public metadata only; no VPN URI, UUID, private key, token, or subscription link",
    }


def choose_status(candidate_score: dict[str, Any]) -> str:
    status = str(candidate_score.get("status") or "missing")
    summary = candidate_score.get("summary") or {}
    viable_count = int(summary.get("viable_count") or 0)
    candidate_count = int(summary.get("candidate_count") or 0)
    if status == "candidate_file_error":
        return "candidate_file_needs_secret_cleanup"
    if viable_count > 0:
        return "candidate_metadata_ready"
    if candidate_count > 0:
        return "candidate_metadata_needs_fix"
    return "awaiting_public_candidate_metadata"


def build_payload(
    *,
    candidate_file: Path,
    candidate_score: dict[str, Any],
    requirements: dict[str, Any],
) -> dict[str, Any]:
    score_summary = candidate_score.get("summary") or {}
    requirements_summary = requirements.get("summary") or {}
    status = choose_status(candidate_score)
    safe = (
        candidate_score.get("nl_mutation_allowed") is False
        and candidate_score.get("spb_fallback_allowed") is False
        and candidate_score.get("automatic_failover_allowed") is False
        and requirements.get("nl_mutation_allowed") is False
        and requirements.get("spb_fallback_allowed") is False
        and requirements.get("automatic_failover_allowed") is False
    )
    if not safe:
        status = "unsafe_flags"

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_candidate_intake.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "candidate_file": str(candidate_file),
            "candidate_score_status": candidate_score.get("status", "missing"),
            "candidate_count": score_summary.get("candidate_count", 0),
            "viable_count": score_summary.get("viable_count", 0),
            "top_candidate_label": score_summary.get("top_candidate_label", "none"),
            "requirements_status": requirements.get("status", "missing"),
            "missing_requirements": requirements_summary.get("missing_items") or [],
            "allowed_field_count": len(ALLOWED_FIELDS),
            "forbidden_material_count": len(FORBIDDEN_MATERIAL),
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "allowed_fields": ALLOWED_FIELDS,
        "forbidden_material": FORBIDDEN_MATERIAL,
        "candidate_template": candidate_template(),
        "safe_local_steps": [
            f"Edit {candidate_file} locally with public metadata only.",
            "Run the candidate scorer before generating any probe config.",
            "Generate a probe config only after candidate_score_status=candidate_pool_ready.",
            "Keep profile secrets outside repo and outside reports.",
        ],
        "validation_commands": [
            (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py "
                f"--candidates {candidate_file}"
            ),
            (
                "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py "
                "--snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T011622Z"
            ),
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Candidate Intake",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"candidate_file={summary.get('candidate_file')}",
        f"candidate_score_status={summary.get('candidate_score_status')}",
        f"candidate_count={summary.get('candidate_count')}",
        f"viable_count={summary.get('viable_count')}",
        f"top_candidate_label={summary.get('top_candidate_label')}",
        f"requirements_status={summary.get('requirements_status')}",
        f"missing_requirements={','.join(summary.get('missing_requirements') or []) or 'none'}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Allowed Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in payload["allowed_fields"])
    lines.extend(["", "## Forbidden Material", ""])
    lines.extend(f"- {value}" for value in payload["forbidden_material"])
    lines.extend(["", "## Candidate Template", "", "```json"])
    lines.append(json.dumps(payload["candidate_template"], indent=2, ensure_ascii=False))
    lines.extend(["```", "", "## Safe Local Steps", ""])
    lines.extend(f"- {value}" for value in payload["safe_local_steps"])
    lines.extend(["", "## Validation Commands", "", "```bash"])
    lines.extend(payload["validation_commands"])
    lines.extend(["```", ""])
    lines.append("No NL or SPB writes were performed by this candidate intake report.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit candidate intake checklist")
    parser.add_argument("--candidate-file", default=str(DEFAULT_CANDIDATE_FILE))
    parser.add_argument("--candidate-score", default=str(DEFAULT_CANDIDATE_SCORE))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(
        candidate_file=Path(args.candidate_file),
        candidate_score=read_json(Path(args.candidate_score)),
        requirements=read_json(Path(args.requirements)),
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
