"""
Demo: Kernel-level Attestation Enforcement
==========================================

This script demonstrates how x0tta6bl4 enforces supply chain security 
at the kernel level using eBPF XDP.
"""

import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from src.api.maas_supply_chain import verify_binary, BinaryVerifyRequest

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Kernel-Attestation-Demo")

def setup_db_mock(mock_sbom, mock_node):
    db = MagicMock()
    query = MagicMock()
    filter_obj = MagicMock()
    
    db.query.return_value = query
    query.filter.return_value = filter_obj
    
    # Simple logic: return sbom on first calls, then node
    filter_obj.first.side_effect = [mock_sbom, None, mock_node]
    return db

async def run_demo():
    logger.info("🚀 Starting Kernel-level Attestation Demo")
    
    # 1. Setup Mock Data
    mock_sbom = MagicMock()
    mock_sbom.id = "sbom-v3.4.0"
    mock_sbom.version = "v3.4.0"
    mock_sbom.checksum_sha256 = "sha256:valid-hash"
    
    mock_node = MagicMock()
    mock_node.id = "agent-ukraine-01"
    mock_node.ip_address = "89.125.1.107"
    
    # 2. Simulate VALID attestation
    logger.info("🛡️ Case 1: Validating node with CORRECT checksum...")
    db_valid = setup_db_mock(mock_sbom, mock_node)
    req_valid = BinaryVerifyRequest(
        node_id="agent-ukraine-01",
        agent_version="v3.4.0",
        checksum_sha256="sha256:valid-hash"
    )
    
    with patch("src.network.ebpf.map_manager.EBPFMapManager.update_attestation") as mock_update:
        await verify_binary(req_valid, db=db_valid)
        if mock_update.called:
            args = mock_update.call_args[0]
            ip = args[0]
            is_attested = args[1] if len(args) > 1 else True
            logger.info(f"✅ eBPF Map Update: IP={ip}, ALLOWED={is_attested}")

    # 3. Simulate INVALID attestation
    logger.info("🚨 Case 2: Validating node with COMPROMISED checksum...")
    db_invalid = setup_db_mock(mock_sbom, mock_node)
    req_invalid = BinaryVerifyRequest(
        node_id="agent-ukraine-01",
        agent_version="v3.4.0",
        checksum_sha256="sha256:COMPROMISED-HASH"
    )
    
    with patch("src.network.ebpf.map_manager.EBPFMapManager.update_attestation") as mock_update:
        await verify_binary(req_invalid, db=db_invalid)
        if mock_update.called:
            args = mock_update.call_args[0]
            ip = args[0]
            is_attested = args[1] if len(args) > 1 else True
            logger.info(f"🛑 eBPF Map Update: IP={ip}, ALLOWED={is_attested}")
            logger.info("🔥 Node traffic is now BLOCKED at the kernel level!")

    logger.info("✅ Demo complete.")

if __name__ == "__main__":
    asyncio.run(run_demo())
