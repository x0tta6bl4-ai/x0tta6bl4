"""Live-rollout image digest and provenance gate.

The gate inspects retained rollout/image-provenance artifacts and keeps the
production objective blocked until all runtime images are digest-pinned and
per-image provenance is retained. It does not contact registries or mutate
deployment manifests.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_RAW_IMAGE_DIGESTS = ".tmp/live-rollout-raw-evidence/image-digests.json"
DEFAULT_PROVENANCE_GATE = ".tmp/validation-shards/deploy-image-provenance-gate-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/live-rollout-image-digest-provenance-gate-2026-05-20.md"
DEFAULT_EXPECTED_OPERATOR_EVIDENCE = ".tmp/production-raw-evidence-operator-bundle/live-rollout/image-digests.json"

DIGEST_REF = re.compile(r"^[^\s@:]+(?:/[^\s@:]+)*@sha256:[a-f0-9]{64}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _is_digest_pinned(image: Any) -> bool:
    return isinstance(image, str) and bool(DIGEST_REF.match(image))


def _entrypoint_exists(root: Path, entrypoint: str) -> bool:
    path = Path(entrypoint)
    if path.is_absolute():
        return path.exists()
    return (root / path).exists()


def _operator_next_actions(raw_display: str, provenance_display: str) -> List[Dict[str, Any]]:
    rollout_command = (
        "python3 -m src.integration.rollout_provenance --root . "
        f"--raw-image-digests {raw_display} "
        f"--provenance-gate {provenance_display} --require-ready"
    )
    return [
        {
            "id": "render_template_pack",
            "status": "OPERATOR_INPUT_REQUIRED",
            "command": "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force",
            "materializes_evidence": False,
            "mutates_files": True,
            "contacts_registry": False,
            "contacts_cluster": False,
        },
        {
            "id": "return_digest_pinned_evidence",
            "status": "OPERATOR_INPUT_REQUIRED",
            "required_path": DEFAULT_EXPECTED_OPERATOR_EVIDENCE,
            "reason": (
                "operator must replace tag-based runtime refs with digest-pinned refs and retain "
                "per-image cosign/SLSA provenance artifacts"
            ),
            "materializes_evidence": True,
            "contacts_registry": False,
            "contacts_cluster": False,
        },
        {
            "id": "verify_live_rollout_evidence_gate",
            "status": "AFTER_OPERATOR_EVIDENCE",
            "command": "python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready",
            "materializes_evidence": False,
            "contacts_registry": False,
            "contacts_cluster": False,
        },
        {
            "id": "rerun_rollout_provenance",
            "status": "AFTER_OPERATOR_EVIDENCE",
            "command": rollout_command,
            "materializes_evidence": False,
            "contacts_registry": False,
            "contacts_cluster": False,
        },
        {
            "id": "rerun_current_evidence_rollup",
            "status": "AFTER_ROLLOUT_READY",
            "command": "python3 -m src.integration.current_evidence_rollup --root . --require-complete",
            "materializes_evidence": False,
            "contacts_registry": False,
            "contacts_cluster": False,
        },
    ]


def _operator_command_checks(root: Path, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected_by_action = {
        "render_template_pack": "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py",
        "verify_live_rollout_evidence_gate": "scripts/ops/verify_live_rollout_evidence_gate.py",
        "rerun_rollout_provenance": "src/integration/rollout_provenance.py",
        "rerun_current_evidence_rollup": "src/integration/current_evidence_rollup.py",
    }
    checks: List[Dict[str, Any]] = []
    for action in actions:
        action_id = str(action.get("id", ""))
        command = str(action.get("command", "") or "")
        expected = expected_by_action.get(action_id)
        if not command or not expected:
            continue
        exists = _entrypoint_exists(root, expected)
        checks.append(
            {
                "action_id": action_id,
                "command": command,
                "expected_entrypoint": expected,
                "entrypoint_exists": exists,
                "shell_redirection_placeholder": "",
                "shell_redirection_placeholder_detected": False,
                "status": "READY" if exists else "MISSING_ENTRYPOINT",
            }
        )
    return checks


@dataclass
class RolloutImageDigestGate:
    raw_path: Path
    provenance_path: Path
    raw_display_path: str = DEFAULT_RAW_IMAGE_DIGESTS
    provenance_display_path: str = DEFAULT_PROVENANCE_GATE
    root: Path = field(default_factory=lambda: Path.cwd())
    raw: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        raw_path: Path,
        provenance_path: Path,
        raw_display_path: str = DEFAULT_RAW_IMAGE_DIGESTS,
        provenance_display_path: str = DEFAULT_PROVENANCE_GATE,
        root: Optional[Path] = None,
    ) -> "RolloutImageDigestGate":
        raw = _read_json(raw_path)
        provenance = _read_json(provenance_path)
        return cls(raw_path, provenance_path, raw_display_path, provenance_display_path, root or Path.cwd(), raw, provenance)

    def runtime_images(self) -> List[str]:
        if not self.raw:
            return []
        images = self.raw.get("runtime_images", [])
        return [image for image in images if isinstance(image, str)]

    def digest_pinned_images(self) -> List[str]:
        return [image for image in self.runtime_images() if _is_digest_pinned(image)]

    def tag_based_images(self) -> List[str]:
        return [image for image in self.runtime_images() if not _is_digest_pinned(image)]

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.raw is None:
            errors.append("raw image-digests evidence is missing or unreadable")
        if self.provenance is None:
            errors.append("deploy-image provenance gate report is missing or unreadable")
        if errors:
            self.errors = errors
            return errors

        raw_status = self.raw.get("status") or self.raw.get("evidence_status")
        if raw_status != "VERIFIED HERE":
            errors.append("raw image-digests evidence must have VERIFIED HERE status")

        images = self.runtime_images()
        if not images:
            errors.append("runtime_images must contain at least one runtime image")
        unpinned = self.tag_based_images()
        if unpinned:
            errors.append(f"runtime_images must be digest-pinned: {unpinned}")

        if self.raw.get("all_deploy_refs_digest_pinned") is not True:
            errors.append("all_deploy_refs_digest_pinned must be true")
        if self.raw.get("runtime_image_provenance_ready") is not True:
            errors.append("runtime_image_provenance_ready must be true")

        summary = self.provenance.get("summary", {})
        deploy_total = summary.get("deploy_images_total", 0)
        deploy_pinned = summary.get("deploy_images_digest_pinned", 0)
        if not deploy_total:
            errors.append("provenance deploy_images_total must be greater than zero")
        if deploy_total and deploy_pinned != deploy_total:
            errors.append("provenance deploy_images_digest_pinned must equal deploy_images_total")
        if summary.get("all_deploy_images_have_verified_provenance") is not True:
            errors.append("all deploy images must have verified provenance")
        if summary.get("runtime_image_provenance_artifacts_retained_here") is not True:
            errors.append("runtime image provenance artifacts must be retained here")
        if summary.get("runtime_image_digest_pinning_ready") is not True:
            errors.append("runtime image digest pinning guard must be ready")

        self.errors = errors
        return errors

    def report(self) -> Dict[str, Any]:
        errors = self.validate()
        images = self.runtime_images()
        pinned = self.digest_pinned_images()
        provenance_summary = (self.provenance or {}).get("summary", {})
        ready = not errors
        actions = [] if ready else _operator_next_actions(self.raw_display_path, self.provenance_display_path)
        command_checks = _operator_command_checks(self.root, actions)
        missing_entrypoints = sum(1 for item in command_checks if item.get("entrypoint_exists") is not True)
        commands = [str(item.get("command")) for item in actions if item.get("command")]

        return {
            "schema_version": "x0tta6bl4-live-rollout-image-digests-closure-attempt-v2",
            "generated_at": utc_now(),
            "status": "VERIFIED HERE",
            "ok": True,
            "claim_boundary": (
                "Read-only closure attempt. It inspects retained local artifacts and refuses to "
                "upgrade image-digests production readiness without digest-pinned deploy refs and "
                "retained per-image provenance."
            ),
            "decision": "READY_TO_CLOSE" if ready else "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
            "operator_handoff_decision": (
                "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
                if ready
                else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
            ),
            "ready_for_completion_rerun": ready,
            "goal_can_be_marked_complete": False,
            "source_artifacts": [
                self.raw_display_path,
                self.provenance_display_path,
            ],
            "blocking_preflight_errors": errors,
            "missing_inputs": [] if ready else [
                {
                    "id": "live_rollout_image_digest_provenance",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "paths": [
                        DEFAULT_EXPECTED_OPERATOR_EVIDENCE,
                        self.raw_display_path,
                        self.provenance_display_path,
                    ],
                    "commands": commands,
                    "reason": (
                        "runtime/deploy image references must be digest-pinned and backed by "
                        "retained per-image cosign/SLSA provenance artifacts"
                    ),
                }
            ],
            "operator_next_actions": actions,
            "operator_command_checks": command_checks,
            "summary": {
                "can_close_image_digests_blocker": ready,
                "collector_image_digest_preflight_errors": len(errors),
                "missing_inputs_total": 0 if ready else 1,
                "operator_actions_total": len(actions),
                "operator_commands_total": len(command_checks),
                "operator_command_entrypoints_missing": missing_entrypoints,
                "operator_command_surface_ready": missing_entrypoints == 0,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
                "provenance_deploy_images_digest_pinned": provenance_summary.get("deploy_images_digest_pinned", 0),
                "provenance_deploy_images_total": provenance_summary.get("deploy_images_total", 0),
                "raw_all_deploy_refs_digest_pinned": (self.raw or {}).get("all_deploy_refs_digest_pinned", False),
                "raw_deploy_images_digest_pinned": len(pinned),
                "raw_deploy_images_total": len(images),
                "raw_runtime_image_provenance_ready": (self.raw or {}).get("runtime_image_provenance_ready", False),
                "runtime_image_digest_pinning_ready": provenance_summary.get("runtime_image_digest_pinning_ready", False),
                "runtime_image_provenance_artifacts_retained_here": provenance_summary.get(
                    "runtime_image_provenance_artifacts_retained_here", False
                ),
            },
            "required_next_evidence": [] if ready else [
                "digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image",
                "retained per-image cosign/SLSA provenance artifacts for current deployed image digests",
                "rerun rollout provenance gate after replacing tag-based runtime image refs",
            ],
            "not_verified_yet": [] if ready else [
                "all deploy refs digest-pinned",
                "runtime image provenance artifacts retained for current deployed digests",
                "live-rollout collector preflight has no image-digests errors",
            ],
        }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Live Rollout Image Digest Provenance Gate",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Decision: `{report.get('decision', '')}`",
        f"Operator handoff: `{report.get('operator_handoff_decision', '')}`",
        f"Ready for completion rerun: `{report.get('ready_for_completion_rerun')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Summary",
        "",
        f"- can close image digests blocker: `{summary.get('can_close_image_digests_blocker')}`",
        f"- raw deploy images digest pinned: `{summary.get('raw_deploy_images_digest_pinned')}/{summary.get('raw_deploy_images_total')}`",
        f"- provenance deploy images digest pinned: `{summary.get('provenance_deploy_images_digest_pinned')}/{summary.get('provenance_deploy_images_total')}`",
        f"- runtime image provenance retained here: `{summary.get('runtime_image_provenance_artifacts_retained_here')}`",
        f"- operator actions: `{summary.get('operator_actions_total')}`",
        f"- operator command entrypoints missing: `{summary.get('operator_command_entrypoints_missing')}`",
        f"- operator command surface ready: `{summary.get('operator_command_surface_ready')}`",
        "",
        "## Missing Inputs",
        "",
    ]
    missing = report.get("missing_inputs", [])
    if isinstance(missing, list) and missing:
        for item in missing:
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('id')}`: `{item.get('status')}` - {item.get('reason', '')}")
            for command in item.get("commands", []):
                if isinstance(command, str):
                    lines.append(f"  - command: `{command}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Operator Command Checks", ""])
    checks = report.get("operator_command_checks", [])
    if isinstance(checks, list) and checks:
        for item in checks:
            if isinstance(item, dict):
                lines.append(
                    f"- `{item.get('action_id')}`: `{item.get('status')}`, entrypoint exists: `{item.get('entrypoint_exists')}`"
                )
    else:
        lines.append("- none")
    lines.extend(["", "## Required Next Evidence", ""])
    required = report.get("required_next_evidence", [])
    if isinstance(required, list) and required:
        lines.extend(f"- {item}" for item in required)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate rollout image digest/provenance evidence")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--raw-image-digests", default=DEFAULT_RAW_IMAGE_DIGESTS)
    parser.add_argument("--provenance-gate", default=DEFAULT_PROVENANCE_GATE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless rollout image evidence is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    raw_input = Path(args.raw_image_digests)
    provenance_input = Path(args.provenance_gate)
    raw_path = raw_input if raw_input.is_absolute() else root / raw_input
    provenance_path = provenance_input if provenance_input.is_absolute() else root / provenance_input

    gate = RolloutImageDigestGate.load(
        raw_path,
        provenance_path,
        str(raw_input),
        str(provenance_input),
        root=root,
    )
    report = gate.report()
    write_json(root / args.output_json, report)
    if args.write_md:
        md_path = root / args.output_md
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["summary"]["can_close_image_digests_blocker"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
