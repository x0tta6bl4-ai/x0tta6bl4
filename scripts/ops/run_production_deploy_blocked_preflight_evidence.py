#!/usr/bin/env python3
"""Retain local evidence that production_deploy.py blocks before live deploy.

This runner is safe to execute locally. It forces ``allow_live_deploy=False``,
patches subprocess execution to fail if reached, and verifies that
``DeploymentOrchestrator.execute_deployment`` records redacted SafeActuator
metadata while refusing to run kubectl or any other live deployment command.
It does not prove live deployment, traffic shifting, customer traffic,
production SLOs, or production readiness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.deploy import production_deploy


SCHEMA = "x0tta6bl4.production_deploy.blocked_preflight_evidence.v1"
DECISION_RETAINED = "PRODUCTION_DEPLOY_BLOCKED_PREFLIGHT_EVIDENCE_RETAINED"
DECISION_FAILED = "PRODUCTION_DEPLOY_BLOCKED_PREFLIGHT_EVIDENCE_FAILED"
DEFAULT_OUTPUT_JSON = Path(
    ".tmp/validation-shards/production-deploy-blocked-preflight-evidence-current.json"
)
SAFE_ACTUATOR_METADATA_SCHEMA = "x0tta6bl4.safe_actuator.evidence_metadata.v1"
CLAIM_BOUNDARY = (
    "Local blocked-preflight evidence for scripts/deploy/production_deploy.py. "
    "It proves only that the deploy command refuses to run live subprocesses "
    "without explicit local authorization and retains redacted SafeActuator "
    "metadata; it does not prove live deployment, traffic shifting, customer "
    "traffic, production SLOs, or production readiness."
)
STRONG_FALSE_CLAIMS = (
    "traffic_shift_claim_allowed",
    "live_customer_traffic_claim_allowed",
    "production_readiness_claim_allowed",
    "production_slo_claim_allowed",
    "external_dpi_bypass_confirmed",
    "external_settlement_finality_claim_allowed",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_claim_state(
    *,
    deploy_result: bool,
    claim_state: Mapping[str, Any],
    subprocess_attempted: bool,
    prerequisites_attempted: bool,
) -> list[str]:
    failures: list[str] = []
    metadata = _mapping(claim_state.get("safe_actuator_evidence_metadata"))
    claim_gate = _mapping(metadata.get("claim_gate"))
    cross_plane = _mapping(metadata.get("cross_plane_claim_gate"))
    evidence = _mapping(metadata.get("evidence"))

    if deploy_result is not False:
        failures.append("deploy_result_not_blocked")
    if subprocess_attempted:
        failures.append("live_subprocess_attempted")
    if prerequisites_attempted:
        failures.append("kubectl_prerequisites_attempted")
    if metadata.get("schema") != SAFE_ACTUATOR_METADATA_SCHEMA:
        failures.append("metadata_schema_invalid")
    if metadata.get("redacted") is not True:
        failures.append("metadata_not_redacted")
    if not metadata.get("claim_boundary"):
        failures.append("metadata_claim_boundary_missing")
    if claim_gate.get("schema") != (
        "x0tta6bl4.ops.production_deploy.safe_actuator_claim_gate.v1"
    ):
        failures.append("claim_gate_schema_invalid")
    if claim_gate.get("redacted") is not True:
        failures.append("claim_gate_not_redacted")
    if cross_plane.get("allowed") is not False:
        failures.append("cross_plane_gate_not_fail_closed")
    if evidence.get("component") != "scripts.deploy.production_deploy":
        failures.append(f"evidence_component_mismatch:{evidence.get('component')}")
    if evidence.get("action") != "deploy":
        failures.append(f"evidence_action_mismatch:{evidence.get('action')}")
    if evidence.get("raw_output_redacted") is not True:
        failures.append("raw_output_redaction_not_recorded")

    if claim_state.get("live_action_authorized") is not False:
        failures.append("claim_state_live_authorization_not_blocked")
    if claim_state.get("real_readiness_checked") is not False:
        failures.append("claim_state_real_readiness_unexpectedly_checked")
    if claim_state.get("real_readiness_passed") is not False:
        failures.append("claim_state_real_readiness_unexpectedly_passed")
    if claim_state.get("production_readiness_claim_allowed") is not False:
        failures.append("claim_state_production_readiness_not_blocked")
    if claim_state.get("production_slo_claim_allowed") is not False:
        failures.append("claim_state_production_slo_not_blocked")
    if claim_state.get("traffic_shift_claim_allowed") is not False:
        failures.append("claim_state_traffic_shift_not_blocked")
    if claim_state.get("live_customer_traffic_proven") is not False:
        failures.append("claim_state_customer_traffic_not_blocked")

    if claim_gate.get("local_deployment_command_attempt_claim_allowed") is not False:
        failures.append("local_deployment_command_attempt_overclaimed")
    if claim_gate.get("local_deployment_command_succeeded") is not False:
        failures.append("local_deployment_command_success_overclaimed")
    if claim_gate.get("local_real_readiness_preflight_claim_allowed") is not False:
        failures.append("real_readiness_preflight_overclaimed")
    if claim_gate.get("local_real_readiness_preflight_passed") is not False:
        failures.append("real_readiness_preflight_passed_overclaimed")
    for claim_key in STRONG_FALSE_CLAIMS:
        if claim_gate.get(claim_key) is not False:
            failures.append(f"claim_gate_overpromoted:{claim_key}")

    if evidence.get("live_action_authorized") is not False:
        failures.append("evidence_live_authorization_not_blocked")
    if evidence.get("live_action_executed") is not False:
        failures.append("evidence_live_execution_not_blocked")
    if evidence.get("real_readiness_checked") is not False:
        failures.append("evidence_real_readiness_unexpectedly_checked")
    if evidence.get("real_readiness_passed") is not False:
        failures.append("evidence_real_readiness_unexpectedly_passed")

    return failures


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    subprocess_attempted = False
    prerequisites_attempted = False

    async def blocked_prerequisites() -> bool:
        nonlocal prerequisites_attempted
        prerequisites_attempted = True
        raise AssertionError("kubectl prerequisites should remain blocked")

    def blocked_subprocess(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal subprocess_attempted
        subprocess_attempted = True
        raise AssertionError("live deployment subprocess should remain blocked")

    config = production_deploy.DeploymentConfig(allow_live_deploy=False)
    orchestrator = production_deploy.DeploymentOrchestrator(config)
    orchestrator.deployer.check_prerequisites = blocked_prerequisites
    with patch.object(production_deploy.subprocess, "run", blocked_subprocess):
        deploy_result = asyncio.run(orchestrator.execute_deployment())

    claim_state = _mapping(orchestrator.last_claim_gate)
    metadata = _mapping(claim_state.get("safe_actuator_evidence_metadata"))
    failures = _validate_claim_state(
        deploy_result=deploy_result,
        claim_state=claim_state,
        subprocess_attempted=subprocess_attempted,
        prerequisites_attempted=prerequisites_attempted,
    )
    ok = not failures
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "decision": DECISION_RETAINED if ok else DECISION_FAILED,
        "ok": ok,
        "claim_boundary": CLAIM_BOUNDARY,
        "root": str(root),
        "summary": {
            "blocked_before_live_subprocess": subprocess_attempted is False,
            "blocked_before_kubectl_prerequisites": prerequisites_attempted is False,
            "deploy_result_blocked": deploy_result is False,
            "safe_actuator_metadata_retained": bool(metadata),
            "claim_gate_fail_closed": ok,
            "live_deploy_authorized": False,
            "live_deploy_subprocess_attempted": subprocess_attempted,
            "kubectl_prerequisites_attempted": prerequisites_attempted,
            "mutates_runtime": False,
            "writes_eventbus": False,
            "raw_outputs_retained": False,
            "traffic_shift_claimed": False,
            "customer_traffic_claimed": False,
            "production_slo_claimed": False,
            "production_readiness_claimed": False,
        },
        "production_deploy": {
            "action": claim_state.get("action"),
            "live_action_authorized": claim_state.get("live_action_authorized"),
            "real_readiness_checked": claim_state.get("real_readiness_checked"),
            "real_readiness_passed": claim_state.get("real_readiness_passed"),
        },
        "safe_actuator_evidence_metadata": metadata,
        "failures": failures,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retain local production_deploy.py blocked-preflight evidence."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Write JSON to stdout")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help="Path for retained evidence JSON.",
    )
    parser.add_argument(
        "--require-retained",
        action="store_true",
        help="Exit 2 when blocked-preflight evidence is not retained.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    output_json = args.output_json
    if not output_json.is_absolute():
        output_json = root / output_json
    report = build_report(root)
    _write_json(output_json, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_retained and not report.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
