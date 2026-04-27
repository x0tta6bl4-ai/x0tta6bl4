#!/usr/bin/env python3
"""
Utrecht 6G-demo deployment helper.

Provides a reproducible CLI entrypoint for provisioning the pilot mesh and
supports dry-run mode for safe preflight checks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml

# Add project root to path (/repo/scripts/ops/file.py -> /repo)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

LOGGER = logging.getLogger("utrecht_6g_deploy")
DEFAULT_DASHBOARD_BASE_URL = "http://maas.x0tta6bl4.io/dashboard"


@dataclass(frozen=True)
class DeploymentConfig:
    owner_id: str = "utrecht_enterprise_001"
    name: str = "Utrecht-6G-Cluster"
    nodes: int = 50
    billing_plan: str = "enterprise"
    pqc_profile: str = "robot"
    pqc_enabled: bool = True
    obfuscation: str = "vless-reality"
    region: str = "eu-west-utrecht"
    dry_run: bool = False
    dashboard_base_url: str = DEFAULT_DASHBOARD_BASE_URL
    output: str = "text"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Utrecht 6G mesh pilot")
    parser.add_argument("--owner-id", default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--nodes", type=int, default=None)
    parser.add_argument("--billing-plan", default=None)
    parser.add_argument("--pqc-profile", default=None)
    parser.add_argument("--obfuscation", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--dashboard-base-url", default=None)
    parser.add_argument(
        "--values-file",
        default=None,
        help="Optional YAML values file (e.g. values-utrecht.yaml)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show request without provisioning")
    parser.add_argument("--disable-pqc", action="store_true", help="Disable PQC for diagnostics")
    parser.add_argument(
        "--output", choices=("text", "json"), default="text", help="Output format"
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser.parse_args(argv)


def load_values_overrides(values_file: Path) -> Dict[str, Any]:
    if not values_file.exists():
        raise FileNotFoundError(f"values file not found: {values_file}")

    loaded = yaml.safe_load(values_file.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("values file must contain a YAML object")

    overrides: Dict[str, Any] = {}
    replicas = loaded.get("replicas")
    if replicas is not None:
        overrides["nodes"] = int(replicas)

    billing = loaded.get("billing", {})
    if isinstance(billing, dict):
        if isinstance(billing.get("plan"), str) and billing["plan"].strip():
            overrides["billing_plan"] = billing["plan"].strip()
        if isinstance(billing.get("region"), str) and billing["region"].strip():
            overrides["region"] = billing["region"].strip()

    pqc = loaded.get("pqc", {})
    if isinstance(pqc, dict) and isinstance(pqc.get("enabled"), bool):
        overrides["pqc_enabled"] = pqc["enabled"]

    network = loaded.get("network", {})
    if isinstance(network, dict) and isinstance(network.get("obfuscation"), str):
        value = network["obfuscation"].strip()
        if value:
            overrides["obfuscation"] = value

    return overrides


def build_config(args: argparse.Namespace) -> DeploymentConfig:
    merged: Dict[str, Any] = {
        "owner_id": DeploymentConfig.owner_id,
        "name": DeploymentConfig.name,
        "nodes": DeploymentConfig.nodes,
        "billing_plan": DeploymentConfig.billing_plan,
        "pqc_profile": DeploymentConfig.pqc_profile,
        "pqc_enabled": DeploymentConfig.pqc_enabled,
        "obfuscation": DeploymentConfig.obfuscation,
        "region": DeploymentConfig.region,
        "dry_run": bool(args.dry_run),
        "dashboard_base_url": DeploymentConfig.dashboard_base_url,
        "output": args.output,
    }

    if args.values_file:
        merged.update(load_values_overrides(Path(args.values_file)))

    direct_overrides = {
        "owner_id": args.owner_id,
        "name": args.name,
        "nodes": args.nodes,
        "billing_plan": args.billing_plan,
        "pqc_profile": args.pqc_profile,
        "obfuscation": args.obfuscation,
        "region": args.region,
    }
    for key, value in direct_overrides.items():
        if value is not None:
            merged[key] = value

    if args.dashboard_base_url is not None:
        merged["dashboard_base_url"] = args.dashboard_base_url
    if args.disable_pqc:
        merged["pqc_enabled"] = False

    merged["dashboard_base_url"] = str(merged["dashboard_base_url"]).rstrip("/")
    merged["nodes"] = int(merged["nodes"])
    if merged["nodes"] <= 0:
        raise ValueError("--nodes must be greater than 0")

    return DeploymentConfig(**merged)


def build_provision_request(config: DeploymentConfig) -> Dict[str, Any]:
    return {
        "owner_id": config.owner_id,
        "name": config.name,
        "nodes": config.nodes,
        "billing_plan": config.billing_plan,
        "pqc_profile": config.pqc_profile,
        "pqc_enabled": config.pqc_enabled,
        "obfuscation": config.obfuscation,
        "region": config.region,
    }


def _coerce_mesh_payload(mesh: Any, dashboard_base_url: str) -> Dict[str, Any]:
    mesh_id = getattr(mesh, "mesh_id", "unknown")
    join_token = getattr(mesh, "join_token", "")
    return {
        "mesh_id": mesh_id,
        "join_token": join_token,
        "dashboard_url": f"{dashboard_base_url}/{mesh_id}",
    }


async def deploy_utrecht_demo(
    config: Optional[DeploymentConfig] = None, provisioner: Optional[Any] = None
) -> Dict[str, Any]:
    cfg = config or DeploymentConfig()
    request_payload = build_provision_request(cfg)

    LOGGER.info("Starting Utrecht 6G-demo deployment")

    if cfg.dry_run:
        return {
            "status": "dry-run",
            "summary": {
                "nodes": cfg.nodes,
                "pqc_enabled": cfg.pqc_enabled,
                "obfuscation": cfg.obfuscation,
            },
        }

    if provisioner is None:
        from src.api.maas.services import MeshProvisioner

        provisioner = MeshProvisioner()

    mesh = await provisioner.provision_mesh(**request_payload)
    mesh_payload = _coerce_mesh_payload(mesh, cfg.dashboard_base_url)

    LOGGER.info("Mesh provisioned successfully: %s", mesh_payload["mesh_id"])
    LOGGER.info("Monitoring dashboard: %s", mesh_payload["dashboard_url"])

    return {"status": "ok", "mesh": mesh_payload}


def format_result(result: Dict[str, Any], output: str) -> str:
    if output == "json":
        return json.dumps(result, ensure_ascii=True, sort_keys=True)

    if result.get("status") == "error":
        return f"ERROR\nmessage={result.get('message', 'unknown')}"

    if result.get("status") == "dry-run":
        summary = result["summary"]
        return (
            "DRY RUN\n"
            f"nodes={summary['nodes']} "
            f"pqc_enabled={summary['pqc_enabled']} "
            f"obfuscation={summary['obfuscation']}"
        )

    mesh = result.get("mesh", {})
    return (
        "DEPLOYED\n"
        f"mesh_id={mesh.get('mesh_id', 'unknown')} "
        f"dashboard={mesh.get('dashboard_url', '')}"
    )


def _build_error_result(message: str) -> Dict[str, Any]:
    return {"status": "error", "message": message}


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="[UTRECHT-6G] %(message)s")

    try:
        config = build_config(args)
        result = asyncio.run(deploy_utrecht_demo(config=config))
    except Exception:  # pragma: no cover - defensive path
        LOGGER.exception("Utrecht 6G deployment helper failed")
        error_result = _build_error_result("internal_deployment_error")
        print(format_result(error_result, output=args.output if hasattr(args, "output") else "text"))
        return 1

    print(format_result(result, output=config.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
