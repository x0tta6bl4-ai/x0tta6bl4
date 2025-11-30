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
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security.spiffe import SPIFFEController, AttestationStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        spire_server_address: str = "spire-server.spire-system.svc.cluster.local:8081"
    ):
        """
        Initialize mesh node SPIFFE deployer.
        
        Args:
            trust_domain: SPIFFE trust domain
            spire_server_address: SPIRE Server address
        """
        self.trust_domain = trust_domain
        self.spire_server_address = spire_server_address
        self.deployed_nodes: List[str] = []
        self.failed_nodes: List[str] = []
    
    async def deploy_to_node(
        self,
        node_id: str,
        join_token: Optional[str] = None,
        attestation_strategy: str = "join_token"
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
                trust_domain=self.trust_domain,
                server_address=self.spire_server_address
            )
            
            # Determine attestation strategy
            if attestation_strategy == "join_token":
                strategy = AttestationStrategy.JOIN_TOKEN
                if not join_token:
                    # Generate join token (would call SPIRE Server API)
                    join_token = await self._generate_join_token()
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
                selectors={
                    "mesh:node_id": node_id,
                    "mesh:type": "node"
                },
                ttl=86400  # 24 hours
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
            logger.error(f"Error deploying SPIFFE to node {node_id}: {e}", exc_info=True)
            self.failed_nodes.append(node_id)
            return False
    
    async def deploy_to_nodes(
        self,
        node_ids: List[str],
        join_token: Optional[str] = None,
        attestation_strategy: str = "join_token",
        max_concurrent: int = 5
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
                return await self.deploy_to_node(node_id, join_token, attestation_strategy)
        
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
        
        return {
            "deployed": deployed,
            "failed": failed,
            "total": len(node_ids)
        }
    
    async def _generate_join_token(self) -> str:
        """
        Generate join token from SPIRE Server.
        
        In production, this would call SPIRE Server API.
        For now, returns a placeholder.
        
        Returns:
            Join token string
        """
        # TODO: Implement actual SPIRE Server API call
        # For now, return placeholder
        import secrets
        return secrets.token_urlsafe(32)
    
    def get_deployment_summary(self) -> Dict[str, any]:
        """Get deployment summary statistics."""
        return {
            "deployed_nodes": len(self.deployed_nodes),
            "failed_nodes": len(self.failed_nodes),
            "deployed": self.deployed_nodes,
            "failed": self.failed_nodes,
            "success_rate": len(self.deployed_nodes) / (len(self.deployed_nodes) + len(self.failed_nodes)) if (self.deployed_nodes or self.failed_nodes) else 0.0
        }


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Deploy SPIFFE/SPIRE to mesh nodes")
    parser.add_argument(
        "--nodes",
        type=str,
        required=True,
        help="Comma-separated node IDs or 'all' for all nodes"
    )
    parser.add_argument(
        "--trust-domain",
        type=str,
        default="x0tta6bl4.mesh",
        help="SPIFFE trust domain"
    )
    parser.add_argument(
        "--spire-server",
        type=str,
        default="spire-server.spire-system.svc.cluster.local:8081",
        help="SPIRE Server address"
    )
    parser.add_argument(
        "--join-token",
        type=str,
        help="Join token (generated if not provided)"
    )
    parser.add_argument(
        "--attestation-strategy",
        type=str,
        default="join_token",
        choices=["join_token", "k8s_psat"],
        help="Node attestation strategy"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent deployments"
    )
    
    args = parser.parse_args()
    
    # Parse node list
    if args.nodes.lower() == "all":
        # TODO: Get actual node list from mesh topology
        node_ids = [f"node-{i:03d}" for i in range(1, 51)]  # Placeholder
        logger.info(f"Deploying to all nodes (placeholder: {len(node_ids)} nodes)")
    else:
        node_ids = [node_id.strip() for node_id in args.nodes.split(",")]
    
    # Create deployer
    deployer = MeshNodeSPIFFEDeployer(
        trust_domain=args.trust_domain,
        spire_server_address=args.spire_server
    )
    
    # Deploy
    result = await deployer.deploy_to_nodes(
        node_ids=node_ids,
        join_token=args.join_token,
        attestation_strategy=args.attestation_strategy,
        max_concurrent=args.max_concurrent
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("SPIFFE Deployment Summary")
    print("=" * 60)
    print(f"Total nodes: {result['total']}")
    print(f"Deployed: {len(result['deployed'])}")
    print(f"Failed: {len(result['failed'])}")
    print(f"Success rate: {result['total'] and len(result['deployed']) / result['total'] * 100:.1f}%")
    print()
    
    if result['deployed']:
        print("Successfully deployed nodes:")
        for node_id in result['deployed']:
            print(f"  ✅ {node_id}")
        print()
    
    if result['failed']:
        print("Failed nodes:")
        for node_id in result['failed']:
            print(f"  ❌ {node_id}")
        print()
    
    # Exit code
    exit(0 if not result['failed'] else 1)


if __name__ == "__main__":
    asyncio.run(main())

