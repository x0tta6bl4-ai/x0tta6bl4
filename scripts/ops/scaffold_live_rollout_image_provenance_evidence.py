#!/usr/bin/env python3
"""Render a template-only live-rollout image provenance intake pack.

This script is intentionally not a collector. It never contacts registries,
clusters, cosign/Rekor services, or writes production evidence. The optional
file writes are limited to operator templates under the configured template
directory.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.rollout_provenance import RolloutImageDigestGate  # noqa: E402


DEFAULT_TEMPLATE_DIR = ".tmp/live-rollout-image-provenance-template-pack"
DEFAULT_EXPECTED_EVIDENCE = ".tmp/production-raw-evidence-operator-bundle/live-rollout/image-digests.json"
DEFAULT_RETAINED_RAW_IMAGE_DIGESTS = ".tmp/live-rollout-raw-evidence/image-digests.json"
DEFAULT_RETAINED_PROVENANCE_GATE = ".tmp/validation-shards/deploy-image-provenance-gate-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/live-rollout-image-provenance-scaffold-current.json"

CURRENT_RUNTIME_IMAGE_REFS = [
    "x0tta6bl4/mesh-node:3.4.0",
    "x0tta6bl4/mesh-operator:3.4.0",
    "x0tta6bl4/proxy-orchestrator:v1.0.0",
    "x0tta6bl4/x0tta6bl4:latest",
    "x0tta6bl4/x0tta6bl4:latest",
    "x0tta6bl4:3.4.0",
    "x0tta6bl4:latest",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _digest_placeholder(image: str, index: int) -> str:
    repo = image.split(":", 1)[0]
    return f"{repo}@sha256:REPLACE_WITH_64_HEX_DIGEST_{index:02d}"


def _image_digest_template_payload(expected_evidence: str) -> Dict[str, Any]:
    replacements = [
        {
            "current_tag_ref": image,
            "digest_ref": _digest_placeholder(image, index),
            "source_manifest_path": "REPLACE_WITH_HELM_ARGOCD_OR_KUSTOMIZE_PATH",
            "digest_resolution_command": f"crane digest {image}",
            "provenance_artifacts": [
                {
                    "kind": "cosign_verify_json",
                    "path": f"REPLACE_WITH_RETAINED_ARTIFACT_PATH/cosign-verify-{index:02d}.json",
                },
                {
                    "kind": "slsa_provenance_attestation_json",
                    "path": f"REPLACE_WITH_RETAINED_ARTIFACT_PATH/slsa-provenance-{index:02d}.json",
                },
            ],
        }
        for index, image in enumerate(CURRENT_RUNTIME_IMAGE_REFS, start=1)
    ]
    return {
        "_instructions": (
            "Use this as an intake checklist only. Do not copy it to the retained evidence "
            "path until every placeholder has been replaced with production cluster, digest, "
            "and provenance data."
        ),
        "_not_evidence": True,
        "_template_only": True,
        "schema_version": "x0tta6bl4-live-rollout-image-digests-operator-evidence-v1",
        "status": "TEMPLATE_ONLY",
        "evidence_status": "TEMPLATE_ONLY",
        "collector_id": "live-rollout",
        "raw_id": "live-rollout/image-digests.json",
        "file_name": "image-digests.json",
        "collected_at": "REPLACE_WITH_PRODUCTION_CAPTURE_TIMESTAMP",
        "collected_by": "REPLACE_WITH_OPERATOR_OR_AUTOMATION_ID",
        "source_commands": [
            "kubectl --context REPLACE_WITH_PROD_CONTEXT -n REPLACE_WITH_NAMESPACE get deploy,sts,ds -o json",
            "argocd app get REPLACE_WITH_APP --output json",
            "crane digest REPLACE_WITH_EACH_RUNTIME_IMAGE_TAG",
            "cosign verify REPLACE_WITH_EACH_DIGEST_PINNED_IMAGE --output json",
            "cosign verify-attestation --type slsaprovenance REPLACE_WITH_EACH_DIGEST_PINNED_IMAGE --output json",
        ],
        "operator_return_path": expected_evidence,
        "production_ready": False,
        "production_promotion_blockers": [
            "template only; replace every image tag with a digest-pinned ref",
            "template only; retain cosign/SLSA provenance artifacts for every deployed digest",
        ],
        "all_deploy_refs_digest_pinned": False,
        "deploy_images_total": len(CURRENT_RUNTIME_IMAGE_REFS),
        "deploy_images_digest_pinned": 0,
        "runtime_image_provenance_ready": False,
        "runtime_image_provenance_artifacts_retained_here": False,
        "runtime_images": [
            _digest_placeholder(image, index)
            for index, image in enumerate(CURRENT_RUNTIME_IMAGE_REFS, start=1)
        ],
        "runtime_image_digest_replacements": replacements,
        "template_only": True,
        "dry_run": False,
        "mock": False,
        "simulated": False,
        "mutates_files": False,
        "mutates_cluster": False,
        "mutates_registry": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
    }


def _provenance_gate_template_payload() -> Dict[str, Any]:
    return {
        "_not_evidence": True,
        "_template_only": True,
        "schema_version": "x0tta6bl4-deploy-image-provenance-gate-template-v1",
        "status": "TEMPLATE_ONLY",
        "ok": False,
        "claim_boundary": "Template-only provenance summary. This is not retained production evidence.",
        "summary": {
            "deploy_images_total": len(CURRENT_RUNTIME_IMAGE_REFS),
            "deploy_images_digest_pinned": 0,
            "all_deploy_images_have_verified_provenance": False,
            "runtime_image_provenance_artifacts_retained_here": False,
            "runtime_image_digest_pinning_ready": False,
        },
        "template_only": True,
    }


def _readme(expected_evidence: str, retained_raw: str, retained_provenance_gate: str) -> str:
    return f"""# Live Rollout Image Digest Provenance Intake Scaffold

This directory is an operator scaffold, not evidence.

Required operator return path:

- `{expected_evidence}`

The current retained rollout blocker is caused by tag-based runtime image refs.
Replace each runtime image with a digest-pinned ref and retain per-image cosign
and SLSA provenance artifacts before setting `production_ready=true`.

Current tag-based refs to replace:

{chr(10).join(f"- `{image}`" for image in CURRENT_RUNTIME_IMAGE_REFS)}

Minimum acceptance:

```bash
python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready
python3 -m src.integration.rollout_provenance --root . \\
  --raw-image-digests {retained_raw} \\
  --provenance-gate {retained_provenance_gate} \\
  --require-ready
```

Do not copy template files into retained evidence paths while `_not_evidence`,
`_template_only`, `template_only`, or `TEMPLATE_ONLY` remain present.
"""


def _verify_script(retained_raw: str, retained_provenance_gate: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../.." && pwd)"
cd "${{ROOT_DIR}}"

python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready
python3 -m src.integration.rollout_provenance --root . \\
  --raw-image-digests {retained_raw} \\
  --provenance-gate {retained_provenance_gate} \\
  --require-ready
"""


def _template_files(
    template_dir: str,
    expected_evidence: str,
    retained_raw: str,
    retained_provenance_gate: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "kind": "json_template",
            "path": f"{template_dir}/image-digests.template.json",
            "mode": "0644",
            "payload": _image_digest_template_payload(expected_evidence),
        },
        {
            "kind": "json_template",
            "path": f"{template_dir}/deploy-image-provenance-gate.template.json",
            "mode": "0644",
            "payload": _provenance_gate_template_payload(),
        },
        {
            "kind": "markdown_instructions",
            "path": f"{template_dir}/README.md",
            "mode": "0644",
            "content": _readme(expected_evidence, retained_raw, retained_provenance_gate),
        },
        {
            "kind": "operator_verify_script",
            "path": f"{template_dir}/verify-filled-evidence.sh",
            "mode": "0755",
            "content": _verify_script(retained_raw, retained_provenance_gate),
        },
    ]


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


def build_report(
    root: Path,
    template_dir: str,
    expected_evidence: str,
    retained_raw: str,
    retained_provenance_gate: str,
    write_template_files: bool,
    force: bool,
) -> Dict[str, Any]:
    template_files = _template_files(template_dir, expected_evidence, retained_raw, retained_provenance_gate)
    written = 0
    if write_template_files:
        for item in template_files:
            if _write_file(_resolve(root, str(item["path"])), item, force):
                written += 1

    image_template = _resolve(root, f"{template_dir}/image-digests.template.json")
    provenance_template = _resolve(root, f"{template_dir}/deploy-image-provenance-gate.template.json")
    template_gate = RolloutImageDigestGate.load(
        image_template,
        provenance_template,
        f"{template_dir}/image-digests.template.json",
        f"{template_dir}/deploy-image-provenance-gate.template.json",
    ).report()
    template_rejected = template_gate["summary"]["can_close_image_digests_blocker"] is False

    return {
        "schema_version": "x0tta6bl4-live-rollout-image-provenance-scaffold-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "scaffold_decision": "TEMPLATE_ONLY_NOT_EVIDENCE",
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Live-rollout image digest/provenance intake scaffold only. It writes optional "
            "operator templates and never contacts registries, clusters, cosign/Rekor services, "
            "writes production evidence, mutates runtime state, or marks the objective complete."
        ),
        "write_template_files_requested": write_template_files,
        "force": force,
        "mutates_files": write_template_files,
        "mutates_files_outside_outputs": False,
        "materializes_evidence": False,
        "updates_deploy_manifests": False,
        "contacts_registry": False,
        "contacts_cluster": False,
        "runs_cosign": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "template_dir": template_dir,
        "expected_evidence_json": expected_evidence,
        "retained_raw_image_digests": retained_raw,
        "retained_provenance_gate": retained_provenance_gate,
        "current_tag_based_runtime_refs": CURRENT_RUNTIME_IMAGE_REFS,
        "template_files": template_files,
        "operator_acceptance_commands": [
            "python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready",
            (
                "python3 -m src.integration.rollout_provenance --root . "
                f"--raw-image-digests {retained_raw} "
                f"--provenance-gate {retained_provenance_gate} --require-ready"
            ),
            "python3 -m src.integration.current_evidence_rollup --root . --require-complete",
        ],
        "summary": {
            "template_files_total": len(template_files),
            "template_files_written": written,
            "templates_marked_not_evidence": True,
            "expected_evidence_file_exists": _resolve(root, expected_evidence).exists(),
            "template_validation_rejects_as_rollout_evidence": template_rejected,
            "current_runtime_tag_refs_total": len(CURRENT_RUNTIME_IMAGE_REFS),
        },
        "template_validation_report": template_gate,
        "not_verified_yet": [
            "operator-returned image-digests.json with production_ready=true",
            "all live rollout runtime image refs digest-pinned",
            "retained per-image cosign/SLSA provenance artifacts for current deployed digests",
            "rollout provenance gate rerun and READY_TO_CLOSE",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render template-only live-rollout image provenance scaffold")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--template-dir", default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--expected-evidence", default=DEFAULT_EXPECTED_EVIDENCE)
    parser.add_argument("--retained-raw-image-digests", default=DEFAULT_RETAINED_RAW_IMAGE_DIGESTS)
    parser.add_argument("--retained-provenance-gate", default=DEFAULT_RETAINED_PROVENANCE_GATE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--write-template-files", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-written", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        template_dir=args.template_dir,
        expected_evidence=args.expected_evidence,
        retained_raw=args.retained_raw_image_digests,
        retained_provenance_gate=args.retained_provenance_gate,
        write_template_files=args.write_template_files,
        force=args.force,
    )
    output_path = _resolve(root, args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "scaffold_decision": report["scaffold_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_written and report["summary"]["template_files_written"] != report["summary"]["template_files_total"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
