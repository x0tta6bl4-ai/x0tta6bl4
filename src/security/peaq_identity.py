"""
Peaq Machine Identity Integration for x0tta6bl4.
Maps mesh nodes to peaq Network Machine DIDs.

Milestone 1 of peaq Grant Implementation.
"""

import asyncio
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

try:
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False

try:
    from peaq_sdk import Sdk
    from peaq_sdk.types import ChainType
    PEAQ_SDK_AVAILABLE = True
except ImportError:
    PEAQ_SDK_AVAILABLE = False

from src.security.decentralized_identity import DIDManager, DIDGenerator

logger = logging.getLogger(__name__)

class PeaqIdentityError(Exception):
    """Base error for peaq identity operations."""
    pass

class PeaqIdentityAdapter:
    """
    Adapts x0tta6bl4 mesh identity to peaq Machine DID.
    
    This adapter handles:
    1. Deriving/managing an EVM-compatible machine account.
    2. Registering the machine as a DID on the peaq network.
    3. Mapping SPIFFE/Mesh identities to peaq Machine DIDs.
    """

    def __init__(self, node_id: str, seed: Optional[bytes] = None):
        self.node_id = node_id
        if not ETH_ACCOUNT_AVAILABLE:
            raise PeaqIdentityError("eth-account library is required but not available.")
        
        # In production, the seed should be derived from the node's TPM or Hardware Enclave.
        # Here we use the node_id to derive a deterministic identity for this node if no seed is provided.
        if seed:
            self.account: LocalAccount = Account.from_key(seed)
        else:
            # Deterministic derivation for the purpose of the demo/pilot
            # WARNING: Use a real hardware-backed seed in production.
            derived_seed = hashlib.sha256(f"peaq-machine-identity-{node_id}".encode()).digest()
            self.account = Account.from_key(derived_seed)
        
        self.did = f"did:peaq:{self.account.address}"
        logger.info(f"Initialized peaq Identity for node {node_id}: {self.did}")

    def get_peaq_did(self) -> str:
        """Return the peaq DID string."""
        return self.did

    def get_account_address(self) -> str:
        """Return the machine's EVM address."""
        return self.account.address

    async def register_machine(self, rpc_url: str, admin_private_key: str) -> Dict[str, Any]:
        """
        Registers the machine on the peaq network.
        
        Status: SIMULATED (if peaq-sdk missing) / REAL (if peaq-sdk present)
        """
        if not PEAQ_SDK_AVAILABLE:
            logger.warning("peaq-sdk not found. Returning SIMULATED registration evidence.")
            return {
                "status": "SIMULATED",
                "did": self.did,
                "node_id": self.node_id,
                "tx_hash": hashlib.sha256(f"sim-tx-{self.did}".encode()).hexdigest(),
                "note": "peaq-sdk missing from environment. Install with 'pip install peaq-sdk'."
            }

        try:
            admin_account = Account.from_key(admin_private_key)
            sdk = await Sdk.create_instance({
                'base_url': rpc_url,
                'chain_type': 1, # EVM
                'auth': admin_account
            })
            
            did_name = f"x0t_{self.node_id[:8]}"
            
            result = await sdk.did.create({
                "name": did_name,
                "address": self.account.address,
                "customDocumentFields": {
                    "mesh_node_id": self.node_id,
                    "transport": "x0tta6bl4-pqc-mesh"
                }
            })
            
            return {
                "status": "VERIFIED_ON_CHAIN",
                "did": self.did,
                "tx_hash": result.tx_hash,
                "node_id": self.node_id
            }
        except Exception as e:
            logger.error(f"Failed to register machine on peaq: {e}")
            raise PeaqIdentityError(f"On-chain registration failed: {e}")

    def sign_telemetry(self, data: bytes) -> Dict[str, Any]:
        """
        Signs telemetry data using the machine's peaq identity.
        Used for Verifiable Machine Data (VMD).
        """
        from eth_account.messages import encode_defunct
        message = encode_defunct(primitive=data)
        signature = self.account.sign_message(message)
        return {
            "did": self.did,
            "signature": signature.signature.hex(),
            "message_hash": signature.message_hash.hex(),
            "v": signature.v,
            "r": hex(signature.r),
            "s": hex(signature.s)
        }

def get_node_peaq_identity(node_id: str) -> PeaqIdentityAdapter:
    """Factory function for node peaq identity."""
    return PeaqIdentityAdapter(node_id)
