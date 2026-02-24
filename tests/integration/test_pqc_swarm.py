"""
Integration Test for PQC-Secure Agents and SPIFFE Bridge
========================================================

Verifies that:
1. PQCSpiffeBridge correctly generates PQC-SVIDs.
2. PQSecureAgent can sign and verify messages using PQC.
"""

import asyncio
import logging
import pytest
import unittest.mock as mock

from src.swarm.pq_agent import create_pq_agent, PQSecureAgent
from src.security.pqc_spiffe import PQCSpiffeBridge

# Mock SPIRE for testing
@pytest.fixture
def mock_spire():
    with mock.patch('src.security.pqc_spiffe.SPIREClient') as mock_client:
        client_instance = mock_client.return_value
        client_instance.fetch_x509_context.return_value = {
            "certificate": b"MOCK_CERT",
            "key": b"MOCK_KEY",
            "bundle": b"MOCK_BUNDLE"
        }
        yield client_instance

@pytest.mark.asyncio
async def test_pq_agent_signing_verification(mock_spire):
    # Create two agents
    agent_a = create_pq_agent("agent-a", "swarm-1", "monitoring")
    agent_b = create_pq_agent("agent-b", "swarm-1", "analysis")
    
    # Get Agent A's public keys
    pkeys_a = agent_a.pqc_bridge.pqc_identity.security.get_public_keys()
    sig_pub_a = pkeys_a["sig_public_key"]
    
    # Agent A executes a task (result is signed)
    task = {"task_type": "monitoring", "payload": {"node_id": "target-1"}}
    result = await agent_a.execute_task(task)
    
    assert result.success
    assert "manifest" in result.result
    assert "proof" in result.result
    assert result.result["proof"]["type"] == "ML-DSA-65"
    
    # Agent B verifies Agent A's signed result
    # We simulate receiving a message
    from src.swarm.agent import AgentMessage
    msg = AgentMessage(
        sender_id="agent-a",
        payload=result.result,
        message_type="task_result"
    )
    
    is_valid = agent_b.verify_message(msg, sig_pub_a)
    assert is_valid, "PQC Signature verification failed"
    print("✅ PQC Signature verified successfully between agents")

@pytest.mark.asyncio
async def test_pqc_spiffe_bridge(mock_spire):
    bridge = PQCSpiffeBridge("test-node")
    svid_bundle = bridge.get_pqc_svid()
    
    assert svid_bundle["spiffe_id"] == "spiffe://x0tta6bl4.mesh/node/test-node"
    assert "pqc_public_keys" in svid_bundle
    assert svid_bundle["attestation"] == "spire-zkp-verified"
    
    is_valid = bridge.verify_pqc_svid(svid_bundle)
    assert is_valid
    print("✅ PQC-SVID bridge verified")

if __name__ == "__main__":
    # Run tests manually if needed
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_pq_agent_signing_verification(None))
