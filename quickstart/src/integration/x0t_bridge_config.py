"""Fail-closed bridge contract address config gate.

This module validates an operator-provided Base Sepolia bridge contract
address before it can be written into the production MeshCluster example. It
does not call RPC, deploy contracts, submit transactions, or mutate chain
state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


SCHEMA_VERSION = "x0tta6bl4-x0t-bridge-config-v1"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/x0t-bridge-config-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/x0t-bridge-config-2026-05-21.md"
DEFAULT_CONFIG_PATH = "charts/x0tta-mesh-operator/examples/meshcluster-production.yaml"
DEFAULT_DEPLOYMENT_MANIFEST = "src/dao/deployments/base_sepolia.json"
EXPECTED_CHAIN_ID = 84532
APPROVAL_ENV = "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
APPROVAL_VALUE = "apply-bridge-address-base-sepolia"
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
OPERATOR_APPROVAL_REQUIRED = "OPERATOR_APPROVAL_REQUIRED"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, f"missing JSON file: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable JSON file: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"JSON file must contain an object: {path}"
    return data, ""


def _read_text(path: Path) -> Tuple[str, str]:
    if not path.exists():
        return "", f"missing file: {path}"
    try:
        return path.read_text(encoding="utf-8"), ""
    except Exception as exc:
        return "", f"unreadable file: {path}: {exc}"


def _is_placeholder_address(value: str) -> bool:
    lower = value.strip().lower()
    return (
        not lower
        or lower == "0x" + ("0" * 40)
        or any(token in lower for token in ("placeholder", "replace", "todo", "changeme", "<", ">"))
    )


def _deployment_addresses(root: Path) -> Dict[str, str]:
    data, _ = _read_json(_resolve(root, DEFAULT_DEPLOYMENT_MANIFEST))
    data = data or {}
    return {
        "MeshGovernance": str(data.get("MeshGovernance", "")),
        "X0TToken": str(data.get("X0TToken", "")),
        "chainId": str(data.get("chainId", "")),
    }


def _nested_get(data: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return default
        current = current.get(part)
    return current if current is not None else default


def _load_config_values(path: Path) -> Tuple[Dict[str, Any], str]:
    text, error = _read_text(path)
    if error:
        return {}, error
    try:
        data = yaml.safe_load(text) or {}
    except Exception as exc:
        return {}, f"unreadable YAML file: {path}: {exc}"
    if not isinstance(data, dict):
        return {}, f"YAML file must contain an object: {path}"
    return data, ""


def _validate_bridge_address(address: str, deployment: Dict[str, str]) -> List[str]:
    value = str(address or "").strip()
    errors: List[str] = []
    if _is_placeholder_address(value):
        errors.append("bridge contract address is required and must not be zero or placeholder")
        return errors
    if not ADDRESS_RE.match(value):
        errors.append("bridge contract address must be a 0x-prefixed 20-byte hex address")
        return errors
    lower = value.lower()
    if deployment.get("MeshGovernance", "").lower() == lower:
        errors.append("bridge contract address must not equal MeshGovernance")
    if deployment.get("X0TToken", "").lower() == lower:
        errors.append("bridge contract address must not equal X0TToken")
    if str(deployment.get("chainId", "")) and str(deployment.get("chainId")) != str(EXPECTED_CHAIN_ID):
        errors.append(f"deployment manifest chainId must be {EXPECTED_CHAIN_ID}")
    return errors


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _replace_bridge_address(text: str, bridge_address: str) -> Tuple[str, str]:
    lines = text.splitlines(keepends=True)
    bridge_indent: Optional[int] = None
    bridge_seen = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"^bridge:\s*(?:#.*)?$", stripped):
            bridge_indent = indent
            bridge_seen = True
            continue
        if bridge_seen and bridge_indent is not None:
            if stripped and indent <= bridge_indent:
                break
            match = re.match(r"^(\s*)contractAddress\s*:\s*([\"']?)([^\"'\s#]*)([\"']?)(.*?)(\r?\n)?$", line)
            if match:
                suffix = match.group(5) or ""
                newline = match.group(6) or ""
                lines[index] = f'{match.group(1)}contractAddress: "{bridge_address}"{suffix}{newline}'
                return "".join(lines), ""
    return text, "could not find spec.dao.bridge.contractAddress in config"


def build_report(
    root: Path,
    *,
    bridge_address: str = "",
    config_path: str = DEFAULT_CONFIG_PATH,
    write_config: bool = False,
    approval: str = "",
) -> Dict[str, Any]:
    config_file = _resolve(root, config_path)
    config_data, config_error = _load_config_values(config_file)
    config_text, text_error = _read_text(config_file)
    deployment = _deployment_addresses(root)
    configured_address = str(
        _nested_get(config_data, ["spec", "dao", "bridge", "contractAddress"], "")
    )
    configured_chain_id = _nested_get(config_data, ["spec", "dao", "bridge", "chainId"], None)
    input_address = str(bridge_address or "").strip()
    input_errors = _validate_bridge_address(input_address, deployment)
    configured_errors = _validate_bridge_address(configured_address, deployment)
    if configured_chain_id != EXPECTED_CHAIN_ID:
        configured_errors.append(f"configured bridge chainId must be {EXPECTED_CHAIN_ID}")
    input_ready = not input_errors
    configured_ready = not config_error and not configured_errors
    config_matches_input = bool(
        input_ready and configured_ready and configured_address.lower() == input_address.lower()
    )
    approval_ready = approval == APPROVAL_VALUE

    write_error = ""
    write_performed = False
    if write_config:
        if not input_ready:
            write_error = "bridge address input is not ready"
        elif not approval_ready:
            write_error = f"{APPROVAL_ENV} must be {APPROVAL_VALUE}"
        elif text_error:
            write_error = text_error
        else:
            new_text, replace_error = _replace_bridge_address(config_text, input_address)
            if replace_error:
                write_error = replace_error
            elif new_text != config_text:
                config_file.write_text(new_text, encoding="utf-8")
                write_performed = True
                configured_address = input_address
                configured_errors = []
                configured_ready = True
                config_matches_input = True
            else:
                configured_address = input_address
                configured_errors = []
                configured_ready = True
                config_matches_input = True

    missing_inputs: List[Dict[str, Any]] = []
    if not input_ready and not configured_ready:
        missing_inputs.append(
            {
                "id": "bridge_contract_address",
                "status": OPERATOR_INPUT_REQUIRED,
                "environment": "X0T_BRIDGE_CONTRACT_ADDRESS",
                "reason": "; ".join(input_errors or configured_errors),
            }
        )
    if input_ready and not config_matches_input and not write_config:
        missing_inputs.append(
            {
                "id": "bridge_config_apply",
                "status": OPERATOR_APPROVAL_REQUIRED,
                "environment": APPROVAL_ENV,
                "expected_value": APPROVAL_VALUE,
                "reason": "validated bridge address has not been written to the operator config",
            }
        )
    if write_config and write_error:
        missing_inputs.append(
            {
                "id": "bridge_config_write",
                "status": "BLOCKED",
                "reason": write_error,
            }
        )

    bridge_config_ready = configured_ready and (not input_ready or config_matches_input)
    decision = (
        "X0T_BRIDGE_CONFIG_READY"
        if bridge_config_ready
        else "X0T_BRIDGE_CONFIG_READY_TO_APPLY"
        if input_ready and not write_error
        else "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    )
    missing_input_status_counts = _status_counts(missing_inputs)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "bridge_config_ready": bridge_config_ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "mutates_config": write_performed,
        "claim_boundary": (
            "Validates and optionally writes the operator MeshCluster bridge contract address. "
            "It does not deploy contracts, call live RPC, submit transactions, mutate chain state, "
            "or close /goal."
        ),
        "source_artifacts": [DEFAULT_DEPLOYMENT_MANIFEST, config_path],
        "config": {
            "path": config_path,
            "chain_id": configured_chain_id,
            "configured_bridge_address": configured_address,
            "configured_errors": configured_errors,
            "configured_ready": configured_ready,
            "config_matches_input": config_matches_input,
        },
        "input": {
            "bridge_address": input_address,
            "errors": input_errors,
            "ready": input_ready,
        },
        "write": {
            "requested": write_config,
            "approval_env": APPROVAL_ENV,
            "approval_ready": approval_ready,
            "approval_value_required": APPROVAL_VALUE,
            "performed": write_performed,
            "error": write_error,
        },
        "deployment_addresses": deployment,
        "missing_inputs": missing_inputs,
        "summary": {
            "bridge_config_ready": bridge_config_ready,
            "bridge_address_input_ready": input_ready,
            "configured_bridge_ready": configured_ready,
            "config_matches_input": config_matches_input,
            "missing_inputs_total": len(missing_inputs),
            "missing_input_status_counts": missing_input_status_counts,
            "missing_inputs_operator_input_required": missing_input_status_counts.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "missing_inputs_operator_approval_required": missing_input_status_counts.get(
                OPERATOR_APPROVAL_REQUIRED, 0
            ),
            "missing_inputs_generic_operator_required": missing_input_status_counts.get(
                OPERATOR_REQUIRED, 0
            ),
            "write_requested": write_config,
            "write_performed": write_performed,
            "approval_ready": approval_ready,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# X0T Bridge Config",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Decision: `{report.get('decision', '')}`",
        f"Bridge config ready: `{report.get('bridge_config_ready')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Summary",
        "",
        f"- bridge address input ready: `{summary.get('bridge_address_input_ready')}`",
        f"- configured bridge ready: `{summary.get('configured_bridge_ready')}`",
        f"- config matches input: `{summary.get('config_matches_input')}`",
        f"- write performed: `{summary.get('write_performed')}`",
        "",
        "## Missing Inputs",
        "",
    ]
    missing = report.get("missing_inputs", [])
    if missing:
        for item in missing:
            lines.append(f"- `{item.get('id')}`: `{item.get('status')}` - {item.get('reason', '')}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "X0T Bridge Config",
            f"decision: {report.get('decision')}",
            f"bridge_config_ready: {report.get('bridge_config_ready')}",
            f"bridge_address_input_ready: {summary.get('bridge_address_input_ready')}",
            f"configured_bridge_ready: {summary.get('configured_bridge_ready')}",
            f"write_performed: {summary.get('write_performed')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate/apply X0T bridge contract address config")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--bridge-address", default=os.getenv("X0T_BRIDGE_CONTRACT_ADDRESS", ""))
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--approval", default=os.getenv(APPROVAL_ENV, ""))
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--write-json", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-input-ready", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root,
        bridge_address=args.bridge_address,
        config_path=args.config_path,
        write_config=args.write_config,
        approval=args.approval,
    )
    if args.write_json:
        write_json(_resolve(root, args.output_json), report)
    if args.write_md:
        md_path = _resolve(root, args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_input_ready and report["summary"]["bridge_address_input_ready"] is not True:
        return 2
    if args.require_ready and report["bridge_config_ready"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
