"""Guard current integration-spine shards against stale restored evidence.

The verifier already exercises the current artifacts, but this guard catches a
different failure mode: a generated shard being overwritten by an old
``source-restored`` artifact, by contradictory legacy count fields, by
generic ``status=BLOCKING`` rows, or by status maps that still preserve
legacy operator-required labels instead of precise operator-input labels. It
also inventories legacy/generic status labels that are still present in old
local shards without making them release-blocking by itself.
It is read-only and only scans local JSON under
``.tmp/validation-shards``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_SHARD_GLOB = ".tmp/validation-shards/*current*.json"
OBSERVED_STATUS_KINDS = {
    "OPERATOR_REQUIRED": "generic_status_operator_required",
    "OPERATOR_INPUTS_REQUIRED": "legacy_status_operator_inputs_required",
    "BLOCKED": "legacy_status_blocked",
    "CONFIG_REQUIRED": "config_required_status",
}
LEGACY_STATUS_MAP_KEYS = {
    "OPERATOR_REQUIRED": "legacy_status_map_operator_required",
    "OPERATOR_INPUTS_REQUIRED": "legacy_status_map_operator_inputs_required",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iter_values(value: Any, prefix: str = "$") -> Iterable[Tuple[str, Any]]:
    yield prefix, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_values(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_values(child, f"{prefix}[{index}]")


def _int_value(mapping: Dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _count_contradictions(mapping: Dict[str, Any], prefix: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    current_raw = _int_value(mapping, "current_raw_files_installed")
    staged_raw = _int_value(mapping, "return_acceptance_raw_files_staged")
    for key in ("coverage_raw_files_reported_installed", "pipeline_raw_files_reported_installed"):
        reported = _int_value(mapping, key)
        if reported is None or reported == 0:
            continue
        if current_raw is not None and current_raw < reported:
            findings.append(
                {
                    "kind": "raw_install_count_contradiction",
                    "path": f"{prefix}.{key}",
                    "message": f"{key}={reported} exceeds current_raw_files_installed={current_raw}",
                }
            )
        if staged_raw is not None and staged_raw < reported:
            findings.append(
                {
                    "kind": "raw_install_count_contradiction",
                    "path": f"{prefix}.{key}",
                    "message": f"{key}={reported} exceeds return_acceptance_raw_files_staged={staged_raw}",
                }
            )
    return findings


def _artifact_findings(path: Path, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for value_path, value in _iter_values(data):
        if isinstance(value, str) and "source-restored" in value:
            findings.append(
                {
                    "kind": "source_restored_marker",
                    "path": value_path,
                    "message": "current shard still contains source-restored marker",
                }
            )
        if value_path.endswith(".status") and value == "BLOCKING":
            findings.append(
                {
                    "kind": "generic_status_blocking",
                    "path": value_path,
                    "message": "current shard uses generic status=BLOCKING instead of a precise status",
                }
            )
        if isinstance(value, dict):
            if value_path.endswith(".statuses"):
                for status in LEGACY_STATUS_MAP_KEYS:
                    if status in value:
                        findings.append(
                            {
                                "kind": LEGACY_STATUS_MAP_KEYS[status],
                                "path": f"{value_path}.{status}",
                                "message": (
                                    f"current shard uses legacy statuses map key {status}; "
                                    "use OPERATOR_INPUT_REQUIRED for operator-supplied inputs"
                                ),
                            }
                        )
            if value.get("checklist_total") == 47 and value.get("checklist_passed") == 39:
                findings.append(
                    {
                        "kind": "stale_completion_audit_counts",
                        "path": value_path,
                        "message": "current shard contains legacy completion audit counts 47/39",
                    }
                )
            findings.extend(_count_contradictions(value, value_path))
    for finding in findings:
        finding["artifact"] = str(path)
    return findings


def _artifact_status_observations(path: Path, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    for value_path, value in _iter_values(data):
        if value_path.startswith("$.status_observations["):
            continue
        if not value_path.endswith(".status") or not isinstance(value, str):
            continue
        kind = OBSERVED_STATUS_KINDS.get(value)
        if kind is None:
            continue
        observations.append(
            {
                "kind": kind,
                "artifact": str(path),
                "path": value_path,
                "status": value,
                "message": f"current shard still carries status={value}",
            }
        )
    return observations


def _count_kind(items: List[Dict[str, Any]], kind: str) -> int:
    return sum(1 for item in items if item["kind"] == kind)


def build_report(root: Path, shard_glob: str = DEFAULT_SHARD_GLOB) -> Dict[str, Any]:
    shard_paths = sorted(root.glob(shard_glob))
    load_errors: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    status_observations: List[Dict[str, Any]] = []
    scanned = 0
    for path in shard_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            load_errors.append(
                {
                    "artifact": str(path.relative_to(root)),
                    "message": f"unreadable JSON: {exc.__class__.__name__}: {exc}",
                }
            )
            continue
        if not isinstance(data, dict):
            load_errors.append({"artifact": str(path.relative_to(root)), "message": "top-level JSON value is not an object"})
            continue
        scanned += 1
        relative_path = path.relative_to(root)
        findings.extend(_artifact_findings(relative_path, data))
        status_observations.extend(_artifact_status_observations(relative_path, data))

    ready = not load_errors and not findings
    return {
        "schema_version": "x0tta6bl4-integration-spine-current-shard-stale-guard-v1-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "CURRENT_SHARDS_CLEAR" if ready else "CURRENT_SHARDS_BLOCKED_ON_STALE_MARKERS",
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only guard for local current-shard regressions. It scans JSON "
            "artifacts for stale restored markers, generic status=BLOCKING rows, legacy operator "
            "status-map keys, and contradictory legacy count fields. It also inventories "
            "legacy/generic operator/config status labels without treating those observations as "
            "production readiness evidence. It does not validate production readiness, contact live "
            "systems, mutate artifacts, or close /goal."
        ),
        "mutates_files": False,
        "contacts_live_systems": False,
        "source_artifacts": [str(path.relative_to(root)) for path in shard_paths],
        "load_errors": load_errors,
        "findings": findings,
        "status_observations": status_observations,
        "summary": {
            "current_shards_seen": len(shard_paths),
            "current_shards_scanned": scanned,
            "load_errors_total": len(load_errors),
            "findings_total": len(findings),
            "status_observations_total": len(status_observations),
            "generic_status_operator_required": _count_kind(
                status_observations, "generic_status_operator_required"
            ),
            "legacy_status_operator_inputs_required": _count_kind(
                status_observations, "legacy_status_operator_inputs_required"
            ),
            "legacy_status_blocked": _count_kind(status_observations, "legacy_status_blocked"),
            "config_required_status": _count_kind(status_observations, "config_required_status"),
            "source_restored_markers": sum(1 for finding in findings if finding["kind"] == "source_restored_marker"),
            "generic_status_blocking": sum(
                1 for finding in findings if finding["kind"] == "generic_status_blocking"
            ),
            "legacy_status_map_operator_required": sum(
                1 for finding in findings if finding["kind"] == "legacy_status_map_operator_required"
            ),
            "legacy_status_map_operator_inputs_required": sum(
                1 for finding in findings if finding["kind"] == "legacy_status_map_operator_inputs_required"
            ),
            "stale_completion_audit_count_markers": sum(
                1 for finding in findings if finding["kind"] == "stale_completion_audit_counts"
            ),
            "raw_install_count_contradictions": sum(
                1 for finding in findings if finding["kind"] == "raw_install_count_contradiction"
            ),
            "ready": ready,
            "goal_can_be_marked_complete": False,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan current integration-spine shards for stale restored markers")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--shard-glob", default=DEFAULT_SHARD_GLOB)
    parser.add_argument("--output-json")
    parser.add_argument("--require-clear", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root, args.shard_glob)
    if args.output_json:
        output = Path(args.output_json)
        write_json(output if output.is_absolute() else root / output, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_clear and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
