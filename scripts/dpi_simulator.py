"""
DPI Simulator for x0tta6bl4
===========================

Simulates Deep Packet Inspection (DPI) behavior by matching traffic 
against common signatures of VPNs, Mesh networks, and encrypted protocols.
"""

import re
import logging
import math
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger("dpi-sim")

class DPISimulator:
    def __init__(self):
        # Common DPI signatures (simplified)
        self.signatures = {
            "OpenVPN": [re.compile(b"^\x00[\x0d-\xff]\x38")],
            "WireGuard": [re.compile(b"^\x01\x00\x00\x00"), re.compile(b"^\x02\x00\x00\x00")],
            "Shadowsocks": [re.compile(b"^\x01\x00\x00\x00")], # Often detected by entropy
            "x0tta6bl4_RAW": [re.compile(b"\"node_id\":"), re.compile(b"\"type\": \"heartbeat\"")],
            "Generic_Encrypted": [] # Detected by high entropy
        }
        
        # Protocols that should be "allowed" (mimicked)
        self.allowed_protocols = {
            "HTTP": re.compile(b"^(GET|POST|HEAD) .* HTTP/1.1"),
            "DNS": re.compile(b"^.{2}[\x01\x00].*\x05stego\x08x0tta6bl4"), # Refined DNS
            "ICMP": re.compile(b"^\x08\x00.*X0TTA6BL4_STEGO") # Adjusted ICMP signature
        }

    def estimate_entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        entropy = 0
        for x in range(256):
            p_x = float(data.count(x)) / len(data)
            if p_x > 0:
                entropy += - p_x * math.log(p_x, 2)
        return entropy

    def inspect(self, packet: bytes) -> Dict[str, Any]:
        """
        Inspects a packet and returns detection results.
        """
        results = {
            "detected": False,
            "detected_as": None,
            "mimic_valid": False,
            "mimic_protocol": None,
            "entropy": self.estimate_entropy(packet),
            "threat_level": 0 # 0 to 10
        }

        # 1. Check for mimicked protocols
        for proto, pattern in self.allowed_protocols.items():
            if pattern.search(packet):
                results["mimic_valid"] = True
                results["mimic_protocol"] = proto
                break

        # 2. Check for known forbidden signatures
        for name, patterns in self.signatures.items():
            for p in patterns:
                if p.search(packet):
                    results["detected"] = True
                    results["detected_as"] = name
                    results["threat_level"] = 10
                    return results

        # 3. Entropy-based detection (if not valid mimic)
        # Encrypted traffic often has entropy > 7.5 bits/byte
        if not results["mimic_valid"] and results["entropy"] > 7.5:
            results["detected"] = True
            results["detected_as"] = "High_Entropy_Unknown"
            results["threat_level"] = 7
        
        # 4. Heuristic: Encrypted data inside protocol
        # If it's HTTP but the "payload" part has very high entropy, some DPIs flag it
        if results["mimic_valid"] and results["entropy"] > 7.8:
            results["threat_level"] = 4 # Suspicious but likely allowed

        return results

def run_dpi_test(packet: bytes, label: str):
    sim = DPISimulator()
    res = sim.inspect(packet)
    print(f"Test: {label}")
    print(f"  Detected: {res['detected']} (As: {res['detected_as']})")
    print(f"  Mimic:    {res['mimic_valid']} (Proto: {res['mimic_protocol']})")
    print(f"  Entropy:  {res['entropy']:.4f}")
    print(f"  Threat:   {res['threat_level']}/10")
    print("-" * 30)
    return res
