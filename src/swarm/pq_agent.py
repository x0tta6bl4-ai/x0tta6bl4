"""
Quantum-Safe (PQC) Swarm Agent
==============================

An agent that implements NIST FIPS 203/204 Post-Quantum Cryptography
(ML-KEM/Kyber and ML-DSA/Dilithium) for all communications.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.swarm.agent import AgentMessage, TaskResult, SpecializedAgent
from src.security.pqc_spiffe import PQCSpiffeBridge

logger = logging.getLogger(__name__)

class PQSecureAgent(SpecializedAgent):
    """
    An agent that signs all its task results and messages using PQC (Dilithium).
    It also integrates with SPIRE to provide PQC-SVIDs.
    """
    
    def __init__(
        self, 
        agent_id: str, 
        swarm_id: str, 
        specialization: str,
        trust_domain: str = "x0tta6bl4.mesh",
        **kwargs
    ):
        super().__init__(agent_id, swarm_id, specialization, **kwargs)
        self.pqc_bridge = PQCSpiffeBridge(agent_id, trust_domain=trust_domain)
        self.pq_thinking_coach = AgentThinkingCoach(
            agent_id=agent_id,
            role="security",
            capabilities=("zero-trust", "pqc", specialization),
        )
        self.last_pq_thinking_context: Dict[str, Any] = {}
        logger.info(f"PQSecureAgent {agent_id} initialized with PQC identity {self.pqc_bridge.pqc_identity.did}")

    def get_pqc_identity(self) -> str:
        """Returns the PQC-DID of the agent."""
        return self.pqc_bridge.pqc_identity.did

    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """
        Executes a task and signs the result with PQC.
        """
        self.last_pq_thinking_context = self.pq_thinking_coach.prepare_task(
            {
                "type": "pqc_signed_task_execution",
                "goal": "execute the task and sign the result with PQC identity",
                "constraints": {
                    "task_type": str((task or {}).get("task_type", "")),
                    "task_id_present": bool((task or {}).get("task_id")),
                    "specialization": self.specialization,
                },
                "safety_boundary": "Do not expose private keys or raw secret material.",
            }
        )
        # Execute the base task logic
        result = await super().execute_task(task)
        
        # If the task was successful, sign the result manifest
        if result.success:
            manifest = {
                "agent_id": self.agent_id,
                "task_id": result.task_id,
                "result_data": result.result,
                "timestamp": time.time()
            }
            # Wrap the result in a PQC signature
            signed_manifest = self.pqc_bridge.create_secure_payload(manifest)
            
            # Attach the PQC signature and public key to the result
            result.result = signed_manifest
            result.thinking_context = {
                **(result.thinking_context or {}),
                "pqc": self.last_pq_thinking_context,
            }
            logger.debug(f"PQC Signed task result for {result.task_id}")
            
        return result

    async def send_pqc_message(self, recipient_id: str, message_type: str, payload: Dict[str, Any]):
        """
        Sends a PQC-signed and ZKP-attested message to another agent.
        """
        self.last_pq_thinking_context = self.pq_thinking_coach.prepare_task(
            {
                "type": "pqc_signed_message",
                "goal": "send a PQC-signed and ZKP-attested agent message",
                "constraints": {
                    "recipient_present": bool(recipient_id),
                    "message_type": message_type,
                    "payload_keys": sorted((payload or {}).keys()),
                },
                "safety_boundary": "Do not expose private keys or raw secret material.",
            }
        )
        # Generate NIZKP for this specific message
        zkp_proof = self.pqc_bridge.zkp_attestor.generate_identity_proof(message=message_type)
        
        manifest = {
            "sender_id": self.agent_id,
            "recipient_id": recipient_id,
            "message_type": message_type,
            "payload": payload,
            "zkp_attestation": zkp_proof,
            "timestamp": time.time()
        }
        
        # Sign the message payload
        signed_payload = self.pqc_bridge.create_secure_payload(manifest)
        
        # Create the standard message with the signed payload
        msg = AgentMessage(
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=signed_payload
        )
        
        await self.send_message(msg)
        logger.debug(f"PQC+ZKP Signed message sent: {message_type}")

    def verify_message(self, message: AgentMessage, remote_pubkey_hex: str) -> bool:
        """
        Verifies PQC signature AND ZKP attestation.
        """
        self.last_pq_thinking_context = self.pq_thinking_coach.prepare_task(
            {
                "type": "pqc_message_verification",
                "goal": "verify PQC signature and optional ZKP attestation",
                "constraints": {
                    "message_type": message.message_type,
                    "remote_pubkey_present": bool(remote_pubkey_hex),
                    "payload_keys": sorted((message.payload or {}).keys()),
                },
                "safety_boundary": "Do not expose private keys or raw secret material.",
            }
        )
        if "manifest" not in message.payload or "proof" not in message.payload:
            return False
            
        # 1. Verify PQC Signature
        pqc_valid = self.pqc_bridge.pqc_identity.verify_remote_node(message.payload, remote_pubkey_hex)
        if not pqc_valid:
            return False
            
        # 2. Verify ZKP Attestation
        manifest = message.payload["manifest"]
        if "zkp_attestation" in manifest:
            from src.security.zkp_attestor import NIZKPAttestor
            return NIZKPAttestor.verify_identity_proof(
                manifest["zkp_attestation"], 
                message=manifest["message_type"]
            )
        
        return True

    def get_status(self) -> Dict[str, Any]:
        """Return status with PQC-specific thinking profile."""
        status = super().get_status()
        status["pqc_thinking"] = self.pq_thinking_coach.status()
        status["last_pq_thinking_context"] = self.last_pq_thinking_context
        return status

# Factory function for PQSecureAgent
def create_pq_agent(
    agent_id: str, 
    swarm_id: str, 
    specialization: Optional[str] = None, 
    **kwargs
) -> PQSecureAgent:
    """Create a PQ-Secure agent with specialization."""
    if not specialization:
        specialization = "monitoring" # Default specialization
    return PQSecureAgent(agent_id, swarm_id, specialization, **kwargs)

