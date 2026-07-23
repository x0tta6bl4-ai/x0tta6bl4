import pytest
import hashlib
from src.security.peaq_identity import PeaqIdentityAdapter, PeaqIdentityError, get_node_peaq_identity

def test_peaq_identity_deterministic():
    node_id = "node-test-peaq-1"
    adapter1 = PeaqIdentityAdapter(node_id)
    adapter2 = PeaqIdentityAdapter(node_id)
    
    assert adapter1.get_peaq_did() == adapter2.get_peaq_did()
    assert adapter1.get_account_address() == adapter2.get_account_address()
    assert adapter1.get_peaq_did().startswith("did:peaq:0x")
    assert len(adapter1.get_account_address()) == 42

def test_peaq_identity_factory():
    node_id = "node-test-peaq-2"
    adapter = get_node_peaq_identity(node_id)
    assert adapter.node_id == node_id
    assert adapter.get_peaq_did().startswith("did:peaq:0x")

@pytest.mark.asyncio
async def test_register_machine_simulated():
    node_id = "node-test-peaq-3"
    adapter = PeaqIdentityAdapter(node_id)
    
    # When peaq-sdk is missing, it returns a simulated result
    res = await adapter.register_machine("http://localhost:8545", "0x" + "a" * 64)
    assert res["status"] == "SIMULATED"
    assert res["did"] == adapter.get_peaq_did()
    assert res["node_id"] == node_id
    assert "tx_hash" in res
    assert "note" in res

def test_sign_telemetry():
    node_id = "node-test-peaq-4"
    adapter = PeaqIdentityAdapter(node_id)
    payload = b"sensor-data-123"
    
    res = adapter.sign_telemetry(payload)
    assert res["did"] == adapter.get_peaq_did()
    assert "signature" in res
    assert "message_hash" in res
    assert "v" in res
    assert "r" in res
    assert "s" in res
