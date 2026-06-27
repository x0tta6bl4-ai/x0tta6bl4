"""
Stego-mesh DPI Evasion Integration Test
========================================

Verifies that stego-encoded traffic bypasses DPI signatures 
while raw or purely encrypted traffic is detected.
"""

import hashlib

import pytest
from src.anti_censorship.stego_mesh import StegoMeshProtocol
from scripts.dpi_simulator import DPISimulator

@pytest.fixture
def stego():
    master_key = hashlib.sha256(b"test_secret_key").digest()
    return StegoMeshProtocol(master_key)

@pytest.fixture
def dpi():
    return DPISimulator()

def test_raw_traffic_detection(dpi):
    """Raw JSON heartbeats should be detected."""
    raw_packet = b'{"type": "heartbeat", "node_id": "node-123", "timestamp": "2026-02-23T12:00:00"}'
    res = dpi.inspect(raw_packet)
    assert res["detected"]
    assert res["detected_as"] == "x0tta6bl4_RAW"

def test_encrypted_traffic_detection(dpi):
    """Purely encrypted random-looking traffic should be detected by entropy."""
    # Deterministic high-entropy payload (~8 bits/byte) to avoid flaky threshold outcomes.
    encrypted_packet = bytes(range(256)) * 2
    res = dpi.inspect(encrypted_packet)
    # Most likely detected as high entropy unknown
    assert res["detected"]
    assert res["entropy"] > 7.0

def test_stego_http_evasion(stego, dpi):
    """HTTP stego-packets should NOT be detected as x0tta6bl4 or VPN."""
    raw_payload = b'{"type": "heartbeat", "node_id": "node-123"}'
    stego_packet = stego.encode_packet(raw_payload, protocol_mimic="http")
    
    res = dpi.inspect(stego_packet)
    
    assert res["mimic_valid"]
    assert res["mimic_protocol"] == "HTTP"
    assert not res["detected"]
    assert res["threat_level"] < 5
    print(f"✅ HTTP Stego Evasion: Entropy={res['entropy']:.4f}")

def test_stego_dns_evasion(stego, dpi):
    """DNS stego-packets should bypass DPI."""
    raw_payload = b'{"type": "heartbeat", "node_id": "node-123"}'
    stego_packet = stego.encode_packet(raw_payload, protocol_mimic="dns")
    
    res = dpi.inspect(stego_packet)
    
    assert res["mimic_valid"]
    assert res["mimic_protocol"] == "DNS"
    assert not res["detected"]
    print(f"✅ DNS Stego Evasion: Entropy={res['entropy']:.4f}")

def test_stego_icmp_evasion(stego, dpi):
    """ICMP stego-packets should bypass DPI."""
    raw_payload = b'{"type": "heartbeat", "node_id": "node-123"}'
    stego_packet = stego.encode_packet(raw_payload, protocol_mimic="icmp")
    
    res = dpi.inspect(stego_packet)
    
    assert res["mimic_valid"]
    assert res["mimic_protocol"] == "ICMP"
    assert not res["detected"]
    print(f"✅ ICMP Stego Evasion: Entropy={res['entropy']:.4f}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
