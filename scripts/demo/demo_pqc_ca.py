"""
Demo: Post-Quantum Certificate Authority (PQC-CA)
================================================

This script demonstrates how x0tta6bl4 issues and rotates 
quantum-resistant identities (ML-DSA-65) for mesh nodes.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.security.pqc_ca import PQCCertificateAuthority, PQCIdentityManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PQC-CA-Demo")

async def run_demo():
    logger.info("🚀 Starting PQC Certificate Authority Demo")
    
    # 1. Setup CA (MaaS Root)
    ca = PQCCertificateAuthority(ca_node_id="maas-root-ca")
    logger.info(f"🏛️ CA Root DID: {ca.identity.did}")
    
    # 2. Setup Node Identity Manager
    node_id = "agent-berlin-01"
    manager = PQCIdentityManager(node_id)
    logger.info(f"🆔 Node Initial DID: {manager.identity.did}")
    
    # 3. Issue Initial PQC-SVID
    logger.info("📜 Step 1: Issuing initial PQC-SVID...")
    svid = manager.rotate_identity(ca)
    
    logger.info(f"✅ SVID Issued: sub={svid.spiffe_id}")
    logger.info(f"🔑 Node PubKey: {svid.public_key_hex[:32]}...")
    logger.info(f"✍️ CA Signature: {svid.signature[:32]}...")
    
    # 4. Verify SVID
    logger.info("🔍 Step 2: Verifying SVID signature...")
    ca_pubkey = ca.identity.security.get_public_keys()["sig_public_key"]
    is_valid = ca.verify_pqc_svid(svid, ca_pubkey)
    
    if is_valid:
        logger.info("✨ SVID VERIFIED: Signature is valid and bound to the node's public key!")
    else:
        logger.error("❌ SVID VERIFICATION FAILED!")
        
    # 5. Rotate Identity
    logger.info("🔄 Step 3: Simulating key rotation (MAPE-K triggered)...")
    new_svid = manager.rotate_identity(ca)
    
    logger.info("✅ New SVID Issued with NEW keys and signature.")
    assert new_svid.signature != svid.signature
    assert new_svid.public_key_hex != svid.public_key_hex
    
    logger.info("✅ PQC-CA Demo Complete. Identity is now quantum-resistant and rotatable.")

if __name__ == "__main__":
    asyncio.run(run_demo())
