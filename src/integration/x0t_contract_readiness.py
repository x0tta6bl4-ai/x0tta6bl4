"""Read-only X0T contract/deployment readiness gate.

This module checks the local contract build surface, reads the separate
compile/test verification artifact, and checks deployment address
configuration. It does not call RPC, install packages, compile contracts,
submit transactions, or mark the goal complete.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = "x0tta6bl4-x0t-contract-readiness-v1"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/x0t-contract-readiness-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/x0t-contract-readiness-2026-05-21.md"
CONTRACT_BUILD_VERIFICATION = ".tmp/validation-shards/x0t-contract-build-verification-current.json"
CONTRACT_PACKAGE_DIR = "src/dao/contracts"
CONTRACT_PACKAGE_JSON = f"{CONTRACT_PACKAGE_DIR}/package.json"
CONTRACT_HARDHAT_CONFIG = f"{CONTRACT_PACKAGE_DIR}/hardhat.config.js"
CONTRACT_NVMRC = f"{CONTRACT_PACKAGE_DIR}/.nvmrc"
BRIDGE_CONTRACT_SOURCE = f"{CONTRACT_PACKAGE_DIR}/contracts/X0TBridge.sol"
BRIDGE_DEPLOY_SCRIPT = f"{CONTRACT_PACKAGE_DIR}/scripts/deploy_bridge.js"
BRIDGE_CONTRACT_TEST = f"{CONTRACT_PACKAGE_DIR}/test/X0TBridge.test.js"
BRIDGE_SOURCE_ARTIFACTS = [
    BRIDGE_CONTRACT_SOURCE,
    BRIDGE_DEPLOY_SCRIPT,
    BRIDGE_CONTRACT_TEST,
]
BASE_SEPOLIA_DEPLOYMENT = "src/dao/deployments/base_sepolia.json"
OPERATOR_CONFIGS = [
    "charts/x0tta6bl4-commercial/values-enterprise.yaml",
    "charts/x0tta-mesh-operator/examples/meshcluster-production.yaml",
]
BRIDGE_CONFIG_APPLY_COMMANDS = [
    'export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"',
    'python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready',
    'X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready',
    "python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md",
]
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
LEGACY_CONTRACTS = [
    "contracts/Voting.sol",
]
EXPECTED_CHAIN_ID = 84532
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
IMPORT_RE = re.compile(r"(?:from\s+[\"']([^\"']+)[\"'])|(?:require\([\"']([^\"']+)[\"']\))")
CONTRACT_ADDRESS_RE = re.compile(r"\bcontractAddress\s*:\s*[\"']?([^\"'\s#]+)")
FUNC_SYNTAX_RE = re.compile(r"\bfunc\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")


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


def _parse_version(value: str) -> Optional[Tuple[int, int, int]]:
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    return major, minor, patch


def _version_satisfies(spec: str, actual: str) -> bool:
    spec = (spec or "").strip()
    actual_version = _parse_version(actual)
    if not spec or spec == "*" or actual_version is None:
        return bool(actual_version)
    if "||" in spec:
        return any(_version_satisfies(part.strip(), actual) for part in spec.split("||"))

    if spec.startswith(">="):
        base = _parse_version(spec)
        return bool(base and actual_version >= base)
    if spec.startswith("^"):
        base = _parse_version(spec)
        if base is None or actual_version < base:
            return False
        if base[0] > 0:
            return actual_version[0] == base[0]
        if base[1] > 0:
            return actual_version[:2] == base[:2]
        return actual_version == base
    if spec.startswith("~"):
        base = _parse_version(spec)
        return bool(base and actual_version >= base and actual_version[:2] == base[:2])
    if spec[0].isdigit():
        base = _parse_version(spec)
        return bool(base and actual_version == base)

    base = _parse_version(spec)
    return bool(base and actual_version >= base)


def _current_node_version() -> str:
    try:
        result = subprocess.run(
            ["node", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _package_json_path(package_dir: Path, name: str) -> Path:
    parts = name.split("/")
    return package_dir / "node_modules" / Path(*parts) / "package.json"


def _installed_version(package_dir: Path, name: str) -> str:
    package_json = _package_json_path(package_dir, name)
    data, _ = _read_json(package_json)
    if not data:
        return ""
    version = data.get("version")
    return str(version) if isinstance(version, str) else ""


def _is_package_import(value: str) -> bool:
    return bool(value and not value.startswith(".") and not value.startswith("/"))


def _package_name_from_import(value: str) -> str:
    if value.startswith("@"):
        parts = value.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else value
    return value.split("/", 1)[0]


def _declared_packages(package_json: Dict[str, Any]) -> Dict[str, str]:
    declared: Dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        value = package_json.get(key, {})
        if isinstance(value, dict):
            declared.update({str(name): str(spec) for name, spec in value.items()})
    return declared


def _build_verification_report(root: Path) -> Dict[str, Any]:
    path = _resolve(root, CONTRACT_BUILD_VERIFICATION)
    data, error = _read_json(path)
    data = data or {}
    summary = data.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    ready = (
        not error
        and data.get("status") == "VERIFIED HERE"
        and data.get("ok") is True
        and data.get("schema_version") == "x0tta6bl4-x0t-contract-build-verification-v1"
        and data.get("contract_build_verified") is True
        and data.get("mutates_chain") is False
        and data.get("runs_live_rpc") is False
        and data.get("submits_transaction") is False
        and summary.get("required_node_runtime_ready") is True
        and summary.get("hardhat_compile_ready") is True
        and summary.get("hardhat_test_ready") is True
    )
    return {
        "path": CONTRACT_BUILD_VERIFICATION,
        "ready": ready,
        "error": error,
        "decision": data.get("decision", ""),
        "generated_at": data.get("generated_at", ""),
        "summary": summary,
    }


def _build_env_report(root: Path, node_version: Optional[str]) -> Dict[str, Any]:
    package_path = _resolve(root, CONTRACT_PACKAGE_JSON)
    config_path = _resolve(root, CONTRACT_HARDHAT_CONFIG)
    nvmrc_path = _resolve(root, CONTRACT_NVMRC)
    package_dir = _resolve(root, CONTRACT_PACKAGE_DIR)
    package_json, package_error = _read_json(package_path)
    config_text, config_error = _read_text(config_path)
    nvmrc_text, nvmrc_error = _read_text(nvmrc_path)

    package_json = package_json or {}
    engine_spec = ""
    engines = package_json.get("engines", {})
    if isinstance(engines, dict):
        engine_spec = str(engines.get("node", ""))
    observed_node = node_version if node_version is not None else _current_node_version()
    node_ready = bool(observed_node and (not engine_spec or _version_satisfies(engine_spec, observed_node)))
    build_verification = _build_verification_report(root)
    build_verification_node_ready = (
        build_verification.get("summary", {}).get("required_node_runtime_ready") is True
    )
    effective_node_ready = node_ready or build_verification_node_ready
    if node_ready:
        node_ready_source = "current_shell"
    elif build_verification_node_ready:
        node_ready_source = "contract_build_verification"
    else:
        node_ready_source = ""

    declared = _declared_packages(package_json)
    dependency_checks: List[Dict[str, Any]] = []
    for name, spec in sorted(declared.items()):
        actual = _installed_version(package_dir, name)
        if not actual:
            status = "MISSING"
        elif not _version_satisfies(spec, actual):
            status = "INVALID_VERSION"
        else:
            status = "READY"
        dependency_checks.append(
            {
                "name": name,
                "declared": spec,
                "installed": actual,
                "status": status,
            }
        )

    imports = sorted(
        {
            _package_name_from_import(match.group(1) or match.group(2) or "")
            for match in IMPORT_RE.finditer(config_text)
            if _is_package_import(match.group(1) or match.group(2) or "")
        }
    )
    missing_import_packages = [
        name for name in imports if not _package_json_path(package_dir, name).exists()
    ]

    missing_dependencies = [item for item in dependency_checks if item["status"] == "MISSING"]
    invalid_dependencies = [item for item in dependency_checks if item["status"] == "INVALID_VERSION"]
    dependencies_ready = not missing_dependencies and not invalid_dependencies
    imports_ready = not missing_import_packages and not config_error
    ready = (
        not package_error
        and not config_error
        and effective_node_ready
        and dependencies_ready
        and imports_ready
        and build_verification["ready"]
    )

    return {
        "ready": ready,
        "package_json": CONTRACT_PACKAGE_JSON,
        "hardhat_config": CONTRACT_HARDHAT_CONFIG,
        "package_error": package_error,
        "config_error": config_error,
        "node_runtime": {
            "engine_spec": engine_spec,
            "nvmrc": nvmrc_text.strip() if not nvmrc_error else "",
            "observed": observed_node,
            "ready": node_ready,
            "effective_ready": effective_node_ready,
            "ready_source": node_ready_source,
        },
        "dependencies": {
            "declared_total": len(dependency_checks),
            "missing_total": len(missing_dependencies),
            "invalid_total": len(invalid_dependencies),
            "ready": dependencies_ready,
            "checks": dependency_checks,
        },
        "hardhat_config_imports": {
            "imports": imports,
            "missing_packages": missing_import_packages,
            "ready": imports_ready,
        },
        "build_verification": build_verification,
    }


def _is_placeholder_address(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    if lower == "0x" + ("0" * 40):
        return True
    tokens = ("placeholder", "replace", "todo", "changeme", "example", "new", "<", ">")
    return any(token in lower for token in tokens)


def _address_status(value: Any) -> Tuple[bool, str]:
    address = str(value or "")
    if _is_placeholder_address(address):
        return False, "PLACEHOLDER_ADDRESS"
    if not ADDRESS_RE.match(address):
        return False, "INVALID_ADDRESS"
    return True, "READY"


def _deployment_manifest_report(root: Path) -> Dict[str, Any]:
    path = _resolve(root, BASE_SEPOLIA_DEPLOYMENT)
    data, error = _read_json(path)
    data = data or {}
    address_fields = ["MeshGovernance", "X0TToken"]
    address_checks: List[Dict[str, Any]] = []
    for field in address_fields:
        value = data.get(field, "")
        ok, status = _address_status(value)
        address_checks.append({"field": field, "value": str(value or ""), "status": status, "ready": ok})

    chain_id = data.get("chainId")
    chain_ready = chain_id == EXPECTED_CHAIN_ID
    ready = not error and chain_ready and all(item["ready"] for item in address_checks)
    return {
        "path": BASE_SEPOLIA_DEPLOYMENT,
        "ready": ready,
        "error": error,
        "expected_chain_id": EXPECTED_CHAIN_ID,
        "chain_id": chain_id,
        "chain_ready": chain_ready,
        "address_checks": address_checks,
    }


def _operator_config_report(root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []
    for relative in OPERATOR_CONFIGS:
        path = _resolve(root, relative)
        text, error = _read_text(path)
        if error:
            errors.append(error)
            checks.append({"path": relative, "ready": False, "error": error, "addresses": []})
            continue
        addresses: List[Dict[str, Any]] = []
        lines = text.splitlines()
        for line_number, line in enumerate(lines, start=1):
            match = CONTRACT_ADDRESS_RE.search(line)
            if not match:
                continue
            value = match.group(1)
            ok, status = _address_status(value)
            context = "\n".join(lines[max(0, line_number - 5):line_number])
            address_kind = "bridge_contract" if "bridge:" in context or "bridge contract" in line else "governance_contract"
            if address_kind == "bridge_contract" and status == "PLACEHOLDER_ADDRESS":
                status = "MISSING_BRIDGE_CONTRACT_ADDRESS"
            addresses.append(
                {
                    "line": line_number,
                    "address_kind": address_kind,
                    "value": value,
                    "status": status,
                    "ready": ok,
                }
            )
        if not addresses:
            errors.append(f"{relative}: missing contractAddress field")
        checks.append(
            {
                "path": relative,
                "ready": bool(addresses and all(item["ready"] for item in addresses)),
                "error": "",
                "addresses": addresses,
            }
        )
    ready = not errors and all(item["ready"] for item in checks)
    return {"ready": ready, "errors": errors, "checks": checks}


def _legacy_contract_report(root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for relative in LEGACY_CONTRACTS:
        path = _resolve(root, relative)
        text, error = _read_text(path)
        issues: List[str] = []
        if error:
            issues.append(error)
        else:
            if FUNC_SYNTAX_RE.search(text):
                issues.append("Solidity syntax marker `func ...` found; expected `function ...`")
            if "contract Voting is Ownable" in text and "constructor(address tokenAddress) Ownable(" not in text:
                issues.append("Voting constructor does not initialize Ownable(initialOwner)")
        checks.append({"path": relative, "ready": not issues, "issues": issues})
    ready = all(item["ready"] for item in checks)
    return {"ready": ready, "checks": checks}


def _required_snippet_issues(text: str, snippets: Iterable[str]) -> List[str]:
    return [f"missing required snippet: {snippet}" for snippet in snippets if snippet not in text]


def _bridge_source_report(root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    required_by_path = {
        BRIDGE_CONTRACT_SOURCE: [
            "contract X0TBridge",
            "SafeERC20",
            "ReentrancyGuard",
            "Pausable",
            "BridgeDeposit",
            "BridgeRelease",
            "bridgeOperators",
            "processedReleases",
            "depositFor",
            "releaseToChain",
        ],
        BRIDGE_DEPLOY_SCRIPT: [
            "X0TBridge",
            "X0T_TOKEN_ADDRESS",
            "X0T_BRIDGE_OPERATOR_ADDRESS",
            "X0T_DEPLOY_BRIDGE_APPROVAL",
            "deploy-bridge-base-sepolia",
            "PRIVATE_KEY",
        ],
        BRIDGE_CONTRACT_TEST: [
            "X0TBridge",
            "BridgeDeposit",
            "BridgeRelease",
            "ReleaseAlreadyProcessed",
            "NotBridgeOperator",
        ],
    }
    for relative in BRIDGE_SOURCE_ARTIFACTS:
        path = _resolve(root, relative)
        text, error = _read_text(path)
        issues: List[str] = []
        if error:
            issues.append(error)
        else:
            issues.extend(_required_snippet_issues(text, required_by_path[relative]))
        checks.append({"path": relative, "ready": not issues, "issues": issues})
    ready = all(item["ready"] for item in checks)
    return {"ready": ready, "checks": checks}


def _flatten(values: Iterable[Iterable[Any]]) -> List[Any]:
    return [item for value in values for item in value]


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _missing_inputs(
    build_env: Dict[str, Any],
    deployment: Dict[str, Any],
    operator_configs: Dict[str, Any],
    legacy_contracts: Dict[str, Any],
    bridge_source: Dict[str, Any],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    node_runtime = build_env["node_runtime"]
    if not node_runtime["effective_ready"]:
        missing.append(
            {
                "id": "node_runtime",
                "status": "LOCAL_ENV_REQUIRED",
                "reason": (
                    f"contract package requires node {node_runtime['engine_spec']}, "
                    f".nvmrc is {node_runtime.get('nvmrc') or 'missing'}, "
                    f"observed {node_runtime['observed'] or 'not found'}, "
                    "and no successful Node 22 build verification artifact is available"
                ),
            }
        )
    if build_env["dependencies"]["missing_total"] or build_env["dependencies"]["invalid_total"]:
        missing.append(
            {
                "id": "contract_npm_dependencies",
                "status": "LOCAL_ENV_REQUIRED",
                "command": "cd src/dao/contracts && npm ci",
                "reason": "node_modules does not match the contract package manifest",
            }
        )
    if build_env["hardhat_config_imports"]["missing_packages"]:
        missing.append(
            {
                "id": "hardhat_config_imports",
                "status": "LOCAL_ENV_REQUIRED",
                "missing_packages": build_env["hardhat_config_imports"]["missing_packages"],
                "reason": "hardhat.config.js imports packages that are not installed locally",
            }
        )
    if not build_env["build_verification"]["ready"]:
        missing.append(
            {
                "id": "contract_build_verification",
                "status": "LOCAL_VERIFICATION_REQUIRED",
                "path": CONTRACT_BUILD_VERIFICATION,
                "command": "python3 scripts/ops/verify_x0t_contract_build.py --write-json --write-md --require-verified",
                "reason": "Hardhat compile/test has not been verified under the required Node 22 runtime",
            }
        )

    bad_manifest_addresses = [
        item for item in deployment["address_checks"] if item["ready"] is not True
    ]
    if deployment["error"] or not deployment["chain_ready"] or bad_manifest_addresses:
        missing.append(
            {
                "id": "base_sepolia_deployment_manifest",
                "status": "OPERATOR_EVIDENCE_REQUIRED",
                "path": BASE_SEPOLIA_DEPLOYMENT,
                "reason": "deployment manifest must contain verified Base Sepolia contract addresses",
            }
        )

    bad_operator_checks = [
        item for item in operator_configs["checks"] if item["ready"] is not True
    ]
    bad_operator_configs = [item["path"] for item in bad_operator_checks]
    if bad_operator_configs:
        missing_bridge = any(
            address.get("status") == "MISSING_BRIDGE_CONTRACT_ADDRESS"
            for check in bad_operator_checks
            for address in check.get("addresses", [])
        )
        missing.append(
            {
                "id": "operator_contract_addresses",
                "status": OPERATOR_INPUT_REQUIRED,
                "paths": bad_operator_configs,
                "commands": BRIDGE_CONFIG_APPLY_COMMANDS if missing_bridge else [],
                "reason": (
                    "operator bridge config still needs its own deployed bridge contract address; "
                    "do not substitute X0TToken or MeshGovernance"
                )
                if missing_bridge
                else "operator/Helm configs must not carry zero or placeholder contract addresses",
            }
        )

    legacy_issues = _flatten(item["issues"] for item in legacy_contracts["checks"])
    if legacy_issues:
        missing.append(
            {
                "id": "legacy_root_contract_surface",
                "status": "REPO_REQUIRED",
                "paths": [item["path"] for item in legacy_contracts["checks"] if item["issues"]],
                "reason": "legacy root contract files still contain compile blockers or stale Solidity patterns",
            }
        )

    bridge_source_issues = _flatten(item["issues"] for item in bridge_source["checks"])
    if bridge_source_issues:
        missing.append(
            {
                "id": "x0t_bridge_contract_source_surface",
                "status": "REPO_REQUIRED",
                "paths": [item["path"] for item in bridge_source["checks"] if item["issues"]],
                "reason": "repo must include a deployable X0TBridge contract, fail-closed deploy script, and Hardhat bridge tests",
            }
        )

    return missing


def _not_verified_yet(
    build_env: Dict[str, Any],
    deployment: Dict[str, Any],
    operator_configs: Dict[str, Any],
    bridge_source: Dict[str, Any],
) -> List[str]:
    items: List[str] = []
    if not build_env["build_verification"]["ready"]:
        items.append("successful Hardhat compile/test under the required Node runtime")
    if not build_env["node_runtime"]["effective_ready"]:
        items.append("Node runtime matching the contract package engine")
    if not deployment["ready"]:
        items.append("authoritative Base Sepolia deployment manifest with non-placeholder addresses")
    if not operator_configs["ready"]:
        missing_bridge = any(
            address.get("status") == "MISSING_BRIDGE_CONTRACT_ADDRESS"
            for check in operator_configs["checks"]
            for address in check.get("addresses", [])
        )
        items.append(
            "deployed bridge contract address for operator bridge config"
            if missing_bridge
            else "operator configs wired to verified contract addresses"
        )
    if not bridge_source["ready"]:
        items.append("deployable X0TBridge contract source/deploy/test surface")
    items.append("live execute receipt and external settlement receipt gates")
    return items


def build_report(root: Path, *, node_version: Optional[str] = None) -> Dict[str, Any]:
    build_env = _build_env_report(root, node_version)
    deployment = _deployment_manifest_report(root)
    operator_configs = _operator_config_report(root)
    legacy_contracts = _legacy_contract_report(root)
    bridge_source = _bridge_source_report(root)
    missing_inputs = _missing_inputs(
        build_env,
        deployment,
        operator_configs,
        legacy_contracts,
        bridge_source,
    )
    missing_input_status_counts = _status_counts(missing_inputs)

    build_env_ready = build_env["ready"]
    deployment_config_ready = deployment["ready"] and operator_configs["ready"]
    legacy_contract_surface_ready = legacy_contracts["ready"]
    bridge_contract_source_ready = bridge_source["ready"]
    contract_readiness_clear = (
        build_env_ready
        and deployment_config_ready
        and legacy_contract_surface_ready
        and bridge_contract_source_ready
    )

    blockers: List[str] = []
    if not build_env_ready:
        blockers.append("BUILD_ENV")
    if not deployment_config_ready:
        blockers.append("DEPLOYMENT_CONFIG")
    if not legacy_contract_surface_ready:
        blockers.append("LEGACY_CONTRACT_SURFACE")
    if not bridge_contract_source_ready:
        blockers.append("BRIDGE_SOURCE_SURFACE")
    decision = "CONTRACT_READINESS_CLEAR" if contract_readiness_clear else "BLOCKED_ON_" + "_AND_".join(blockers)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only X0T contract/deployment readiness gate. It checks local package metadata, "
            "Hardhat import availability, deployment address placeholders, operator config addresses, "
            "a separate Hardhat compile/test verification artifact, and obvious legacy Solidity "
            "blockers. It does not install packages, compile contracts, call RPC, submit transactions, "
            "mutate chain/runtime state, or close /goal."
        ),
        "decision": decision,
        "contract_readiness_clear": contract_readiness_clear,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_artifacts": [
            CONTRACT_PACKAGE_JSON,
            CONTRACT_HARDHAT_CONFIG,
            CONTRACT_BUILD_VERIFICATION,
            *BRIDGE_SOURCE_ARTIFACTS,
            "scripts/ops/apply_x0t_bridge_contract_address.py",
            BASE_SEPOLIA_DEPLOYMENT,
            *OPERATOR_CONFIGS,
            *LEGACY_CONTRACTS,
        ],
        "build_env": build_env,
        "deployment_manifest": deployment,
        "operator_configs": operator_configs,
        "legacy_contracts": legacy_contracts,
        "bridge_source": bridge_source,
        "missing_inputs": missing_inputs,
        "not_verified_yet": _not_verified_yet(build_env, deployment, operator_configs, bridge_source),
        "summary": {
            "contract_readiness_clear": contract_readiness_clear,
            "build_env_ready": build_env_ready,
            "node_runtime_ready": build_env["node_runtime"]["ready"],
            "effective_node_runtime_ready": build_env["node_runtime"]["effective_ready"],
            "node_runtime_ready_source": build_env["node_runtime"]["ready_source"],
            "contract_build_verification_ready": build_env["build_verification"]["ready"],
            "contract_dependencies_ready": build_env["dependencies"]["ready"],
            "missing_contract_dependencies": build_env["dependencies"]["missing_total"],
            "invalid_contract_dependencies": build_env["dependencies"]["invalid_total"],
            "hardhat_config_imports_ready": build_env["hardhat_config_imports"]["ready"],
            "deployment_config_ready": deployment_config_ready,
            "base_sepolia_manifest_ready": deployment["ready"],
            "operator_configs_ready": operator_configs["ready"],
            "legacy_contract_surface_ready": legacy_contract_surface_ready,
            "bridge_contract_source_ready": bridge_contract_source_ready,
            "missing_inputs_total": len(missing_inputs),
            "missing_input_status_counts": missing_input_status_counts,
            "missing_inputs_operator_input_required": missing_input_status_counts.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "missing_inputs_generic_operator_required": missing_input_status_counts.get(
                "OPERATOR_REQUIRED", 0
            ),
            "safety_flags_ready": True,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# X0T Contract Readiness",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Decision: `{report.get('decision', '')}`",
        f"Contract readiness clear: `{report.get('contract_readiness_clear')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Summary",
        "",
        f"- build env ready: `{summary.get('build_env_ready')}`",
        f"- node runtime ready: `{summary.get('node_runtime_ready')}`",
        f"- effective node runtime ready: `{summary.get('effective_node_runtime_ready')}`",
        f"- node runtime ready source: `{summary.get('node_runtime_ready_source')}`",
        f"- contract build verification ready: `{summary.get('contract_build_verification_ready')}`",
        f"- contract dependencies ready: `{summary.get('contract_dependencies_ready')}`",
        f"- missing contract dependencies: `{summary.get('missing_contract_dependencies')}`",
        f"- invalid contract dependencies: `{summary.get('invalid_contract_dependencies')}`",
        f"- deployment config ready: `{summary.get('deployment_config_ready')}`",
        f"- base sepolia manifest ready: `{summary.get('base_sepolia_manifest_ready')}`",
        f"- operator configs ready: `{summary.get('operator_configs_ready')}`",
        f"- legacy contract surface ready: `{summary.get('legacy_contract_surface_ready')}`",
        f"- bridge contract source ready: `{summary.get('bridge_contract_source_ready')}`",
        "",
        "## Missing Inputs",
        "",
    ]
    missing = report.get("missing_inputs", [])
    if isinstance(missing, list) and missing:
        for item in missing:
            if isinstance(item, dict):
                lines.append(f"- `{item.get('id')}`: `{item.get('status')}` - {item.get('reason', '')}")
                for command in item.get("commands", []):
                    if isinstance(command, str):
                        lines.append(f"  - command: `{command}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "X0T Contract Readiness",
            f"decision: {report.get('decision')}",
            f"contract_readiness_clear: {report.get('contract_readiness_clear')}",
            f"build_env_ready: {summary.get('build_env_ready')}",
            f"deployment_config_ready: {summary.get('deployment_config_ready')}",
            f"legacy_contract_surface_ready: {summary.get('legacy_contract_surface_ready')}",
            f"bridge_contract_source_ready: {summary.get('bridge_contract_source_ready')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate read-only X0T contract/deployment readiness evidence")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--write-json", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
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
    if args.require_ready and not report["contract_readiness_clear"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
