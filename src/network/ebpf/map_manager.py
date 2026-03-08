"""
eBPF Map Manager - Write and update eBPF maps from userspace
"""

import logging
import subprocess
import socket

logger = logging.getLogger(__name__)

class EBPFMapManager:
    """
    Manager for eBPF maps, providing write/update capabilities.
    """

    @staticmethod
    def _ip_to_hex(ip_str: str) -> str:
        """Convert IP string to hex format for bpftool."""
        try:
            # Packed binary format (network byte order)
            packed_ip = socket.inet_aton(ip_str)
            # bpftool expects hex bytes in the order they appear in memory
            return " ".join(f"0x{b:02x}" for b in packed_ip)
        except Exception as e:
            logger.error(f"Failed to convert IP {ip_str} to hex: {e}")
            return ""

    @staticmethod
    def update_attestation(ip_address: str, is_attested: bool = True) -> bool:
        """
        Update the attestation status of a node in the eBPF map.
        
        Args:
            ip_address: IPv4 address of the node
            is_attested: True to allow traffic, False to block
        """
        map_name = "attested_nodes_map"
        key_hex = EBPFMapManager._ip_to_hex(ip_address)
        value_hex = "0x01" if is_attested else "0x00"
        
        if not key_hex:
            return False

        try:
            # Use shell=True if needed for complex hex strings, but list is safer
            # We need to split the key_hex string into individual arguments for subprocess
            full_cmd = ["bpftool", "map", "update", "name", map_name, "key"] + key_hex.split() + ["value", value_hex]
            
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info(f"✅ Updated eBPF attestation for {ip_address}: {is_attested}")
                return True
            else:
                # If map doesn't exist yet (eBPF not loaded), just log warning
                if "not found" in result.stderr.lower():
                    logger.warning(f"⚠️ eBPF map '{map_name}' not found. Is the XDP program loaded?")
                else:
                    logger.error(f"❌ Failed to update eBPF map: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error updating eBPF map: {e}")
            return False

    @staticmethod
    def remove_node(ip_address: str) -> bool:
        """Remove a node from the eBPF map (defaults to blocking)."""
        map_name = "attested_nodes_map"
        key_hex = EBPFMapManager._ip_to_hex(ip_address)
        
        if not key_hex:
            return False

        try:
            full_cmd = ["bpftool", "map", "delete", "name", map_name, "key"] + key_hex.split()
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
