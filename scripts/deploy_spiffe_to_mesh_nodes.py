#!/usr/bin/env python3
"""
Deploy SPIFFE/SPIRE to Mesh Nodes

Bootstrap script for deploying SPIFFE identity management to all mesh nodes.
Supports both Kubernetes and bare-metal mesh nodes.

Usage:
    # Deploy to all nodes
    python scripts/deploy_spiffe_to_mesh_nodes.py --nodes all

    # Deploy to specific nodes
    python scripts/deploy_spiffe_to_mesh_nodes.py --nodes node-001,node-002

    # Deploy with custom trust domain
    python scripts/deploy_spiffe_to_mesh_nodes.py --trust-domain custom.mesh
"""

import argparse
import asyncio
import json
import logging
import os
import shlex
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security.spiffe import AttestationStrategy, SPIFFEController

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MeshNodeSPIFFEDeployer:
    """
    Deploy SPIFFE/SPIRE to mesh nodes.

    Handles:
    - SPIRE Agent installation
    - Node attestation
    - Workload identity registration
    - mTLS configuration
    """

    def __init__(
        self,
        trust_domain: str = "x0tta6bl4.mesh",
        spire_server_address: str = "spire-server.spire-system.svc.cluster.local:8081",
        spire_server_bin: str = "spire-server",
        join_token_command: Optional[Sequence[str]] = None,
        join_token_file: Optional[Path] = None,
    ):
        """
        Initialize mesh node SPIFFE deployer.

        Args:
            trust_domain: SPIFFE trust domain
            spire_server_address: SPIRE Server address
        """
        self.trust_domain = trust_domain
        self.spire_server_address = spire_server_address
        self.spire_server_bin = spire_server_bin
        self.join_token_command = list(join_token_command or [])
        self.join_token_file = join_token_file
        self.deployed_nodes: List[str] = []
        self.failed_nodes: List[str] = []

    async def deploy_to_node(
        self,
        node_id: str,
        join_token: Optional[str] = None,
        attestation_strategy: str = "join_token",
    ) -> bool:
        """
        Deploy SPIFFE to a single mesh node.

        Args:
            node_id: Mesh node identifier
            join_token: Optional join token (generated if None)
            attestation_strategy: Attestation strategy (join_token, k8s_psat)

        Returns:
            True if deployment successful
        """
        logger.info(f"Deploying SPIFFE to node: {node_id}")

        try:
            # Initialize SPIFFE controller for this node
            controller = SPIFFEController(
                trust_domain=self.trust_domain, server_address=self.spire_server_address
            )

            # Determine attestation strategy
            if attestation_strategy == "join_token":
                strategy = AttestationStrategy.JOIN_TOKEN
                if not join_token:
                    join_token = await self._generate_join_token(node_id)
                attestation_data = {"token": join_token}
            elif attestation_strategy == "k8s_psat":
                strategy = AttestationStrategy.K8S_PSAT
                attestation_data = {}
            else:
                logger.error(f"Unknown attestation strategy: {attestation_strategy}")
                return False

            # Initialize SPIFFE infrastructure
            if not controller.initialize(strategy, **attestation_data):
                logger.error(f"Failed to initialize SPIFFE for node {node_id}")
                return False

            # Register mesh node identity
            node_spiffe_id = f"spiffe://{self.trust_domain}/node/{node_id}"
            if not controller.register_workload(
                spiffe_id=node_spiffe_id,
                selectors={"mesh:node_id": node_id, "mesh:type": "node"},
                ttl=86400,  # 24 hours
            ):
                logger.error(f"Failed to register workload for node {node_id}")
                return False

            # Verify identity
            identity = controller.get_identity()
            logger.info(f"Node {node_id} identity: {identity.spiffe_id}")

            # Health check
            health = controller.health_check()
            if not all(health.values()):
                logger.warning(f"Health check failed for node {node_id}: {health}")

            self.deployed_nodes.append(node_id)
            logger.info(f"Successfully deployed SPIFFE to node {node_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error deploying SPIFFE to node {node_id}: {e}", exc_info=True
            )
            self.failed_nodes.append(node_id)
            return False

    async def deploy_to_nodes(
        self,
        node_ids: List[str],
        join_token: Optional[str] = None,
        attestation_strategy: str = "join_token",
        max_concurrent: int = 5,
    ) -> Dict[str, List[str]]:
        """
        Deploy SPIFFE to multiple mesh nodes concurrently.

        Args:
            node_ids: List of node identifiers
            join_token: Optional join token (shared for all nodes)
            attestation_strategy: Attestation strategy
            max_concurrent: Maximum concurrent deployments

        Returns:
            Dict with 'deployed' and 'failed' node lists
        """
        logger.info(f"Deploying SPIFFE to {len(node_ids)} nodes")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def deploy_with_semaphore(node_id: str):
            async with semaphore:
                return await self.deploy_to_node(
                    node_id, join_token, attestation_strategy
                )

        # Deploy to all nodes
        tasks = [deploy_with_semaphore(node_id) for node_id in node_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        deployed = []
        failed = []

        for node_id, result in zip(node_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Exception deploying to {node_id}: {result}")
                failed.append(node_id)
            elif result:
                deployed.append(node_id)
            else:
                failed.append(node_id)

        return {"deployed": deployed, "failed": failed, "total": len(node_ids)}

    async def _generate_join_token(self, node_id: str) -> str:
        """
        Generate a join token from a configured local SPIRE Server source.

        Returns:
            Join token string
        """
        if self.join_token_file is not None:
            return _read_join_token_file(self.join_token_file)

        command = (
            list(self.join_token_command)
            if self.join_token_command
            else [
                self.spire_server_bin,
                "token",
                "generate",
                "-spiffeID",
                f"spiffe://{self.trust_domain}/node/{node_id}",
            ]
        )
        env = os.environ.copy()
        env.update(
            {
                "x0tta6bl4_SPIFFE_NODE_ID": node_id,
                "x0tta6bl4_SPIFFE_TRUST_DOMAIN": self.trust_domain,
                "x0tta6bl4_SPIRE_SERVER_ADDRESS": self.spire_server_address,
            }
        )

        return await asyncio.to_thread(_run_join_token_command, command, env)

    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get deployment summary statistics."""
        return {
            "deployed_nodes": len(self.deployed_nodes),
            "failed_nodes": len(self.failed_nodes),
            "deployed": self.deployed_nodes,
            "failed": self.failed_nodes,
            "success_rate": (
                len(self.deployed_nodes)
                / (len(self.deployed_nodes) + len(self.failed_nodes))
                if (self.deployed_nodes or self.failed_nodes)
                else 0.0
            ),
        }


def _parse_node_ids(raw: str) -> List[str]:
    """Parse comma/newline separated node IDs."""
    node_ids: List[str] = []
    seen = set()
    for item in raw.replace("\n", ",").split(","):
        node_id = item.strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        node_ids.append(node_id)
    return node_ids


def _node_id_from_item(item: Any) -> Optional[str]:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("id", "node_id", "name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _load_node_ids_from_json(payload: Any) -> List[str]:
    if isinstance(payload, list):
        return [
            node_id
            for node_id in (_node_id_from_item(item) for item in payload)
            if node_id is not None
        ]
    if isinstance(payload, dict):
        for key in ("node_ids", "nodes", "items"):
            if key in payload:
                return _load_node_ids_from_json(payload[key])
    return []


def load_node_ids_from_file(path: Path) -> List[str]:
    """Load node IDs from JSON, JSON object inventory, or text list."""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _parse_node_ids(raw)
    node_ids = _load_node_ids_from_json(payload)
    return _parse_node_ids("\n".join(node_ids))


def resolve_node_ids(nodes: str, nodes_file: Optional[Path] = None) -> List[str]:
    """
    Resolve CLI node selection.

    `--nodes all` is intentionally fail-closed: production deploys must use a
    real inventory source instead of a synthetic node range.
    """
    if nodes.lower() != "all":
        return _parse_node_ids(nodes)

    inventory_file = nodes_file
    env_file = os.getenv("x0tta6bl4_MESH_NODES_FILE")
    if inventory_file is None and env_file:
        inventory_file = Path(env_file)
    if inventory_file is not None:
        node_ids = load_node_ids_from_file(inventory_file)
        if node_ids:
            return node_ids

    env_node_ids = os.getenv("x0tta6bl4_MESH_NODE_IDS", "")
    node_ids = _parse_node_ids(env_node_ids)
    if node_ids:
        return node_ids

    raise ValueError(
        "--nodes all requires a real mesh inventory. Provide --nodes-file, "
        "x0tta6bl4_MESH_NODES_FILE, or x0tta6bl4_MESH_NODE_IDS."
    )


def _read_join_token_file(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"Join token file is empty: {path}")
    return token


def _extract_join_token(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        value = line.strip()
        if not value:
            continue
        if ":" in value:
            key, candidate = value.split(":", 1)
            if key.strip().lower() in {"token", "join token", "jointoken"}:
                value = candidate.strip()
        if value:
            return value
    raise RuntimeError("SPIRE join token command returned no token")


def _run_join_token_command(command: Sequence[str], env: Dict[str, str]) -> str:
    if not command:
        raise RuntimeError("Join token command is empty")
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Join token command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Join token command timed out") from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise RuntimeError(f"Join token command failed: {stderr}")
    return _extract_join_token(result.stdout)


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Deploy SPIFFE/SPIRE to mesh nodes")
    parser.add_argument(
        "--nodes",
        type=str,
        required=True,
        help="Comma-separated node IDs or 'all' for all nodes",
    )
    parser.add_argument(
        "--nodes-file",
        type=Path,
        help=(
            "Mesh node inventory for --nodes all. Supports JSON arrays, JSON objects "
            "with node_ids/nodes/items, or comma/newline text."
        ),
    )
    parser.add_argument(
        "--trust-domain", type=str, default="x0tta6bl4.mesh", help="SPIFFE trust domain"
    )
    parser.add_argument(
        "--spire-server",
        type=str,
        default="spire-server.spire-system.svc.cluster.local:8081",
        help="SPIRE Server address",
    )
    parser.add_argument(
        "--join-token", type=str, help="Join token (generated if not provided)"
    )
    parser.add_argument(
        "--join-token-file",
        type=Path,
        help="Local file containing a join token. Do not pass secrets through chat.",
    )
    parser.add_argument(
        "--join-token-command",
        type=str,
        help=(
            "Local command that prints a join token. The command receives "
            "x0tta6bl4_SPIFFE_NODE_ID and x0tta6bl4_SPIFFE_TRUST_DOMAIN."
        ),
    )
    parser.add_argument(
        "--spire-server-bin",
        type=str,
        default="spire-server",
        help="Path to spire-server CLI used to generate join tokens",
    )
    parser.add_argument(
        "--attestation-strategy",
        type=str,
        default="join_token",
        choices=["join_token", "k8s_psat"],
        help="Node attestation strategy",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=5, help="Maximum concurrent deployments"
    )

    args = parser.parse_args()

    try:
        node_ids = resolve_node_ids(args.nodes, args.nodes_file)
    except ValueError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc
    if not node_ids:
        logger.error("No mesh node IDs resolved")
        raise SystemExit(2)
    if args.nodes.lower() == "all":
        logger.info("Deploying to all nodes from inventory: %s nodes", len(node_ids))

    # Create deployer
    join_token_command = (
        shlex.split(args.join_token_command) if args.join_token_command else None
    )
    deployer = MeshNodeSPIFFEDeployer(
        trust_domain=args.trust_domain,
        spire_server_address=args.spire_server,
        spire_server_bin=args.spire_server_bin,
        join_token_command=join_token_command,
        join_token_file=args.join_token_file,
    )

    # Deploy
    result = await deployer.deploy_to_nodes(
        node_ids=node_ids,
        join_token=args.join_token,
        attestation_strategy=args.attestation_strategy,
        max_concurrent=args.max_concurrent,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("SPIFFE Deployment Summary")
    print("=" * 60)
    print(f"Total nodes: {result['total']}")
    print(f"Deployed: {len(result['deployed'])}")
    print(f"Failed: {len(result['failed'])}")
    print(
        f"Success rate: {result['total'] and len(result['deployed']) / result['total'] * 100:.1f}%"
    )
    print()

    if result["deployed"]:
        print("Successfully deployed nodes:")
        for node_id in result["deployed"]:
            print(f"  ✅ {node_id}")
        print()

    if result["failed"]:
        print("Failed nodes:")
        for node_id in result["failed"]:
            print(f"  ❌ {node_id}")
        print()

    # Exit code
    exit(0 if not result["failed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
