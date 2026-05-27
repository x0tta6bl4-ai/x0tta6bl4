#!/usr/bin/env python3
"""Render template-only raw production evidence intake files.

This script is intentionally not a collector and not an importer. It reads the
production evidence replacement passport and writes operator templates under a
separate template directory only when explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_PASSPORT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json"
DEFAULT_TEMPLATE_DIR = ".tmp/production-raw-evidence-template-pack"
DEFAULT_OPERATOR_BUNDLE_ROOT = ".tmp/production-raw-evidence-operator-bundle"
DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-template-pack-current.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, "artifact missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"artifact unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "artifact root must be a JSON object"
    return payload, ""


def _raw_items(passport: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not passport:
        return []
    items = passport.get("required_evidence_files", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("kind") == "raw_evidence"]


def _file_name(item: Dict[str, Any]) -> str:
    raw_id = str(item.get("raw_id", ""))
    value = item.get("file_name")
    if isinstance(value, str) and value:
        return value
    return raw_id.split("/")[-1] if raw_id else "evidence.json"


def _collector_id(item: Dict[str, Any]) -> str:
    raw_id = str(item.get("raw_id", ""))
    return raw_id.split("/", 1)[0] if "/" in raw_id else str(item.get("collector_id") or "unknown")


def _contract_list(item: Dict[str, Any], key: str) -> List[Any]:
    value = item.get(key, [])
    return value if isinstance(value, list) else []


def _template_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_id = str(item.get("raw_id", ""))
    file_name = _file_name(item)
    collector_id = _collector_id(item)
    return {
        "_instructions": (
            "This is an intake template only. Copy it to operator_return_path only after "
            "replacing every placeholder with retained production data captured from the "
            "named production environment."
        ),
        "_not_evidence": True,
        "_template_only": True,
        "schema_version": "x0tta6bl4-production-raw-evidence-template-v1",
        "status": "TEMPLATE_ONLY",
        "evidence_status": "TEMPLATE_ONLY",
        "evidence_key": item.get("evidence_key", ""),
        "collector_id": collector_id,
        "raw_id": raw_id,
        "file_name": file_name,
        "operator_return_path": item.get("operator_return_path", ""),
        "retained_destination_path": item.get("retained_destination_path", ""),
        "collected_at": "REPLACE_WITH_PRODUCTION_CAPTURE_TIMESTAMP",
        "collected_by": "REPLACE_WITH_OPERATOR_OR_CI_IDENTITY",
        "production_environment": "REPLACE_WITH_PRODUCTION_ENVIRONMENT_ID",
        "source_commands": ["REPLACE_WITH_EXACT_PRODUCTION_CAPTURE_COMMAND"],
        "source_artifact_hashes": [
            {
                "path": "REPLACE_WITH_RETAINED_SOURCE_ARTIFACT_PATH",
                "sha256": "REPLACE_WITH_SHA256",
            }
        ],
        "required_statuses": _contract_list(item, "required_statuses"),
        "required_operator_provenance_fields": _contract_list(item, "required_operator_provenance_fields"),
        "required_hash_binding_fields": _contract_list(item, "required_hash_binding_fields"),
        "semantic_json_pointers": _contract_list(item, "semantic_json_pointers"),
        "production_evidence_requirements": _contract_list(item, "production_evidence_requirements"),
        "validation_commands": _contract_list(item, "validation_commands"),
        "production_ready": False,
        "production_promotion_blockers": [
            "template only; replace with retained production evidence",
            "template only; run the domain collector, source-candidate audit, production intake, and completion audit",
        ],
        "template_only": True,
        "dry_run": False,
        "mock": False,
        "simulated": False,
        "mutates_files": False,
        "mutates_cluster": False,
        "mutates_chain": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
    }


def _readme(raw_items: List[Dict[str, Any]], operator_bundle_root: str) -> str:
    rows = "\n".join(
        f"- `{item.get('operator_return_path')}` from template `{item.get('raw_id')}`"
        for item in raw_items
    )
    return f"""# Production Raw Evidence Template Pack

This directory is an operator scaffold, not evidence.

Expected operator bundle root:

- `{operator_bundle_root}`

Template files:

{rows}

Minimum acceptance after replacing templates with real production JSON:

```bash
python3 scripts/ops/import_production_raw_evidence_bundle.py \\
  --bundle-root {operator_bundle_root} \\
  --require-ready

python3 -m src.integration.operator_bundle_identity --root . \\
  --operator-bundle-root {operator_bundle_root} \\
  --require-clean

python3 -m src.integration.evidence_source_candidates --root . --require-ready
python3 -m src.integration.production_evidence_intake --root . --require-ready
python3 -m src.integration.completion_audit --root . --require-complete
```

Do not copy template files into retained evidence paths while `_not_evidence`,
`_template_only`, `template_only`, or `TEMPLATE_ONLY` remain present.
"""


def _verify_script(operator_bundle_root: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../.." && pwd)"
cd "${{ROOT_DIR}}"

python3 scripts/ops/import_production_raw_evidence_bundle.py \\
  --bundle-root {operator_bundle_root} \\
  --require-ready

python3 -m src.integration.operator_bundle_identity --root . \\
  --operator-bundle-root {operator_bundle_root} \\
  --require-clean

python3 -m src.integration.evidence_source_candidates --root . --require-ready
python3 -m src.integration.production_evidence_intake --root . --require-ready
python3 -m src.integration.completion_audit --root . --require-complete
"""


def _template_files(
    template_dir: str,
    raw_items: List[Dict[str, Any]],
    operator_bundle_root: str,
) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for item in raw_items:
        raw_id = str(item.get("raw_id", ""))
        if not raw_id:
            continue
        files.append(
            {
                "kind": "json_template",
                "raw_id": raw_id,
                "operator_return_path": item.get("operator_return_path", ""),
                "path": f"{template_dir}/{raw_id}",
                "mode": "0644",
                "payload": _template_payload(item),
            }
        )
    files.extend(
        [
            {
                "kind": "markdown_instructions",
                "path": f"{template_dir}/README.md",
                "mode": "0644",
                "content": _readme(raw_items, operator_bundle_root),
            },
            {
                "kind": "operator_verify_script",
                "path": f"{template_dir}/verify-filled-bundle.sh",
                "mode": "0755",
                "content": _verify_script(operator_bundle_root),
            },
        ]
    )
    return files


def _write_file(path: Path, item: Dict[str, Any], force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if "payload" in item:
        path.write_text(
            json.dumps(item["payload"], ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(str(item.get("content", "")), encoding="utf-8")
    if item.get("mode") == "0755":
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def _template_markers_clean(files: List[Dict[str, Any]]) -> bool:
    payloads = [item.get("payload", {}) for item in files if item.get("kind") == "json_template"]
    return bool(payloads) and all(
        isinstance(payload, dict)
        and payload.get("_not_evidence") is True
        and payload.get("_template_only") is True
        and payload.get("template_only") is True
        and payload.get("status") == "TEMPLATE_ONLY"
        and payload.get("evidence_status") == "TEMPLATE_ONLY"
        and payload.get("production_ready") is False
        for payload in payloads
    )


def build_report(
    *,
    root: Path,
    passport_path: str,
    template_dir: str,
    operator_bundle_root: str,
    write_template_files: bool,
    force: bool,
) -> Dict[str, Any]:
    passport, passport_error = _read_json(_resolve(root, passport_path))
    raw_items = _raw_items(passport)
    template_files = _template_files(template_dir, raw_items, operator_bundle_root)
    written = 0
    if write_template_files:
        for item in template_files:
            if _write_file(_resolve(root, str(item["path"])), item, force):
                written += 1

    expected_operator_paths = [
        str(item.get("operator_return_path", ""))
        for item in raw_items
        if isinstance(item.get("operator_return_path"), str) and item.get("operator_return_path")
    ]
    existing_operator_paths = [
        path for path in expected_operator_paths if _resolve(root, path).exists()
    ]

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-template-pack-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": passport_error == "",
        "scaffold_decision": "TEMPLATE_ONLY_NOT_EVIDENCE",
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Template-only raw production evidence intake pack. It reads the replacement passport "
            "and optionally writes scaffold files under the template directory, but never runs "
            "collectors, installs raw evidence, writes operator bundle evidence, contacts live "
            "systems, mutates VPN/runtime state, or marks the objective complete."
        ),
        "source_passport": passport_path,
        "passport_error": passport_error,
        "write_template_files_requested": write_template_files,
        "force": force,
        "mutates_files": write_template_files,
        "mutates_files_outside_outputs": False,
        "materializes_evidence": False,
        "installs_raw_evidence": False,
        "runs_collectors": False,
        "runs_live_cluster": False,
        "runs_live_chain": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "runs_live_rpc": False,
        "mutates_chain": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "template_dir": template_dir,
        "operator_bundle_root": operator_bundle_root,
        "expected_operator_bundle_paths": expected_operator_paths,
        "template_files": template_files,
        "operator_acceptance_commands": [
            f"python3 scripts/ops/import_production_raw_evidence_bundle.py --bundle-root {operator_bundle_root} --require-ready",
            f"python3 -m src.integration.operator_bundle_identity --root . --operator-bundle-root {operator_bundle_root} --require-clean",
            "python3 -m src.integration.evidence_source_candidates --root . --require-ready",
            "python3 -m src.integration.production_evidence_intake --root . --require-ready",
            "python3 -m src.integration.completion_audit --root . --require-complete",
        ],
        "summary": {
            "raw_template_files_total": len(raw_items),
            "template_files_total": len(template_files),
            "template_files_written": written,
            "templates_marked_not_evidence": _template_markers_clean(template_files),
            "expected_operator_bundle_files_total": len(expected_operator_paths),
            "expected_operator_bundle_files_existing": len(existing_operator_paths),
            "source_errors_total": 1 if passport_error else 0,
        },
        "not_verified_yet": [
            "operator-filled raw production evidence bundle",
            "operator bundle identity report with OPERATOR_BUNDLE_IDENTITY_CLEAN",
            "source-candidate audit READY_TO_INSTALL for every raw evidence key",
            "production evidence intake ready",
            "completion audit complete",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render template-only production raw evidence scaffold")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--passport", default=DEFAULT_PASSPORT)
    parser.add_argument("--template-dir", default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--write-template-files", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-written", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        passport_path=args.passport,
        template_dir=args.template_dir,
        operator_bundle_root=args.operator_bundle_root,
        write_template_files=args.write_template_files,
        force=args.force,
    )
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "scaffold_decision": report["scaffold_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if not report["ok"]:
        return 2
    if args.require_written and report["summary"]["template_files_written"] != report["summary"]["template_files_total"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
