#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parents[2]

DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MATRIX_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
DEFAULT_ANDROID_ADB_PROBE_PATH = Path(
    "nl-diagnostics/nl-anti-block-android-adb-probe-2026-06-02.json"
)
DEFAULT_EVIDENCE_PLAN_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.json"
)
DEFAULT_EVIDENCE_PLAN_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.md"
)
DEFAULT_REMOTE_INTAKE_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.json"
)
DEFAULT_REMOTE_INTAKE_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.md"
)
DEFAULT_RUNTIME_SUMMARY_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json"
)
DEFAULT_RUNTIME_SUMMARY_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.md"
)
DEFAULT_REMOTE_REQUEST_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json"
)
DEFAULT_REMOTE_REQUEST_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.md"
)
DEFAULT_RUNTIME_PROBE_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json"
)
DEFAULT_RUNTIME_DEPLOY_PLAN_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json"
)
DEFAULT_PRODUCTION_AUDIT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-production-audit-2026-06-02.json"
)
DEFAULT_PRODUCTION_AUDIT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-production-audit-2026-06-02.md"
)
DEFAULT_GOAL_BUILDER_PATH = WORKSPACE / "nl-diagnostics" / "build_vpn_goal_status.py"
DEFAULT_GOAL_STATUS_JSON_PATH = Path(
    "nl-diagnostics/vpn-production-candidate-goal-2026-06-02.json"
)
DEFAULT_GOAL_STATUS_MARKDOWN_PATH = Path(
    "nl-diagnostics/vpn-production-candidate-goal-2026-06-02.md"
)
DEFAULT_GOAL_DECISION_JSON_PATH = Path("nl-diagnostics/current-vpn-decision-2026-05-28.json")
DEFAULT_GOAL_TELEGRAM_WARP_PLAN_JSON_PATH = Path(
    "nl-diagnostics/nl-telegram-media-warp-route-plan-2026-06-02-fresh.json"
)
DEFAULT_GOAL_READINESS_AUDIT_JSON_PATH = Path(
    "nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.json"
)
DEFAULT_GOAL_MANIFEST_JSON_PATH = Path("services/nl-server/manifest.json")
DEFAULT_GOAL_PREFLIGHT_VALIDATOR_PATH = Path(
    "services/nl-server/tools/validate_preflight_readiness.py"
)


class RefreshError(ValueError):
    pass


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RefreshError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RefreshError(f"{path} is not valid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def require_json(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload is None:
        raise RefreshError(f"required JSON artifact missing or not object: {path}")
    return payload


def build_refresh_report(
    *,
    matrix: dict[str, Any],
    remote_intake: dict[str, Any],
    runtime_summary: dict[str, Any],
    evidence_plan: dict[str, Any],
    remote_request: dict[str, Any],
    production_audit: dict[str, Any],
    goal_status: dict[str, Any] | None,
    written: bool,
) -> dict[str, Any]:
    rule = matrix.get("completion_rule") if isinstance(matrix.get("completion_rule"), dict) else {}
    report = {
        "decision": "CLIENT_EVIDENCE_ARTIFACTS_REFRESHED" if written else "CLIENT_EVIDENCE_ARTIFACTS_REFRESH_DRY_RUN",
        "written": written,
        "matrix_decision": matrix.get("decision"),
        "matrix_current_status": rule.get("current_status"),
        "missing_requirements": rule.get("missing_requirements") if isinstance(rule.get("missing_requirements"), list) else [],
        "completion": rule.get("evidence") if isinstance(rule.get("evidence"), dict) else {},
        "remote_intake_decision": remote_intake.get("decision"),
        "runtime_summary_decision": runtime_summary.get("decision"),
        "runtime_summary_complete": runtime_summary.get("complete"),
        "evidence_plan_decision": evidence_plan.get("decision"),
        "remote_request_decision": remote_request.get("decision"),
        "remote_request_minimum_reports_required": remote_request.get("minimum_reports_required"),
        "production_audit_decision": production_audit.get("decision"),
        "production_audit_remaining_count": len(
            production_audit.get("remaining_before_goal_complete") or []
        ),
        "privacy": {
            "output_privacy_ok": all(
                [
                    (runtime_summary.get("privacy") or {}).get("output_privacy_ok") is True,
                    (remote_intake.get("privacy") or {}).get("output_privacy_ok") is True,
                    (evidence_plan.get("privacy") or {}).get("output_privacy_ok") is True,
                    (remote_request.get("privacy") or {}).get("output_privacy_ok") is True,
                    (production_audit.get("privacy") or {}).get("output_privacy_ok") is True,
                ]
            ),
            "raw_real_client_rows_returned": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
        },
    }
    if goal_status is not None:
        report.update(
            {
                "goal_status_decision": goal_status.get("decision"),
                "goal_complete": goal_status.get("goal_complete"),
                "goal_requirements_passed": goal_status.get("requirements_passed"),
                "goal_requirements_total": goal_status.get("requirements_total"),
            }
        )
    return report


def build_runtime_summary_from_matrix(
    *,
    runtime_module: Any,
    recorder_module: Any,
    matrix: dict[str, Any],
    matrix_path: Path,
) -> dict[str, Any]:
    tmp_path = matrix_path.with_name(f".{matrix_path.name}.refresh-tmp")
    try:
        recorder_module.write_matrix(tmp_path, matrix)
        return runtime_module.build_summary(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def build_goal_preflight(args: argparse.Namespace, goal_module: Any) -> dict[str, Any]:
    if args.goal_preflight_json:
        return require_json(args.goal_preflight_json)
    return goal_module.run_preflight_validator(args.goal_preflight_validator)


def build_goal_status(
    *,
    args: argparse.Namespace,
    goal_module: Any,
    matrix: dict[str, Any],
    production_audit: dict[str, Any],
    remote_request: dict[str, Any],
) -> dict[str, Any]:
    return goal_module.build_payload(
        {
            "decision": require_json(args.goal_decision_json),
            "anti_block_audit": production_audit,
            "client_matrix": matrix,
            "remote_request": remote_request,
            "telegram_warp_plan": require_json(args.goal_telegram_warp_plan_json),
            "readiness_audit": require_json(args.goal_readiness_audit_json),
            "manifest": require_json(args.goal_manifest_json),
            "preflight": build_goal_preflight(args, goal_module),
        }
    )


def refresh(args: argparse.Namespace) -> dict[str, Any]:
    recorder = load_module("record_client_compatibility", SCRIPT_DIR / "record_client_compatibility.py")
    remote = load_module("record_remote_client_evidence", SCRIPT_DIR / "record_remote_client_evidence.py")
    runtime = load_module(
        "build_client_compatibility_runtime_summary",
        SCRIPT_DIR / "build_client_compatibility_runtime_summary.py",
    )
    plan_builder = load_module("build_client_evidence_plan", SCRIPT_DIR / "build_client_evidence_plan.py")
    request_builder = load_module(
        "build_remote_client_evidence_request_packet",
        SCRIPT_DIR / "build_remote_client_evidence_request_packet.py",
    )
    audit_builder = load_module(
        "build_anti_block_production_audit",
        SCRIPT_DIR / "build_anti_block_production_audit.py",
    )
    goal_builder = load_module("build_vpn_goal_status", args.goal_builder)

    try:
        matrix = recorder.load_matrix(args.matrix)
    except Exception as exc:
        if exc.__class__.__name__ == "CompatibilityError":
            raise RefreshError(str(exc)) from exc
        raise
    recorder.refresh_completion(matrix)
    matrix_findings = recorder.validate_report(matrix)
    if matrix_findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in matrix_findings[:5])
        raise RefreshError(f"matrix failed privacy validation: {details}")

    remote_report = remote.build_report(
        recorder=recorder,
        matrix=matrix,
        candidate=None,
        matrix_after=None,
        record_matrix=False,
        wrote_matrix=False,
    )
    remote_findings = remote.validate_safe_payload(remote_report, recorder)
    if remote_findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in remote_findings[:5])
        raise RefreshError(f"remote intake failed privacy validation: {details}")

    runtime_summary = build_runtime_summary_from_matrix(
        runtime_module=runtime,
        recorder_module=recorder,
        matrix=matrix,
        matrix_path=args.matrix,
    )
    evidence_plan = plan_builder.build_plan(
        matrix,
        android_adb_probe=load_json(args.android_adb_probe),
    )
    plan_findings = plan_builder.validate_output(evidence_plan)
    if plan_findings:
        raise RefreshError(
            "evidence plan failed privacy validation: "
            + ", ".join(item["kind"] for item in plan_findings)
        )
    remote_request = request_builder.build_packet(
        matrix,
        android_adb_probe=load_json(args.android_adb_probe),
    )
    request_findings = request_builder.validate_output(remote_request)
    if request_findings:
        raise RefreshError(
            "remote request packet failed privacy validation: "
            + ", ".join(item["kind"] for item in request_findings)
        )
    production_audit = audit_builder.build_audit(
        server_evidence_seed=load_json(args.server_evidence_json),
        matrix=matrix,
        evidence_plan=evidence_plan,
        remote_intake=remote_report,
        remote_request=remote_request,
        runtime_summary=runtime_summary,
        runtime_probe=require_json(args.runtime_probe_json),
        runtime_deploy_plan=require_json(args.runtime_deploy_plan_json),
    )
    audit_findings = audit_builder.validate_output(production_audit)
    if audit_findings:
        raise RefreshError(
            "production audit failed privacy validation: "
            + ", ".join(item["kind"] for item in audit_findings)
        )
    goal_status = build_goal_status(
        args=args,
        goal_module=goal_builder,
        matrix=matrix,
        production_audit=production_audit,
        remote_request=remote_request,
    )

    if args.write:
        recorder.write_matrix(args.matrix, matrix)
        recorder.write_markdown(args.matrix_markdown, matrix)
        remote.write_json(args.remote_intake_json_out, remote_report)
        remote.write_markdown(args.remote_intake_markdown_out, remote_report, recorder)
        runtime.write_json(args.runtime_summary_json_out, runtime_summary)
        runtime.write_markdown(args.runtime_summary_markdown_out, runtime_summary)
        plan_builder.write_json(args.evidence_plan_json_out, evidence_plan)
        plan_builder.write_markdown(args.evidence_plan_markdown_out, evidence_plan)
        request_builder.write_json(args.remote_request_json_out, remote_request)
        request_builder.write_markdown(args.remote_request_markdown_out, remote_request)
        audit_builder.write_json(args.production_audit_json_out, production_audit)
        audit_builder.write_markdown(args.production_audit_markdown_out, production_audit)
        args.goal_status_json_out.write_text(
            json.dumps(goal_status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        args.goal_status_markdown_out.write_text(
            goal_builder.render_markdown(goal_status),
            encoding="utf-8",
        )

    return build_refresh_report(
        matrix=matrix,
        remote_intake=remote_report,
        runtime_summary=runtime_summary,
        evidence_plan=evidence_plan,
        remote_request=remote_request,
        production_audit=production_audit,
        goal_status=goal_status,
        written=args.write,
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Refresh privacy-safe NL client evidence artifacts from the matrix."
    )
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--matrix-markdown", type=Path, default=DEFAULT_MATRIX_MARKDOWN_PATH)
    p.add_argument("--android-adb-probe", type=Path, default=DEFAULT_ANDROID_ADB_PROBE_PATH)
    p.add_argument("--evidence-plan-json-out", type=Path, default=DEFAULT_EVIDENCE_PLAN_JSON_PATH)
    p.add_argument(
        "--evidence-plan-markdown-out",
        type=Path,
        default=DEFAULT_EVIDENCE_PLAN_MARKDOWN_PATH,
    )
    p.add_argument("--remote-intake-json-out", type=Path, default=DEFAULT_REMOTE_INTAKE_JSON_PATH)
    p.add_argument(
        "--remote-intake-markdown-out",
        type=Path,
        default=DEFAULT_REMOTE_INTAKE_MARKDOWN_PATH,
    )
    p.add_argument("--runtime-summary-json-out", type=Path, default=DEFAULT_RUNTIME_SUMMARY_JSON_PATH)
    p.add_argument(
        "--runtime-summary-markdown-out",
        type=Path,
        default=DEFAULT_RUNTIME_SUMMARY_MARKDOWN_PATH,
    )
    p.add_argument("--remote-request-json-out", type=Path, default=DEFAULT_REMOTE_REQUEST_JSON_PATH)
    p.add_argument(
        "--remote-request-markdown-out",
        type=Path,
        default=DEFAULT_REMOTE_REQUEST_MARKDOWN_PATH,
    )
    p.add_argument("--runtime-probe-json", type=Path, default=DEFAULT_RUNTIME_PROBE_JSON_PATH)
    p.add_argument("--runtime-deploy-plan-json", type=Path, default=DEFAULT_RUNTIME_DEPLOY_PLAN_JSON_PATH)
    p.add_argument("--server-evidence-json", type=Path, default=DEFAULT_PRODUCTION_AUDIT_JSON_PATH)
    p.add_argument("--production-audit-json-out", type=Path, default=DEFAULT_PRODUCTION_AUDIT_JSON_PATH)
    p.add_argument(
        "--production-audit-markdown-out",
        type=Path,
        default=DEFAULT_PRODUCTION_AUDIT_MARKDOWN_PATH,
    )
    p.add_argument("--goal-builder", type=Path, default=DEFAULT_GOAL_BUILDER_PATH)
    p.add_argument("--goal-status-json-out", type=Path, default=DEFAULT_GOAL_STATUS_JSON_PATH)
    p.add_argument(
        "--goal-status-markdown-out",
        type=Path,
        default=DEFAULT_GOAL_STATUS_MARKDOWN_PATH,
    )
    p.add_argument("--goal-decision-json", type=Path, default=DEFAULT_GOAL_DECISION_JSON_PATH)
    p.add_argument(
        "--goal-telegram-warp-plan-json",
        type=Path,
        default=DEFAULT_GOAL_TELEGRAM_WARP_PLAN_JSON_PATH,
    )
    p.add_argument(
        "--goal-readiness-audit-json",
        type=Path,
        default=DEFAULT_GOAL_READINESS_AUDIT_JSON_PATH,
    )
    p.add_argument("--goal-manifest-json", type=Path, default=DEFAULT_GOAL_MANIFEST_JSON_PATH)
    p.add_argument(
        "--goal-preflight-validator",
        type=Path,
        default=DEFAULT_GOAL_PREFLIGHT_VALIDATOR_PATH,
    )
    p.add_argument("--goal-preflight-json", type=Path)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = refresh(args)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={report['decision']} "
                f"missing={len(report['missing_requirements'])}"
            )
        return 0 if (report.get("privacy") or {}).get("output_privacy_ok") is True else 1
    except RefreshError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
